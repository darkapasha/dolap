"""Bir parçanın baskın renklerini piksellerden Türkçe adlarla bulur."""
from PIL import Image

RENKLER = {
    "siyah": (22, 22, 24), "koyu gri": (62, 62, 66), "gri": (125, 125, 128), "açık gri": (190, 190, 192),
    "beyaz": (243, 243, 240), "krem": (238, 228, 200), "bej": (212, 190, 158), "taba": (176, 118, 66),
    "kahverengi": (100, 64, 40), "haki": (112, 112, 72), "yeşil": (46, 128, 64), "koyu yeşil": (32, 68, 46),
    "mint": (160, 215, 190), "lacivert": (28, 36, 72), "mavi": (44, 92, 186), "açık mavi": (150, 188, 228),
    "kot mavisi": (72, 100, 138), "turkuaz": (40, 170, 175), "mor": (104, 52, 136), "lila": (190, 160, 214),
    "pembe": (234, 146, 176), "fuşya": (204, 40, 120), "kırmızı": (192, 32, 40), "bordo": (106, 24, 38),
    "turuncu": (234, 120, 34), "hardal": (196, 154, 40), "sarı": (240, 210, 50),
}
_adlar = list(RENKLER)
_lab = None


def bul(rgba: Image.Image, en_fazla: int = 3) -> list[str]:
    # numpy/skimage burada yüklenir: cizim.py yalnızca RENKLER tablosunu ister
    global _lab
    import numpy as np
    from skimage.color import rgb2lab
    if _lab is None:
        _lab = rgb2lab(np.array([RENKLER[a] for a in _adlar], dtype=np.float64)[None] / 255.0)[0]
    a = np.asarray(rgba.convert("RGBA"))
    px = a[a[..., 3] > 200][:, :3]
    if len(px) < 50:
        return []
    rng = np.random.default_rng(0)
    if len(px) > 15000:
        px = px[rng.choice(len(px), 15000, replace=False)]
    lab = rgb2lab(px[None].astype(np.float64) / 255.0)[0]
    # basit k-ortalama (k=4)
    merkez = lab[rng.choice(len(lab), 4, replace=False)]
    for _ in range(12):
        d = ((lab[:, None] - merkez[None]) ** 2).sum(-1)
        grup = d.argmin(1)
        merkez = np.array([lab[grup == i].mean(0) if (grup == i).any() else merkez[i] for i in range(4)])
    pay = np.bincount(grup, minlength=4) / len(lab)
    sonuc: dict[str, float] = {}
    for i in np.argsort(-pay):
        if pay[i] < 0.15:
            continue
        ad = _adlar[int(((_lab - merkez[i]) ** 2).sum(-1).argmin())]
        sonuc[ad] = sonuc.get(ad, 0) + pay[i]
    return [a for a, _ in sorted(sonuc.items(), key=lambda x: -x[1])][:en_fazla]
