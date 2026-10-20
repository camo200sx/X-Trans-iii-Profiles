#!/usr/bin/env python3
"""
validate_profiles.py - Automated validation suite for Fujifilm X-E3 .FP1 profiles

Validates .FP1 files against:
1. XML schema and syntax
2. Ground-truth XRFC.dll enums (FilmSimulation, WhiteBalance, WBColorTemp, DynamicRange, ExposureBias)
3. Camera model (X-E3), firmware version (X-E3_0100), and hardware constraints
4. Header comments and source links
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
from typing import List, Dict, Set

# Valid XRFC enums for X-Trans III / X-E3
VALID_FILM_SIMULATIONS: Set[str] = {
    "Provia", "Velvia", "Astia", "Classic", "NEGAhi", "NEGAStd",
    "Acros", "AcrosYe", "AcrosR", "AcrosG", "BW", "BYe", "BR", "BG", "Sepia"
}

VALID_DYNAMIC_RANGE: Set[str] = {"100", "200", "400"}
VALID_GRAIN_EFFECT: Set[str] = {"OFF", "WEAK", "STRONG"}
VALID_GRAIN_SIZE: Set[str] = {"SMALL"} # Fixed on X-E3

VALID_WHITE_BALANCE: Set[str] = {
    "Auto", "Auto_White", "Auto_Ambience",
    "Custom1", "Custom2", "Custom3",
    "Temperature", "Daylight", "Shade",
    "FLight1", "FLight2", "FLight3", "Incand", "UWater"
}

VALID_KELVIN: Set[str] = {
    "0K", "10000K", "9100K", "8300K", "7700K", "7100K", "6700K", "6300K", "5900K",
    "5600K", "5300K", "5000K", "4800K", "4500K", "4300K", "4200K", "4000K", "3800K",
    "3700K", "3600K", "3400K", "3300K", "3200K", "3100K", "3000K", "2950K", "2850K",
    "2800K", "2700K", "2650K", "2550K", "2500K"
}

VALID_EXPOSURE_BIAS: Set[str] = {
    "M5P00", "M4P67", "M4P33", "M4P00", "M3P67", "M3P33", "M3P00", "M2P67", "M2P33", "M2P00",
    "M1P67", "M1P33", "M1P00", "M0P67", "M0P33", "0",
    "P0P33", "P0P67", "P1P00", "P1P33", "P1P67", "P2P00", "P2P33", "P2P67", "P3P00", "P3P33",
    "P3P67", "P4P00", "P4P33", "P4P67", "P5P00"
}

def validate_profile(file_path: str, is_converted: bool = True, expected_device: str = "X-E3", expected_ver: str = "X-E3_0100") -> List[str]:
    errors = []
    filename = os.path.basename(file_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as e:
        return [f"Failed to read file: {e}"]

    # Check XML declaration & comments
    lines = raw_text.splitlines()
    if not lines or not lines[0].startswith('<?xml version="1.0" encoding="utf-8"?>'):
        errors.append("Missing or invalid XML declaration on line 1")

    has_github_comment = any("github.com/plamf/fuji-x-weekly-simulation-profiles" in l for l in lines[:5])
    has_source_comment = any("fujixweekly.com" in l or "film.recipes" in l for l in lines[:5])
    if not has_github_comment:
        errors.append("Missing GitHub reference comment in header")
    if not has_source_comment:
        errors.append("Missing recipe source URL comment (fujixweekly.com or film.recipes) in header")

    try:
        root = ET.fromstring(raw_text)
    except ET.ParseError as e:
        return [f"XML parse error: {e}"]

    if root.tag != "ConversionProfile":
        errors.append(f"Root tag is '{root.tag}', expected 'ConversionProfile'")

    prop = root.find("./PropertyGroup")
    if prop is None:
        return errors + ["Missing <PropertyGroup> element"]

    if is_converted:
        if root.get("application") != "XRFC":
            errors.append(f"application attribute is '{root.get('application')}', expected 'XRFC'")
        if not root.get("version"):
            errors.append("Missing application version attribute")
        if prop.get("device") != expected_device:
            errors.append(f"device attribute is '{prop.get('device')}', expected '{expected_device}'")
        if prop.get("version") != expected_ver:
            errors.append(f"version attribute is '{prop.get('version')}', expected '{expected_ver}'")

    label = prop.get("label", "")
    if not label:
        errors.append("Missing or empty 'label' attribute on PropertyGroup")

    # Helper to get child text
    def get_val(tag: str) -> str:
        el = prop.find(tag)
        return el.text if el is not None and el.text is not None else ""

    # Check hardware fields
    if is_converted:
        sn = get_val("SerialNumber")
        if not sn:
            errors.append("SerialNumber is empty in converted profile")
        tether = get_val("TetherRAWConditonCode")
        if tether != expected_ver:
            errors.append(f"TetherRAWConditonCode is '{tether}', expected '{expected_ver}'")
        if get_val("Editable") != "TRUE":
            errors.append(f"Editable is '{get_val('Editable')}', expected 'TRUE'")
        if get_val("StructVer") != "65536":
            errors.append(f"StructVer is '{get_val('StructVer')}', expected '65536'")
        if get_val("FileType") != "JPG":
            errors.append(f"FileType is '{get_val('FileType')}', expected 'JPG'")

    # Fixed X-E3 tags
    if get_val("WideDRange") != "0":
        errors.append(f"WideDRange is '{get_val('WideDRange')}', expected '0'")
    if get_val("GrainEffectSize") != "SMALL":
        errors.append(f"GrainEffectSize is '{get_val('GrainEffectSize')}', expected 'SMALL'")
    if get_val("ChromeEffect") != "OFF":
        errors.append(f"ChromeEffect is '{get_val('ChromeEffect')}', expected 'OFF'")
    if get_val("Clarity") != "0":
        errors.append(f"Clarity is '{get_val('Clarity')}', expected '0'")
    if get_val("ColorChromeBlue") != "":
        errors.append(f"ColorChromeBlue must be empty on X-E3, found '{get_val('ColorChromeBlue')}'")
    if get_val("SmoothSkinEffect") != "":
        errors.append(f"SmoothSkinEffect must be empty on X-E3, found '{get_val('SmoothSkinEffect')}'")

    # Simulation enum values
    sim = get_val("FilmSimulation")
    if sim not in VALID_FILM_SIMULATIONS:
        errors.append(f"FilmSimulation '{sim}' is not a valid X-E3 simulation enum")

    dr = get_val("DynamicRange")
    if dr not in VALID_DYNAMIC_RANGE:
        errors.append(f"DynamicRange '{dr}' is invalid (must be 100, 200, or 400)")

    grain = get_val("GrainEffect")
    if grain not in VALID_GRAIN_EFFECT:
        errors.append(f"GrainEffect '{grain}' is invalid (must be OFF, WEAK, STRONG)")

    wb = get_val("WhiteBalance")
    if wb not in VALID_WHITE_BALANCE:
        errors.append(f"WhiteBalance '{wb}' is invalid")

    kelvin = get_val("WBColorTemp")
    if kelvin not in VALID_KELVIN:
        errors.append(f"WBColorTemp '{kelvin}' is not a valid uppercase Kelvin step")

    if wb == "Temperature" and kelvin == "0K":
        errors.append("WhiteBalance is 'Temperature' but WBColorTemp is '0K'")
    if wb != "Temperature" and kelvin != "0K":
        errors.append(f"WhiteBalance is '{wb}' but WBColorTemp is '{kelvin}' instead of '0K'")

    exp = get_val("ExposureBias")
    if exp not in VALID_EXPOSURE_BIAS:
        errors.append(f"ExposureBias '{exp}' is not a valid XRFC enum")

    # Shift ranges
    for shift_tag in ("WBShiftR", "WBShiftB"):
        val = get_val(shift_tag)
        try:
            int_val = int(val)
            if not (-9 <= int_val <= 9):
                errors.append(f"{shift_tag} value {int_val} outside [-9, 9]")
        except ValueError:
            errors.append(f"{shift_tag} '{val}' is not an integer")

    # Tone / Color / Sharpness / NR ranges
    for tone_tag in ("HighlightTone", "ShadowTone"):
        val = get_val(tone_tag)
        try:
            int_val = int(val)
            if not (-2 <= int_val <= 4):
                errors.append(f"{tone_tag} value {int_val} outside [-2, 4]")
        except ValueError:
            errors.append(f"{tone_tag} '{val}' is not an integer")

    for col_tag in ("Color", "Sharpness", "NoisReduction"):
        val = get_val(col_tag)
        try:
            int_val = int(val)
            if not (-4 <= int_val <= 4):
                errors.append(f"{col_tag} value {int_val} outside [-4, 4]")
        except ValueError:
            errors.append(f"{col_tag} '{val}' is not an integer")

    return errors

def main():
    parser = argparse.ArgumentParser(description="Validate Fujifilm X-E3 .FP1 profiles")
    parser.add_argument("target_dir", nargs="?", default=None, help="Directory to validate (default: 'Fuji X Weekly Recipes/X-Trans III/converted')")
    parser.add_argument("--templates", action="store_true", help="Validate generic templates instead of converted profiles")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if args.target_dir:
        target_dir = args.target_dir
    else:
        if args.templates:
            target_dir = os.path.join(project_root, "Fuji X Weekly Recipes", "X-Trans III")
        else:
            target_dir = os.path.join(project_root, "Fuji X Weekly Recipes", "X-Trans III", "converted")

    if not os.path.isdir(target_dir):
        print(f"Error: Target directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    fp1_files = [os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.endswith(".FP1") and os.path.isfile(os.path.join(target_dir, f))]
    if not fp1_files:
        print(f"Error: No .FP1 files found in {target_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Validating {len(fp1_files)} profiles in:\n  {target_dir}\n")

    total_errors = 0
    valid_count = 0

    for file_path in sorted(fp1_files):
        fname = os.path.basename(file_path)
        errors = validate_profile(file_path, is_converted=(not args.templates))
        if errors:
            print(f"FAIL: {fname}")
            for err in errors:
                print(f"  - {err}")
            total_errors += len(errors)
        else:
            valid_count += 1
            # print(f"PASS: {fname}")

    print("\n" + "=" * 50)
    print(f"Validation Summary: {valid_count}/{len(fp1_files)} profiles valid")
    if total_errors > 0:
        print(f"FAILED: Found {total_errors} errors across invalid profiles.")
        sys.exit(1)
    else:
        print("SUCCESS: All profiles strictly comply with XRFC.dll and X-E3 specifications!")
        sys.exit(0)

if __name__ == "__main__":
    main()

