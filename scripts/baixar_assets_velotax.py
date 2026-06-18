"""Baixa logo e mascote oficiais da Velotax para uso offline no dashboard."""

from __future__ import annotations

import urllib.request
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "dashboard" / "assets"
FILES = {
    "velo-mascote.png": "https://velotax.com.br/images/mascote/velo-afirmativo.png",
    "velotax-logo-branco.png": "https://velotax.com.br/images/logos/velotax-logo-branco.png",
}


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dest = ASSETS / name
        print(f"Baixando {name}...")
        urllib.request.urlretrieve(url, dest)
        print(f"  ok ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
