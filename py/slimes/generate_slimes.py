#!/usr/bin/env python3
"""Generate one 96x96 pixel-art icon for every entry in list.txt.

The script deliberately has no Python dependency: ImageMagick 7 (``magick``)
does the PNG work.  The five shades of base.png are recoloured and small,
deterministic decorations identify every slime type and Largo combination.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE_PALETTE = ("#123a19", "#247433", "#2f9842", "#3abb52", "#57cb6c")

# Main body colour for each Slime Rancher family.
COLOURS = {
    "Pink": "#f477ad", "Rock": "#5185b8", "Phosphor": "#f3e879",
    "Tabby": "#a88d82", "Rad": "#72e36d", "Boom": "#d84b37",
    "Honey": "#e6a83e", "Crystal": "#7a73d8", "Hunter": "#66556e",
    "Quantum": "#f6e25e", "Dervish": "#7869d7", "Tangle": "#e98078",
    "Mosaic": "#69c9d3", "Saber": "#d08d67", "Puddle": "#5fc7e5",
    "Fire": "#ef6537", "Quicksilver": "#aebac8", "Glitch": "#df70e7",
    "Gold": "#f5ca3f", "Lucky": "#ded5c4", "Twinkle": "#e9a8ed",
    "Tarr": "#262238",
}
FAMILIES = tuple(COLOURS)


def parse_names(path: Path) -> list[str]:
    names = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        value = raw.strip().rstrip(",").strip().strip('"').strip()
        if value:
            names.append(value)
    if not names:
        raise ValueError(f"No slime names found in {path}")
    return names


def traits_for(name: str) -> list[str]:
    # Repair only for interpretation; the original spelling remains in manifest.
    cleaned = name.replace("Quant Umlargo", "Quantum Largo").replace("Mosai C", "Mosaic")
    traits = [family for family in FAMILIES if re.search(rf"\b{family}\b", cleaned, re.I)]
    return traits or ["Pink"]


def palette(hex_colour: str) -> list[str]:
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, light, sat = colorsys.rgb_to_hls(r, g, b)
    result = []
    for factor in (0.34, 0.57, 0.73, 0.90, 1.08):
        rr, gg, bb = colorsys.hls_to_rgb(h, min(0.92, light * factor), min(1, sat * 1.04))
        result.append(f"#{round(rr*255):02x}{round(gg*255):02x}{round(bb*255):02x}")
    return result


def draw_commands(traits: list[str], largo: bool) -> str:
    """Return ImageMagick MVG commands for face and family identifiers."""
    cmds: list[str] = []
    accent = COLOURS[traits[1] if len(traits) > 1 else traits[0]]
    accent_dark, accent_shadow, accent_mid, accent_light, accent_shine = palette(accent)
    dark = "#35263d"
    xoff = 0
    # Family markers. They are intentionally chunky to survive at icon size.
    for trait in traits:
        if trait in {"Tabby", "Hunter", "Lucky"}:
            cmds += [
                f"fill '{accent_dark}' polygon 35,42 39,32 45,42",
                f"fill '{accent_dark}' polygon 53,42 59,32 63,43",
                f"fill '{accent_mid}' polygon 38,40 40,34 43,41",
                f"fill '{accent_mid}' polygon 56,40 59,34 61,41",
                f"fill '{accent_shine}' rectangle 39,34 40,36",
            ]
        elif trait == "Rock":
            cmds += ["fill '#466783' polygon 38,42 41,34 45,42", "fill '#6f9cbd' polygon 49,40 53,31 57,42", "fill '#527b9b' polygon 57,45 62,37 64,47", "fill '#d8efff' polygon 40,38 41,34 42,38", "fill '#d8efff' polygon 52,35 53,31 54,36", "fill '#a9cce5' rectangle 60,40 61,42"]
        elif trait == "Crystal":
            cmds += ["fill '#c9baff' polygon 37,44 40,31 44,43", "fill '#eedbff' polygon 46,42 50,28 54,43", "fill '#a5dcff' polygon 56,44 60,33 63,46"]
        elif trait == "Phosphor":
            cmds += ["fill '#b99e51' polygon 36,47 24,39 27,52 36,55", "fill '#b99e51' polygon 61,47 72,39 70,53 61,55", "fill '#f1db79' polygon 34,47 26,41 29,49 36,52", "fill '#f1db79' polygon 63,47 70,41 68,50 61,52", "fill '#fffbd1' rectangle 27,42 29,44", "fill '#fffbd1' rectangle 68,42 70,44"]
        elif trait == "Rad":
            cmds += ["fill none stroke '#267f3b' stroke-width 5 ellipse 48,50 23,20 0,360", "fill none stroke '#70e868' stroke-width 3 ellipse 48,50 23,20 0,360", "fill '#d7ffc5' rectangle 31,36 34,38", "fill '#a6ff91' rectangle 66,56 68,59"]
        elif trait in {"Boom", "Fire"}:
            cmds += ["fill '#ffdc57' polygon 43,42 46,29 50,38 56,27 55,44", "fill '#ff7b35' polygon 47,41 50,33 53,42"]
        elif trait == "Honey":
            cmds += ["fill '#9b6020' polygon 41,44 46,39 52,40 57,45 53,49 46,49", "fill '#eab347' polygon 43,43 47,40 52,41 55,44 52,47 46,47", "fill '#fff0a0' polygon 46,41 51,41 53,43 47,43"]
        elif trait == "Quantum":
            cmds += ["fill '#b79425' rectangle 29,44 34,49", "fill '#fffbd0' rectangle 30,44 32,46", "fill '#c9a92f' rectangle 65,37 70,42", "fill '#fffbd0' rectangle 65,37 67,39", "fill '#b79425' rectangle 61,62 66,67", "fill '#fff3a0' rectangle 61,62 63,64"]
        elif trait == "Dervish":
            cmds += ["fill none stroke '#493c92' stroke-width 5 path 'M 30,43 C 36,29 63,28 68,43'", "fill none stroke '#bda8f0' stroke-width 3 path 'M 30,42 C 36,29 63,28 68,42'", "fill '#6554ae' polygon 65,38 71,43 64,45", "fill '#eee5ff' polygon 66,39 69,42 65,42"]
        elif trait == "Tangle":
            cmds += ["fill none stroke '#276b37' stroke-width 6 path 'M 35,56 C 24,70 41,75 30,83'", "fill none stroke '#61b968' stroke-width 3 path 'M 34,55 C 24,70 41,75 30,83'", "fill '#347e42' ellipse 30,81 5,3 0,360", "fill '#9be78b' polygon 26,80 30,78 31,81 28,81"]
        elif trait == "Mosaic":
            cmds += ["fill '#fff4cb' polygon 37,47 42,36 47,47", "fill '#80e7ef' polygon 50,43 55,32 60,45", "fill '#f6a8df' polygon 57,53 64,45 65,57"]
        elif trait == "Saber":
            cmds += ["fill '#8c6748' polygon 39,51 42,62 45,52", "fill '#8c6748' polygon 53,52 56,62 59,51", "fill '#f5e0b7' polygon 40,51 42,59 43,52", "fill '#fff4d9' polygon 54,52 56,59 57,52"]
        elif trait == "Puddle":
            cmds += ["fill '#277b9d' ellipse 65,59 4,5 0,360", "fill '#75d8ec' ellipse 64,58 3,4 0,360", "fill '#ddfbff' rectangle 63,56 64,57"]
        elif trait == "Quicksilver":
            cmds += ["fill none stroke '#526473' stroke-width 4 path 'M 34,47 L 42,43 L 48,47 L 56,41 L 64,46'", "fill none stroke '#e8f7ff' stroke-width 2 path 'M 34,46 L 42,42 L 48,46 L 56,40 L 64,45'", "fill '#ffffff' rectangle 55,40 57,41"]
        elif trait == "Glitch":
            cmds += ["fill '#53f3df' rectangle 33,45 39,49", "fill '#ff55c8' rectangle 57,39 64,44", "fill '#fff' rectangle 46,34 51,38"]
        elif trait in {"Gold", "Twinkle"}:
            cmds += ["fill '#8b651a' polygon 49,28 52,37 61,38 54,44 56,53 49,48 42,53 44,44 37,38 46,37", "fill '#f2c842' polygon 49,30 51,39 58,39 52,43 54,49 49,46 44,49 46,43 40,39 47,39", "fill '#fff7b0' polygon 48,31 50,31 50,39 47,40"]
        elif trait == "Tarr":
            cmds += ["fill '#422653' ellipse 35,43 5,5 0,360", "fill '#9b5fc0' ellipse 34,42 3,3 0,360", "fill '#d33c58' ellipse 65,52 5,5 0,360", "fill '#ff879a' rectangle 62,49 64,51"]
        xoff += 1

    # Face is drawn last and remains readable over all decorations.
    eye_y = 48 if largo else 47
    if "Tarr" in traits:
        cmds += ["fill '#ffcf38' polygon 39,47 44,44 44,51", "fill '#ffcf38' polygon 58,47 53,44 53,51"]
    else:
        cmds += [f"fill '{dark}' ellipse 41,{eye_y+3} 2,3 0,360", f"fill '{dark}' ellipse 57,{eye_y+3} 2,3 0,360"]
    cmds += [f"fill none stroke '{dark}' stroke-width 2 path 'M 45,{eye_y+8} Q 49,{eye_y+11} 53,{eye_y+8}'"]
    return " ".join(cmds)


def make_icon(magick: str, base: Path, destination: Path, name: str) -> None:
    traits = traits_for(name)
    largo = "Largo" in name or len(traits) > 1
    colours = palette(COLOURS[traits[0]])
    command = [magick, str(base), "-alpha", "on"]
    for source, target in zip(SOURCE_PALETTE, colours):
        command += ["-fill", target, "-opaque", source]
    if largo:
        command += ["-filter", "point", "-resize", "135%", "-background", "none", "-gravity", "center", "-extent", "96x96"]
    # Draw without vector antialiasing, then snap the complete sprite to a 2x
    # pixel grid.  The final nearest-neighbour upscale makes every visible
    # detail genuine pixel art instead of a smooth shape laid over pixel art.
    command += [
        "+antialias", "-draw", draw_commands(traits, largo),
        "-sample", "48x48", "-sample", "96x96",
        "-channel", "A", "-threshold", "50%", "+channel",
        "+dither", "-colors", "32", "-strip", str(destination),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=HERE / "base.png")
    parser.add_argument("--list", dest="name_list", type=Path, default=HERE / "list.txt")
    parser.add_argument("--output", type=Path, default=HERE / "generated")
    parser.add_argument("--magick", default="magick", help="ImageMagick executable")
    parser.add_argument("--clean", action="store_true", help="remove old numbered PNGs first")
    args = parser.parse_args()

    magick = shutil.which(args.magick)
    if not magick:
        parser.error("ImageMagick 7 was not found (expected the 'magick' command)")
    if not args.base.is_file() or not args.name_list.is_file():
        parser.error("--base and --list must point to existing files")

    names = parse_names(args.name_list)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for old_icon in args.output.glob("[0-9]*.png"):
            old_icon.unlink()

    manifest = []
    for index, name in enumerate(names):
        filename = f"{index+1}.png"
        try:
            make_icon(magick, args.base, args.output / filename, name)
        except subprocess.CalledProcessError as exc:
            print(exc.stderr, file=sys.stderr)
            return 1
        manifest.append({"index": index, "name": name, "file": filename, "traits": traits_for(name)})

    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Generated {len(names)} icons in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
