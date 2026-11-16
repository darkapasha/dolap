"""Bir parçanın türünden ve renginden temiz bir SVG çizimi üretir.

Kombin fotoğrafından kesilen parçalar bulanık ve kırpık oluyor; dolapta ve kolajda
bunun yerine bu çizim gösterilir. 200x200'lük düz, önden görünüşlü bir illüstrasyon.
"""
import hashlib
import json
from html import escape

from renk import RENKLER

_VARSAYILAN = (150, 150, 150)
SURUM = 1  # kalıplar değişince artır: çizim adresleri değişir, telefon önbelleği yenilenir


def anahtar(p: dict) -> str:
    """Çizimi etkileyen alanların kısa özeti (adres önbelleği için)."""
    alan = [SURUM, p.get("tur"), p.get("ad"), p.get("yuva"), p.get("desen"), p.get("renkler"), p.get("isim")]
    return hashlib.md5(json.dumps(alan, ensure_ascii=False).encode()).hexdigest()[:10]


def kucuk(s: str) -> str:
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def renk_rgb(ad: str) -> tuple[int, int, int] | None:
    a = kucuk(ad).strip()
    if a in RENKLER:
        return RENKLER[a]
    # "koyu lacivert", "lacivert-beyaz" gibi: içinde geçen en uzun renk adı
    adaylar = [k for k in RENKLER if k in a]
    return RENKLER[max(adaylar, key=len)] if adaylar else None


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in c)


def _karis(c, hedef, t):
    return tuple(a + (b - a) * t for a, b in zip(c, hedef))


def _parlak(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


# --- kalıplar -----------------------------------------------------------
# Her kalıp: (gövde yolları, ayrıntı çizen işlev). Ayrıntılar R (renk sözlüğü) alır.

TISORT = ("M72 28 C84 36 116 36 128 28 L162 42 C170 46 178 60 186 78 L162 92 L150 76 L150 176 "
          "C120 180 80 180 50 176 L50 76 L38 92 L14 78 C22 60 30 46 38 42 Z")
UZUN = ("M72 28 C84 36 116 36 128 28 L160 40 C172 46 178 62 180 84 L188 162 L166 166 L156 96 L150 80 "
        "L150 172 L50 172 L50 80 L44 96 L34 166 L12 162 L20 84 C22 62 28 46 40 40 Z")
UZUN_ETEK = ("M72 24 C84 32 116 32 128 24 L160 36 C172 42 178 58 180 80 L188 160 L166 164 L156 94 L152 80 "
             "L154 190 L46 190 L48 80 L44 94 L34 164 L12 160 L20 80 C22 58 28 42 40 36 Z")
YELEK = "M72 28 C84 36 116 36 128 28 L146 36 C144 56 148 70 152 80 L152 174 L48 174 L48 80 C52 70 56 56 54 36 Z"
PANTOLON = "M54 34 L146 34 L152 186 L110 186 L100 82 L90 186 L48 186 Z"
ESOFMAN = "M54 34 L146 34 L146 176 L110 176 L100 82 L90 176 L54 176 Z"
TAYT = "M58 34 L142 34 L136 186 L108 186 L100 84 L92 186 L64 186 Z"
SORT = "M54 34 L146 34 L158 114 L108 118 L100 74 L92 118 L42 114 Z"
BEL = "M54 20 L146 20 L146 34 L54 34 Z"
ETEK = "M62 30 L138 30 L164 168 C120 178 80 178 36 168 Z"
ELBISE = ("M78 22 C88 30 112 30 122 22 L126 72 C140 110 156 150 166 182 C122 190 78 190 34 182 "
          "C44 150 60 110 74 72 Z")
SPOR = "M24 134 C20 106 34 86 58 82 L90 78 C102 94 124 102 150 106 C174 110 184 120 184 134 Z"
BOT = "M44 134 L44 42 C60 38 80 38 96 42 L98 92 C130 100 170 106 182 134 Z"
TABAN = "M18 134 L188 134 C192 134 192 152 182 152 L24 152 C14 152 12 134 18 134 Z"


def _cizgi(d, c, w=1.6, ek=""):
    return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" {ek}/>'


def _dikis(d, c):
    return _cizgi(d, c, 1.3, 'stroke-dasharray="3 3" opacity=".8"')


def _uzun_ayrinti(R, ribanali=True):
    s = R["kenar"]
    o = _cizgi("M50 80 C50 64 46 50 40 40", s, 1.2) + _cizgi("M150 80 C150 64 154 50 160 40", s, 1.2)
    if ribanali:
        o += f'<path d="M50 160 L150 160 L150 172 L50 172 Z" fill="{R["koyu"]}"/>'
        o += f'<path d="M14 150 L35 153 L34 166 L12 162 Z M186 150 L165 153 L166 166 L188 162 Z" fill="{R["koyu"]}"/>'
    return o


def _kapusonlu(R, fermuar):
    s, k = R["kenar"], R["koyu"]
    o = (f'<path d="M64 36 C54 10 78 2 100 2 C122 2 146 10 136 36 L126 31 C114 42 86 42 74 31 Z" fill="{R["ana"]}" stroke="{s}" stroke-width="1.6"/>'
         f'<path d="M76 31 C78 14 122 14 124 31 C112 40 88 40 76 31 Z" fill="{R["ic"]}"/>')
    o += _uzun_ayrinti(R)
    o += _cizgi("M91 39 L89 70", R["ip"], 2.2) + _cizgi("M109 39 L111 70", R["ip"], 2.2)
    if fermuar:
        o += _cizgi("M100 38 L100 172", k, 3) + _cizgi("M100 38 L100 172", s, 1, 'stroke-dasharray="1.5 2.5"')
        o += _cizgi("M94 120 L64 120 L56 158", s, 1.6) + _cizgi("M106 120 L136 120 L144 158", s, 1.6)
    else:
        o += _cizgi("M66 118 L134 118 L144 158 L56 158 Z", s, 1.6)
    return o


def _forma(R):
    v = R["vurgu"]
    o = _cizgi("M80 30 L100 54 L120 30", v, 6) + _cizgi("M162 92 L186 78", v, 6) + _cizgi("M38 92 L14 78", v, 6)
    o += _cizgi("M50 76 L50 176", v, 3, 'opacity=".55"') + _cizgi("M150 76 L150 176", v, 3, 'opacity=".55"')
    o += (f'<path d="M116 62 L132 62 L132 74 C132 80 124 84 124 84 C124 84 116 80 116 74 Z" fill="{v}"/>'
          f'<path d="M70 66 L84 62" stroke="{v}" stroke-width="3" stroke-linecap="round"/>')
    return o


def _polo(R):
    s = R["kenar"]
    o = (f'<path d="M72 28 L86 52 L100 36 Z M128 28 L114 52 L100 36 Z" fill="{R["acik"]}" stroke="{s}" stroke-width="1.6" stroke-linejoin="round"/>')
    o += _cizgi("M100 36 L100 72", s, 1.4) + _cizgi("M94 36 L94 72 L106 72 L106 36", s, 1.2)
    o += f'<circle cx="100" cy="50" r="2.2" fill="{s}"/><circle cx="100" cy="63" r="2.2" fill="{s}"/>'
    return o


def _gomlek(R):
    s = R["kenar"]
    o = _uzun_ayrinti(R, ribanali=False)
    o += _cizgi("M100 40 L100 172", s, 1.4)
    o += "".join(f'<circle cx="104" cy="{y}" r="2.2" fill="{s}"/>' for y in (54, 80, 106, 132, 158))
    o += f'<path d="M72 28 L86 54 L100 38 Z M128 28 L114 54 L100 38 Z" fill="{R["acik"]}" stroke="{s}" stroke-width="1.6" stroke-linejoin="round"/>'
    o += _cizgi("M64 70 L84 70 L84 92 L64 92 Z", s, 1.3)
    o += _cizgi("M188 162 L166 166 L165 154 L187 150", s, 1.3) + _cizgi("M12 162 L34 166 L35 154 L13 150", s, 1.3)
    return o


def _ceket(R, tur):
    s, k = R["kenar"], R["koyu"]
    o = _uzun_ayrinti(R, ribanali=False)
    if tur == "mont":
        o += "".join(_cizgi(f"M50 {y} L150 {y}", s, 1.2, 'opacity=".7"') for y in (66, 92, 118, 144))
        o += "".join(_cizgi(f"M{x1} {y} L{x2} {y + 2}", s, 1.2, 'opacity=".7"') for x1, x2, y in ((24, 44, 104), (21, 44, 130), (176, 156, 104), (179, 156, 130)))
        o += f'<path d="M74 22 C84 30 116 30 126 22 L128 38 C116 44 84 44 72 38 Z" fill="{R["ana"]}" stroke="{s}" stroke-width="1.6"/>'
        o += _cizgi("M100 42 L100 172", k, 3)
        o += f'<path d="M50 162 L150 162 L150 172 L50 172 Z" fill="{k}"/>'
        return o
    alt = 190 if tur == "kaban" else 172
    o += f'<path d="M84 30 L100 84 L116 30 C110 34 90 34 84 30 Z" fill="{R["gomlek"]}"/>'
    o += (f'<path d="M84 30 L72 34 L76 62 L86 70 L100 96 Z M116 30 L128 34 L124 62 L114 70 L100 96 Z" '
          f'fill="{R["acik"]}" stroke="{s}" stroke-width="1.5" stroke-linejoin="round"/>')
    o += _cizgi(f"M100 96 L100 {alt}", s, 1.4)
    dugme = (112, 136) if tur == "kaban" else (118, 140)
    for y in dugme:
        o += f'<circle cx="108" cy="{y}" r="3" fill="{k}" stroke="{s}" stroke-width="1"/>'
        if tur == "kaban":
            o += f'<circle cx="92" cy="{y}" r="3" fill="{k}" stroke="{s}" stroke-width="1"/>'
    o += _cizgi("M60 132 L84 130", s, 1.4) + _cizgi("M116 130 L140 132", s, 1.4)
    if tur != "kaban":
        o += _cizgi("M116 72 L136 70", s, 1.3)
    return o


def _hirka(R):
    s, k = R["kenar"], R["koyu"]
    o = _uzun_ayrinti(R)
    o += f'<path d="M80 30 L100 92 L120 30 C112 34 88 34 80 30 Z" fill="{R["gomlek"]}"/>'
    o += _cizgi("M80 30 L100 92 L120 30", k, 5)
    o += _cizgi("M100 92 L100 172", k, 4)
    o += "".join(f'<circle cx="100" cy="{y}" r="2.4" fill="{R["acik"]}"/>' for y in (104, 124, 144))
    return o


def _kazak(R):
    o = _uzun_ayrinti(R)
    o += _cizgi("M72 28 C84 40 116 40 128 28", R["koyu"], 5)
    for x in (72, 100, 128):
        o += _cizgi(f"M{x} 50 C{x - 6} 60 {x + 6} 70 {x} 80 C{x - 6} 90 {x + 6} 100 {x} 110 C{x - 6} 120 {x + 6} 130 {x} 140 "
                    f"C{x - 6} 150 {x + 6} 156 {x} 158", R["kenar"], 1.3, 'opacity=".55"')
    return o


def _pantolon(R, tur):
    s, k = R["kenar"], R["koyu"]
    o = f'<path d="{BEL}" fill="{R["ana"]}" stroke="{s}" stroke-width="1.6" stroke-linejoin="round"/>'
    if tur == "esofman":
        o = f'<path d="{BEL}" fill="{k}" stroke="{s}" stroke-width="1.6"/>'
        o += _cizgi("M96 26 L92 46", R["ip"], 2) + _cizgi("M104 26 L108 46", R["ip"], 2)
        o += f'<path d="M56 168 L90 168 L90 176 L56 176 Z M110 168 L146 168 L146 176 L110 176 Z" fill="{k}"/>'
        o += _cizgi("M54 40 L56 166", R["vurgu"], 4) + _cizgi("M146 40 L144 166", R["vurgu"], 4)
        return o
    o += _cizgi("M100 34 C100 52 98 62 94 74", s, 1.4)
    o += _cizgi("M58 42 C70 44 78 40 80 34", s, 1.4) + _cizgi("M142 42 C130 44 122 40 120 34", s, 1.4)
    for x in (66, 100, 134):
        o += f'<path d="M{x - 2} 18 L{x + 2} 18 L{x + 2} 36 L{x - 2} 36 Z" fill="{k}"/>'
    if tur == "kot":
        ip = R["kotip"]
        o += _dikis("M60 46 C72 48 80 44 84 34", ip) + _dikis("M140 46 C128 48 120 44 116 34", ip)
        o += _dikis("M96 36 C96 52 94 62 90 72", ip) + _dikis("M56 22 L144 22", ip)
        o += _dikis("M52 180 L88 180", ip) + _dikis("M112 180 L148 180", ip)
    if tur == "kargo":
        o += _cizgi("M48 100 L66 100 L66 128 L50 128", s, 1.5) + _cizgi("M152 100 L134 100 L134 128 L150 128", s, 1.5)
        o += _cizgi("M48 108 L66 108", s, 1.2) + _cizgi("M152 108 L134 108", s, 1.2)
    return o


def _ayakkabi(R, tur):
    s = R["kenar"]
    if tur == "bot":
        o = _cizgi("M96 50 L72 50 M97 62 L73 62 M98 74 L74 74 M98 86 L76 86", R["ip"], 2.4)
        o += _cizgi("M44 46 C60 42 80 42 96 46", s, 1.4) + _cizgi("M98 92 C110 100 126 104 140 106", s, 1.3)
        return o
    o = _cizgi("M58 82 C64 74 82 72 90 78", s, 1.8)
    o += "".join(_cizgi(f"M{94 + i * 7} {84 + i * 5} L{80 + i * 7} {96 + i * 4}", R["ip"], 2.4) for i in range(4))
    o += _cizgi("M150 106 C162 112 168 124 166 134", s, 1.3)
    o += _cizgi("M54 120 C80 114 110 118 136 128", R["vurgu"], 3.2)
    return o


def _aksesuar(R, tur):
    s, k, a = R["kenar"], R["koyu"], R["ana"]
    if tur == "sapka":
        return (f'<path d="M46 120 C46 66 154 66 154 120 Z" fill="{a}" stroke="{s}" stroke-width="1.6"/>'
                f'<path d="M100 120 C130 120 172 124 186 134 C170 142 120 140 100 132 Z" fill="{k}" stroke="{s}" stroke-width="1.6"/>'
                f'<circle cx="100" cy="72" r="4" fill="{k}"/>' + _cizgi("M100 76 L100 120", s, 1.2))
    if tur == "bere":
        return (f'<path d="M48 136 C40 50 160 50 152 136 Z" fill="{a}" stroke="{s}" stroke-width="1.6"/>'
                f'<path d="M44 124 L156 124 L156 146 L44 146 Z" fill="{k}" stroke="{s}" stroke-width="1.6"/>'
                f'<circle cx="100" cy="50" r="14" fill="{R["acik"]}" stroke="{s}" stroke-width="1.4"/>')
    if tur == "kemer":
        return (f'<path d="M14 92 L186 92 L186 112 L14 112 Z" fill="{a}" stroke="{s}" stroke-width="1.6"/>'
                f'<path d="M126 84 L156 84 L156 120 L126 120 Z" fill="none" stroke="#b9b2a4" stroke-width="5"/>'
                + _cizgi("M132 102 L150 102", "#b9b2a4", 4))
    return (f'<path d="M70 74 C70 36 130 36 130 74" fill="none" stroke="{k}" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M40 72 L160 72 L168 170 L32 170 Z" fill="{a}" stroke="{s}" stroke-width="1.6" stroke-linejoin="round"/>'
            + _cizgi("M40 92 L160 92", s, 1.3) + f'<rect x="92" y="86" width="16" height="12" rx="2" fill="{k}"/>')


# tür anahtarı -> (gövde yolları, ayrıntı(R))
KALIPLAR = {
    "tisort": ([TISORT], lambda R: _cizgi("M72 28 C84 44 116 44 128 28", R["koyu"], 5)
               + _cizgi("M50 76 C50 64 52 52 54 40", R["kenar"], 1.2) + _cizgi("M150 76 C150 64 148 52 146 40", R["kenar"], 1.2)),
    "forma": ([TISORT], _forma),
    "polo": ([TISORT], _polo),
    "gomlek": ([UZUN], _gomlek),
    "sweat": ([UZUN], lambda R: _uzun_ayrinti(R) + _cizgi("M72 28 C84 40 116 40 128 28", R["koyu"], 5)),
    "kazak": ([UZUN], _kazak),
    "kapusonlu": ([UZUN], lambda R: _kapusonlu(R, False)),
    "kapusonlu_fermuarli": ([UZUN], lambda R: _kapusonlu(R, True)),
    "ceket": ([UZUN], lambda R: _ceket(R, "ceket")),
    "kaban": ([UZUN_ETEK], lambda R: _ceket(R, "kaban")),
    "mont": ([UZUN], lambda R: _ceket(R, "mont")),
    "hirka": ([UZUN], _hirka),
    "yelek": ([YELEK], lambda R: _cizgi("M100 34 L100 174", R["koyu"], 3)),
    "pantolon": ([PANTOLON], lambda R: _pantolon(R, "pantolon")),
    "kot": ([PANTOLON], lambda R: _pantolon(R, "kot")),
    "kargo": ([PANTOLON], lambda R: _pantolon(R, "kargo")),
    "esofman": ([ESOFMAN], lambda R: _pantolon(R, "esofman")),
    "tayt": ([TAYT], lambda R: _cizgi("M58 40 L142 40", R["kenar"], 1.2)),
    "sort": ([SORT], lambda R: _pantolon(R, "sort")),
    "etek": ([ETEK], lambda R: f'<path d="M62 30 L138 30 L140 42 L60 42 Z" fill="{R["koyu"]}"/>'),
    "elbise": ([ELBISE], lambda R: _cizgi("M78 22 C88 34 112 34 122 22", R["koyu"], 4) + _cizgi("M74 72 C90 78 110 78 126 72", R["kenar"], 1.4)),
    "spor": ([SPOR], lambda R: _ayakkabi(R, "spor")),
    "bot": ([BOT], lambda R: _ayakkabi(R, "bot")),
    "sapka": ([], lambda R: _aksesuar(R, "sapka")),
    "bere": ([], lambda R: _aksesuar(R, "bere")),
    "kemer": ([], lambda R: _aksesuar(R, "kemer")),
    "canta": ([], lambda R: _aksesuar(R, "canta")),
}

# sıra önemli: önce özel türler, en sonda genel kelimeler
_KELIMELER = [
    ("forma", ["forma", "jersey"]), ("polo", ["polo"]), ("gomlek", ["gömlek"]),
    ("kapusonlu", ["kapüşon", "kapşon", "hoodie"]),
    ("mont", ["mont", "parka", "şişme", "puffer"]), ("kaban", ["kaban", "palto", "trençkot", "trenchcoat"]),
    ("ceket", ["ceket", "blazer"]), ("hirka", ["hırka"]), ("yelek", ["yelek"]),
    ("elbise", ["elbise"]), ("etek", ["etek"]), ("sort", ["şort", "bermuda"]),
    ("esofman", ["eşofman", "jogger"]), ("kargo", ["kargo"]), ("tayt", ["tayt", "legging"]),
    ("kot", ["kot", "jean", "denim"]), ("pantolon", ["pantolon", "chino"]),
    ("bot", ["bot", "çizme"]), ("spor", ["ayakkabı", "sneaker", "terlik", "sandalet", "mokasen", "loafer"]),
    ("sapka", ["şapka", "kep"]), ("bere", ["bere"]), ("kemer", ["kemer"]), ("canta", ["çanta"]),
    ("kazak", ["kazak", "triko", "balıkçı"]), ("sweat", ["sweat", "uzun kollu"]),
    ("tisort", ["tişört", "t-shirt", "tshirt", "atlet", "crop", "body"]),
]
_YUVA_KALIP = {"ust": "tisort", "alt": "pantolon", "dis_giyim": "ceket", "tek_parca": "elbise",
               "ayakkabi": "spor", "aksesuar": "canta"}


def kalip_bul(p: dict) -> str:
    # tür ve açıklama birlikte: "kapüşonlu tişört" türü tişört olsa da kapüşonlu çizilir
    metin = kucuk((p.get("tur") or "") + " " + (p.get("ad") or ""))
    for kalip, kelimeler in _KELIMELER:
        if any(k in metin for k in kelimeler):
            if kalip == "kapusonlu" and any(k in metin for k in ("fermuar", "zip")):
                return "kapusonlu_fermuarli"
            return kalip
    return _YUVA_KALIP.get(p.get("yuva") or "", "tisort")


def _renkler(p: dict, kalip: str) -> dict:
    adlar = [a for a in (p.get("renkler") or []) if isinstance(a, str)]
    rgb = [c for c in (renk_rgb(a) for a in adlar) if c]
    ana = rgb[0] if rgb else _VARSAYILAN
    if kalip == "kot" and not rgb:
        ana = RENKLER.get("kot mavisi", (72, 100, 138))
    karanlik = _parlak(ana) < 70
    kenar = _karis(ana, (255, 255, 255), 0.28) if karanlik else _karis(ana, (0, 0, 0), 0.38)
    koyu = _karis(ana, (255, 255, 255), 0.12) if karanlik else _karis(ana, (0, 0, 0), 0.18)
    acik = _karis(ana, (255, 255, 255), 0.18)
    ikinci = next((c for c in rgb[1:] if abs(_parlak(c) - _parlak(ana)) > 30), None)
    vurgu = ikinci or ((235, 235, 232) if karanlik or _parlak(ana) < 150 else _karis(ana, (0, 0, 0), 0.45))
    return {
        "ana": _hex(ana), "kenar": _hex(kenar), "koyu": _hex(koyu), "acik": _hex(acik), "vurgu": _hex(vurgu),
        "ic": _hex(_karis(ana, (0, 0, 0), 0.4)), "ip": _hex(vurgu if ikinci else _karis(ana, (255, 255, 255), 0.55)),
        "gomlek": "#f3f1ec" if not karanlik else "#2b2b2e",
        "kotip": "#d9a441",
        "taban": _hex(ikinci or ((244, 242, 238) if _parlak(ana) < 200 else (60, 60, 64))),
    }


def _desen(desen: str, R: dict) -> tuple[str, str]:
    d = kucuk(desen)
    v = R["vurgu"]
    if "çizgi" in d:
        return (f'<pattern id="d" width="12" height="12" patternUnits="userSpaceOnUse">'
                f'<rect width="12" height="5" fill="{v}" opacity=".75"/></pattern>'), "url(#d)"
    if "kare" in d or "ekose" in d:
        return (f'<pattern id="d" width="22" height="22" patternUnits="userSpaceOnUse">'
                f'<rect width="22" height="6" fill="{v}" opacity=".45"/><rect width="6" height="22" fill="{v}" opacity=".45"/></pattern>'), "url(#d)"
    if "çiçek" in d or "puan" in d or "nokta" in d:
        return (f'<pattern id="d" width="16" height="16" patternUnits="userSpaceOnUse">'
                f'<circle cx="4" cy="4" r="2.6" fill="{v}"/><circle cx="12" cy="12" r="2.6" fill="{v}"/></pattern>'), "url(#d)"
    return "", ""


def svg(p: dict) -> str:
    kalip = kalip_bul(p)
    R = _renkler(p, kalip)
    yollar, ayrinti = KALIPLAR[kalip]
    tanim, desen_dolgu = _desen(p.get("desen") or "", R)
    parca = []
    if kalip in ("spor", "bot"):
        parca.append(f'<path d="{TABAN}" fill="{R["taban"]}" stroke="{R["kenar"]}" stroke-width="1.6"/>')
    for d in yollar:
        parca.append(f'<path d="{d}" fill="{R["ana"]}" stroke="{R["kenar"]}" stroke-width="1.8" stroke-linejoin="round"/>')
        if desen_dolgu:
            parca.append(f'<path d="{d}" fill="{desen_dolgu}"/>')
    parca.append(ayrinti(R))
    yazili = kucuk(p.get("desen") or "")
    if kalip in ("tisort", "sweat", "kapusonlu", "kazak") and any(k in yazili for k in ("baskı", "logo", "yazı")):
        parca.append(f'<rect x="80" y="70" width="40" height="26" rx="4" fill="{R["vurgu"]}" opacity=".85"/>')
    baslik = escape(p.get("isim") or p.get("ad") or kalip)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
            f'<title>{baslik}</title><defs>{tanim}</defs>'
            '<ellipse cx="100" cy="194" rx="70" ry="4" fill="#000" opacity=".08"/>'
            + "".join(parca) + "</svg>")
