"""Dolap ikonlarını üretir (askı çizimi). Kurulumda bir kez çalışır."""
from pathlib import Path
from PIL import Image, ImageDraw

WEB = Path(__file__).resolve().parent / "web"
ARKA = (181, 83, 47)      # vurgu rengi
ON = (255, 248, 240)


def ciz(boyut: int) -> Image.Image:
    s = 4  # yumuşak kenar için büyük çiz, sonra küçült
    B = boyut * s
    im = Image.new("RGB", (B, B), ARKA)
    d = ImageDraw.Draw(im)
    w = int(B * 0.045)
    cx = B / 2
    # kanca
    r = B * 0.075
    d.arc([cx - r, B * 0.22, cx + r, B * 0.22 + 2 * r], start=180, end=90, fill=ON, width=w)
    boyun_y = B * 0.22 + 2 * r
    d.line([cx, B * 0.22 + r * 2 - 1, cx, B * 0.42], fill=ON, width=w)
    # omuzlar
    sol, sag, alt = (B * 0.18, B * 0.70), (B * 0.82, B * 0.70), B * 0.70
    tepe = (cx, B * 0.42)
    d.line([tepe, sol], fill=ON, width=w, joint="curve")
    d.line([tepe, sag], fill=ON, width=w, joint="curve")
    d.line([sol, sag], fill=ON, width=w)
    for p in (sol, sag, tepe):
        d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=ON)
    return im.resize((boyut, boyut), Image.LANCZOS)


for ad, b in (("ikon-192.png", 192), ("ikon-512.png", 512), ("apple-touch-icon.png", 180)):
    ciz(b).save(WEB / ad)
print("ikonlar tamam")
