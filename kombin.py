"""A3: aynada kombin fotoğrafı -> ayrı parçalar.

SegFormer (Fashionpedia, 46 sınıf) her pikseli bir giysiye ya da giysi parçasına
(kol, kapüşon, yaka, fermuar, cep...) ayırır. Parçalar ait oldukları giysiye eklenir:
kol ve kapüşon varsa dış giyime (ceket, mont), yoksa üste; cep, yaka gibileri değdiği
giysiye. Kişi küçük görünüyorsa önce kişinin çevresi kırpılıp ikinci kez bakılır.
Renkler piksellerden hesaplanır (model renkte yanılıyordu ve her parçaya ayrı model
çağrısı ~60 sn sürer).
"""
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

MODEL = "sayeed99/segformer-b3-fashion"

# sınıf -> (yuva, Türkçe ipucu)
GIYSI = {
    1: ("ust", "gömlek"), 2: ("ust", "tişört / sweatshirt"), 3: ("ust", "kazak"),
    4: ("dis_giyim", "hırka"), 5: ("dis_giyim", "ceket"), 6: ("dis_giyim", "yelek"),
    7: ("alt", "pantolon"), 8: ("alt", "şort"), 9: ("alt", "etek"),
    10: ("dis_giyim", "kaban / mont"), 11: ("tek_parca", "elbise"), 12: ("tek_parca", "tulum"),
    13: ("dis_giyim", "pelerin"), 14: ("aksesuar", "gözlük"), 15: ("aksesuar", "şapka"),
    16: ("aksesuar", "saç aksesuarı"), 17: ("aksesuar", "kravat"), 18: ("aksesuar", "eldiven"),
    19: ("aksesuar", "saat"), 20: ("aksesuar", "kemer"), 22: ("alt", "külotlu çorap"),
    24: ("ayakkabi", "ayakkabı"), 25: ("aksesuar", "çanta"), 26: ("aksesuar", "atkı"),
}
KOLLU_DIS = {4, 5, 10, 13}          # kol ve kapüşon bunlara gider (yelek kolsuz)
UST_KAT = {1, 2, 3, 11, 12}
DIS_PARCA = {28, 30, 31, 32, 36}   # kapüşon, klapa, apolet, kol, fermuar
KUCUK = {14, 15, 16, 17, 18, 19, 20, 25, 26}

_model = None


def _yukle():
    global _model
    if _model is None:
        import torch
        from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
        torch.set_num_threads(4)
        _model = (AutoImageProcessor.from_pretrained(MODEL),
                  AutoModelForSemanticSegmentation.from_pretrained(MODEL).eval())
    return _model


def _etiketle(im: Image.Image) -> np.ndarray:
    import torch
    pr, m = _yukle()
    with torch.no_grad():
        lo = m(**pr(images=im, return_tensors="pt")).logits
    return torch.nn.functional.interpolate(lo, size=im.size[::-1], mode="bilinear").argmax(1)[0].numpy().astype(np.uint8)


def _parcalari_bagla(et: np.ndarray) -> np.ndarray:
    """Kol, yaka, cep gibi sınıfları ait oldukları giysinin sınıfına çevirir."""
    sonuc = np.where(np.isin(et, list(GIYSI)), et, 0).astype(np.uint8)
    var = set(np.unique(sonuc)) - {0}
    for sinif in set(np.unique(et)) - set(GIYSI) - {0, 21, 23, 27}:
        bilesen, n = ndimage.label(et == sinif)
        for i in range(1, n + 1):
            b = bilesen == i
            halka = ndimage.binary_dilation(b, iterations=9) & ~b
            komsu = sonuc[halka]
            if sinif in DIS_PARCA and var & KOLLU_DIS:
                izin = var & KOLLU_DIS
            elif sinif in DIS_PARCA:
                izin = var & UST_KAT or var & {6}
            else:
                izin = var - KUCUK
            if not izin:
                continue
            say = {s: int((komsu == s).sum()) for s in izin}
            hedef = max(say, key=say.get)
            if say[hedef] == 0:  # hiçbir şeye değmiyor: tek aday varsa ona ver
                if len(izin) != 1:
                    continue
                hedef = next(iter(izin))
            sonuc[b] = hedef
    return sonuc


def _temizle(maske: np.ndarray) -> np.ndarray:
    """Ufak lekeleri at, büyük parçaları tut (ayakkabının iki teki kalsın)."""
    bilesen, n = ndimage.label(maske)
    if n <= 1:
        return maske
    boy = ndimage.sum(maske, bilesen, range(1, n + 1))
    tut = [i + 1 for i, s in enumerate(boy) if s >= 0.15 * boy.max()]
    return np.isin(bilesen, tut)


def ayir(im: Image.Image) -> tuple[Image.Image, list[dict]]:
    """Kişinin kırpılmış fotoğrafını ve bulunan parçaları döndürür.
    Her parça: {sinif, yuva, ipucu, resim (RGBA), maske_payi}"""
    im = im.convert("RGB")
    et = _etiketle(im)
    ys, xs = np.nonzero(et)
    if len(xs) == 0:
        return im, []
    W, H = im.size
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    pay = int(0.08 * max(x1 - x0, y1 - y0))
    kutu = (max(0, x0 - pay), max(0, y0 - pay), min(W, x1 + pay), min(H, y1 + pay))
    if (kutu[2] - kutu[0]) * (kutu[3] - kutu[1]) < 0.8 * W * H:
        im = im.crop(kutu)
        et = _etiketle(im)
    bag = _parcalari_bagla(et)
    alan = bag.size
    parcalar = []
    for sinif in sorted(set(np.unique(bag)) - {0}):
        m = _temizle(bag == sinif)
        oran = m.sum() / alan
        if oran < (0.0008 if sinif in KUCUK else 0.004):
            continue
        ys, xs = np.nonzero(m)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        p = int(0.04 * max(x1 - x0, y1 - y0)) + 2
        k = (max(0, x0 - p), max(0, y0 - p), min(im.width, x1 + p + 1), min(im.height, y1 + p + 1))
        # kenardan bir piksel içeri: arka plan rengi kenarda hale yapmasın
        ic = ndimage.binary_erosion(m, iterations=1)
        alfa = Image.fromarray((ic * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
        rgba = im.crop(k).convert("RGBA")
        rgba.putalpha(alfa.crop(k))
        yuva, ipucu = GIYSI[sinif]
        parcalar.append({"sinif": int(sinif), "yuva": yuva, "ipucu": ipucu, "resim": rgba, "oran": float(oran)})
    # okunma sırası: yukarıdan aşağı (şapka, dış giyim, üst, alt, ayakkabı)
    sira = {"aksesuar": 0, "dis_giyim": 1, "tek_parca": 2, "ust": 2, "alt": 3, "ayakkabi": 4}
    parcalar.sort(key=lambda d: (sira[d["yuva"]], -d["oran"]))
    return im, parcalar
