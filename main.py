"""Dolap API — A1 iskeleti.

Tek kullanıcılı. Telefon bir kere gizli anahtarla eşlenir; her API isteği
X-Anahtar başlığıyla gelir. PWA dosyaları da buradan sunulur (aynı adres,
CORS derdi yok).
"""
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

SURUM = "1.0"
KOK = Path(__file__).resolve().parent
WEB = KOK / "web"
VERI = KOK / "veri"
VERI.mkdir(exist_ok=True)

_anahtar_dosya = VERI / "anahtar.txt"
if not _anahtar_dosya.exists():
    _anahtar_dosya.write_text(secrets.token_urlsafe(32))
    os.chmod(_anahtar_dosya, 0o600)
ANAHTAR = _anahtar_dosya.read_text().strip()

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

from parca import Depo  # noqa: E402
import cizim  # noqa: E402
import oneri as oneri_mod  # noqa: E402

depo = Depo(VERI)
oneri = oneri_mod.Oneri(depo)


def _dogru(k: str | None) -> bool:
    return bool(k) and secrets.compare_digest(k, ANAHTAR)


def kontrol(k: str | None) -> None:
    if not _dogru(k):
        raise HTTPException(status_code=401, detail="anahtar yanlış")


@app.get("/api/durum")
def durum(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    return {
        "ok": True,
        "surum": SURUM,
        "sunucu_saati": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --- Kısa eşleme kodu ---------------------------------------------------
# iPhone'da ana ekran uygulaması Safari'den ayrı depolama kullanır; uzun
# anahtarı yazmak zor. Eşlenmiş bir cihaz 6 haneli, 10 dakikalık bir kod
# alır; yeni cihaz bu kodu girip anahtarı alır.
_kodlar: dict[str, float] = {}
_hatalar: list[float] = []


class KodIstek(BaseModel):
    kod: str


@app.post("/api/kod")
def kod_al(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    simdi = time.time()
    for k in [k for k, t in _kodlar.items() if t < simdi]:
        del _kodlar[k]
    kod = f"{secrets.randbelow(1_000_000):06d}"
    _kodlar[kod] = simdi + 600
    return {"kod": kod, "sure_dk": 10}


@app.post("/api/kod/kullan")
def kod_kullan(istek: KodIstek):
    simdi = time.time()
    _hatalar[:] = [t for t in _hatalar if t > simdi - 600]
    if len(_hatalar) >= 8:
        raise HTTPException(status_code=429, detail="çok fazla deneme, 10 dk bekle")
    kod = istek.kod.strip()
    if _kodlar.get(kod, 0) > simdi:
        del _kodlar[kod]
        return {"anahtar": ANAHTAR}
    _hatalar.append(simdi)
    raise HTTPException(status_code=400, detail="kod yanlış ya da süresi dolmuş")


# --- A2: parçalar -------------------------------------------------------
@app.post("/api/parca")
async def parca_ekle(istek: Request, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    veri = await istek.body()
    if not veri or len(veri) > 20_000_000:
        raise HTTPException(status_code=413, detail="fotoğraf boş ya da çok büyük")
    try:
        pid = depo.ekle(veri)
    except Exception:
        raise HTTPException(status_code=400, detail="fotoğraf okunamadı")
    return depo.al(pid)


@app.post("/api/kombin")
async def kombin_ekle(istek: Request, x_anahtar: str | None = Header(default=None)):
    """A3: aynada üzerindeki kombinin fotoğrafı; parçalara ayrılıp dolaba eklenir."""
    kontrol(x_anahtar)
    veri = await istek.body()
    if not veri or len(veri) > 20_000_000:
        raise HTTPException(status_code=413, detail="fotoğraf boş ya da çok büyük")
    try:
        kid = depo.kombin_ekle(veri)
    except Exception:
        raise HTTPException(status_code=400, detail="fotoğraf okunamadı")
    return {"id": kid}


@app.get("/api/kombinler")
def kombinler(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    return depo.kombinler()


@app.delete("/api/kombin/{kid}")
def kombin_sil(kid: int, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    depo.kombin_sil(kid)
    return {"ok": True}


class OnayIstek(BaseModel):
    tut: list[int]
    giydim: bool = False


@app.post("/api/kombin/{kid}/onay")
def kombin_onay(kid: int, istek: OnayIstek, x_anahtar: str | None = Header(default=None)):
    """Kombin fotoğrafından çıkan parçaları dolaba al (tutulmayanlar silinir)."""
    kontrol(x_anahtar)
    tutulan = depo.onayla(kid, istek.tut)
    # isim verilip eski kıyafetle birleşenler de istek.tut içinde (eski id ile) gelir
    giyilen = [i for i in dict.fromkeys(istek.tut) if depo.al(i)]
    kirlenen = oneri.giydim(oneri_mod.bugun(), giyilen) if istek.giydim and giyilen else []
    return {"tutulan": tutulan, "kirlenen": kirlenen}


# --- A4-A6: öneri, hava, geri bildirim, geçmiş --------------------------------
class BugunIstek(BaseModel):
    ortam: str | None = None
    baska: bool = False


@app.get("/api/bugun")
def bugun_al(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    d = oneri.gunun()
    if not d["oneriler"]:
        d = oneri.uret()
    return d


@app.post("/api/bugun")
def bugun_yenile(istek: BugunIstek, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    return oneri.uret(ortam=istek.ortam, baska=istek.baska)


class TepkiIstek(BaseModel):
    tepki: str


@app.post("/api/oneri/{oid}/tepki")
def oneri_tepki(oid: int, istek: TepkiIstek, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    if istek.tepki not in ("begen", "begenme", "giydim"):
        raise HTTPException(400)
    try:
        return oneri.tepki(oid, istek.tepki)
    except KeyError:
        raise HTTPException(404)


class KonumIstek(BaseModel):
    lat: float | None = None
    lon: float | None = None
    sehir: str | None = None


@app.post("/api/konum")
def konum(istek: KonumIstek, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    if istek.sehir:
        bulunan = oneri_mod.sehir_ara(istek.sehir)
        if not bulunan:
            raise HTTPException(404, "şehir bulunamadı")
        return oneri.konum_yaz(bulunan["lat"], bulunan["lon"], bulunan["sehir"], elle=True)
    if istek.lat is None or istek.lon is None:
        raise HTTPException(400)
    eski = oneri.ayar("konum") or {}
    if eski.get("elle"):  # elle seçilen şehir varken telefon konumu onu ezmesin
        return eski
    return oneri.konum_yaz(istek.lat, istek.lon)


@app.delete("/api/konum/elle")
def konum_elle_kaldir(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    k = oneri.ayar("konum") or {}
    k["elle"] = False
    oneri.ayar_yaz("konum", k)
    return k


@app.get("/api/ayarlar")
def ayarlar_al(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    return oneri.ayarlar()


@app.post("/api/ayarlar")
def ayarlar_yaz(alanlar: dict, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    s = alanlar.get("saat")
    if isinstance(s, str) and len(s) == 5 and s[2] == ":" and s[:2].isdigit() and s[3:].isdigit() \
            and int(s[:2]) < 24 and int(s[3:]) < 60:
        oneri.ayar_yaz("saat", s)
    if isinstance(alanlar.get("aksam_uyari"), bool):
        oneri.ayar_yaz("aksam_uyari", alanlar["aksam_uyari"])
    return oneri.ayarlar()


@app.post("/api/yikandi")
def yikandi(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    return {"temizlenen": oneri.yikandi()}


@app.get("/api/gecmis")
def gecmis(ay: str = "", x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    if not (len(ay) == 7 and ay[4] == "-"):
        ay = oneri_mod.bugun()[:7]
    return oneri.gecmis(ay)


# --- A5: bildirimler ----------------------------------------------------------
def vapid():
    yol = VERI / "vapid.pem"
    from py_vapid import Vapid01
    if not yol.exists():
        v = Vapid01()
        v.generate_keys()
        v.save_key(str(yol))
        os.chmod(yol, 0o600)
    from py_vapid.utils import b64urlencode
    from cryptography.hazmat.primitives import serialization
    v = Vapid01.from_file(str(yol))
    ham = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return str(yol), b64urlencode(ham)


@app.get("/api/push/anahtar")
def push_anahtar(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    return {"anahtar": vapid()[1]}


@app.post("/api/push/abone")
async def push_abone(istek: Request, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    abone = await istek.json()
    if not isinstance(abone, dict) or not str(abone.get("endpoint", "")).startswith("https://"):
        raise HTTPException(400)
    liste = [a for a in oneri.ayar("aboneler", []) if a.get("endpoint") != abone["endpoint"]]
    liste.append({"endpoint": abone["endpoint"], "keys": abone.get("keys", {})})
    oneri.ayar_yaz("aboneler", liste[-5:])
    return {"ok": True}


@app.post("/api/push/dene")
def push_dene(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    s = oneri.ayar("saat", "06:00")
    return {"gonderilen": bildir("Bildirimler açık 👍", f"Her sabah {s}'da günün kombinini göndereceğim.")}


def bildir(baslik: str, govde: str) -> int:
    from pywebpush import WebPushException, webpush
    yol, _ = vapid()
    kalan, sayi = [], 0
    for a in oneri.ayar("aboneler", []):
        try:
            webpush(a, json.dumps({"baslik": baslik, "govde": govde}, ensure_ascii=False),
                    vapid_private_key=yol, vapid_claims={"sub": "mailto:dolap@example.com"}, ttl=3 * 3600)
            kalan.append(a)
            sayi += 1
        except WebPushException as e:
            if getattr(e.response, "status_code", 0) not in (404, 410):
                kalan.append(a)
        except Exception:
            kalan.append(a)
    oneri.ayar_yaz("aboneler", kalan)
    return sayi


def zamanlayici():
    """Sabah: bildirimden 20 dk önce öneriler hazırlanır, saatinde gönderilir. Akşam 20:00 hava uyarısı."""
    while True:
        try:
            simdi = datetime.now(oneri_mod.TZ)
            gun = simdi.strftime("%Y-%m-%d")
            dk = simdi.hour * 60 + simdi.minute
            s = oneri.ayar("saat", "06:00")
            hedef = int(s[:2]) * 60 + int(s[3:])
            durum = oneri.ayar("zamanlayici", {})
            if hedef - 20 <= dk < hedef + 120 and durum.get("hazir") != gun:
                if not oneri.gunun(gun)["oneriler"]:
                    oneri.uret(gun)
                durum["hazir"] = gun
            if hedef <= dk < hedef + 120 and durum.get("sabah") != gun:
                baslik, govde = oneri.sabah_metni()
                bildir(baslik, govde)
                durum["sabah"] = gun
            if oneri.ayar("aksam_uyari", True) and 20 * 60 <= dk < 22 * 60 and durum.get("aksam") != gun:
                m = oneri.aksam_metni()
                if m:
                    bildir(*m)
                durum["aksam"] = gun
            oneri.ayar_yaz("zamanlayici", durum)
        except Exception as e:  # zamanlayıcı asla ölmesin
            print("zamanlayici hata:", e, flush=True)
        time.sleep(60)


@app.on_event("startup")
def baslat():
    threading.Thread(target=zamanlayici, daemon=True).start()


@app.get("/api/parcalar")
def parcalar(x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    return depo.liste()


@app.patch("/api/parca/{pid}")
def parca_duzenle(pid: int, alanlar: dict, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    if not depo.al(pid):
        raise HTTPException(status_code=404)
    yeni = depo.guncelle(pid, alanlar)
    return {**depo.al(yeni), "birlesti": yeni != pid}


@app.delete("/api/parca/{pid}")
def parca_sil(pid: int, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    depo.sil(pid)
    return {"ok": True}


@app.post("/api/parca/{pid}/yeniden")
def parca_yeniden(pid: int, x_anahtar: str | None = Header(default=None)):
    kontrol(x_anahtar)
    if not depo.al(pid):
        raise HTTPException(status_code=404)
    depo.yeniden(pid)
    return depo.al(pid)


@app.get("/resim/{pid}")
def resim(pid: int, boy: str = "k", k: str = "", x_anahtar: str | None = Header(default=None)):
    # <img> başlık gönderemez: anahtar adreste gelir (aynı adres, no-referrer)
    if not (_dogru(k) or _dogru(x_anahtar)):
        raise HTTPException(status_code=401)
    ad = {"k": f"{pid}_k.webp", "b": f"{pid}.png", "o": f"{pid}_orj.jpg"}.get(boy)
    yol = depo.foto / ad if ad else None
    if not yol or not yol.exists():
        raise HTTPException(status_code=404)
    return FileResponse(yol, headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.get("/resim/g/{gid}")
def gorunum_resmi(gid: int, boy: str = "k", k: str = "", x_anahtar: str | None = Header(default=None)):
    if not (_dogru(k) or _dogru(x_anahtar)):
        raise HTTPException(status_code=401)
    yol = depo.foto / (f"g{gid}_k.webp" if boy == "k" else f"g{gid}.png")
    if not yol.exists():
        raise HTTPException(status_code=404)
    return FileResponse(yol, headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.get("/cizim/{pid}")
def cizim_svg(pid: int, k: str = "", x_anahtar: str | None = Header(default=None)):
    # adres, çizimi etkileyen alanların özetini (h=) taşır; değişince yeni adres olur
    if not (_dogru(k) or _dogru(x_anahtar)):
        raise HTTPException(status_code=401)
    p = depo.al(pid)
    if not p:
        raise HTTPException(status_code=404)
    return Response(cizim.svg(p), media_type="image/svg+xml",
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def ana_sayfa(k: str = ""):
    # Anahtar adreste varsa manifest bağlantısı daha ilk HTML'de anahtarlı gelir;
    # Safari "Ana Ekrana Ekle" derken JS'in değiştirmesini beklemez.
    html = (WEB / "index.html").read_text(encoding="utf-8")
    if _dogru(k):
        html = html.replace('href="/manifest.webmanifest"', f'href="/manifest.webmanifest?k={k}"', 1)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def manifest(k: str = ""):
    # Anahtar doğruysa ana ekrandan açılış adresine eklenir; böylece
    # Safari'den ana ekrana eklenen uygulama eşlenmiş olarak açılır.
    baslangic = f"/?k={k}" if _dogru(k) else "/"
    veri = {
        "name": "Dolap",
        "short_name": "Dolap",
        "lang": "tr",
        "start_url": baslangic,
        "scope": "/",
        "display": "standalone",
        "background_color": "#F6F3EE",
        "theme_color": "#F6F3EE",
        "icons": [
            {"src": "/ikon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/ikon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    return JSONResponse(veri, media_type="application/manifest+json",
                        headers={"Cache-Control": "no-store"})


@app.get("/sw.js")
def sw():
    return FileResponse(WEB / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
