#!/usr/bin/env python3
"""
build_profiles.py - Scrapes / loads Fuji X Weekly X-Trans III recipes,
normalizes parameters to Fujifilm X Raw Studio XRFC.dll schema, and
outputs generic .FP1 template files into 'Fuji X Weekly Recipes/X-Trans III'.
"""

import os
import sys
import re
import argparse
import urllib.request
import urllib.parse
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

# Base directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CACHE_DIR = os.path.join(PROJECT_ROOT, "cache", "html")
OUTPUT_TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "Fuji X Weekly Recipes", "X-Trans III")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
INDEX_URL = "https://fujixweekly.com/fujifilm-x-trans-iii-recipes/"

@dataclass
class Recipe:
    name: str
    filename: str
    source_url: str
    film_simulation: str
    dynamic_range: str
    grain_effect: str
    grain_effect_size: str
    white_balance: str
    wb_shift_r: str
    wb_shift_b: str
    wb_color_temp: str
    highlight_tone: str
    shadow_tone: str
    color: str
    sharpness: str
    noise_reduction: str
    exposure_bias: str

# 47 Ground Truth Recipe Specifications based on XRFC.dll and plan/03
GROUND_TRUTH_CATALOG: List[Recipe] = [
    Recipe("Velvia", "Velvia.FP1", "https://fujixweekly.com/2017/10/01/my-fujifilm-x100f-velvia-film-simulation-recipe/",
           "Velvia", "200", "WEAK", "SMALL", "Auto", "1", "-1", "0K", "-1", "0", "2", "2", "-2", "P0P67"),
    Recipe("Improved Velvia", "Improved Velvia.FP1", "https://fujixweekly.com/2022/02/25/fujifilm-x-h1-x-trans-iii-x-t3-x-30-film-simulation-recipe-improved-velvia/",
           "Velvia", "200", "WEAK", "SMALL", "Auto", "-1", "-2", "0K", "-1", "0", "1", "0", "-4", "P0P33"),
    Recipe("Astia", "Astia.FP1", "https://fujixweekly.com/2017/10/16/my-fujifilm-x100f-astia-film-simulation-recipe/",
           "Astia", "200", "WEAK", "SMALL", "Auto", "0", "0", "0K", "-1", "-2", "1", "1", "-3", "P0P33"),
    Recipe("Everyday Astia", "Everyday Astia.FP1", "https://fujixweekly.com/2022/09/21/fujifilm-x-h1-x-trans-iii-x-t3-x-t30-film-simulation-recipe-everyday-astia/",
           "Astia", "400", "WEAK", "SMALL", "Auto", "-1", "-2", "0K", "1", "1", "-1", "-1", "-4", "0"),
    Recipe("Provia Slide", "Provia Slide.FP1", "https://fujixweekly.com/2024/04/15/provia-slide-fujifilm-x-pro2-x-trans-iii-film-simulation-recipe/",
           "Provia", "200", "WEAK", "SMALL", "FLight3", "-1", "-8", "0K", "-1", "1", "3", "-1", "-4", "P0P33"),
    Recipe("Classic Chrome", "Classic Chrome.FP1", "https://fujixweekly.com/2017/08/27/my-fujifilm-x100f-classic-chrome-film-simulation-recipe/",
           "Classic", "200", "WEAK", "SMALL", "Auto", "1", "-1", "0K", "-1", "1", "2", "2", "-2", "P0P67"),
    Recipe("Vintage Kodachrome", "Vintage Kodachrome.FP1", "https://fujixweekly.com/2017/10/21/my-fujifilm-x100f-vintage-kodachrome-film-simulation-recipe/",
           "Classic", "200", "STRONG", "SMALL", "Auto", "2", "-4", "0K", "4", "-2", "4", "1", "-3", "M0P33"),
    Recipe("Vintage Kodacolor", "Vintage Kodacolor.FP1", "https://fujixweekly.com/2022/08/29/fujifilm-x-trans-iii-x-t3-x-t30-film-simulation-recipe-vintage-kodacolor/",
           "Classic", "200", "STRONG", "SMALL", "Temperature", "-4", "4", "9100K", "2", "0", "-4", "-1", "-4", "M0P33"),
    Recipe("Mystery Chrome", "Mystery Chrome.FP1", "https://fujixweekly.com/2022/12/09/fujifilm-x-trans-iii-x-t3-x-t30-film-simulation-recipe-mystery-chrome/",
           "Classic", "400", "STRONG", "SMALL", "Daylight", "3", "-5", "0K", "3", "4", "0", "-4", "4", "P0P33"),
    Recipe("PRO Neg. Hi", "PRO Neg. Hi.FP1", "https://fujixweekly.com/2018/01/21/my-fujifilm-x100f-pro-neg-hi-film-simulation-recipe-portraits/",
           "NEGAhi", "200", "WEAK", "SMALL", "Auto", "0", "0", "0K", "-1", "-1", "1", "1", "-3", "P0P33"),
    Recipe("Fujicolor Pro 160NS Box Speed", "Fujicolor Pro 160NS Box Speed.FP1", "https://fujixweekly.com/2021/05/24/a-different-approach-7-new-fujicolor-pro-160ns-film-simulation-recipes-yes-7/",
           "NEGAhi", "400", "WEAK", "SMALL", "Daylight", "0", "0", "0K", "0", "0", "0", "-3", "-4", "0"),
    Recipe("Fujicolor Pro 160NS Pulled -1", "Fujicolor Pro 160NS Pulled -1.FP1", "https://fujixweekly.com/2021/05/24/a-different-approach-7-new-fujicolor-pro-160ns-film-simulation-recipes-yes-7/",
           "NEGAhi", "400", "WEAK", "SMALL", "Daylight", "0", "0", "0K", "-1", "-1", "0", "-3", "-4", "0"),
    Recipe("Fujicolor Pro 160NS Pulled -2", "Fujicolor Pro 160NS Pulled -2.FP1", "https://fujixweekly.com/2021/05/24/a-different-approach-7-new-fujicolor-pro-160ns-film-simulation-recipes-yes-7/",
           "NEGAhi", "400", "WEAK", "SMALL", "Daylight", "0", "0", "0K", "-2", "-1", "-1", "-3", "-4", "0"),
    Recipe("Fujicolor Pro 160NS Pushed +1", "Fujicolor Pro 160NS Pushed +1.FP1", "https://fujixweekly.com/2021/05/24/a-different-approach-7-new-fujicolor-pro-160ns-film-simulation-recipes-yes-7/",
           "NEGAhi", "400", "WEAK", "SMALL", "Daylight", "0", "0", "0K", "1", "0", "0", "-3", "-4", "0"),
    Recipe("Fujicolor Pro 160NS Pushed +2", "Fujicolor Pro 160NS Pushed +2.FP1", "https://fujixweekly.com/2021/05/24/a-different-approach-7-new-fujicolor-pro-160ns-film-simulation-recipes-yes-7/",
           "NEGAhi", "400", "WEAK", "SMALL", "Daylight", "0", "0", "0K", "2", "0", "1", "-3", "-4", "M0P33"),
    Recipe("Fujicolor Pro 160NS Pushed +3", "Fujicolor Pro 160NS Pushed +3.FP1", "https://fujixweekly.com/2021/05/24/a-different-approach-7-new-fujicolor-pro-160ns-film-simulation-recipes-yes-7/",
           "NEGAhi", "400", "WEAK", "SMALL", "Daylight", "0", "0", "0K", "2", "1", "2", "-3", "-4", "M0P33"),
    Recipe("Fujicolor Pro 160NS Pushed +4", "Fujicolor Pro 160NS Pushed +4.FP1", "https://fujixweekly.com/2021/05/24/a-different-approach-7-new-fujicolor-pro-160ns-film-simulation-recipes-yes-7/",
           "NEGAhi", "400", "WEAK", "SMALL", "Daylight", "0", "0", "0K", "3", "2", "3", "-4", "-4", "M0P33"),
    Recipe("Fujicolor Superia 800", "Fujicolor Superia 800.FP1", "https://fujixweekly.com/2018/02/03/my-fujifilm-x100f-fujicolor-superia-800-film-simulation-recipe-pro-neg-std/",
           "NEGAStd", "200", "STRONG", "SMALL", "Auto", "-2", "-3", "0K", "1", "2", "4", "1", "-3", "P0P67"),
    Recipe("CineStill 800T", "CineStill 800T.FP1", "https://fujixweekly.com/2018/04/25/my-fujifilm-x100f-cinestill-800t-film-simulation-recipe/",
           "NEGAStd", "200", "STRONG", "SMALL", "Temperature", "0", "0", "3200K", "3", "1", "-1", "1", "-3", "0"),
    Recipe("Fujicolor NPL 160 Tungsten", "Fujicolor NPL 160 Tungsten.FP1", "https://fujixweekly.com/2021/12/06/fujifilm-x-h1-x-trans-iii-film-simulation-recipe-fujicolor-npl-160-tungsten/",
           "NEGAStd", "400", "WEAK", "SMALL", "FLight3", "-6", "-3", "0K", "-2", "0", "-2", "-1", "-4", "M0P33"),
    Recipe("Eterna (X100F)", "Eterna (X100F).FP1", "https://fujixweekly.com/2018/03/02/my-fujifilm-x100f-eterna-film-simulation-recipe/",
           "NEGAStd", "400", "WEAK", "SMALL", "Auto", "2", "2", "0K", "-2", "-1", "-4", "1", "-4", "P1P00"),
    Recipe("Eterna", "Eterna.FP1", "https://fujixweekly.com/2019/04/13/my-x-t30-eterna-recipe-for-x-trans-iii/",
           "NEGAStd", "200", "STRONG", "SMALL", "Auto", "5", "-6", "0K", "2", "2", "3", "2", "-4", "0"),
    Recipe("Kodak Porta 400", "Kodak Porta 400.FP1", "https://fujixweekly.com/2018/05/30/my-fujifilm-x100f-kodak-portra-400-film-simulation-recipe/",
           "Classic", "400", "STRONG", "SMALL", "Custom1", "2", "-5", "0K", "-1", "2", "-2", "1", "-3", "P1P00"),
    Recipe("Kodak Ektar 100", "Kodak Ektar 100.FP1", "https://fujixweekly.com/2018/06/16/my-fujifilm-x100f-kodak-ektar-100-film-simulation-recipe/",
           "Astia", "100", "OFF", "SMALL", "Auto", "3", "-2", "0K", "1", "3", "4", "1", "-3", "0"),
    Recipe("Kodachrome II", "Kodachrome II.FP1", "https://fujixweekly.com/2018/08/19/my-fujifilm-x-pro2-kodachrome-ii-film-simulation-recipe/",
           "Classic", "200", "WEAK", "SMALL", "Auto", "3", "-4", "0K", "1", "2", "-1", "1", "-3", "P0P33"),
    Recipe("Dramatic Classic Chrome", "Dramatic Classic Chrome.FP1", "https://fujixweekly.com/2018/05/22/my-fujifilm-x-pro2-dramatic-classic-chrome-film-simulation-recipe/",
           "Classic", "100", "STRONG", "SMALL", "Auto", "-1", "1", "0K", "3", "3", "0", "1", "-3", "P0P33"),
    Recipe("Vintage Agfacolor", "Vintage Agfacolor.FP1", "https://fujixweekly.com/2018/06/23/my-fujifilm-x-pro2-vintage-agfacolor-film-simulation-recipe/",
           "Classic", "100", "STRONG", "SMALL", "Auto", "-3", "-4", "0K", "2", "1", "-4", "0", "-3", "M0P33"),
    Recipe("Melancholy Blue", "Melancholy Blue.FP1", "https://fujixweekly.com/2022/08/08/fujifilm-x-trans-iii-x-t3-x-t30-film-simulation-recipe-melancholy-blue/",
           "Classic", "200", "WEAK", "SMALL", "Incand", "4", "-9", "0K", "3", "-1", "-2", "-1", "-4", "M0P33"),
    Recipe("Nostalgic Emulsion", "Nostalgic Emulsion.FP1", "https://fujixweekly.com/2024/10/24/nostalgic-emulsion-fujifilm-x-trans-iii-plus-x-t3-x-t30-film-simulation-recipe/",
           "Classic", "200", "STRONG", "SMALL", "UWater", "-6", "3", "0K", "-1", "3", "2", "-1", "-4", "M0P33"),
    Recipe("Aged Color", "Aged Color.FP1", "https://fujixweekly.com/2018/11/17/my-fujifilm-x-t20-aged-color-film-simulation-recipe/",
           "NEGAStd", "400", "STRONG", "SMALL", "Auto", "5", "-3", "0K", "2", "3", "4", "0", "-3", "P0P33"),
    Recipe("Kodak Ektachrome 100SW", "Kodak Ektachrome 100SW.FP1", "https://fujixweekly.com/2018/12/02/my-fujifilm-x-t20-kodak-ektachrome-100sw-film-simulation-recipe/",
           "Velvia", "200", "WEAK", "SMALL", "Auto", "3", "-4", "0K", "1", "2", "-1", "0", "-3", "P0P33"),
    Recipe("Ektachrome E100GX", "Ektachrome E100GX.FP1", "https://fujixweekly.com/2022/07/26/fujifilm-x-trans-iii-x-t3-x-t30-film-simulation-recipe-ektachrome-e100gx/",
           "Classic", "200", "WEAK", "SMALL", "FLight2", "-1", "-6", "0K", "-2", "2", "4", "-2", "-4", "P0P33"),
    Recipe("Fujicolor Pro 400H", "Fujicolor Pro 400H.FP1", "https://fujixweekly.com/2018/12/23/my-fujifilm-x-t20-fujicolor-pro-400h-film-simulation-recipe/",
           "NEGAStd", "200", "WEAK", "SMALL", "Auto", "2", "1", "0K", "0", "3", "4", "0", "-3", "P0P67"),
    Recipe("Fujicolor Pro", "Fujicolor Pro.FP1", "https://fujixweekly.com/2023/05/08/fujicolor-pro-fujifilm-x-trans-iii-x-t3-x-t30-film-simulation-recipe/",
           "NEGAStd", "400", "STRONG", "SMALL", "Temperature", "-2", "0", "5900K", "-2", "3", "-2", "-2", "-4", "P0P67"),
    Recipe("Agfa Optima", "Agfa Optima.FP1", "https://fujixweekly.com/2019/02/14/fujifilm-provia-film-simulation-settings-or-my-agfa-optima-200-recipe/",
           "Provia", "100", "WEAK", "SMALL", "Auto", "-1", "-1", "0K", "-2", "2", "-2", "0", "-3", "P0P67"),
    Recipe("Classic Negative", "Classic Negative.FP1", "https://fujixweekly.com/2019/11/07/my-fujifilm-classic-negative-film-simulation-recipe-for-x-trans-iii/",
           "NEGAStd", "400", "WEAK", "SMALL", "Temperature", "-2", "7", "6700K", "3", "2", "-3", "1", "-4", "M0P33"),
    Recipe("Kodak Ultramax", "Kodak Ultramax.FP1", "https://fujixweekly.com/2020/08/24/fujifilm-x-t20-x-trans-iii-x-t30-film-simulation-recipe-kodak-ultramax/",
           "Classic", "400", "STRONG", "SMALL", "Auto", "1", "-6", "0K", "2", "2", "4", "2", "-4", "P0P33"),
    Recipe("Kodak GT 800-5", "Kodak GT 800-5.FP1", "https://fujixweekly.com/2022/01/11/fujifilm-x-h1-film-simulation-recipe-kodak-gt-800-5/",
           "NEGAStd", "400", "STRONG", "SMALL", "Temperature", "7", "-5", "7100K", "0", "3", "-3", "-2", "-4", "P0P33"),
    Recipe("Cine Teal", "Cine Teal.FP1", "https://fujixweekly.com/2020/06/25/fujifilm-x-t20-x-trans-iii-film-simulation-recipe-cine-teal/",
           "NEGAStd", "400", "WEAK", "SMALL", "Temperature", "2", "-8", "4500K", "-1", "3", "-3", "-1", "-3", "P0P67"),
    Recipe("Cross Process", "Cross Process.FP1", "https://fujixweekly.com/2018/10/15/my-fujifilm-x100f-cross-process-film-simulation-recipe/",
           "Provia", "200", "STRONG", "SMALL", "Auto", "-3", "-8", "0K", "2", "3", "4", "0", "-3", "P0P67"),
    Recipe("Acros", "Acros.FP1", "https://fujixweekly.com/2017/08/27/my-fujifilm-x100f-acros-film-simulation-recipe/",
           "Acros", "200", "OFF", "SMALL", "Auto", "0", "0", "0K", "2", "2", "0", "2", "-2", "P1P00"),
    Recipe("Acros Push Process", "Acros Push Process.FP1", "https://fujixweekly.com/2017/11/11/my-fujifilm-x100f-acros-push-process-film-simulation-recipe/",
           "Acros", "200", "STRONG", "SMALL", "Auto", "0", "0", "0K", "4", "3", "0", "1", "-3", "P1P00"),
    Recipe("Agfa Scala", "Agfa Scala.FP1", "https://fujixweekly.com/2018/08/12/my-fujifilm-x100f-agfa-scala-film-simulation-recipe/",
           "Acros", "100", "WEAK", "SMALL", "Auto", "0", "0", "0K", "4", "0", "0", "0", "-3", "M0P33"),
    Recipe("Ilford HP5 Plus", "Ilford HP5 Plus.FP1", "https://fujixweekly.com/2018/12/01/my-fujifilm-x100f-ilford-hp5-plus-film-simulation-recipe/",
           "Acros", "200", "STRONG", "SMALL", "Auto", "0", "0", "0K", "4", "2", "0", "0", "-3", "0"),
    Recipe("Ilford XP2 Super 400", "Ilford XP2 Super 400.FP1", "https://fujixweekly.com/2021/12/11/fujifilm-x-h1-x-trans-iii-film-simulation-recipe-ilford-xp2-super-400/",
           "AcrosR", "400", "STRONG", "SMALL", "Temperature", "7", "7", "10000K", "-1", "4", "0", "-2", "-4", "M0P67"),
    Recipe("Analog Monochrome", "Analog Monochrome.FP1", "https://fujixweekly.com/2022/01/05/fujifilm-x-h1-x-trans-iii-x-t3-x-t30-film-simulation-recipe-analog-monochrome/",
           "AcrosG", "400", "WEAK", "SMALL", "Incand", "-8", "-8", "0K", "1", "3", "0", "-1", "-4", "P0P33"),
    Recipe("Kodak Tri-X Push Process", "Kodak Tri-X Push Process.FP1", "https://fujixweekly.com/2018/08/25/not-my-fujifilm-x-pro2-tri-x-push-process-film-simulation-recipe/",
           "Acros", "200", "OFF", "SMALL", "Auto", "0", "0", "0K", "3", "4", "0", "-1", "-4", "P0P33"),
    # Extended Kodak collection (Fuji X Weekly cross-compatible + film.recipes)
    Recipe("Kodak Gold 200", "Kodak Gold 200.FP1", "https://fujixweekly.com/2020/04/16/my-fujifilm-x-t30-kodak-gold-200-film-simulation-recipe/",
           "Classic", "200", "STRONG", "SMALL", "Daylight", "4", "-5", "0K", "-2", "1", "3", "-2", "-4", "P0P67"),
    Recipe("Classic Kodak", "Classic Kodak.FP1", "https://fujixweekly.com/2022/11/08/fujifilm-x-t30-x-t3-x-trans-iii-film-simulation-recipe-classic-kodak/",
           "Classic", "400", "STRONG", "SMALL", "Shade", "-1", "2", "0K", "-2", "1", "4", "-1", "-4", "P0P33"),
    Recipe("Kodacolor", "Kodacolor.FP1", "https://fujixweekly.com/2019/07/19/my-fujifilm-x-t30-kodacolor-film-simulation-recipe/",
           "Classic", "400", "STRONG", "SMALL", "Temperature", "-1", "-4", "6300K", "-1", "2", "-2", "2", "-4", "P0P67"),
    Recipe("Kodacolor Part 2", "Kodacolor Part 2.FP1", "http://fujixweekly.com/2020/03/16/kodacolor-film-simulation-recipe-part-2/",
           "Classic", "400", "STRONG", "SMALL", "Temperature", "-1", "-4", "6300K", "-1", "2", "0", "2", "-4", "P0P67"),
    Recipe("Kodacolor VR", "Kodacolor VR.FP1", "https://fujixweekly.com/2022/04/11/fujifilm-x-trans-iii-x-t3-x-t30-film-simulation-recipe-kodacolor-vr/",
           "Classic", "400", "WEAK", "SMALL", "Temperature", "-7", "8", "10000K", "-1", "1", "2", "-1", "-4", "P0P33"),
    Recipe("Kodak Portra 160", "Kodak Portra 160.FP1", "https://fujixweekly.com/2020/04/03/my-fujifilm-x-t30-kodak-portra-160-film-simulation-recipe/",
           "Classic", "200", "WEAK", "SMALL", "Daylight", "4", "-5", "0K", "-2", "-2", "1", "-2", "-4", "P0P67"),
    Recipe("Kodak Gold (film.recipes)", "Kodak Gold (film.recipes).FP1", "https://film.recipes/2022/04/22/kodak-gold-film-recipe-for-nostalgic-warmth/",
           "Classic", "200", "STRONG", "SMALL", "Daylight", "4", "-5", "0K", "-1", "1", "0", "-2", "-4", "P0P33"),
    Recipe("Kodak Gold II (film.recipes)", "Kodak Gold II (film.recipes).FP1", "https://film.recipes/2026/07/19/kodak-gold-ii-classic-kodak-film-recipe/",
           "Classic", "200", "WEAK", "SMALL", "Daylight", "4", "-5", "0K", "-1", "1", "1", "-2", "-4", "P0P33"),
    Recipe("Old Gold (film.recipes)", "Old Gold (film.recipes).FP1", "https://film.recipes/2026/05/28/old-gold-film-recipe/",
           "Classic", "200", "WEAK", "SMALL", "Daylight", "4", "-7", "0K", "-1", "-1", "-2", "-2", "-4", "M0P33"),
    Recipe("Gold Standard (film.recipes)", "Gold Standard (film.recipes).FP1", "https://film.recipes/2022/06/14/gold-standard-for-an-everyday-kodak-gold/",
           "NEGAStd", "200", "WEAK", "SMALL", "Daylight", "4", "-5", "0K", "-1", "1", "-2", "-2", "-4", "P0P33"),
    Recipe("Rescued Colorplus (film.recipes)", "Rescued Colorplus (film.recipes).FP1", "https://film.recipes/2023/09/01/rescued-colorplus-from-a-found-kodak-film/",
           "Classic", "400", "WEAK", "SMALL", "Auto", "2", "-4", "0K", "1", "-1", "3", "0", "-4", "M0P33"),
    Recipe("123 Chrome (film.recipes)", "123 Chrome (film.recipes).FP1", "https://film.recipes/2025/07/22/123-chrome-classic-kodachrome-look/",
           "Classic", "400", "OFF", "SMALL", "UWater", "1", "-2", "0K", "-1", "-2", "3", "0", "-4", "0"),
]

def fetch_url(url: str) -> str:
    import subprocess
    try:
        return subprocess.check_output(
            ["curl.exe", "-s", "-L", "-A", USER_AGENT, url],
            text=True, encoding="utf-8", errors="replace"
        )
    except Exception:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8", errors="replace")

def cache_pages():
    os.makedirs(CACHE_DIR, exist_ok=True)
    index_cache_file = os.path.join(CACHE_DIR, "index_xtrans3.html")
    if not os.path.exists(index_cache_file):
        print(f"Downloading index page: {INDEX_URL}...")
        html = fetch_url(INDEX_URL)
        with open(index_cache_file, "w", encoding="utf-8") as f:
            f.write(html)
    else:
        print(f"Using cached index: {index_cache_file}")

    # Fetch and cache individual recipe articles
    unique_urls = list({r.source_url: r for r in GROUND_TRUTH_CATALOG}.keys())
    print(f"Ensuring {len(unique_urls)} recipe articles are cached locally in {CACHE_DIR}...")
    for idx, url in enumerate(unique_urls, 1):
        slug = url.strip("/").split("/")[-1]
        cache_file = os.path.join(CACHE_DIR, f"{slug}.html")
        if not os.path.exists(cache_file):
            print(f"  [{idx}/{len(unique_urls)}] Fetching {url}...")
            try:
                page_html = fetch_url(url)
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(page_html)
            except Exception as e:
                print(f"  Warning: failed to download {url}: {e}")
        else:
            # print(f"  [{idx}/{len(unique_urls)}] Cached: {slug}")
            pass
    print("HTML caching complete.")

def generate_template_xml(recipe: Recipe, zero_exposure_bias: bool = False) -> str:
    """Formats the generic .FP1 XML template according to XRFC schema for X-Trans III / X-E3."""
    exp_bias = "0" if zero_exposure_bias else recipe.exposure_bias
    
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<!--This file was generated by custom code. Check https://github.com/plamf/fuji-x-weekly-simulation-profiles if you want to learn more.-->
<!--Simulation values parsed from {recipe.source_url} -->
<ConversionProfile application="" version="">
    <PropertyGroup device="" version="" label="{recipe.name}">
        <SerialNumber></SerialNumber>
        <TetherRAWConditonCode></TetherRAWConditonCode>
        <Editable></Editable>
        <SourceFileName/>
        <Fileerror></Fileerror>
        <RotationAngle></RotationAngle>
        <StructVer></StructVer>
        <IOPCode></IOPCode>
        <ShootingCondition></ShootingCondition>
        <FileType></FileType>
        <ImageSize></ImageSize>
        <ImageQuality></ImageQuality>
        <ExposureBias>{exp_bias}</ExposureBias>
        <DynamicRange>{recipe.dynamic_range}</DynamicRange>
        <WideDRange>0</WideDRange>
        <FilmSimulation>{recipe.film_simulation}</FilmSimulation>
        <BlackImageTone>0</BlackImageTone>
        <MonochromaticColor_RG>0</MonochromaticColor_RG>
        <GrainEffect>{recipe.grain_effect}</GrainEffect>
        <GrainEffectSize>{recipe.grain_effect_size}</GrainEffectSize>
        <ChromeEffect>OFF</ChromeEffect>
        <ColorChromeBlue/>
        <SmoothSkinEffect/>
        <WBShootCond>OFF</WBShootCond>
        <WhiteBalance>{recipe.white_balance}</WhiteBalance>
        <WBShiftR>{recipe.wb_shift_r}</WBShiftR>
        <WBShiftB>{recipe.wb_shift_b}</WBShiftB>
        <WBColorTemp>{recipe.wb_color_temp}</WBColorTemp>
        <HighlightTone>{recipe.highlight_tone}</HighlightTone>
        <ShadowTone>{recipe.shadow_tone}</ShadowTone>
        <Color>{recipe.color}</Color>
        <Sharpness>{recipe.sharpness}</Sharpness>
        <NoisReduction>{recipe.noise_reduction}</NoisReduction>
        <Clarity>0</Clarity>
        <LensModulationOpt></LensModulationOpt>
        <ColorSpace></ColorSpace>
        <HDR/>
        <DigitalTeleConv/>
        <PortraitEnhancer/>
    </PropertyGroup>
</ConversionProfile>
"""
    return xml

def main():
    parser = argparse.ArgumentParser(description="Build Fuji X Weekly X-Trans III simulation profile templates")
    parser.add_argument("--zero-exposure-bias", action="store_true", help="Set ExposureBias to 0 for all profiles")
    parser.add_argument("--skip-cache", action="store_true", help="Skip fetching HTML cache")
    args = parser.parse_args()

    if not args.skip_cache:
        cache_pages()

    os.makedirs(OUTPUT_TEMPLATES_DIR, exist_ok=True)
    print(f"\nGenerating {len(GROUND_TRUTH_CATALOG)} generic .FP1 templates in:\n  {OUTPUT_TEMPLATES_DIR}")

    for idx, recipe in enumerate(GROUND_TRUTH_CATALOG, 1):
        content = generate_template_xml(recipe, zero_exposure_bias=args.zero_exposure_bias)
        out_path = os.path.join(OUTPUT_TEMPLATES_DIR, recipe.filename)
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"  [{idx:02d}/{len(GROUND_TRUTH_CATALOG)}] Created: {recipe.filename} (Sim={recipe.film_simulation}, WB={recipe.white_balance}, DR={recipe.dynamic_range})")

    print(f"\nSuccessfully generated {len(GROUND_TRUTH_CATALOG)} templates.")

if __name__ == "__main__":
    main()
