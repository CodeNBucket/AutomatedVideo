# AutomatedVideo

Konu yaz, dakikayı söyle, video çıksın. Elle hiçbir şey yapmadan.

```
python -m autovideo --tema godfather --konu "1957 Apalachin toplantısı" --dakika 3
python -m autovideo --tema sopranos --konu "New Jersey'de çöp işinin mafyayla ilişkisi" --dakika 5
python -m autovideo --tema godfather --konu "Lucky Luciano'nun yükselişi" --dakika 4 --dil tr
```

Ne yapıyor:

1. **Metin**: DeepSeek anlatım metnini yazar ve her cümle için bir görüntü arama sorgusu üretir
   (`DEEPSEEK_API_KEY` ortam değişkeninden ya da `.env` dosyasından okunur).
2. **Ses**: açık kaynak [Kokoro-82M](https://github.com/thewh1teagle/kokoro-onnx) (Apache-2.0) İngilizce okur,
   GPU gerekmez; model ilk çalıştırmada `models/` klasörüne iner (~350 MB). Türkçe için `--dil tr`
   edge-tts kullanır (ücretsiz Microsoft sesi, internet ister); tamamen çevrimdışı Türkçe için
   `--ses-motoru piper --ses tr_TR-dfki-medium`.
3. **Görüntü**: Wikimedia Commons (yalnızca serbest lisans / kamu malı) ve Internet Archive'daki kamu
   malı / Prelinger filmlerinden önce video, yoksa fotoğraf (yavaş zoom ile) seçilir. Kendi
   kliplerin varsa `--yerel klasör`.
4. **Montaj**: tema rengine göre renk ayarı, gren, vinyet, geçişler (fadeblack/dissolve/kesme),
   altyazı, konuşma girince kısılan müzik (Commons'tan kamu malı müzik ya da `--muzik dosya.mp3`).

Çıktı `out/<tarih>-<konu>/` altında: video, `script.json`, `description.txt` (YouTube açıklaması +
gerekli atıflar), `credits.txt`.

## Görüntüler hakkında dürüst not

Godfather ve Sopranos sahneleri telifli; telifsiz versiyonları yok. Tema bu yüzden o dünyanın
**gerçek** görüntülerini arar: 1930-50'ler New York ve Little Italy, Sicilya, gerçek mafya
babalarının kamu malı FBI/polis fotoğrafları, New Jersey yerleri, eski kamu malı filmler.
CC BY lisanslı dosyalar atıf ister; `description.txt` bunu hazır yazar.

## Kurulum

Python 3.10+:

```
pip install -r requirements.txt
```

ffmpeg PATH'te yoksa `imageio-ffmpeg` paketindeki kullanılır.

Temalar `autovideo/themes.py` içinde (godfather, sopranos, peaky blinders); başka her tema adı da
çalışır, DeepSeek sorguları o temaya göre yazar.

Eski tek dosyalık sürüm (`youtube.py`: alıntılar + AllTalk + YouTube yükleme) olduğu gibi duruyor.
