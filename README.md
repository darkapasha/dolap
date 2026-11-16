# 👕 Dolap — kişisel kombin asistanı

> Aynaya geç, bir fotoğraf çek. Dolap üzerindeki her parçayı ayırır, dolabını kendisi kurar ve
> **her sabah havaya göre 3 kombin** önerir.

iPhone'da ana ekrana eklenen bir web uygulaması (PWA). Bütün yapay zekâ kendi sunucumda çalışır:
fotoğraflar hiçbir yere gönderilmez, hiçbir ücretli servis kullanılmaz.

---

## Bir günün akışı

```
06:00  🔔 "Günün kombini hazır 👕 · İstanbul 13°/17°"
       "Lacivert mont + gri kazak + siyah kot. Yağmur var, dış katmanın hazır."
       ↓
       Uygulamayı açarsın → "Bugün nereye?"  [Günlük] [İş/okul] [Spor] [Evde] [Özel gün]
       Seçimine göre 3 kombin anında yenilenir (kaydırarak bakarsın)
       ↓
       👍 / 👎 / Giydim  → zevkin öğrenilir, giydiklerin takvime yazılır
       ↓
20:00  🔔 (sadece gerekirse) "Yarın yağmur ihtimali %80 ☔"
```

## Özellikler

### 📸 Ayna fotoğrafından dolap
- Boy aynasında çekilmiş tek fotoğraf; üst, alt, dış giyim, ayakkabı ve aksesuarlar **ayrı ayrı parça** olur.
- Ayırma: **SegFormer** (Fashionpedia veri setiyle eğitilmiş, 46 giysi sınıfı). Kişi fotoğrafta küçükse çevresi kırpılıp ikinci kez bakılır.
- Etiket: **gemma3:4b** (görsel model) her parçaya ad, tür, desen, kalınlık, resmiyet ve mevsim yazar.
- Renk: pikseller kümelenir ve Türkçe renk adına çevrilir (lacivert, haki, bordo, kot mavisi...).
- Model etiketleri bazen parça sırasından farklı döndürüyor; türdeki kelimeye ve renge bakarak doğru parçaya yeniden eşlenir.
- Tek parça fotoğrafı da olur (düz zemine serilmiş kıyafet): arka planı **rembg** ile silinir.

### ✅ Onay ekranı
Fotoğraftan çıkan parçalar dolaba girmeden önce fotoğraflarıyla gösterilir. Yanlış çıkanı atarsın, türü yanlışsa
yuvasını düzeltirsin, istersen isim verirsin. **Aynı isim = aynı kıyafet**: yeni fotoğraf eskisine eklenir,
dolapta iki tane olmaz. "Bu kombini bugün giydim" kutusu da var.

### 🎨 Çizim görünümü
Ayna fotoğrafından kesilen parçalar bulanık oluyordu. Onun yerine her parça türüne ve rengine göre
temiz bir **SVG çizimle** gösterilir: tişört, forma, polo, gömlek, kapüşonlu, ceket, kaban, hırka, kot, kargo,
eşofman, şort, etek, elbise, spor ayakkabı, bot, şapka, bere, kemer, çanta... Çizgili, kareli, çiçekli desenler dahil.
Kombin kolajları da bu çizimlerle yapılır.

### ☀️ Öneri motoru
Kural tabanlı, milisaniyeler sürer. Önce bütün geçerli kombinler çıkarılır (üst + alt ya da tek parça,
gerekirse dış giyim, ayakkabı; çok soğukta bere/atkı), sonra her biri puanlanır:

| Ölçüt | Nasıl |
|---|---|
| 🌡️ Sıcaklık | Parçaların kalınlık toplamı, günün **hissedilen** sıcaklığına göre hedefle karşılaştırılır |
| 🧥 Dış giyim | 15°'nin altında dış katmansız kombin ceza alır, 22°'nin üstünde dış katman ceza alır |
| ☔ Yağmur | Su geçirmez dış giyim ve bot artı; kanvas/süet ayakkabı eksi |
| 🍂 Mevsim | Mevsimine uymayan parça eksi |
| 👔 Ortam | Parçaların resmiyeti seçtiğin güne göre (özel günde eşofman olmaz) |
| 🎨 Renk | Nötrler + en fazla bir vurgu rengi iyi; iki desenli parça birbiriyle çakışır |
| 🔁 Tekrar | Son 2 günde giyilen ağır, son hafta hafif ceza |
| ❤️ Zevk | 👍/👎/Giydim'den öğrenilen parça ve **parça çifti** puanları |

En iyi 3 kombin, birbirinden en az bir ana parçada farklı olacak şekilde seçilir. "Başka öner" daha önce gösterilmeyenleri getirir.

### 🔔 Bildirimler (Web Push)
- **Sabah**, seçtiğin saatte (varsayılan 06:00): günün kombini, hava ve kısa açıklama. Öneriler 20 dakika önceden hazırlanır.
- **Akşam 20:00**, sadece gerekirse: yarın yağmur, kar, sert soğuma ya da çok sıcak varsa. Yağmur var ve montun kirliyse onu da söyler.

### 🧺 Kirli takibi
"Giydim" deyince parçalar türüne göre sayılır ve sınıra gelince kendiliğinden **kirli** olur:

| Tür | Kaç giyimde kirli |
|---|---|
| Tişört, forma, polo, şort | 1 |
| Gömlek, elbise | 2 |
| Kazak, hırka, sweatshirt, pantolon, eşofman | 3 |
| Kot | 4 |
| Mont, ceket, ayakkabı, aksesuar | hiç (elle işaretlenir) |

Kirliler öneriye girmez. Dolap'taki "Kirli sepeti → Yıkadım" ile hepsi temize döner. "Giydim"i geri alırsan kirlenen de geri temizlenir.

### 📅 Geçmiş ve uyarılar
- Ay ay takvim: her güne o gün giydiğin kombinin çizimi düşer, dokununca parçaları görünür.
- **Eksik parça uyarısı:** "Dolabında hiç ayakkabı yok", "Hava serin ama dış giyimin yok", "Temiz üstün kalmadı, çamaşır günü 🧺".

## Mimari

```
iPhone (PWA)  ──HTTPS──>  Caddy  ──>  FastAPI (main.py)  ──>  SQLite (veri/dolap.db)
                                       │
                                       ├─ parca.py    fotoğraf kuyruğu (tek iş parçacığı), rembg, gemma etiketleri, onay, birleştirme
                                       ├─ kombin.py   SegFormer ile ayna fotoğrafını parçalara ayırma (torch, CPU)
                                       ├─ renk.py     Lab uzayında k-ortalama → Türkçe renk adı
                                       ├─ cizim.py    türe ve renge göre SVG çizim
                                       ├─ oneri.py    hava, puanlama, öğrenme, giyim geçmişi, bildirim metinleri
                                       └─ zamanlayıcı sabah hazırlık + push, akşam hava uyarısı
                                       │
                                       ├─ Ollama (gemma3:4b)   yerel görsel model
                                       ├─ Open-Meteo           hava (anahtarsız)
                                       └─ BigDataCloud         koordinattan şehir adı (anahtarsız)
```

- **GPU yok:** 4 çekirdekli ARM sunucuda çalışıyor. Bir ayna fotoğrafı ~1,5 dakikada parçalanıp etiketlenir; telefon bu sırada ilerlemeyi gösterir.
- **Tek kullanıcı:** Telefon bir kere QR ya da 6 haneli kodla eşlenir; her istek gizli bir anahtar taşır.
  iPhone'da ana ekran uygulaması Safari'den ayrı depolama kullandığı için kodla eşleme bunun için var.
- **Gizlilik:** Fotoğraflar sadece sunucuda. Dışarıya yalnızca ~1 km'ye yuvarlanmış konum gider (hava için).

## Kurulum

ARM ya da x86 Ubuntu sunucu (GPU gerekmez):

```bash
python3 -m venv venv
venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch
venv/bin/pip install -r requirements.txt pywebpush
ollama pull gemma3:4b
bash kur.sh        # systemd servisi + Caddy bloğu (kur.sh içindeki alan adını kendininkiyle değiştir)
```

Gizli anahtar (`veri/anahtar.txt`), bildirim anahtarı (`veri/vapid.pem`), veritabanı ve fotoğraflar ilk
çalıştırmada `veri/` içinde oluşur; bu klasör depoya girmez.

Tasarım kararları ve aşama aşama geliştirme günlüğü: [PLAN.md](PLAN.md)

---

Claude ile birlikte, vibe coding ile yapıldı 🎧
