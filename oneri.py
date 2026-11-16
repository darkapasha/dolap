"""A4-A6: hava + kurallar + öğrenme ile günün 3 kombini, giyim geçmişi, kirli takibi.

Aday üretimi ve puanlama tamamen kural tabanlı (milisaniyeler sürer); böylece sabah
ortamı değiştirince ya da "başka öner" deyince anında yeni kombin gelir.
"""
import itertools
import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
KALIN = {"ince": 1, "orta": 2, "kalin": 3}
ORTAMLAR = {  # ad, hedef resmiyet
    "gunluk": ("Günlük", 2.0), "is": ("İş / okul", 3.2), "spor": ("Spor", 1.0),
    "ev": ("Evde", 1.0), "ozel": ("Özel gün", 4.3),
}
NOTR = {"siyah", "beyaz", "gri", "koyu gri", "açık gri", "lacivert", "bej", "krem", "kahverengi",
        "taba", "haki", "kot mavisi", "antrasit"}
HAVA_KOD = {0: "açık", 1: "az bulutlu", 2: "parçalı bulutlu", 3: "kapalı", 45: "sisli", 48: "sisli",
            51: "çiseleme", 53: "çiseleme", 55: "çiseleme", 61: "yağmurlu", 63: "yağmurlu", 65: "sağanak",
            66: "dondurucu yağmur", 67: "dondurucu yağmur", 71: "kar", 73: "kar", 75: "yoğun kar", 77: "kar",
            80: "sağanak", 81: "sağanak", 82: "şiddetli sağanak", 85: "kar sağanağı", 86: "kar sağanağı",
            95: "fırtına", 96: "dolu", 99: "dolu"}
SU_GECIRMEZ = ["yağmurluk", "mont", "parka", "trençkot", "kaban", "palto", "şişme", "rüzgarlık"]
YAGMUR_KOTU = ["kanvas", "süet", "sandalet", "terlik", "babet"]
# Kaç giyimde kirliye düşer (0 = hiç, elle işaretlenir)
_KIRLI_KURAL = [
    (0, ["mont", "ceket", "kaban", "palto", "yağmurluk", "parka", "trençkot", "yelek", "blazer",
         "ayakkabı", "ayakkabi", "bot", "çizme", "sneaker", "terlik", "sandalet", "çanta", "şapka",
         "bere", "kemer", "atkı", "eldiven", "saat", "gözlük"]),
    (4, ["kot", "jean"]),
    (3, ["hırka", "kazak", "sweat", "kapüşonlu", "triko", "pantolon", "etek", "eşofman", "jogger", "chino", "kargo"]),
    (2, ["elbise", "tulum", "gömlek"]),
    (1, ["tişört", "t-shirt", "atlet", "polo", "forma", "body", "tayt", "şort", "crop", "bluz"]),
]
VARSAYILAN_KIRLI = {"ust": 1, "alt": 3, "tek_parca": 2, "dis_giyim": 0, "ayakkabi": 0, "aksesuar": 0}


def bugun() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def kirli_siniri(p: dict) -> int:
    t = (p.get("tur") or "").lower() + " " + (p.get("ad") or "").lower()
    for n, kelimeler in _KIRLI_KURAL:
        if any(k in t for k in kelimeler):
            return n
    return VARSAYILAN_KIRLI.get(p.get("yuva"), 1)


def mevsim(gun: date) -> str:
    return {12: "kis", 1: "kis", 2: "kis", 3: "ilkbahar", 4: "ilkbahar", 5: "ilkbahar",
            6: "yaz", 7: "yaz", 8: "yaz"}.get(gun.month, "sonbahar")


def _get(url: str, timeout=12):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dolap/1.0"}), timeout=timeout)
    return json.load(r)


def hava_getir(lat: float, lon: float) -> list[dict]:
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "Europe/Istanbul", "forecast_days": 3,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                 "apparent_temperature_min,precipitation_probability_max,wind_speed_10m_max"})
    d = _get("https://api.open-meteo.com/v1/forecast?" + q)["daily"]
    gunler = []
    for i, g in enumerate(d["time"]):
        gunler.append({
            "gun": g, "kod": d["weather_code"][i], "durum": HAVA_KOD.get(d["weather_code"][i], ""),
            "en_yuksek": round(d["temperature_2m_max"][i]), "en_dusuk": round(d["temperature_2m_min"][i]),
            "his_yuksek": d["apparent_temperature_max"][i], "his_dusuk": d["apparent_temperature_min"][i],
            "yagmur": d["precipitation_probability_max"][i] or 0, "ruzgar": round(d["wind_speed_10m_max"][i] or 0),
        })
    return gunler


def sehir_bul(lat: float, lon: float) -> str:
    try:
        d = _get("https://api.bigdatacloud.net/data/reverse-geocode-client?" + urllib.parse.urlencode(
            {"latitude": lat, "longitude": lon, "localityLanguage": "tr"}), timeout=8)
        return d.get("city") or d.get("locality") or d.get("principalSubdivision") or ""
    except Exception:
        return ""


def sehir_ara(ad: str) -> dict | None:
    d = _get("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": ad, "count": 1, "language": "tr"}), timeout=8)
    r = (d.get("results") or [None])[0]
    return {"lat": round(r["latitude"], 2), "lon": round(r["longitude"], 2), "sehir": r["name"]} if r else None


class Oneri:
    def __init__(self, depo):
        self.depo = depo
        self.db = depo.db
        self.kilit = depo.kilit
        with self.kilit:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS ayar (ad TEXT PRIMARY KEY, deger TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS oneri (
              id INTEGER PRIMARY KEY AUTOINCREMENT, gun TEXT NOT NULL, sira INTEGER NOT NULL,
              parcalar TEXT NOT NULL, aciklama TEXT, puan REAL, ortam TEXT, tepki TEXT,
              olusturuldu TEXT NOT NULL, gecerli INTEGER NOT NULL DEFAULT 1);
            CREATE INDEX IF NOT EXISTS oneri_gun ON oneri(gun, gecerli);
            CREATE TABLE IF NOT EXISTS giyim (
              id INTEGER PRIMARY KEY AUTOINCREMENT, gun TEXT NOT NULL, parcalar TEXT NOT NULL, oneri INTEGER);
            CREATE TABLE IF NOT EXISTS zevk (anahtar TEXT PRIMARY KEY, puan REAL NOT NULL);
            """)
            sutun = {r[1] for r in self.db.execute("PRAGMA table_info(parca)")}
            if "giyim_sayisi" not in sutun:
                self.db.execute("ALTER TABLE parca ADD COLUMN giyim_sayisi INTEGER NOT NULL DEFAULT 0")
            if "kirlenen" not in {r[1] for r in self.db.execute("PRAGMA table_info(giyim)")}:
                # giyim kaydı geri alınınca bu yüzden kirliye düşenler temize döner: [[id, eski sayı], ...]
                self.db.execute("ALTER TABLE giyim ADD COLUMN kirlenen TEXT")
            self.db.commit()

    # --- ayarlar ------------------------------------------------------------
    def ayar(self, ad: str, varsayilan=None):
        with self.kilit:
            r = self.db.execute("SELECT deger FROM ayar WHERE ad=?", (ad,)).fetchone()
        return json.loads(r[0]) if r else varsayilan

    def ayar_yaz(self, ad: str, deger) -> None:
        with self.kilit:
            self.db.execute("INSERT OR REPLACE INTO ayar VALUES (?,?)", (ad, json.dumps(deger, ensure_ascii=False)))
            self.db.commit()

    def ayarlar(self) -> dict:
        return {"saat": self.ayar("saat", "06:00"), "konum": self.ayar("konum"),
                "aksam_uyari": self.ayar("aksam_uyari", True), "ortamlar": {k: v[0] for k, v in ORTAMLAR.items()}}

    def konum_yaz(self, lat: float, lon: float, sehir: str | None = None, elle=False) -> dict:
        lat, lon = round(float(lat), 2), round(float(lon), 2)  # ~1 km
        eski = self.ayar("konum") or {}
        if not sehir:
            sehir = eski.get("sehir") if (eski.get("lat"), eski.get("lon")) == (lat, lon) else sehir_bul(lat, lon)
        k = {"lat": lat, "lon": lon, "sehir": sehir or "", "elle": elle, "t": datetime.now(TZ).isoformat(timespec="minutes")}
        self.ayar_yaz("konum", k)
        if (eski.get("lat"), eski.get("lon")) != (lat, lon):
            self.ayar_yaz("hava", None)
        return k

    def hava(self, gun: str | None = None) -> dict | None:
        """Gün için hava; önbellek 2 saat."""
        k = self.ayar("konum")
        if not k:
            return None
        gun = gun or bugun()
        o = self.ayar("hava") or {}
        taze = o.get("t") and datetime.fromisoformat(o["t"]) > datetime.now(TZ) - timedelta(hours=2)
        if not taze or not any(g["gun"] == gun for g in o.get("gunler", [])):
            try:
                o = {"t": datetime.now(TZ).isoformat(), "gunler": hava_getir(k["lat"], k["lon"])}
                self.ayar_yaz("hava", o)
            except Exception as e:
                print("hava alınamadı:", e, flush=True)
        g = next((g for g in o.get("gunler", []) if g["gun"] == gun), None)
        return {**g, "sehir": k.get("sehir", "")} if g else None

    # --- parçalar -----------------------------------------------------------
    def _parcalar(self, temiz=True) -> list[dict]:
        hepsi = [p for p in self.depo.liste() if p["islem"] == "hazir" and not p.get("bekliyor")]
        return [p for p in hepsi if p["temizlik"] == "temiz"] if temiz else hepsi

    def _son_giyim(self, gun: str, kac_gun: int) -> dict[int, int]:
        """parça id -> kaç gün önce giyildi (en yakın)."""
        sinir = (date.fromisoformat(gun) - timedelta(days=kac_gun)).isoformat()
        out: dict[int, int] = {}
        with self.kilit:
            for r in self.db.execute("SELECT gun, parcalar FROM giyim WHERE gun>=? AND gun<?", (sinir, gun)):
                once = (date.fromisoformat(gun) - date.fromisoformat(r[0])).days
                for pid in json.loads(r[1]):
                    out[pid] = min(out.get(pid, 99), once)
        return out

    def _zevk(self) -> dict[str, float]:
        with self.kilit:
            return {r[0]: r[1] for r in self.db.execute("SELECT anahtar, puan FROM zevk")}

    # --- puanlama -----------------------------------------------------------
    @staticmethod
    def _hedef_sicaklik(h: dict | None) -> float | None:
        if not h:
            return None
        return 0.6 * h["his_yuksek"] + 0.4 * h["his_dusuk"]

    @staticmethod
    def _hedef_sicak_puan(t: float) -> float:
        for esik, deger in ((26, 2), (20, 3), (15, 4.5), (10, 6), (5, 7.5)):
            if t >= esik:
                return deger
        return 8.5

    def _puanla(self, k: list[dict], h, ortam: str, son: dict, zevk: dict, gun: date) -> tuple[float, list[str]]:
        puan, neden = 0.0, []
        yuva = {p["yuva"]: p for p in k}
        ana = [p for p in k if p["yuva"] in ("ust", "alt", "tek_parca", "dis_giyim")]
        metin = lambda p: ((p.get("tur") or "") + " " + (p.get("ad") or "") + " " + (p.get("isim") or "")).lower()
        t = self._hedef_sicaklik(h)
        if t is not None:
            sicak = sum(KALIN.get(p.get("kalinlik"), 2) * (1.5 if p["yuva"] == "tek_parca" else 1)
                        for p in k if p["yuva"] in ("ust", "alt", "tek_parca"))
            if "dis_giyim" in yuva:
                sicak += KALIN.get(yuva["dis_giyim"].get("kalinlik"), 2) + 1
            fark = sicak - self._hedef_sicak_puan(t)
            puan -= abs(fark) * 1.6
            if t < 15 and "dis_giyim" not in yuva:
                puan -= 3
            if t >= 22 and "dis_giyim" in yuva:
                puan -= 2.5
            if h["yagmur"] >= 50:
                d = yuva.get("dis_giyim")
                if d and any(w in metin(d) for w in SU_GECIRMEZ):
                    puan += 1.5
                    neden.append("yagmur_dis")
                elif not d:
                    puan -= 1
                a = yuva.get("ayakkabi")
                if a and any(w in metin(a) for w in ("bot", "çizme")):
                    puan += 1
                if a and any(w in metin(a) for w in YAGMUR_KOTU):
                    puan -= 1.5
        mev = mevsim(gun)
        for p in ana:
            if p.get("mevsim") and mev not in p["mevsim"]:
                puan -= 1.5
        hedef = ORTAMLAR.get(ortam, ORTAMLAR["gunluk"])[1]
        if ana:
            ort = sum(p.get("resmiyet") or 2 for p in ana) / len(ana)
            puan -= abs(ort - hedef) * 1.5
        if ortam == "ozel" and any(w in metin(p) for p in k for w in ("eşofman", "forma", "spor ayakkabı", "şort")):
            puan -= 2
        if ortam == "spor" and any(w in metin(p) for p in k for w in ("eşofman", "tayt", "spor", "şort", "forma")):
            puan += 1
        # Renk: nötr + en fazla bir vurgu iyi; desenli iki parça çakışır
        vurgular = set()
        for p in ana:
            ilk = (p.get("renkler") or [""])[0]
            if ilk and ilk not in NOTR:
                vurgular.add(ilk)
        puan += {0: 1.0, 1: 1.5, 2: -0.5}.get(len(vurgular), -2.0)
        desenli = [p for p in ana if (p.get("desen") or "düz") not in ("düz", "", "logolu")]
        if len(desenli) >= 2:
            puan -= 1.5
        # Tekrar cezası
        for p in k:
            if p["yuva"] in ("ayakkabi", "aksesuar"):
                continue
            once = son.get(p["id"])
            if once is not None:
                puan -= 3 if once <= 2 else 1.2 if once <= 6 else 0.4
        # Öğrenilen zevk
        idler = sorted(p["id"] for p in k)
        puan += sum(zevk.get(f"p:{i}", 0) for i in idler) * 0.6
        puan += sum(zevk.get(f"c:{a}-{b}", 0) for a, b in itertools.combinations(idler, 2)) * 0.8
        return puan, neden

    def adaylar(self, h, ortam: str, gun: date, haric: set[frozenset] = frozenset()) -> list[tuple[float, list[dict]]]:
        ps = self._parcalar()
        by = {y: [p for p in ps if p["yuva"] == y] for y in ("ust", "alt", "tek_parca", "dis_giyim", "ayakkabi", "aksesuar")}
        govde = [[u, a] for u in by["ust"] for a in by["alt"]] + [[t] for t in by["tek_parca"]]
        if not govde:  # sadece üst ya da sadece alt varsa yine de öner
            govde = [[p] for p in by["ust"] + by["alt"]]
        dislar = [None] + by["dis_giyim"]
        ayak = by["ayakkabi"] or [None]
        son = self._son_giyim(gun.isoformat(), 14)
        zevk = self._zevk()
        sonuc = []
        for g in govde:
            for d in dislar:
                for a in ayak:
                    k = g + [x for x in (d, a) if x]
                    if frozenset(p["id"] for p in k) in haric:
                        continue
                    puan, _ = self._puanla(k, h, ortam, son, zevk, gun)
                    sonuc.append((puan, k))
        # soğukta bere/atkı/eldiven ekle (temizse)
        t = self._hedef_sicaklik(h)
        if t is not None and t < 6:
            kis = [p for p in by["aksesuar"] if any(w in (p.get("tur") or "") for w in ("bere", "atkı", "eldiven", "kaşkol"))]
            if kis:
                sonuc = [(pn, k + kis[:1]) for pn, k in sonuc]
        sonuc.sort(key=lambda x: -x[0])
        return sonuc

    @staticmethod
    def _sec(adaylar, n=3) -> list[tuple[float, list[dict]]]:
        """En iyi n'i seç; birbirine çok benzeyenleri atla (en az bir ana parça farklı)."""
        secilen = []
        for pn, k in adaylar:
            ana = {p["id"] for p in k if p["yuva"] in ("ust", "alt", "tek_parca")}
            if all(len(ana ^ {p["id"] for p in s[1] if p["yuva"] in ("ust", "alt", "tek_parca")}) >= 2 for s in secilen):
                secilen.append((pn, k))
            if len(secilen) == n:
                break
        if len(secilen) < n:  # dolap küçükse benzerleri de al
            for pn, k in adaylar:
                if all({p["id"] for p in k} != {p["id"] for p in s[1]} for s in secilen):
                    secilen.append((pn, k))
                if len(secilen) == n:
                    break
        return secilen

    @staticmethod
    def aciklama(k: list[dict], h, ortam: str) -> str:
        ad = lambda p: p.get("isim") or p.get("ad") or p.get("tur") or "parça"
        sira = {"dis_giyim": 0, "ust": 1, "tek_parca": 1, "alt": 2, "ayakkabi": 3, "aksesuar": 4}
        parcalar = " + ".join(ad(p) for p in sorted(k, key=lambda p: sira.get(p["yuva"], 5)))
        on = []
        if h:
            on.append(f"{h['en_dusuk']}°–{h['en_yuksek']}°")
            if h["yagmur"] >= 50:
                on.append(f"yağmur %{h['yagmur']}")
            if h["ruzgar"] >= 30:
                on.append("rüzgârlı")
        ek = ""
        t = Oneri._hedef_sicaklik(h)
        dis = next((p for p in k if p["yuva"] == "dis_giyim"), None)
        su = dis and any(w in ((dis.get("tur") or "") + " " + (dis.get("ad") or "")).lower() for w in SU_GECIRMEZ)
        if h and h["yagmur"] >= 50 and su:
            ek = " Yağmura karşı dış katman var."
        elif h and h["yagmur"] >= 50:
            ek = " Yağmur var, şemsiyeni al ☂️"
        elif t is not None and t < 15 and dis:
            ek = " Serin, üstüne bir kat iyi gelir."
        elif t is not None and t >= 22 and not dis:
            ek = " Sıcak, ince ve tek kat."
        return (" · ".join(on) + ". " if on else "") + parcalar + "." + ek

    # --- öneri üret / getir -------------------------------------------------
    def uret(self, gun: str | None = None, ortam: str | None = None, baska=False) -> dict:
        gun = gun or bugun()
        mevcut = self.gunun(gun)
        ortam = ortam or (mevcut["ortam"] if mevcut["oneriler"] else None) or "gunluk"
        if ortam not in ORTAMLAR:
            ortam = "gunluk"
        h = self.hava(gun)
        haric = set()
        if baska:
            with self.kilit:
                for r in self.db.execute("SELECT parcalar FROM oneri WHERE gun=?", (gun,)):
                    haric.add(frozenset(json.loads(r[0])))
        ad = self.adaylar(h, ortam, date.fromisoformat(gun), haric)
        hepsi_goruldu = False
        if baska and not ad:  # hepsi gösterildiyse baştan
            ad = self.adaylar(h, ortam, date.fromisoformat(gun))
            hepsi_goruldu = True
        secilen = self._sec(ad)
        simdi = datetime.now(TZ).isoformat(timespec="seconds")
        with self.kilit:
            self.db.execute("UPDATE oneri SET gecerli=0 WHERE gun=? AND tepki IS NULL", (gun,))
            # tepki verilmişler (giydim/beğen) görünür kalsın diye geçerli bırakılır, yenileri arkadan gelir
            kalan = self.db.execute("SELECT COUNT(*) FROM oneri WHERE gun=? AND gecerli=1", (gun,)).fetchone()[0]
            for i, (pn, k) in enumerate(secilen):
                self.db.execute(
                    "INSERT INTO oneri (gun, sira, parcalar, aciklama, puan, ortam, olusturuldu) VALUES (?,?,?,?,?,?,?)",
                    (gun, kalan + i, json.dumps([p["id"] for p in k]), self.aciklama(k, h, ortam), round(pn, 2), ortam, simdi))
            self.db.commit()
        return {**self.gunun(gun), "hepsi_goruldu": hepsi_goruldu}

    def gunun(self, gun: str | None = None) -> dict:
        gun = gun or bugun()
        with self.kilit:
            satirlar = [dict(r) for r in self.db.execute(
                "SELECT * FROM oneri WHERE gun=? AND gecerli=1 ORDER BY (tepki='giydim') DESC, sira", (gun,))]
        parcalar = {p["id"]: p for p in self.depo.liste()}
        out = []
        for r in satirlar:
            ids = json.loads(r["parcalar"])
            out.append({"id": r["id"], "aciklama": r["aciklama"], "puan": r["puan"], "tepki": r["tepki"],
                        "parcalar": [parcalar[i] for i in ids if i in parcalar]})
        ortam = satirlar[-1]["ortam"] if satirlar else None
        return {"gun": gun, "ortam": ortam, "oneriler": out, "hava": self.hava(gun), "eksik": self.eksikler(gun),
                "giyilen": self.giyilen(gun)}

    def giyilen(self, gun: str) -> list[int]:
        with self.kilit:
            r = self.db.execute("SELECT parcalar FROM giyim WHERE gun=? ORDER BY id DESC", (gun,)).fetchone()
        return json.loads(r[0]) if r else []

    # --- eksik parça uyarısı ------------------------------------------------
    def eksikler(self, gun: str | None = None) -> list[str]:
        hepsi = self._parcalar(temiz=False)
        temiz = [p for p in hepsi if p["temizlik"] == "temiz"]
        say = lambda ps, y: sum(1 for p in ps if p["yuva"] == y)
        out = []
        if not hepsi:
            return ["Dolabın boş. Ekle sekmesinden aynada bir kombin fotoğrafı çek."]
        if say(hepsi, "ayakkabi") == 0:
            out.append("Dolabında hiç ayakkabı yok; kombinler ayakkabısız kalıyor. Bir ayakkabı fotoğrafı ekle.")
        if say(hepsi, "alt") + say(hepsi, "tek_parca") == 0:
            out.append("Hiç alt giysi (pantolon, etek, şort) yok.")
        if say(hepsi, "ust") + say(hepsi, "tek_parca") == 0:
            out.append("Hiç üst giysi yok.")
        h = self.hava(gun)
        t = self._hedef_sicaklik(h)
        if t is not None and t < 15 and say(hepsi, "dis_giyim") == 0:
            out.append("Hava serin ama dolabında dış giyim (mont, ceket, hırka) yok.")
        if h and h["yagmur"] >= 60 and not any(any(w in (p.get("tur") or "") for w in SU_GECIRMEZ) for p in hepsi if p["yuva"] == "dis_giyim"):
            out.append("Yağmur var; dolabında yağmurluk ya da mont görünmüyor.")
        if hepsi and say(temiz, "ust") == 0 and say(hepsi, "ust") > 0:
            out.append("Temiz üstün kalmadı, çamaşır günü 🧺")
        elif hepsi and say(temiz, "alt") == 0 and say(hepsi, "alt") > 0:
            out.append("Temiz altın kalmadı, çamaşır günü 🧺")
        if 0 < say(hepsi, "ust") < 3:
            out.append("Daha çeşitli öneri için birkaç üst daha ekle.")
        return out

    # --- tepki / giydim / öğrenme ------------------------------------------
    def _zevk_ekle(self, ids: list[int], deger: float) -> None:
        ids = sorted(ids)
        with self.kilit:
            for a in [f"p:{i}" for i in ids] + [f"c:{a}-{b}" for a, b in itertools.combinations(ids, 2)]:
                d = deger if a.startswith("p:") else deger * 0.6
                self.db.execute("INSERT INTO zevk VALUES (?,?) ON CONFLICT(anahtar) DO UPDATE SET puan=max(-4, min(4, puan+?))",
                                (a, d, d))
            self.db.commit()

    def tepki(self, oid: int, tepki: str) -> dict:
        with self.kilit:
            r = self.db.execute("SELECT * FROM oneri WHERE id=?", (oid,)).fetchone()
        if not r:
            raise KeyError(oid)
        ids, eski = json.loads(r["parcalar"]), r["tepki"]
        if tepki == eski:  # aynı düğmeye ikinci dokunuş geri alır
            tepki = None
        geri = {"begen": -1.0, "begenme": 1.0, "giydim": -0.5}.get(eski, 0)
        ileri = {"begen": 1.0, "begenme": -1.0, "giydim": 0.5}.get(tepki, 0)
        if geri or ileri:
            self._zevk_ekle(ids, geri + ileri)
        if eski == "giydim":
            self.giydim_geri(r["gun"], oid)
        with self.kilit:
            self.db.execute("UPDATE oneri SET tepki=? WHERE id=?", (tepki, oid))
            if tepki == "giydim":  # aynı gün başka öneriye "giydim" dendiyse o geri alınır
                for o in self.db.execute("SELECT id FROM oneri WHERE gun=? AND id!=? AND tepki='giydim'", (r["gun"], oid)).fetchall():
                    self.db.execute("UPDATE oneri SET tepki=NULL WHERE id=?", (o[0],))
            self.db.commit()
        if tepki == "giydim":
            self.giydim(r["gun"], ids, oid)
        return self.gunun(r["gun"])

    def giydim(self, gun: str, ids: list[int], oid: int | None = None) -> list[str]:
        """Günün kaydı (gün başına bir kombin) + giyim sayacı; sınıra gelen parça kirliye düşer."""
        self.giydim_geri(gun)
        kirlenen, kayit = [], []
        with self.kilit:
            for pid in ids:
                r = self.db.execute("SELECT * FROM parca WHERE id=?", (pid,)).fetchone()
                if not r:
                    continue
                n = kirli_siniri(dict(r))
                sayi = r["giyim_sayisi"] + 1
                if n and sayi >= n and r["temizlik"] == "temiz":
                    self.db.execute("UPDATE parca SET temizlik='kirli', giyim_sayisi=0 WHERE id=?", (pid,))
                    kirlenen.append(r["isim"] or r["ad"] or r["tur"])
                    kayit.append([pid, r["giyim_sayisi"]])
                else:
                    self.db.execute("UPDATE parca SET giyim_sayisi=? WHERE id=?", (sayi, pid))
            self.db.execute("INSERT INTO giyim (gun, parcalar, oneri, kirlenen) VALUES (?,?,?,?)",
                            (gun, json.dumps(ids), oid, json.dumps(kayit)))
            self.db.commit()
        return kirlenen

    def giydim_geri(self, gun: str, oid: int | None = None) -> None:
        with self.kilit:
            for r in self.db.execute("SELECT id, parcalar, kirlenen FROM giyim WHERE gun=?", (gun,)).fetchall():
                geri = {pid: eski for pid, eski in json.loads(r[2] or "[]")}
                for pid in json.loads(r[1]):
                    if pid in geri:  # bu giyimle kirliye düşmüştü: temize ve eski sayıya dön
                        self.db.execute("UPDATE parca SET temizlik='temiz', giyim_sayisi=? WHERE id=? AND temizlik='kirli'",
                                        (geri[pid], pid))
                        continue
                    p = self.db.execute("SELECT giyim_sayisi FROM parca WHERE id=?", (pid,)).fetchone()
                    if p and p[0] > 0:
                        self.db.execute("UPDATE parca SET giyim_sayisi=giyim_sayisi-1 WHERE id=?", (pid,))
                self.db.execute("DELETE FROM giyim WHERE id=?", (r[0],))
            self.db.commit()

    def yikandi(self) -> int:
        with self.kilit:
            n = self.db.execute("UPDATE parca SET temizlik='temiz', giyim_sayisi=0 WHERE temizlik!='temiz'").rowcount
            self.db.commit()
        return n

    # --- geçmiş (takvim) ----------------------------------------------------
    def gecmis(self, ay: str) -> dict:
        """ay: '2026-11' -> {gün: [parça...]}"""
        parcalar = {p["id"]: p for p in self.depo.liste()}
        with self.kilit:
            satir = self.db.execute("SELECT gun, parcalar FROM giyim WHERE gun LIKE ? ORDER BY id", (ay + "-%",)).fetchall()
        gunler = {}
        for g, ids in satir:
            gunler[g] = [parcalar[i] for i in json.loads(ids) if i in parcalar]
        return {"ay": ay, "gunler": gunler}

    # --- bildirim metinleri -------------------------------------------------
    def sabah_metni(self) -> tuple[str, str]:
        d = self.gunun()
        if not d["oneriler"]:
            d = self.uret()
        h = d["hava"]
        if not d["oneriler"]:
            return "Günaydın ☀️", (d["eksik"] or ["Bugün için kombin çıkaramadım."])[0]
        ilk = d["oneriler"][0]["aciklama"]
        baslik = "Günün kombini hazır 👕" + (f" · {h['sehir']} {h['en_dusuk']}°/{h['en_yuksek']}°" if h and h.get("sehir") else "")
        return baslik, ilk + " Bugün nereye gidiyorsun? Seç, ona göre yenileyeyim."

    def aksam_metni(self) -> tuple[str, str] | None:
        yarin = (datetime.now(TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
        b, y = self.hava(), self.hava(yarin)
        if not y:
            return None
        satir = []
        if y["yagmur"] >= 60:
            satir.append(f"Yarın yağmur ihtimali %{y['yagmur']} ☔")
        if b and y["his_dusuk"] <= b["his_dusuk"] - 5:
            satir.append(f"Yarın hava soğuyor: {y['en_dusuk']}°–{y['en_yuksek']}° 🥶")
        elif y["en_yuksek"] <= 5:
            satir.append(f"Yarın çok soğuk: en fazla {y['en_yuksek']}°")
        if y["en_yuksek"] >= 32:
            satir.append(f"Yarın çok sıcak: {y['en_yuksek']}° 🥵")
        if y["kod"] in (71, 73, 75, 77, 85, 86):
            satir.append("Yarın kar bekleniyor ❄️")
        if not satir:
            return None
        kirli_dis = [p for p in self._parcalar(temiz=False) if p["yuva"] == "dis_giyim" and p["temizlik"] != "temiz"
                     and any(w in (p.get("tur") or "") for w in SU_GECIRMEZ)]
        ek = f" {kirli_dis[0].get('isim') or kirli_dis[0].get('ad')} kirli görünüyor, temizse işaretle." if kirli_dis and y["yagmur"] >= 60 else ""
        return "Yarın için hava uyarısı", ". ".join(satir) + "." + ek
