#!/usr/bin/env python3
"""Gera artes do Grinch com fotos do time (CLI).

Uso:
  python gerar.py fotos/*.jpg -o saida/
  python gerar.py foto.png --nome Ana -o saida/
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s or "membro"


def cover_paste(
    photo: Image.Image,
    box: int,
    scale: float,
    offset_x: float,
    offset_y: float,
) -> Image.Image:
    """Scale photo to cover a square box, with optional pan/zoom."""
    pw, ph = photo.size
    base = max(box / pw, box / ph)
    s = base * scale
    dw, dh = int(round(pw * s)), int(round(ph * s))
    resized = photo.resize((dw, dh), Image.Resampling.LANCZOS)
    max_ox = max(0, (dw - box) / 2)
    max_oy = max(0, (dh - box) / 2)
    left = int(round((dw - box) / 2 - offset_x * max_ox))
    top = int(round((dh - box) / 2 - offset_y * max_oy))
    return resized.crop((left, top, left + box, top + box))


def compose(
    photo_path: Path,
    template: Image.Image,
    gloss: Image.Image,
    meta: dict,
    scale: float = 1.08,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> Image.Image:
    circle = meta["circle"]
    cx, cy, r = circle["cx"], circle["cy"], circle["radius"]
    w, h = meta["width"], meta["height"]

    photo = Image.open(photo_path).convert("RGBA")
    face = cover_paste(photo, int(round(r * 2)), scale, offset_x, offset_y)

    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.paste(face, (int(round(cx - r)), int(round(cy - r))))
    base = Image.composite(layer, base, mask)
    base = Image.alpha_composite(base, template)
    base = Image.alpha_composite(base, gloss)
    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="Grinch + fotos do time")
    parser.add_argument("fotos", nargs="+", type=Path, help="Arquivos de foto")
    parser.add_argument("-o", "--out", type=Path, default=ROOT / "saida", help="Pasta de saída")
    parser.add_argument("--nome", help="Nome (só vale com uma foto)")
    parser.add_argument("--scale", type=float, default=1.08, help="Zoom (>=1)")
    args = parser.parse_args()

    meta = json.loads((ASSETS / "meta.json").read_text())
    template = Image.open(ASSETS / "template.png").convert("RGBA")
    gloss = Image.open(ASSETS / "gloss_overlay.png").convert("RGBA")
    args.out.mkdir(parents=True, exist_ok=True)

    used: dict[str, int] = {}
    for i, path in enumerate(args.fotos):
        name = args.nome if args.nome and len(args.fotos) == 1 else path.stem
        key = slugify(name)
        n = used.get(key, 0) + 1
        used[key] = n
        out_name = f"grinch-{key}.png" if n == 1 else f"grinch-{key}-{n}.png"
        art = compose(path, template, gloss, meta, scale=args.scale)
        dest = args.out / out_name
        art.save(dest)
        print(f"ok  {dest}")


if __name__ == "__main__":
    main()
