import os
from dotenv import load_dotenv
import yt_dlp
from openai import OpenAI
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, TextClip
import json
import re
import cv2
import numpy as np
from PIL import Image
import io
from moviepy.config import change_settings

# ImageMagick yapılandırması
IMAGEMAGICK_BINARY = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"
change_settings({"IMAGEMAGICK_BINARY": IMAGEMAGICK_BINARY})

# .env dosyasından API anahtarlarını yükle
load_dotenv()

# OpenAI istemcisini oluştur
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
OPENAI_MODEL = os.getenv('OPENAI_MODEL')

def extract_video_id(url):
    """YouTube URL'sinden video ID'sini çıkarır"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?]+)',
        r'youtube\.com\/embed\/([^&\n?]+)',
        r'youtube\.com\/v\/([^&\n?]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def download_video(url):
    """YouTube videosunu indirir"""
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Geçersiz YouTube URL'si")
        
    output_template = f'{video_id}.mp4'
    
    ydl_opts = {
        'format': 'best[ext=mp4]',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'force_generic_extractor': False,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['tr', 'en'],
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return output_template, info
    except Exception as e:
        print(f"Video indirme hatası: {str(e)}")
        print("Alternatif indirme yöntemi deneniyor...")
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['tr', 'en'],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return output_template, info

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
            "reason": "Bu kısımda ilgi çekici bir an var",
            "title": "İlgi çekici başlık",
            "speaker_detected": true,
            "speaker_time": 15
        }},
        {{
            "start_time": 45,
            "end_time": 75,
            "reason": "Bu kısımda komik bir sahne var",
            "title": "Komik başlık",
            "speaker_detected": true,
            "speaker_time": 60
        }}
    ]

    Önemli kurallar:
    1. Yanıtın SADECE JSON array olmalı
    2. Her kısım için start_time ve end_time saniye cinsinden olmalı
    3. Her kısım 15-60 saniye arası olmalı
    4. En fazla 5 viral kısım belirle
    5. Her kısım için ilgi çekici bir başlık ekle
    6. Konuşan kişi tespit edildiyse speaker_detected true olmalı ve speaker_time belirtilmeli
    7. Başka hiçbir açıklama ekleme, sadece JSON döndür

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
        return json.loads(content)
    except Exception as e:
        print(f"Beklenmeyen hata: {str(e)}")
        raise

def get_video_thumbnail(video_path, time):
    """Belirli bir zamandaki video karesini alır ve küçültür"""
    video = cv2.VideoCapture(video_path)
    video.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
    success, frame = video.read()
    video.release()
    
    if success:
        # BGR'den RGB'ye dönüştür
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # PIL Image'e dönüştür
        image = Image.fromarray(frame)
        # 124x124 boyutuna küçült
        image = image.resize((124, 124), Image.Resampling.LANCZOS)
        return image
    return None

def create_shorts(video_path, viral_parts):
    """Viral kısımlardan Shorts videoları oluşturur"""
    try:
        video = VideoFileClip(video_path)
        video_id = os.path.splitext(os.path.basename(video_path))[0]
        
        # Video boyutlarını al
        w, h = video.size
        target_w, target_h = 1080, 1920  # Shorts için hedef boyutlar
        
        for i, part in enumerate(viral_parts):
            try:
                start_time = part['start_time']
                end_time = part['end_time']
                
                # Kısa video klibi oluştur
                clip = video.subclip(start_time, end_time)
                
                # Konuşan kişi tespit edildiyse o kısma zoom yap
                if part.get('speaker_detected', False):
                    speaker_time = part['speaker_time']
                    # Konuşan kişinin olduğu kareyi al
                    frame = get_video_thumbnail(video_path, speaker_time)
                    if frame is not None:
                        # Frame'i numpy array'e dönüştür
                        frame_np = np.array(frame)
                        # Yüz tespiti yap
                        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                        gray = cv2.cvtColor(frame_np, cv2.COLOR_RGB2GRAY)
                        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                        
                        if len(faces) > 0:
                            # En büyük yüzü al
                            face = max(faces, key=lambda x: x[2] * x[3])
                            x, y, w, h = face
                            # Yüzü merkeze alacak şekilde zoom yap
                            center_x = x + w/2
                            center_y = y + h/2
                            zoom_factor = 1.5
                            
                            # Zoom uygula
                            clip = clip.resize(lambda t: zoom_factor)
                            clip = clip.set_position(('center', 'center'))
                
                # Videoyu dikey formata dönüştür
                clip = clip.resize(width=target_w)
                
                # Başlık ekle
                title = part.get('title', '')
                if title:
                    try:
                        txt_clip = TextClip(title, fontsize=70, color='white', font='Arial-Bold')
                        txt_clip = txt_clip.set_position(('center', 50)).set_duration(clip.duration)
                        clip = CompositeVideoClip([clip, txt_clip])
                    except Exception as e:
                        print(f"Başlık eklenirken hata oluştu: {str(e)}")
                        print("Başlık olmadan devam ediliyor...")
                
                # Klibi kaydet
                output_path = f'{video_id}_short_{i+1}.mp4'
                clip.write_videofile(output_path, codec='libx264')
                
            except Exception as e:
                print(f"Kısa video {i+1} oluşturulurken hata: {str(e)}")
                continue
        
        video.close()
        
    except Exception as e:
        print(f"Video işlenirken hata oluştu: {str(e)}")
        raise

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