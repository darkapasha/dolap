"""A2: tek parça fotoğrafı -> arka planı silinmiş PNG + etiketler.

Yükleme hemen kaydedilir, işleme sırayla tek bir arka plan iş parçacığında yapılır
(rembg ~3 sn, gemma3 etiketleme ~30-60 sn CPU'da). Telefon listeyi yoklayarak bekler.
"""
import base64
import io
import json
import queue
import sqlite3
import threading
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

import cizim

OLLAMA = "http://127.0.0.1:11434"
GORME_MODELI = "gemma3:4b"
YUVALAR = ["ust", "alt", "tek_parca", "dis_giyim", "ayakkabi", "aksesuar"]
KALINLIK = ["ince", "orta", "kalin"]
MEVSIM = ["ilkbahar", "yaz", "sonbahar", "kis"]
TEMIZLIK = ["temiz", "kirli", "yikamada"]

# Model yuvayı bazen şaşırıyor (tişörte "tek parça" dedi). Türün adında açık bir
# kelime varsa yuva ondan gelir. Sıra önemli: "kot ceket" dış giyim, "spor ayakkabı" ayakkabı.
_YUVA_KELIME = [
    ("tek_parca", ["elbise", "tulum", "salopet"]),
    ("ayakkabi", ["ayakkabı", "ayakkabi", "bot", "çizme", "sneaker", "terlik", "sandalet", "mokasen", "loafer", "babet"]),
    ("aksesuar", ["çanta", "şapka", "bere", "kemer", "atkı", "kaşkol", "eldiven", "saat", "gözlük", "kolye", "bileklik", "kravat", "fular", "şal"]),
    ("dis_giyim", ["mont", "ceket", "kaban", "palto", "yağmurluk", "trençkot", "parka", "blazer", "yelek"]),
    ("alt", ["pantolon", "kot", "jean", "etek", "şort", "tayt", "eşofman altı", "jogger", "chino"]),
    ("ust", ["tişört", "t-shirt", "gömlek", "kazak", "sweat", "bluz", "hırka", "atlet", "polo", "body", "crop", "triko", "hoodie", "kapüşonlu", "forma"]),
]


def yuva_bul(tur: str, model_yuvasi: str) -> str:
    t = (tur or "").lower()
    for yuva, kelimeler in _YUVA_KELIME:
        if any(k in t for k in kelimeler):
            return yuva
    return model_yuvasi if model_yuvasi in YUVALAR else "ust"


def kelime_yuvasi(tur: str) -> str | None:
    t = (tur or "").lower()
    for yuva, kelimeler in _YUVA_KELIME:
        if any(k in t for k in kelimeler):
            return yuva
    return None


def etiketleri_esle(yuvalar: list[str], etiketler: list[dict], renkler: list[list[str]] | None = None) -> list[dict]:
    """Model etiketleri parça sırasından farklı sırayla döndürebiliyor (2026-11-08: eşofman altı
    'üst' parçaya, hırka 'alt' parçaya yazıldı). Etiketin türündeki kelimenin yuvası parçanın
    yuvasıyla uyuşacak şekilde yer değiştirir. Üst ile dış giyim birbirine yakın sayılır.
    Eşitlikte renk bozar: etiketin adında parçanın piksel rengi geçiyorsa o eşleşme tercih edilir."""
    renkler = renkler or [[] for _ in yuvalar]

    def uyum(i, e):
        yuva = yuvalar[i]
        ad = (e.get("ad", "") or "").replace("I", "ı").replace("İ", "i").lower()
        renk = 0.3 if any(r and r in ad for r in renkler[i]) else 0
        k = kelime_yuvasi(e.get("tur", "") + " " + e.get("ad", ""))
        if k is None:
            return renk
        if k == yuva:
            return 1 + renk
        return (1 if {k, yuva} == {"ust", "dis_giyim"} else -1) + renk  # üst ile dış katman kelimeden ayrılamaz
    e = list(etiketler)
    degisti = True
    while degisti:
        degisti = False
        for i in range(len(e)):
            for j in range(i + 1, len(e)):
                once = uyum(i, e[i]) + uyum(j, e[j])
                sonra = uyum(i, e[j]) + uyum(j, e[i])
                if sonra > once:
                    e[i], e[j] = e[j], e[i]
                    degisti = True
    return e


class Depo:
    def __init__(self, veri: Path):
        self.foto = veri / "foto"
        self.foto.mkdir(exist_ok=True)
        self.db = sqlite3.connect(veri / "dolap.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.kilit = threading.Lock()
        with self.kilit:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS parca (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              eklendi TEXT NOT NULL,
              islem TEXT NOT NULL DEFAULT 'sirada',   -- sirada / isleniyor / hazir / hata
              hata TEXT,
              surum INTEGER NOT NULL DEFAULT 0,       -- resim değişince artar (önbellek kırma)
              ad TEXT, tur TEXT, yuva TEXT,
              renkler TEXT, desen TEXT, kalinlik TEXT, resmiyet INTEGER, mevsim TEXT,
              temizlik TEXT NOT NULL DEFAULT 'temiz',
              kesik INTEGER NOT NULL DEFAULT 1        -- 0: arka plan silinemedi, foto olduğu gibi
            );
            """)
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS kombin (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              eklendi TEXT NOT NULL,
              islem TEXT NOT NULL DEFAULT 'sirada',   -- sirada / ayriliyor / etiketleniyor / hazir / hata
              hata TEXT,
              parca_sayisi INTEGER NOT NULL DEFAULT 0
            );
            """)
            sutunlar = {r[1] for r in self.db.execute("PRAGMA table_info(parca)")}
            if "kaynak" not in sutunlar:
                self.db.execute("ALTER TABLE parca ADD COLUMN kaynak INTEGER")  # kombin id
            # isim: kullanıcının verdiği ad; aynı isim = aynı kıyafet (birleştirilir)
            if "isim" not in sutunlar:
                self.db.execute("ALTER TABLE parca ADD COLUMN isim TEXT")
            # gorsel: 'cizim' / 'foto'; boşsa kombinden gelen çizim, tek parça foto gösterir
            if "gorsel" not in sutunlar:
                self.db.execute("ALTER TABLE parca ADD COLUMN gorsel TEXT")
            # bekliyor: 1 = kombin fotoğrafından çıktı, kullanıcı onaylayana kadar dolapta sayılmaz
            if "bekliyor" not in sutunlar:
                self.db.execute("ALTER TABLE parca ADD COLUMN bekliyor INTEGER NOT NULL DEFAULT 0")
            # aynı kıyafetin başka fotoğraflardaki kesikleri (birleştirmede taşınır)
            self.db.execute("""CREATE TABLE IF NOT EXISTS gorunum (
              id INTEGER PRIMARY KEY AUTOINCREMENT, parca INTEGER NOT NULL, kaynak INTEGER, eklendi TEXT NOT NULL)""")
            self.db.commit()
        # iş: ("parca", id) ya da ("kombin", id)
        self.kuyruk: "queue.Queue[tuple[str, int]]" = queue.Queue()
        self._rembg = None
        for r in self.db.execute("SELECT id FROM kombin WHERE islem NOT IN ('hazir','hata') ORDER BY id"):
            self.db.execute("DELETE FROM parca WHERE kaynak=? AND islem!='hazir'", (r["id"],))
            self.kuyruk.put(("kombin", r["id"]))
        for r in self.db.execute("SELECT id FROM parca WHERE islem IN ('sirada','isleniyor') AND kaynak IS NULL ORDER BY id"):
            self.kuyruk.put(("parca", r["id"]))
        self.db.commit()
        threading.Thread(target=self._isci, daemon=True).start()

    # --- kayıtlar ---------------------------------------------------------
    def satir(self, r: sqlite3.Row) -> dict:
        d = dict(r)
        d["renkler"] = json.loads(d["renkler"] or "[]")
        d["mevsim"] = json.loads(d["mevsim"] or "[]")
        d["sira"] = self._sira(d["id"]) if d["islem"] in ("sirada", "isleniyor") else 0
        d["gorunumler"] = [g[0] for g in self.db.execute("SELECT id FROM gorunum WHERE parca=? ORDER BY id", (d["id"],))]
        d["cizim"] = cizim.anahtar(d)
        return d

    def _sira(self, pid: int) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM parca WHERE islem IN ('sirada','isleniyor') AND id <= ?", (pid,)
        ).fetchone()[0]

    def liste(self) -> list[dict]:
        with self.kilit:
            return [self.satir(r) for r in self.db.execute("SELECT * FROM parca ORDER BY id DESC")]

    def al(self, pid: int) -> dict | None:
        with self.kilit:
            r = self.db.execute("SELECT * FROM parca WHERE id=?", (pid,)).fetchone()
            return self.satir(r) if r else None

    @staticmethod
    def _ac(veri: bytes) -> Image.Image:
        im = Image.open(io.BytesIO(veri))  # bozuk dosyayı hemen reddet
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((2600, 2600))
        return im

    @staticmethod
    def _simdi() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def ekle(self, veri: bytes) -> int:
        im = self._ac(veri)
        with self.kilit:
            cur = self.db.execute("INSERT INTO parca (eklendi) VALUES (?)", (self._simdi(),))
            self.db.commit()
            pid = cur.lastrowid
        im.save(self.foto / f"{pid}_orj.jpg", quality=90)
        self.kuyruk.put(("parca", pid))
        return pid

    def kombin_ekle(self, veri: bytes) -> int:
        im = self._ac(veri)
        with self.kilit:
            cur = self.db.execute("INSERT INTO kombin (eklendi) VALUES (?)", (self._simdi(),))
            self.db.commit()
            kid = cur.lastrowid
        im.save(self.foto / f"k{kid}.jpg", quality=90)
        self.kuyruk.put(("kombin", kid))
        return kid

    def kombinler(self) -> list[dict]:
        """İşi bitmemiş ya da hata vermiş kombin fotoğrafları."""
        with self.kilit:
            return [dict(r) for r in self.db.execute(
                "SELECT * FROM kombin WHERE islem NOT IN ('hazir') ORDER BY id DESC LIMIT 20")]

    def kombin_sil(self, kid: int) -> None:
        with self.kilit:
            self.db.execute("DELETE FROM kombin WHERE id=?", (kid,))
            self.db.commit()
        (self.foto / f"k{kid}.jpg").unlink(missing_ok=True)

    def onayla(self, kid: int, tut: list[int]) -> list[int]:
        """Kombin fotoğrafından çıkan parçalar: tutulanlar dolaba girer, kalanlar silinir."""
        with self.kilit:
            idler = [r[0] for r in self.db.execute("SELECT id FROM parca WHERE kaynak=? AND bekliyor=1", (kid,))]
        for pid in idler:
            if pid in tut:
                with self.kilit:
                    self.db.execute("UPDATE parca SET bekliyor=0 WHERE id=?", (pid,))
                    self.db.commit()
            else:
                self.sil(pid)
        return [p for p in idler if p in tut]

    def guncelle(self, pid: int, alanlar: dict) -> int:
        """Alanları yazar. İsim başka bir parçanınkiyle aynıysa ikisini birleştirir ve kalan parçanın id'sini döndürür."""
        izin = {"ad", "tur", "yuva", "renkler", "desen", "kalinlik", "resmiyet", "mevsim", "temizlik", "isim", "gorsel"}
        temiz = {}
        for k, v in alanlar.items():
            if k not in izin or v is None:
                continue
            if k == "yuva" and v not in YUVALAR: continue
            if k == "kalinlik" and v not in KALINLIK: continue
            if k == "temizlik" and v not in TEMIZLIK: continue
            if k == "gorsel" and v not in ("cizim", "foto"): continue
            if k == "resmiyet": v = max(1, min(5, int(v)))
            if k in ("renkler", "mevsim"):
                v = json.dumps([str(x)[:30] for x in v][:6], ensure_ascii=False)
            elif isinstance(v, str):
                v = v.strip()[:60]
            temiz[k] = v
        if "isim" in temiz:
            temiz["isim"] = " ".join(temiz["isim"].split()) or None
        hedef = self.ayni_isimli(temiz["isim"], pid) if temiz.get("isim") else None
        if hedef:
            # aynı kıyafet: yeni parça eskisine görünüm olarak katılır; eskinin etiketleri kalır
            self.birlestir(pid, hedef)
            return hedef
        if not temiz:
            return pid
        with self.kilit:
            self.db.execute(f"UPDATE parca SET {', '.join(k + '=?' for k in temiz)} WHERE id=?",
                            (*temiz.values(), pid))
            self.db.commit()
        return pid

    @staticmethod
    def isim_anahtar(isim: str) -> str:
        return " ".join((isim or "").replace("I", "ı").replace("İ", "i").lower().split())

    def ayni_isimli(self, isim: str, haric: int) -> int | None:
        a = self.isim_anahtar(isim)
        with self.kilit:
            for r in self.db.execute("SELECT id, isim FROM parca WHERE isim IS NOT NULL AND id!=? ORDER BY id", (haric,)):
                if self.isim_anahtar(r["isim"]) == a:
                    return r["id"]
        return None

    def birlestir(self, kaynak: int, hedef: int) -> None:
        """kaynak parçanın kesik fotoğrafı hedefin görünümü olur, kaynak satırı silinir."""
        with self.kilit:
            k = self.db.execute("SELECT * FROM parca WHERE id=?", (kaynak,)).fetchone()
            if not k:
                return
            self.db.execute("UPDATE gorunum SET parca=? WHERE parca=?", (hedef, kaynak))
            gid = None
            if (self.foto / f"{kaynak}.png").exists():
                gid = self.db.execute("INSERT INTO gorunum (parca, kaynak, eklendi) VALUES (?,?,?)",
                                      (hedef, k["kaynak"], k["eklendi"])).lastrowid
            self.db.execute("DELETE FROM parca WHERE id=?", (kaynak,))
            self.db.commit()
        if gid:
            (self.foto / f"{kaynak}.png").replace(self.foto / f"g{gid}.png")
            if (self.foto / f"{kaynak}_k.webp").exists():
                (self.foto / f"{kaynak}_k.webp").replace(self.foto / f"g{gid}_k.webp")
        for ek in ("_orj.jpg", ".png", "_k.webp"):
            (self.foto / f"{kaynak}{ek}").unlink(missing_ok=True)

    def sil(self, pid: int) -> None:
        with self.kilit:
            gler = [g[0] for g in self.db.execute("SELECT id FROM gorunum WHERE parca=?", (pid,))]
            self.db.execute("DELETE FROM gorunum WHERE parca=?", (pid,))
            self.db.execute("DELETE FROM parca WHERE id=?", (pid,))
            self.db.commit()
        for g in gler:
            for ek in (".png", "_k.webp"):
                (self.foto / f"g{g}{ek}").unlink(missing_ok=True)
        for ek in ("_orj.jpg", ".png", "_k.webp"):
            (self.foto / f"{pid}{ek}").unlink(missing_ok=True)

    def yeniden(self, pid: int) -> None:
        with self.kilit:
            self.db.execute("UPDATE parca SET islem='sirada', hata=NULL WHERE id=?", (pid,))
            self.db.commit()
        self.kuyruk.put(("parca", pid))

    def _yaz(self, pid: int, **alan) -> None:
        with self.kilit:
            self.db.execute(f"UPDATE parca SET {', '.join(k + '=?' for k in alan)} WHERE id=?",
                            (*alan.values(), pid))
            self.db.commit()

    # --- işleme -----------------------------------------------------------
    def _isci(self) -> None:
        while True:
            tur, no = self.kuyruk.get()
            try:
                if tur == "kombin":
                    if (self.foto / f"k{no}.jpg").exists():
                        self._kombin_isle(no)
                    continue
                if not (self.foto / f"{no}_orj.jpg").exists():
                    continue
                self._yaz(no, islem="isleniyor")
                self._isle(no)
            except Exception as e:  # bir işin hatası işçiyi durdurmasın
                traceback.print_exc()
                if tur == "kombin":
                    with self.kilit:
                        self.db.execute("UPDATE kombin SET islem='hata', hata=? WHERE id=?", (str(e)[:200], no))
                        self.db.execute("UPDATE parca SET islem='hata', hata=? WHERE kaynak=? AND islem!='hazir'",
                                        (str(e)[:200], no))
                        self.db.commit()
                else:
                    self._yaz(no, islem="hata", hata=str(e)[:200])

    def _kombin_yaz(self, kid: int, **alan) -> None:
        with self.kilit:
            self.db.execute(f"UPDATE kombin SET {', '.join(k + '=?' for k in alan)} WHERE id=?", (*alan.values(), kid))
            self.db.commit()

    def _resimleri_kaydet(self, pid: int, kesik: Image.Image) -> None:
        kesik = kesik.copy()
        kesik.thumbnail((1024, 1024))
        kesik.save(self.foto / f"{pid}.png", optimize=True)
        k = kesik.copy()
        k.thumbnail((420, 420))
        k.save(self.foto / f"{pid}_k.webp", quality=82)

    def _kombin_isle(self, kid: int) -> None:
        import kombin
        import renk
        t0 = time.time()
        self._kombin_yaz(kid, islem="ayriliyor")
        kisi, bulunan = kombin.ayir(Image.open(self.foto / f"k{kid}.jpg"))
        if not bulunan:
            self._kombin_yaz(kid, islem="hata", hata="fotoğrafta kıyafet bulunamadı")
            return
        idler = []
        # Dolap en yeniyi önce gösterir: tersten eklenince kombin yukarıdan aşağı okunur
        for b in reversed(bulunan):
            with self.kilit:
                cur = self.db.execute(
                    "INSERT INTO parca (eklendi, islem, kaynak, yuva, renkler, surum, bekliyor) VALUES (?,?,?,?,?,1,1)",
                    (self._simdi(), "isleniyor", kid, b["yuva"],
                     json.dumps(renk.bul(b["resim"]), ensure_ascii=False)))
                self.db.commit()
                pid = cur.lastrowid
            self._resimleri_kaydet(pid, b["resim"])
            # "yeniden işle" tek parça yolundan geçebilsin diye beyaz zeminli kopya
            beyaz = Image.new("RGB", b["resim"].size, (255, 255, 255))
            beyaz.paste(b["resim"], mask=b["resim"].getchannel("A"))
            beyaz.save(self.foto / f"{pid}_orj.jpg", quality=90)
            b["id"] = pid
            idler.append(pid)
        self._kombin_yaz(kid, islem="etiketleniyor", parca_sayisi=len(idler))
        t1 = time.time()
        etiketler = self._kombin_etiketle(kisi, bulunan)
        for b, e in zip(bulunan, etiketler):
            e["yuva"] = b["yuva"]  # yuvayı bölütleme sınıfı belirler; model sadece adlandırır
            self._yaz(b["id"], islem="hazir", hata=None, **e)
        self._kombin_yaz(kid, islem="hazir")
        print(f"kombin {kid}: {len(idler)} parça, ayırma {t1 - t0:.1f}s, etiket {time.time() - t1:.1f}s", flush=True)

    def _gorsel_sor(self, im: Image.Image, istem: str, sema: dict) -> dict:
        beyaz = im.convert("RGB") if im.mode != "RGBA" else None
        if beyaz is None:
            beyaz = Image.new("RGB", im.size, (255, 255, 255))
            beyaz.paste(im, mask=im.getchannel("A"))
        beyaz.thumbnail((896, 896))
        tampon = io.BytesIO()
        beyaz.save(tampon, "JPEG", quality=88)
        govde = {
            "model": GORME_MODELI, "stream": False, "format": sema, "keep_alive": "5m",
            "options": {"temperature": 0.2, "num_ctx": 4096},
            "messages": [{"role": "user", "content": istem,
                          "images": [base64.b64encode(tampon.getvalue()).decode()]}],
        }
        r = urllib.request.urlopen(urllib.request.Request(
            OLLAMA + "/api/chat", json.dumps(govde).encode(), {"Content-Type": "application/json"}), timeout=900)
        return json.loads(json.load(r)["message"]["content"])

    _ETIKET_OZ = {
        "ad": {"type": "string"},
        "tur": {"type": "string"},
        "desen": {"type": "string"},
        "kalinlik": {"type": "string", "enum": KALINLIK},
        "resmiyet": {"type": "integer"},
        "mevsim": {"type": "array", "items": {"type": "string", "enum": MEVSIM}},
    }
    _ETIKET_ACIKLAMA = (
        "ad: 2-4 kelimelik kısa Türkçe ad, rengini de söyle (ör. 'Gri fermuarlı kapüşonlu', 'Siyah futbol forması').\n"
        "tur: türü, küçük harf (ör. tişört, forma, kot pantolon, kapüşonlu sweatshirt, spor ayakkabı, bot).\n"
        "desen: düz, çizgili, kareli, çiçekli, baskılı, logolu, yazılı...\n"
        "kalinlik: ince (yazlık), orta, kalin (kışlık).\n"
        "resmiyet: 1 spor/ev, 2 günlük, 3 smart casual, 4 iş, 5 resmi.\n"
        "mevsim: giyilebileceği mevsimler.")

    def _temiz_etiket(self, e: dict) -> dict:
        tur = str(e.get("tur", "")).strip().lower()[:40]
        try:
            resmi = max(1, min(5, int(e.get("resmiyet") or 2)))
        except (TypeError, ValueError):
            resmi = 2
        return {
            "ad": str(e.get("ad", "")).strip()[:60] or tur.capitalize(),
            "tur": tur,
            "desen": str(e.get("desen", "")).strip().lower()[:30],
            "kalinlik": e.get("kalinlik") if e.get("kalinlik") in KALINLIK else "orta",
            "resmiyet": resmi,
            "mevsim": json.dumps([m for m in e.get("mevsim", []) if m in MEVSIM] or MEVSIM, ensure_ascii=False),
        }

    def _kombin_etiketle(self, kisi: Image.Image, bulunan: list[dict]) -> list[dict]:
        """Tüm parçalar tek model çağrısıyla: kişinin fotoğrafı + bulunan parçaların listesi."""
        import renk
        # Bölütleme sınıfının adı (ör. "ceket") ipucu olarak verilince model ona uyuyordu
        # (kapüşonluya ceket, formaya tişört dedi, 2026-11-07). Sadece katman ve renk verilir.
        yuva_ad = {"ust": "üst giysi (dış katmanın altındaki)", "alt": "alt giysi", "tek_parca": "tek parça (elbise, tulum)",
                   "dis_giyim": "en üstteki dış katman (ceket, mont, hırka, kapüşonlu...)",
                   "ayakkabi": "ayakkabı", "aksesuar": "aksesuar"}
        satirlar = "\n".join(
            f"{i + 1}) {yuva_ad[b['yuva']]}, renk: {', '.join(renk.bul(b['resim'])) or '?'}"
            for i, b in enumerate(bulunan))
        n = len(bulunan)
        sema = {"type": "object", "properties": {"parcalar": {
            "type": "array", "minItems": n, "maxItems": n,
            "items": {"type": "object", "properties": self._ETIKET_OZ, "required": list(self._ETIKET_OZ)}}},
            "required": ["parcalar"]}
        istem = (f"Fotoğraftaki kişinin üzerindeki {n} parçayı yukarıdan aşağı sırayla etiketle:\n{satirlar}\n\n"
                 "Her parçaya dikkatle bak: fermuar, kapüşon, yaka, düğme, logo, yazı, numara, kumaş (kot, örgü, eşofman, "
                 "deri) gibi ayrıntılardan türünü bul. Özel türleri genel adla geçme (ör. polo, gömlek, futbol forması, "
                 "kapüşonlu sweatshirt, hırka, kot, eşofman altı, kargo pantolon, bot). "
                 f"Tam {n} öğelik parcalar listesi döndür.\n" + self._ETIKET_ACIKLAMA)
        liste = self._gorsel_sor(kisi, istem, sema).get("parcalar", [])
        liste = [e if isinstance(e, dict) else {} for e in liste][:n] + [{}] * max(0, n - len(liste))
        liste = etiketleri_esle([b["yuva"] for b in bulunan], liste, [renk.bul(b["resim"]) for b in bulunan])
        sonuc = []
        for i, b in enumerate(bulunan):
            e = liste[i]
            if not e.get("tur"):
                e = {**e, "tur": b["ipucu"].split(" / ")[0]}
            sonuc.append(self._temiz_etiket(e))
        return sonuc

    def _kes(self, im: Image.Image) -> tuple[Image.Image, bool]:
        if self._rembg is None:
            from rembg import new_session
            self._rembg = new_session("isnet-general-use")
        from rembg import remove
        kucuk = im.copy()
        kucuk.thumbnail((1280, 1280))
        o = remove(kucuk, session=self._rembg)
        a = o.getchannel("A").point(lambda v: 255 if v > 24 else 0)
        kutu = a.getbbox()
        w, h = o.size
        # hiçbir şey bulunamadı ya da neredeyse tüm kare / minicik bir leke: kesmeden kullan
        if not kutu:
            return kucuk.convert("RGBA"), False
        kw, kh = kutu[2] - kutu[0], kutu[3] - kutu[1]
        if kw * kh < 0.02 * w * h:
            return kucuk.convert("RGBA"), False
        pay = int(0.04 * max(kw, kh))
        kutu = (max(0, kutu[0] - pay), max(0, kutu[1] - pay), min(w, kutu[2] + pay), min(h, kutu[3] + pay))
        return o.crop(kutu), True

    def _etiketle(self, im: Image.Image) -> dict:
        import renk
        sema = {"type": "object",
                "properties": {**self._ETIKET_OZ, "yuva": {"type": "string", "enum": YUVALAR}},
                "required": list(self._ETIKET_OZ) + ["yuva"]}
        istem = ("Fotoğrafta tek bir kıyafet ya da aksesuar var. Türkçe etiketle.\n"
                 "yuva: ust (tişört, gömlek, kazak, sweatshirt), alt (pantolon, etek, şort), "
                 "tek_parca (elbise, tulum), dis_giyim (mont, ceket, kaban), ayakkabi, aksesuar (çanta, şapka, kemer, atkı).\n"
                 + self._ETIKET_ACIKLAMA)
        e = self._gorsel_sor(im, istem, sema)
        sonuc = self._temiz_etiket(e)
        sonuc["yuva"] = yuva_bul(sonuc["tur"], e.get("yuva", ""))
        sonuc["renkler"] = json.dumps(renk.bul(im), ensure_ascii=False)
        return sonuc

    def _isle(self, pid: int) -> None:
        t0 = time.time()
        im = Image.open(self.foto / f"{pid}_orj.jpg").convert("RGB")
        kesik, oldu = self._kes(im)
        with self.kilit:
            s = self.db.execute("SELECT surum FROM parca WHERE id=?", (pid,)).fetchone()
        if s is None:  # bu arada silindi
            return
        self._resimleri_kaydet(pid, kesik)
        self._yaz(pid, kesik=int(oldu), surum=s["surum"] + 1)
        t1 = time.time()
        etiket = self._etiketle(kesik)
        self._yaz(pid, islem="hazir", hata=None, **etiket)
        print(f"parça {pid}: kesme {t1 - t0:.1f}s, etiket {time.time() - t1:.1f}s", flush=True)
