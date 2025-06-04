import os
from dotenv import load_dotenv
import yt_dlp
from openai import OpenAI
from moviepy.editor import VideoFileClip
import json

# .env dosyasından API anahtarlarını yükle
load_dotenv()

# OpenAI istemcisini oluştur
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
OPENAI_MODEL = os.getenv('OPENAI_MODEL')

def download_video(url):
    """YouTube videosunu indirir"""
    ydl_opts = {
        'format': 'best[ext=mp4]',
        'outtmpl': 'video.mp4',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'force_generic_extractor': False,
        'writesubtitles': True,  # Altyazıları indir
        'writeautomaticsub': True,  # Otomatik altyazıları da indir
        'subtitleslangs': ['tr', 'en'],  # Türkçe ve İngilizce altyazıları indir
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return 'video.mp4', info
    except Exception as e:
        print(f"Video indirme hatası: {str(e)}")
        print("Alternatif indirme yöntemi deneniyor...")
        ydl_opts = {
            'format': 'best',
            'outtmpl': 'video.mp4',
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['tr', 'en'],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return 'video.mp4', info

def extract_subtitles(info):
    """Video bilgilerinden altyazıları çıkarır"""
    try:
        print("Mevcut altyazı dilleri:", list(info.get('subtitles', {}).keys()))
        print("Mevcut otomatik altyazı dilleri:", list(info.get('automatic_captions', {}).keys()))
        
        # Önce Türkçe altyazıyı dene
        if 'tr' in info.get('subtitles', {}):
            subtitles = info['subtitles']['tr']
            if isinstance(subtitles, list) and len(subtitles) > 0:
                if 'data' in subtitles[0]:
                    return subtitles[0]['data']
                elif 'ext' in subtitles[0]:
                    return subtitles[0]['ext']
        
        # Türkçe yoksa İngilizce altyazıyı dene
        if 'en' in info.get('subtitles', {}):
            subtitles = info['subtitles']['en']
            if isinstance(subtitles, list) and len(subtitles) > 0:
                if 'data' in subtitles[0]:
                    return subtitles[0]['data']
                elif 'ext' in subtitles[0]:
                    return subtitles[0]['ext']
        
        # Hiçbiri yoksa otomatik altyazıyı dene
        if 'en' in info.get('automatic_captions', {}):
            auto_captions = info['automatic_captions']['en']
            if isinstance(auto_captions, list) and len(auto_captions) > 0:
                if 'data' in auto_captions[0]:
                    return auto_captions[0]['data']
                elif 'ext' in auto_captions[0]:
                    return auto_captions[0]['ext']
        
        # Altyazı bulunamadıysa
        print("Uyarı: Hiç altyazı bulunamadı!")
        return ""
        
    except Exception as e:
        print(f"Altyazı çıkarma hatası: {str(e)}")
        print("Hata detayları:")
        import traceback
        traceback.print_exc()
        return ""

def analyze_content(text):
    """ChatGPT ile içeriği analiz eder ve viral kısımları belirler"""
    if not text:
        raise Exception("Altyazı metni boş!")
        
    prompt = f"""
    Aşağıdaki video altyazısını analiz et ve en ilgi çekici, viral olabilecek kısımları belirle.
    Yanıtını KESİNLİKLE aşağıdaki JSON formatında ver:

    [
        {{
            "start_time": 0,
            "end_time": 30,
            "reason": "Bu kısımda ilgi çekici bir an var"
        }},
        {{
            "start_time": 45,
            "end_time": 75,
            "reason": "Bu kısımda komik bir sahne var"
        }}
    ]

    Önemli kurallar:
    1. Yanıtın SADECE JSON array olmalı
    2. Her kısım için start_time ve end_time saniye cinsinden olmalı
    3. Her kısım 15-60 saniye arası olmalı
    4. En fazla 5 viral kısım belirle
    5. Başka hiçbir açıklama ekleme, sadece JSON döndür

    Altyazı:
    {text}
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content.strip()
        print("ChatGPT yanıtı:", content)  # Debug için yanıtı yazdır
        
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"JSON ayrıştırma hatası: {str(e)}")
        print("Alınan yanıt:", content)
        raise
    except Exception as e:
        print(f"Beklenmeyen hata: {str(e)}")
        raise

def create_shorts(video_path, viral_parts):
    """Viral kısımlardan Shorts videoları oluşturur"""
    video = VideoFileClip(video_path)
    
    for i, part in enumerate(viral_parts):
        start_time = part['start_time']
        end_time = part['end_time']
        
        # Kısa video klibi oluştur
        clip = video.subclip(start_time, end_time)
        
        # Dikey formata dönüştür (9:16 aspect ratio)
        w, h = clip.size
        new_h = int(w * (16/9))
        clip = clip.resize(height=new_h)
        
        # Merkeze hizala
        clip = clip.set_position(('center', 'center'))
        
        # Arka plan ekle
        background = VideoFileClip(video_path).subclip(start_time, end_time)
        background = background.resize(height=new_h)
        background = background.set_position(('center', 'center'))
        
        # Klibi kaydet
        output_path = f'short_{i+1}.mp4'
        clip.write_videofile(output_path, codec='libx264')
        
    video.close()

def main():
    # YouTube URL'sini al
    url = input("YouTube video URL'sini girin: ")
    
    # Videoyu indir
    print("\n1. Video indiriliyor...")
    video_path, info = download_video(url)
    print("✓ Video indirildi!")
    
    # Altyazıları çıkar
    print("\n2. Altyazılar çıkarılıyor...")
    subtitles = extract_subtitles(info)
    print(f"✓ Altyazılar çıkarıldı! (Uzunluk: {len(subtitles)} karakter)")
    
    # İçeriği analiz et
    print("\n3. İçerik analiz ediliyor...")
    print("OpenAI API'ye istek gönderiliyor...")
    viral_parts = analyze_content(subtitles)
    print(f"✓ İçerik analiz edildi! {len(viral_parts)} viral kısım bulundu.")
    
    # Shorts videoları oluştur
    print("\n4. Shorts videoları oluşturuluyor...")
    create_shorts(video_path, viral_parts)
    print("✓ Shorts videoları oluşturuldu!")
    
    print("\nİşlem tamamlandı!")

if __name__ == "__main__":
    main() 