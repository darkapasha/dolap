# Dolap — kişisel kombin uygulaması (plan)

Tarih: 2026-11-06 · Durum: 1.0 kullanımda (2026-11-17)

## Anket kararları

| Konu | Karar |
|---|---|
| Platform | iPhone PWA (Safari → Ana Ekrana Ekle) |
| Fotoğraf | Hepsi desteklenecek; **ana yol: aynada üzerimdeki kombin fotoğrafı** → parçalara ayrılır. Ek: tek parça fotoğrafı, dolap fotoğrafı |
| Önizleme | Kolaj (arka planı silinmiş parçalar). Gerçekçi giydirme **şimdilik yok** (ileride Gemini görsel ya da try-on API eklenebilir) |
| Yapay zeka | Oracle sunucusundaki modeller (Ollama + CPU modelleri) |
| Sabah | PWA bildirimi (Web Push) |
| Kurallar | Hava durumu, tekrar etmeme, ortam/etkinlik, beğenilerden öğrenme (+ kirli/yıkamada işareti) |
| Seçenek sayısı | 3 kombin (1 ana + 2 alternatif) |

## Mimari

```
iPhone (PWA)  ──HTTPS──►  Oracle sunucu (ARM, 24 GB, GPU yok)
                          ├─ Caddy (HTTPS, otomatik sertifika)  → PWA dosyalarını da sunar
                          ├─ FastAPI (dolap-api, systemd)
                          │   ├─ /yukle    fotoğraf → parçalar
                          │   ├─ /dolap    parçalar, etiketler, durum
                          │   ├─ /oneri    günün 3 kombini
                          │   └─ /geri     beğen / beğenme / giydim
                          ├─ Bölütleme: SegFormer "clothes" (üst, alt, elbise, ayakkabı, çanta, şapka…)
                          ├─ Arka plan silme: rembg (u2net / isnet)
                          ├─ Etiketleme + öneri metni: Ollama gemma3:4b (görselleri anlıyor)
                          ├─ Hava: Open-Meteo (anahtar gerektirmez)
                          ├─ Zamanlayıcı: her sabah kombin üret → Web Push (pywebpush, VAPID)
                          └─ SQLite + fotoğraf klasörü
```

**Neden PWA da sunucudan sunuluyor?** github.io'dan sunucuya istek atmak hem HTTPS hem CORS ayarı ister (Panel'deki CORS derdi). Uygulama ile API aynı adresten gelirse bu sorun hiç çıkmaz. iPhone bildirimleri için de HTTPS zorunlu.
**Alan adı:** hesap gerektirmeyen **sslip.io** kullanılır. Sunucunun IP'si adresin içine yazılır (örn. `1-2-3-4.sslip.io`), Caddy bu adrese otomatik HTTPS sertifikası alır.
**Gereken:** Oracle güvenlik listesinde 80/443 portlarının açılması (Oracle web panelinden; sunucudaki iptables'ı ben açarım).

**Kullanıcı:** tek kişi (sen). Hesap/kayıt sistemi yok, cihaz bir kere gizli anahtarla eşlenir.

## Akışlar

### 1. Kombin fotoğrafı ekleme (ana yol)
1. Aynanın karşısında boy fotoğrafı çek → yükle.
2. Sunucu SegFormer ile pikselleri sınıflara ayırır: üst, alt, elbise, dış giyim, ayakkabı, aksesuar.
3. Her parça kırpılır, arka planı silinir, PNG olarak kaydedilir.
4. gemma3 her parçayı etiketler: tür, renk(ler), desen, kalınlık (yazlık/kışlık), resmiyet (spor → resmi), mevsim.
   **Tür listesi sabit değil:** model türü kıyafete bakarak serbestçe yazar ("kapüşonlu sweatshirt", "kargo pantolon", "forma"). Öneri motoru için her tür ayrıca bir **yuvaya** konur: üst, alt, tek parça (elbise/tulum), dış giyim, ayakkabı, aksesuar. Yuvayı da model seçer; yanlışsa onay ekranında düzeltirsin.
5. Telefonda **onay ekranı**: bulunan parçalar kart olarak gelir; düzelt, sil, "bu zaten dolabımda" ile var olan parçayla birleştir (aynı tişört iki kez girilmesin — görsel benzerlik ile öneri yapılır).
6. Fotoğraf aynı zamanda "giyilmiş kombin" olarak kaydedilir → beğenilen kombin örneği olur.

Not: aynadaki fotoğrafta kesimler tek parça fotoğrafından kirli olur (kol arkada, katlanma). Onay ekranında "bu parçayı yeniden çek" seçeneği olacak.

### 2. Tek parça / dolap fotoğrafı
- Tek parça: zemine serilmiş → doğrudan rembg + etiket. En temiz sonuç.
- Dolap/yığın: sunucu birden çok nesne bulmaya çalışır, hepsi onay ekranına düşer. En hatalı yol, yardımcı olarak kalır.

### 3. Sabah önerisi
1. Kalkış 06:00 → sunucu **05:40**'ta üretmeye başlar, bildirim 06:00'da gelir (Ayarlar'dan değiştirilebilir). Radyo işleri 08:00/08:10'da olduğu için CPU çakışması yok.
2. Hava: o günün en düşük/en yüksek sıcaklığı, yağmur ihtimali, rüzgar. Hava, **telefonun konumuna** göre alınır (aşağıdaki "Konum" bölümü).
3. Ortam: varsayılan haftalık plan (örn. hafta içi iş, hafta sonu rahat); sabah uygulamadan değiştirilebilir → yeniden üretir.
4. **Aday üretimi (kural, hızlı):** temiz parçalardan geçerli kombinler (üst+alt+ayakkabı ya da elbise+ayakkabı, gerekirse dış giyim).
5. **Puanlama:**
   - sıcaklık uyumu (kalınlık ve katman sayısı)
   - yağmur → su geçirmez dış giyim ve ayakkabı
   - resmiyet ↔ ortam
   - renk uyumu (nötr + bir vurgu, ton-sür-ton, çakışan desenler eksi)
   - tekrar cezası (son 3-7 günde giyilen parça)
   - öğrenilen zevk (beğenilen/beğenilmeyen parça çiftleri)
6. İlk 10 aday gemma3'e gider. Model 3 farklı kombin seçer ve her biri için kısa bir Türkçe açıklama yazar ("Hava 9°, akşam yağmur var; lacivert mont + gri kazak").
7. Kolaj resimleri üretilir (sunucuda Pillow ile) → Web Push: "Günün kombini hazır 👕".

### 4. Geri bildirim
- Her kombin: 👍 / 👎 / **Giydim**.
- Parça durumu: temiz / kirli / yıkamada. "Giydim" sonrası N giyimde kirliye düşebilir (parça türüne göre).
- Öğrenme: başta basit puan tablosu (parça ve çift bazında). Veri birikince küçük bir sıralama modeli (LightGBM) denenebilir.

## Konum (şehri elle girmek yerine)
- Uygulama ilk açılışta konum izni ister (iPhone'da "Uygulamayı Kullanırken" izni yeterli).
- Uygulamayı her açtığında konum yenilenir ve sunucuya kaydedilir. Kayıttan önce koordinatlar ~1 km'ye yuvarlanır, tam adres saklanmaz.
- Sabah önerisi uygulama kapalıyken hazırlanır. Bu yüzden telefonun o anki konumu okunamaz, **son bilinen konum** kullanılır. Başka şehre gidince uygulamayı bir kez açman yeterli; o akşamdan itibaren yeni şehrin havası kullanılır.
- Şehir adı (ekranda "İstanbul, 9°" gibi görünsün diye) koordinattan bulunur. Bunun için anahtar istemeyen bir ters adres servisi kullanılır (BigDataCloud ya da OpenStreetMap Nominatim).
- İzin verilmezse Ayarlar'dan şehir elle seçilir.

## Ekranlar (PWA)
1. **Bugün:** hava özeti, ortam seçici, 3 kombin kolajı (kaydırmalı), 👍👎 Giydim, "başka öner".
2. **Dolap:** parça ızgarası; tür/renk/mevsim filtresi; temiz/kirli rozeti.
3. **Ekle:** kamera/galeri → işleniyor → onay ekranı.
4. **Kombin geçmişi:** giydiğin günler takvimi.
5. **Ayarlar:** konum (otomatik; izin yoksa elle şehir), kalkış saati, haftalık ortam planı, bildirim izni, tarz notları (sevdiğin/sevmediğin renkler, "şort giymem" gibi kurallar).

## Gizlilik
- Fotoğraflar yalnızca senin sunucunda durur. Dışarıya yalnızca ~1 km'ye yuvarlanmış koordinat gider: hava durumu için Open-Meteo'ya, şehir adı için ters adres servisine.
- Uygulamaya giriş: tek kullanıcılı olduğu için uzun bir gizli anahtar (ilk açılışta QR/bağlantı ile cihaza kaydedilir).

## Aşamalar
1. **A1 — Altyapı:** ✅ 2026-11-06. Adres `https://SUNUCU-IP.sslip.io` (Caddy 2.11, otomatik sertifika). Sunucuda `~/dolap` (main.py, web/, venv, veri/anahtar.txt), servis `dolap-api` (uvicorn 127.0.0.1:8090). Yerel kopya `dolap/sunucu/`; güncelleme = dosyaları scp ile `~/dolap`'a at, `sudo systemctl restart dolap-api`. Eşleme bağlantısı + QR: `dolap/esleme.txt`, `dolap/esleme.png` (gizli, paylaşma). Ana ekrana eklerken manifest `start_url` anahtarı taşır, böylece iPhone'da Safari ile ana ekran uygulamasının ayrı depolaması sorun olmaz.
2. **A2 — Tek parça ekleme:** ✅ 2026-11-07. `parca.py`: SQLite `veri/dolap.db` (tablo `parca`), fotolar `veri/foto/{id}_orj.jpg`, `{id}.png` (kesik), `{id}_k.webp` (küçük). Tek iş parçacığı sırayla işler: rembg `isnet-general-use` (~3 sn), gemma3:4b JSON şemalı etiket (~60 sn CPU'da). Yuva, tür adındaki kelimeden düzeltilir (model tişörte "tek parça" demişti). API: `POST /api/parca` (ham JPEG), `GET /api/parcalar`, `PATCH/DELETE /api/parca/{id}`, `POST /api/parca/{id}/yeniden`, `GET /resim/{id}?boy=k|b|o&k=` (img başlık gönderemediği için anahtar adreste). PWA: Ekle (kamera/galeri, telefonda 1600 px JPEG'e küçültür), Dolap ızgarası + yuva filtresi, detay sayfası (düzenle, temiz/kirli, yeniden işle, sil). 4 sn'de bir yoklar.
3. **A3 — Ayna fotoğrafından ayırma:** ✅ (ilk hali) 2026-11-07. `kombin.py`: SegFormer `sayeed99/segformer-b3-fashion` (Fashionpedia 46 sınıf, torch CPU, ~2 sn/geçiş). Kişi küçükse çevresi kırpılıp ikinci kez bakılır. Kol/kapüşon/fermuar dış giyime (yoksa üste), cep/yaka gibi parçalar değdiği giysiye bağlanır. `renk.py`: renkler piksellerden (Lab k-ortalama, Türkçe renk adları). Etiketler tüm parçalar için **tek** gemma çağrısında (~90 sn): ona sınıf adı ipucu verilmez (verilince kapüşonluya "ceket" dedi), sadece katman + renk. Tablo `kombin`, `parca.kaynak`. API `POST /api/kombin`, `GET /api/kombinler`, `DELETE /api/kombin/{id}`. Ekle'de ana kart "Üzerimdeki kombin". İlk deneme (Salim'in fotoğrafı): kapüşonlu, forma, kot, ayakkabı ayrı çıktı; formaya bazen "tişört" diyor. **Kalan:** ayrı onay ekranı yok (parçalar direkt dolaba girer, yanlışı silinir).
   **A3.1 (2026-11-08):** Salim kesik fotoğrafları beğenmedi → Google'da benzerini aratma yerine (ücretsiz API yok) **çizim** seçti. `cizim.py`: tür+açıklamadan kalıp (tişört, forma, polo, gömlek, sweat, kazak, kapüşonlu/fermuarlı, ceket, kaban, mont, hırka, yelek, pantolon, kot, kargo, eşofman, tayt, şort, etek, elbise, spor ayakkabı, bot, şapka, bere, kemer, çanta) + renk tablosundan renkler + desen (çizgili/kareli/çiçekli/baskılı). `GET /cizim/{id}?h=` SVG; `h` sunucunun özeti (`cizim.SURUM` artınca önbellek kırılır). Varsayılan: kombinden gelen parça çizim, tek parça foto; detayda "Görsel: Çizim/Fotoğraf". **İsim:** `parca.isim` kullanıcının verdiği ad; aynı isim (büyük/küçük harf, boşluk farkı yok) = aynı kıyafet → `birlestir`: yeni parçanın kesiği eskisinin `gorunum`ü olur (`g{id}.png`), satırı silinir, eskinin etiketleri kalır. Dolap'ta "İsim ver" kartı (öneri çipleri: aynı yuvada ortak renkli isimli parçalar). cairosvg sunucuda kurulu (kolaj için). DB yedeği `veri/dolap.db.a3yedek`.
4. **A4 — Öneri motoru:** ✅ 2026-11-17 (sürüm 1.0). `oneri.py`: kural tabanlı, milisaniyeler sürer (gemma yok; sabah ortam değişince anında yeniler). Adaylar: üst+alt ya da tek parça, ± dış giyim, ± ayakkabı (soğukta bere/atkı). Puan: sıcaklık (kalınlık toplamı ↔ hissedilen sıcaklık), dış giyim gerekliliği, yağmur (su geçirmez dış/bot +, kanvas/süet −), mevsim, ortam↔resmiyet, renk (nötr + 1 vurgu iyi, 2 desenli −), tekrar cezası (son 2/6/14 gün), öğrenilen zevk. 3 öneri, birbirinden en az bir ana parça farklı. Açıklama şablonla yazılır. Hava Open-Meteo (2 saat önbellek), şehir adı BigDataCloud, elle şehir Open-Meteo geocoding. Kolaj istemcide, hep çizimlerle (Salim'in seçimi). Ortam her sabah elle seçilir (Günlük / İş-okul / Spor / Evde / Özel gün); varsayılan günlük. Eksik parça uyarıları Bugün'de.
5. **A5 — Sabah bildirimi:** ✅ 2026-11-17. Web Push (pywebpush, `veri/vapid.pem`, aboneler `ayar` tablosunda). Zamanlayıcı iş parçacığı: bildirim saatinden 20 dk önce öneri hazır, saatinde push (varsayılan 06:00, Ayarlar'dan değişir). Akşam 20:00 yarın için hava uyarısı (yağmur ≥%60, 5°+ soğuma, kar, ≤5° ya da ≥32°), kapatılabilir.
6. **A6 — Öğrenme:** ✅ 2026-11-17. 👍/👎/Giydim → `zevk` tablosu (parça ve parça çifti puanı, −4..4). Giydim → `giyim` tablosu (gün başına bir kombin, takvim buradan), parça sayacı türe göre kirliye düşer (tişört/forma 1, gömlek/elbise 2, kazak/hırka/pantolon 3, kot 4, dış giyim/ayakkabı/aksesuar hiç); geri alınca kirlenen temize döner. Dolap'ta "Kirli sepeti → Yıkadım".
   **Onay ekranı:** kombin fotoğrafından çıkan parçalar `bekliyor=1` ile gelir; Dolap'ın üstünde fotoğraflarıyla listelenir: çıkar, yuva düzelt, isim ver (aynı isim = birleştir), "bugün bunu giydim". Onaylanmadan öneriye girmez.
   **Etiket kayması düzeltmesi:** gemma etiketleri parça sırasından farklı döndürebiliyor → `etiketleri_esle` türdeki kelimeyle (ve eşitlikte renkle) yer değiştirir. Kombin 4'ün kaymış etiketleri elle düzeltildi, parçaları onaya düştü.
   **Geçmiş takvimi:** Bugün ekranının altında ay ay; gün dokununca o günün parçaları.
7. **İleride:** "Üstümde göster" (Gemini görsel / try-on API), takvimden etkinlik okuma.

## Kararlaşanlar (son tur)
- Ad: **Dolap** (önemli değil, tek kullanıcı).
- Kalkış 06:00 → öneri 05:40'ta hazırlanır, bildirim 06:00.
- Şehir: telefon konumundan.
- Alan adı: sslip.io (hesapsız).
- Kıyafet türleri: model kıyafete göre kendisi seçer, sabit liste yok.

Açık soru kalmadı. Sıradaki iş: A1.
