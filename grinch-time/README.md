# Grinch · Fotos do time

Gera a arte do Grinch segurando a bola de Natal com a foto de cada pessoa do time.

## App no navegador

```bash
cd grinch-time
python3 -m http.server 8765
```

Abra <http://127.0.0.1:8765>, arraste as fotos, ajuste zoom/posição do rosto (arrastar na prévia) e baixe PNG ou ZIP.

## CLI

```bash
python3 gerar.py caminho/para/fotos/*.jpg -o saida/
python3 gerar.py ana.jpg --nome Ana -o saida/
```

## Assets

| Arquivo | Função |
|---------|--------|
| `assets/template.png` | Grinch + aro vermelho, centro transparente |
| `assets/gloss_overlay.png` | Brilho da bola por cima da foto |
| `assets/meta.json` | Centro e raio do círculo |

## Artes geradas

As PNGs do time ficam em `grinch-time/artes/` (também tem o ZIP `grinch-time.zip` nessa pasta).

Uso interno do time, a partir da arte de referência fornecida.
