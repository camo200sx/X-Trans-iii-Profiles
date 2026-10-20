#!/usr/bin/env python3
"""
fx-templater.py - Fujifilm X Raw Studio Master Profile Converter & Stamper

Converts generic Fujifilm X-Trans III film simulation recipe templates (.FP1)
into camera-ready profiles by stamping them with your camera model, serial number,
and firmware metadata.

Compatible with all Fujifilm X-Trans III cameras:
  - Fujifilm X-E3
  - Fujifilm X-T2
  - Fujifilm X-T20
  - Fujifilm X-Pro2
  - Fujifilm X100F
  - Fujifilm X-H1

Usage:
    # 1. Basic conversion (outputs to ./converted/):
    python fx-templater.py "path/to/your/master_profile.FP1"

    # 2. Convert and directly install into Fujifilm X Raw Studio:
    python fx-templater.py "path/to/your/master_profile.FP1" --install

    # 3. Auto-detect an existing camera profile from X Raw Studio:
    python fx-templater.py --auto --install
"""

import os
import sys
import glob
import shutil
import argparse
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional

# Supported X-Trans III camera models
X_TRANS_III_MODELS = {"X-E3", "X-T2", "X-T20", "X-Pro2", "X100F", "X-H1"}

TAGS_TO_COPY_FROM_MASTER = [
    "SerialNumber",
    "TetherRAWConditonCode",
    "Editable",
    "SourceFileName",
    "Fileerror",
    "RotationAngle",
    "StructVer",
    "IOPCode",
    "ShootingCondition",
    "FileType",
    "ImageSize",
    "ImageQuality",
    "LensModulationOpt",
    "ColorSpace"
]

SELF_CLOSING_EMPTY_TAGS = {
    "SourceFileName",
    "ColorChromeBlue",
    "SmoothSkinEffect",
    "HDR",
    "DigitalTeleConv",
    "PortraitEnhancer"
}

def get_xraw_studio_base_dir() -> Optional[str]:
    """Returns the default X Raw Studio profile directory on Windows or macOS."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return os.path.join(local_app_data, "com.fujifilm.denji", "X_RAW_STUDIO")
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        return os.path.join(home, "Library", "Application Support", "com.fujifilm.denji", "X_RAW_STUDIO")
    return None

def find_installed_profiles() -> List[str]:
    """Finds all existing .FP1 profiles in the local X Raw Studio directory."""
    base_dir = get_xraw_studio_base_dir()
    if not base_dir or not os.path.isdir(base_dir):
        return []
    pattern = os.path.join(base_dir, "**", "*.FP1")
    return glob.glob(pattern, recursive=True)

def find_template_dir(candidate_dirs: List[Optional[str]]) -> Optional[str]:
    """Finds the directory containing .FP1 template files."""
    for c in candidate_dirs:
        if c and os.path.isdir(c):
            fp1_files = [f for f in os.listdir(c) if f.endswith(".FP1") and os.path.isfile(os.path.join(c, f))]
            if fp1_files:
                return os.path.abspath(c)
    return None

def extract_comments_and_root(file_path: str) -> Tuple[List[str], ET.Element]:
    """Reads an .FP1 file, extracting header XML comments and parsing ElementTree."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    comments = []
    for line in content.splitlines()[:5]:
        stripped = line.strip()
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            comments.append(stripped)

    root = ET.fromstring(content)
    return comments, root

def stamp_profile(template_path: str, master_root: ET.Element, zero_exposure_bias: bool = False) -> str:
    """Stamps a single template with master metadata and returns formatted XML string."""
    comments, template_root = extract_comments_and_root(template_path)

    app = master_root.get("application", "XRFC")
    ver = master_root.get("version", "1.12.0.0")
    master_prop = master_root.find("./PropertyGroup")
    device = master_prop.get("device", "X-E3") if master_prop is not None else "X-E3"
    cam_ver = master_prop.get("version", "X-E3_0100") if master_prop is not None else "X-E3_0100"

    template_prop = template_root.find("./PropertyGroup")
    label = template_prop.get("label", "") if template_prop is not None else os.path.splitext(os.path.basename(template_path))[0]

    master_values = {}
    if master_prop is not None:
        for child in master_prop:
            master_values[child.tag] = child.text or ""

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>'
    ]
    for c in comments:
        lines.append(c)

    lines.append(f'<ConversionProfile application="{app}" version="{ver}">')
    lines.append(f'    <PropertyGroup device="{device}" version="{cam_ver}" label="{label}">')

    if template_prop is not None:
        for child in template_prop:
            tag = child.tag
            if tag in TAGS_TO_COPY_FROM_MASTER:
                val = master_values.get(tag, child.text or "")
            else:
                val = child.text or ""

            if tag == "ExposureBias" and zero_exposure_bias:
                val = "0"

            if tag in SELF_CLOSING_EMPTY_TAGS and not val:
                lines.append(f'        <{tag}/>')
            else:
                lines.append(f'        <{tag}>{val}</{tag}>')

    lines.append('    </PropertyGroup>')
    lines.append('</ConversionProfile>')
    lines.append('')
    return "\n".join(lines)

def convert_templates(
    master_path: str,
    input_dir: str,
    output_dir: str,
    install_to_xraw: bool = False,
    zero_exposure_bias: bool = False
) -> int:
    if not os.path.isfile(master_path):
        print(f"Error: Master profile not found at: {master_path}", file=sys.stderr)
        return 0

    print(f"Reading master profile: {master_path}")
    try:
        _, master_root = extract_comments_and_root(master_path)
    except Exception as e:
        print(f"Error parsing master profile: {e}", file=sys.stderr)
        return 0

    master_prop = master_root.find("./PropertyGroup")
    if master_prop is None:
        print("Error: Master profile missing <PropertyGroup>", file=sys.stderr)
        return 0

    device = master_prop.get("device", "Unknown")
    version = master_prop.get("version", "Unknown")
    sn = master_root.findtext("./PropertyGroup/SerialNumber") or "Unknown"

    print(f"  Camera Model : {device}")
    print(f"  Condition Code: {version}")
    print(f"  Serial Number : {sn}")

    if device not in X_TRANS_III_MODELS:
        print(f"  Note: '{device}' is not in the primary X-Trans III list ({', '.join(sorted(X_TRANS_III_MODELS))}). Converting anyway.")

    os.makedirs(output_dir, exist_ok=True)

    fp1_files = [f for f in os.listdir(input_dir) if f.endswith(".FP1") and os.path.isfile(os.path.join(input_dir, f))]
    if not fp1_files:
        print(f"No .FP1 templates found in: {input_dir}", file=sys.stderr)
        return 0

    print(f"\nConverting {len(fp1_files)} profiles from:\n  {input_dir}\nto:\n  {output_dir}")

    converted_paths = []
    for idx, filename in enumerate(sorted(fp1_files), 1):
        in_file = os.path.join(input_dir, filename)
        out_file = os.path.join(output_dir, filename)
        stamped_xml = stamp_profile(in_file, master_root, zero_exposure_bias=zero_exposure_bias)
        with open(out_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(stamped_xml)
        converted_paths.append(out_file)
        print(f"  [{idx:02d}/{len(fp1_files)}] Converted: {filename}")

    print(f"\nSuccessfully converted {len(converted_paths)} profiles into '{output_dir}'.")

    if install_to_xraw:
        base_dir = get_xraw_studio_base_dir()
        if not base_dir:
            print("Warning: Could not determine X Raw Studio directory for this OS. Skipping --install.", file=sys.stderr)
            return len(converted_paths)

        install_dir = os.path.join(base_dir, device, version)
        os.makedirs(install_dir, exist_ok=True)
        print(f"\nInstalling {len(converted_paths)} profiles directly into X Raw Studio:\n  {install_dir}")

        for p in converted_paths:
            dst = os.path.join(install_dir, os.path.basename(p))
            shutil.copy2(p, dst)

        print(f"Successfully installed {len(converted_paths)} profiles! They will appear in X Raw Studio immediately.")

    return len(converted_paths)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_template_candidates = [
        os.path.join(script_dir, "Fuji X Weekly Recipes", "X-Trans III"),
        os.path.join(script_dir, "profiles", "X-Trans III"),
        os.path.join(script_dir, "profiles"),
        script_dir
    ]

    parser = argparse.ArgumentParser(
        description="Convert Fujifilm X-Trans III simulation profile templates for your camera in X Raw Studio"
    )
    parser.add_argument(
        "master_template",
        nargs="?",
        default=None,
        help="Path to any .FP1 profile exported from your camera in X Raw Studio"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-discover an existing master .FP1 profile from your local X Raw Studio installation"
    )
    parser.add_argument(
        "--input-dir", "-i",
        default=None,
        help="Directory containing .FP1 templates (default: auto-detected)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory for converted profiles (default: ./converted)"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Automatically install converted profiles into your local X Raw Studio user folder"
    )
    parser.add_argument(
        "--zero-exposure-bias",
        action="store_true",
        help="Force ExposureBias to 0 in all converted profiles"
    )

    args = parser.parse_args()

    # Determine master template
    master_path = args.master_template
    if not master_path and args.auto:
        profiles = find_installed_profiles()
        if not profiles:
            print("Error: No existing .FP1 profiles found in X Raw Studio directory to auto-detect.", file=sys.stderr)
            sys.exit(1)
        # Select first profile found
        master_path = profiles[0]
        print(f"Auto-detected master profile from X Raw Studio: {master_path}")

    if not master_path:
        # Check if user ran without arguments - provide helpful guidance
        profiles = find_installed_profiles()
        if profiles:
            print("No master profile specified. Found existing profiles in your X Raw Studio directory:")
            for p in profiles[:3]:
                print(f"  - {p}")
            print(f"\nRun with:\n  python fx-templater.py \"{profiles[0]}\" --install\n")
        else:
            parser.print_help()
            print("\nTip: Export any profile from X Raw Studio with your camera connected, then run:")
            print('  python fx-templater.py "path/to/exported_profile.FP1"')
        sys.exit(1)

    # Determine input directory
    input_dir = args.input_dir
    if not input_dir:
        input_dir = find_template_dir(default_template_candidates)

    if not input_dir:
        print("Error: Could not locate .FP1 templates. Please specify with --input-dir.", file=sys.stderr)
        sys.exit(1)

    # Determine output directory
    output_dir = args.output_dir
    if not output_dir:
        output_dir = os.path.join(script_dir, "converted")

    convert_templates(
        master_path,
        input_dir,
        output_dir,
        install_to_xraw=args.install,
        zero_exposure_bias=args.zero_exposure_bias
    )

if __name__ == "__main__":
    main()
