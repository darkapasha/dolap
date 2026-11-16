# 👕 Dolap — kişisel kombin asistanı

Aynada çektiğin bir boy fotoğrafından kıyafetlerini tek tek ayırır, dolabını kurar ve
**her sabah havaya göre 3 kombin** önerir. iPhone'da ana ekrana eklenen bir web uygulaması (PWA);
yapay zekâ kısmı tamamen kendi sunucunda çalışır, hiçbir ücretli servis kullanmaz.

## Ne yapıyor?

| | |
|---|---|
| 📸 **Ayna fotoğrafı → parçalar** | SegFormer (Fashionpedia) üstü, altı, dış giyimi, ayakkabıyı ayırır; gemma3:4b her parçaya ad, tür, kalınlık, resmiyet ve mevsim yazar. Renkler piksellerden bulunur. |
| ✅ **Onay ekranı** | Fotoğraftan çıkan parçalar önce onaya düşer: yanlış çıkanı at, türünü düzelt, isim ver. Aynı isim = aynı kıyafet, fotoğraflar birleşir. |
| 🎨 **Çizim görünümü** | Bulanık kesikler yerine her kıyafet türüne ve rengine göre SVG çizimle gösterilir. |
| ☀️ **Sabah önerisi** | Open-Meteo havası, mevsim, gün (günlük / iş / spor / evde / özel gün), renk uyumu, son günlerde giyilenler ve beğenilerin puanlanır; birbirinden farklı 3 kombin seçilir. |
| 🔔 **Bildirim** | Sabah seçtiğin saatte "Günün kombini hazır", akşam 20:00'de ertesi gün yağmur/soğuk varsa uyarı (Web Push). |
| 👍 **Öğrenme** | Beğen / beğenme / giydim; parça ve parça çifti puanları zamanla zevkini öğrenir. |
| 🧺 **Kirli takibi** | Giydiğin parça türüne göre (tişört 1, kazak 3, kot 4 giyim…) kirliye düşer; "Yıkadım" ile hepsi temiz. |
| 📅 **Geçmiş** | Hangi gün ne giydiğin ay ay takvimde. |
| ⚠️ **Eksik parça uyarısı** | "Dolabında ayakkabı yok", "yağmur var ama yağmurluğun yok" gibi. |

## Nasıl çalışıyor?

```
iPhone (PWA)  ──HTTPS──>  Caddy  ──>  FastAPI (main.py)
                                       ├─ parca.py   fotoğraf kuyruğu, SQLite, rembg kesme, gemma etiketleri
                                       ├─ kombin.py  SegFormer ile ayna fotoğrafını parçalara ayırma
                                       ├─ renk.py    piksellerden Türkçe renk adları
                                       ├─ cizim.py   türe ve renge göre SVG çizim
                                       └─ oneri.py   hava + kurallar + öğrenme, giyim geçmişi, bildirim metinleri
```

- Tek kullanıcı: telefon bir kere QR ya da 6 haneli kodla eşlenir, her istek gizli bir anahtar taşır.
- Fotoğraflar yalnızca sunucuda durur. Dışarıya yalnızca ~1 km'ye yuvarlanmış konum gider (hava için).
- Öneri motoru kural tabanlıdır ve milisaniyeler sürer; ortamı değiştirince anında yeni kombin gelir.

## Kurulum (özet)

ARM Ubuntu sunucuda (GPU gerekmez):

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt pywebpush
# CPU torch: venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch
ollama pull gemma3:4b
bash kur.sh        # systemd servisi + Caddy bloğu (kur.sh içindeki alan adını kendininkiyle değiştir)
```

Gizli anahtar (`veri/anahtar.txt`), bildirim anahtarı (`veri/vapid.pem`) ve veritabanı ilk
çalıştırmada `veri/` içinde oluşur; bu klasör depoya girmez.

Ayrıntılı tasarım ve aşamalar: [PLAN.md](PLAN.md)

---
Claude Code ile birlikte geliştirildi.
