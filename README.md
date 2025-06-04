# Long to Short Video Converter

Bu uygulama, uzun YouTube videolarını analiz ederek viral potansiyeli olan kısımları tespit eder ve bunlardan Shorts formatında videolar oluşturur.

## Özellikler

- YouTube videolarını indirme
- Otomatik altyazı çıkarma
- ChatGPT ile içerik analizi
- Viral kısımları tespit etme
- Shorts formatında video oluşturma

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. `.env` dosyası oluşturun ve OpenAI API anahtarınızı ekleyin:
```
OPENAI_API_KEY=your_api_key_here
```

## Kullanım

1. Uygulamayı çalıştırın:
```bash
python main.py
```

2. İstendiğinde YouTube video URL'sini girin
3. Uygulama otomatik olarak:
   - Videoyu indirecek
   - Altyazıları çıkaracak
   - İçeriği analiz edecek
   - Shorts videoları oluşturacak

## Gereksinimler

- Python 3.8+
- OpenAI API anahtarı
- İnternet bağlantısı 
