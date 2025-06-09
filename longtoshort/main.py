import os
from dotenv import load_dotenv
import yt_dlp
from openai import OpenAI
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, TextClip, ColorClip, concatenate_videoclips
import json
import re
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
from moviepy.config import change_settings
import textwrap
from xml.etree import ElementTree as ET
from datetime import datetime
import subprocess
import emoji

# FFmpeg yolunu ekle
os.environ["PATH"] += os.pathsep + r"D:\ffmpeg\bin"

# ImageMagick yapılandırması
IMAGEMAGICK_BINARY = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"
change_settings({
    "IMAGEMAGICK_BINARY": IMAGEMAGICK_BINARY
})

# Font dosyasını Windows font klasöründen al
font_path = r"C:\Windows\Fonts\ITCKRIST.TTF"
try:
    # ImageMagick'e font dosyasını tanıt
    subprocess.run([
        IMAGEMAGICK_BINARY,
        'convert',
        '-font', font_path,
        '-list', 'font'
    ], capture_output=True, text=True)
    print("ImageMagick font listesi alındı")
except Exception as e:
    print(f"ImageMagick font listesi alınamadı: {str(e)}")

# Font ayarlarını güncelle
os.environ['IMAGEMAGICK_FONT'] = 'Arial'
os.environ['IMAGEMAGICK_FONT_PATH'] = r"C:\Windows\Fonts"

# MoviePy font ayarlarını güncelle
change_settings({
    "IMAGEMAGICK_BINARY": IMAGEMAGICK_BINARY,
    "IMAGEMAGICK_FONT": 'Arial',
    "IMAGEMAGICK_FONT_PATH": r"C:\Windows\Fonts"
})

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

def read_vtt_file(file_path):
    """VTT dosyasını okur ve metni çıkarır"""
    try:
        print(f"\nVTT dosyası okunuyor: {file_path}")
        print(f"Dosya boyutu: {os.path.getsize(file_path)} byte")
        
        # Farklı encoding'leri dene
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1254', 'cp1252', 'iso-8859-9']
        content = None
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    print(f"Başarılı encoding: {encoding}")
                    break
            except UnicodeDecodeError:
                print(f"Encoding {encoding} başarısız, diğeri deneniyor...")
                continue
        
        if content is None:
            raise Exception("Hiçbir encoding ile dosya okunamadı!")
            
        print(f"Ham içerik uzunluğu: {len(content)} karakter")
        print("İlk 200 karakter:", content[:200])
        
        # VTT başlığını ve zaman damgalarını kaldır
        lines = content.split('\n')
        text_lines = []
        current_text = []
        
        for line in lines:
            line = line.strip()
            
            # Zaman damgası satırlarını atla
            if '-->' in line:
                if current_text:  # Eğer önceki metin varsa, onu ekle
                    text_lines.append(' '.join(current_text))
                    current_text = []
                continue
                
            # Boş satırları atla
            if not line:
                continue
                
            # VTT başlığını atla
            if line.startswith('WEBVTT'):
                continue
                
            # HTML etiketlerini temizle
            line = re.sub(r'<[^>]+>', '', line)
            current_text.append(line)
            
        # Son metni de ekle
        if current_text:
            text_lines.append(' '.join(current_text))
            
        # Tüm metinleri birleştir
        full_text = ' '.join(text_lines)
        
        # Metni temizle
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        
        print(f"İşlenmiş metin uzunluğu: {len(full_text)} karakter")
        if len(full_text) > 0:
            print("İlk 500 karakter:", full_text[:500])
        else:
            print("Uyarı: VTT dosyasından hiç metin çıkarılamadı!")
            print("VTT dosyası içeriği:")
            print(content[:1000])  # İlk 1000 karakteri göster
        
        return full_text
    except Exception as e:
        print(f"VTT dosyası okuma hatası: {str(e)}")
        print("Hata detayları:")
        import traceback
        traceback.print_exc()
        return ""

def download_video(url, subtitle_choice='1'):
    """YouTube videosunu indirir"""
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Geçersiz YouTube URL'si")
        
    output_template = f'{video_id}.mov'
    
    ydl_opts = {
        'format': 'bestvideo[height>=1080]+bestaudio/bestvideo[height>=720]+bestaudio/bestvideo[height>=480]+bestaudio/bestvideo[height>=360]+bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'force_generic_extractor': False,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['tr', 'en', 'tr-TR', 'en-US'],
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mov',
        }],
        'skip_download': False,
        'keepvideo': True,
        'verbose': True,
        'format_sort': ['res:1080', 'size', 'br', 'asr'],
        'merge_output_format': 'mov',
        'ffmpeg_location': r"D:\ffmpeg\bin\ffmpeg.exe"
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("\nVideo bilgileri alınıyor...")
            info = ydl.extract_info(url, download=True)
            print("\nVideo bilgileri:")
            print(f"Başlık: {info.get('title', 'Bilinmiyor')}")
            print(f"Süre: {info.get('duration', 'Bilinmiyor')} saniye")
            print(f"Çözünürlük: {info.get('height', 'Bilinmiyor')}p")
            print(f"Format: {info.get('format', 'Bilinmiyor')}")
            print(f"Format ID: {info.get('format_id', 'Bilinmiyor')}")
            print(f"Format Açıklaması: {info.get('format_note', 'Bilinmiyor')}")
            print(f"Video Codec: {info.get('vcodec', 'Bilinmiyor')}")
            print(f"Audio Codec: {info.get('acodec', 'Bilinmiyor')}")
            
            print(f"Altyazı dilleri: {list(info.get('subtitles', {}).keys())}")
            print(f"Otomatik altyazı dilleri: {list(info.get('automatic_captions', {}).keys())}")
            
            # Altyazı dosyalarını kontrol et
            print("\nAltyazı dosyaları kontrol ediliyor...")
            tr_vtt = f"{video_id}.tr.vtt"
            tr_tr_vtt = f"{video_id}.tr-TR.vtt"
            en_vtt = f"{video_id}.en.vtt"
            en_us_vtt = f"{video_id}.en-US.vtt"
            
            # Türkçe altyazıları kontrol et
            if os.path.exists(tr_vtt):
                print(f"Türkçe altyazı dosyası bulundu: {tr_vtt}")
                print(f"Dosya boyutu: {os.path.getsize(tr_vtt)} byte")
            elif os.path.exists(tr_tr_vtt):
                print(f"Türkçe altyazı dosyası bulundu: {tr_tr_vtt}")
                print(f"Dosya boyutu: {os.path.getsize(tr_tr_vtt)} byte")
                # Dosyayı tr.vtt olarak kopyala
                import shutil
                shutil.copy2(tr_tr_vtt, tr_vtt)
            else:
                print("Türkçe altyazı dosyası bulunamadı!")
                
            # İngilizce altyazıları kontrol et
            if os.path.exists(en_vtt):
                print(f"İngilizce altyazı dosyası bulundu: {en_vtt}")
                print(f"Dosya boyutu: {os.path.getsize(en_vtt)} byte")
            elif os.path.exists(en_us_vtt):
                print(f"İngilizce altyazı dosyası bulundu: {en_us_vtt}")
                print(f"Dosya boyutu: {os.path.getsize(en_us_vtt)} byte")
                # Dosyayı en.vtt olarak kopyala
                import shutil
                shutil.copy2(en_us_vtt, en_vtt)
            else:
                print("İngilizce altyazı dosyası bulunamadı!")
            
            return output_template, info
    except Exception as e:
        print(f"Video indirme hatası: {str(e)}")
        print("Alternatif indirme yöntemi deneniyor...")
        ydl_opts = {
            'format': 'bestvideo[height>=1080]+bestaudio/bestvideo[height>=720]+bestaudio/bestvideo[height>=480]+bestaudio/bestvideo[height>=360]+bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['tr', 'en', 'tr-TR', 'en-US'],
            'verbose': True,
            'ffmpeg_location': r"D:\ffmpeg\bin\ffmpeg.exe"
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Altyazı dosyalarını kontrol et
            print("\nAltyazı dosyaları kontrol ediliyor...")
            tr_vtt = f"{video_id}.tr.vtt"
            tr_tr_vtt = f"{video_id}.tr-TR.vtt"
            en_vtt = f"{video_id}.en.vtt"
            en_us_vtt = f"{video_id}.en-US.vtt"
            
            # Türkçe altyazıları kontrol et
            if os.path.exists(tr_vtt):
                print(f"Türkçe altyazı dosyası bulundu: {tr_vtt}")
                print(f"Dosya boyutu: {os.path.getsize(tr_vtt)} byte")
            elif os.path.exists(tr_tr_vtt):
                print(f"Türkçe altyazı dosyası bulundu: {tr_tr_vtt}")
                print(f"Dosya boyutu: {os.path.getsize(tr_tr_vtt)} byte")
                # Dosyayı tr.vtt olarak kopyala
                import shutil
                shutil.copy2(tr_tr_vtt, tr_vtt)
            else:
                print("Türkçe altyazı dosyası bulunamadı!")
                
            # İngilizce altyazıları kontrol et
            if os.path.exists(en_vtt):
                print(f"İngilizce altyazı dosyası bulundu: {en_vtt}")
                print(f"Dosya boyutu: {os.path.getsize(en_vtt)} byte")
            elif os.path.exists(en_us_vtt):
                print(f"İngilizce altyazı dosyası bulundu: {en_us_vtt}")
                print(f"Dosya boyutu: {os.path.getsize(en_us_vtt)} byte")
                # Dosyayı en.vtt olarak kopyala
                import shutil
                shutil.copy2(en_us_vtt, en_vtt)
            else:
                print("İngilizce altyazı dosyası bulunamadı!")
                
            return output_template, info

def extract_subtitles(info, subtitle_choice='1'):
    """Video bilgilerinden altyazıları çıkarır"""
    try:
        print("\nMevcut altyazı dilleri:", list(info.get('subtitles', {}).keys()))
        print("Mevcut otomatik altyazı dilleri:", list(info.get('automatic_captions', {}).keys()))
        
        video_id = info.get('id', '')
        if not video_id:
            raise Exception("Video ID bulunamadı!")
            
        # Önce Türkçe altyazıyı dene
        tr_vtt = f"{video_id}.tr.vtt"
        if os.path.exists(tr_vtt):
            print(f"Türkçe VTT dosyası bulundu: {tr_vtt}")
            text = read_vtt_file(tr_vtt)
            if len(text) > 100:
                return text, False  # Altyazıları gösterme
        
        # Türkçe yoksa veya kısaysa İngilizce'yi dene
        en_vtt = f"{video_id}.en.vtt"
        if os.path.exists(en_vtt):
            print(f"İngilizce VTT dosyası bulundu: {en_vtt}")
            text = read_vtt_file(en_vtt)
            if len(text) > 100:
                return text, False  # Altyazıları gösterme
                
        # İngilizce yoksa veya kısaysa otomatik altyazıyı dene
        if 'en' in info.get('automatic_captions', {}):
            auto_captions = info['automatic_captions']['en']
            if isinstance(auto_captions, list) and len(auto_captions) > 0:
                if 'data' in auto_captions[0]:
                    text = auto_captions[0]['data']
                    if len(text) > 100:
                        return text, False  # Altyazıları gösterme
                        
        # Hiçbir altyazı bulunamadıysa
        print("Uyarı: Yeterli uzunlukta altyazı bulunamadı!")
        return "", False  # Altyazıları gösterme
        
    except Exception as e:
        print(f"Altyazı çıkarma hatası: {str(e)}")
        print("Hata detayları:")
        import traceback
        traceback.print_exc()
        return "", False  # Altyazıları gösterme

def smart_wrap_text(text, font, max_width):
    """Metni piksel genişliğine göre akıllıca satırlara böler"""
    lines = []
    current_line_words = []
    
    # Create a dummy ImageDraw object to measure text width
    dummy_img = Image.new('RGBA', (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    words = text.split()
    for word in words:
        test_line = " ".join(current_line_words + [word])
        # Calculate text width using the font
        bbox = dummy_draw.textbbox((0,0), test_line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            current_line_words.append(word)
        else:
            if current_line_words: # Add the current line if it's not empty
                lines.append(" ".join(current_line_words))
            
            # Start a new line with the current word
            current_line_words = [word]
            
    if current_line_words:
        lines.append(" ".join(current_line_words))
    
    return '\n'.join(lines)

def calculate_video_count(duration):
    """Video süresine göre oluşturulacak video sayısını hesaplar"""
    # Her 2 dakika için 1 video
    base_count = max(3, min(20, int(duration / 120)))
    return base_count

def analyze_content(text, duration):
    """ChatGPT ile içeriği analiz eder ve viral kısımları belirler"""
    if not text or len(text) < 100:
        print("Uyarı: Altyazı metni yetersiz! Video süresine göre bölümlere ayırılacak.")
        # Video süresine göre bölümler oluştur
        parts = []
        part_duration = min(30, duration)  # Her bölüm en fazla 30 saniye
        current_time = 0
        
        while current_time < duration:
            end_time = min(current_time + part_duration, duration)
            parts.append({
                "start": current_time,
                "end": end_time,
                "title": f"Bölüm {len(parts) + 1}",
                "description": f"Video içeriğinin {current_time}-{end_time} saniye arası"
            })
            current_time = end_time
            
        return [{
            "start_time": part["start"],
            "end_time": part["end"],
            "title": part["title"],
            "reason": part["description"],
            "speaker_detected": False,
            "speaker_time": None,
            "context": part["description"],
            "sentence_start": part["start"]
        } for part in parts]
        
    print(f"\nAltyazı metni uzunluğu: {len(text)} karakter")
    print("İlk 500 karakter:", text[:500])
    
    # Video sayısını hesapla
    video_count = calculate_video_count(duration)
    print(f"\nVideo süresi: {duration} saniye")
    print(f"Oluşturulacak video sayısı: {video_count}")
    
    prompt = f"""
    Aşağıdaki video altyazısını analiz et ve en ilgi çekici, viral olabilecek kısımları belirle.
    Her kısım için başlangıç ve bitiş sürelerini, başlığı ve açıklamayı belirt.
    Yanıtını aşağıdaki formatta ver:

    [
        {{
            "start": 0,
            "end": 30,
            "title": "Başlık buraya",
            "description": "Açıklama buraya"
        }}
    ]

    Önemli kurallar:
    1. Her kısım 15-120 saniye arası olmalı
    2. Tam olarak {video_count} kısım belirle
    3. Başlıklar şu özelliklere sahip olmalı:
       - Seçilen kısımdaki içerikle TAMAMEN ilgili olmalı
       - Seçilen kısımdaki konuşmanın ana fikrini yansıtmalı
       - İlgi çekici ve tıklama isteği uyandırmalı
       - Kısa ve öz olmalı (en fazla 50 karakter)
       - Clickbait tarzında ama yanıltıcı olmamalı
       - Merak uyandırmalı
       - Emoji kullanabilirsin (en fazla 2 tane)
       - Türkçe karakterler kullan (ç, ş, ı, ğ, ü, ö)
       - Büyük harfle başla
    4. Her kısım için açıklama şu özelliklere sahip olmalı:
       - Seçilen kısımda ne anlatıldığını özetle
       - En fazla 100 karakter
       - Türkçe karakterler kullan
    5. Sadece JSON array döndür, başka açıklama ekleme
    6. JSON formatına tam olarak uy, virgül ve süslü parantezlere dikkat et
    7. Her kısım için start ve end değerleri sayı olmalı
    8. Her kısım için title ve description string olmalı
    9. Boş array döndürme, en az bir kısım belirt
    10. start değeri her zaman end değerinden küçük olmalı
    11. Tüm süreler video süresi ({duration} saniye) içinde olmalı
    12. Her kısım için başlık ve açıklama altyazı metninden alınmalı
    13. Kısımları sıralı seçme, en ilgi çekici ve viral olabilecek kısımları seç
    14. Her kısım için başlık, o kısımdaki içerikle doğrudan ilgili olmalı

    Altyazı:
    {text}
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Sen bir video içerik analisti ve başlık uzmanısın. Verilen metni analiz edip en ilgi çekici kısımları bulacak ve her kısım için içerikle tamamen ilgili, özgün başlıklar oluşturacaksın. Başlıklar ve açıklamalar Türkçe olmalı ve altyazı metninden alınmalı. Yanıtını KESİNLİKLE JSON array formatında ver, başka hiçbir açıklama ekleme. Boş array döndürme, en az bir kısım belirt."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            print("\nChatGPT yanıtı:", content[:500])
            
            # JSON formatını temizle
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            try:
                result = json.loads(content)
                if not result or not isinstance(result, list):
                    print("Uyarı: ChatGPT geçersiz bir JSON array döndürdü, varsayılan yanıt kullanılıyor.")
                    return [{
                        "start_time": 0,
                        "end_time": min(30, duration),
                        "title": "Video Başlangıcı",
                        "reason": "Video içeriğinin başlangıç kısmı",
                        "speaker_detected": False,
                        "speaker_time": None,
                        "context": "Video içeriğinin başlangıç kısmı",
                        "sentence_start": 0
                    }]
                    
                if len(result) == 0:
                    print("Uyarı: ChatGPT boş bir liste döndürdü, varsayılan yanıt kullanılıyor.")
                    return [{
                        "start_time": 0,
                        "end_time": min(30, duration),
                        "title": "Video Başlangıcı",
                        "reason": "Video içeriğinin başlangıç kısmı",
                        "speaker_detected": False,
                        "speaker_time": None,
                        "context": "Video içeriğinin başlangıç kısmı",
                        "sentence_start": 0
                    }]
                    
                # Her kısmın formatını kontrol et
                for part in result:
                    if not isinstance(part, dict):
                        raise Exception("Her kısım bir dictionary olmalı!")
                    if 'start' not in part or 'end' not in part or 'title' not in part or 'description' not in part:
                        raise Exception("Her kısımda start, end, title ve description olmalı!")
                    if not isinstance(part['start'], (int, float)) or not isinstance(part['end'], (int, float)):
                        raise Exception("start ve end değerleri sayı olmalı!")
                    if not isinstance(part['title'], str) or not isinstance(part['description'], str):
                        raise Exception("title ve description değerleri string olmalı!")
                    if part['start'] >= part['end']:
                        raise Exception("start değeri end değerinden küçük olmalı!")
                    if part['start'] < 0 or part['end'] > duration:
                        raise Exception(f"Tüm süreler 0 ile {duration} saniye arasında olmalı!")
                    if len(part['title']) > 50:
                        raise Exception("Başlık en fazla 50 karakter olmalı!")
                    if len(part['description']) > 100:
                        raise Exception("Açıklama en fazla 100 karakter olmalı!")
                
                print(f"\nBulunan viral kısım sayısı: {len(result)}")
                
                # Sonuçları eski formata dönüştür
                formatted_result = []
                for part in result:
                    formatted_part = {
                        "start_time": part["start"],
                        "end_time": part["end"],
                        "title": part["title"],
                        "reason": part["description"],
                        "speaker_detected": False,
                        "speaker_time": None,
                        "context": part["description"],
                        "sentence_start": part["start"]
                    }
                    formatted_result.append(formatted_part)
                
                return formatted_result
                
            except json.JSONDecodeError as e:
                print(f"JSON ayrıştırma hatası: {str(e)}")
                print("Ham yanıt:", content)
                if attempt < max_retries - 1:
                    print(f"Yeniden deneniyor... (Deneme {attempt + 2}/{max_retries})")
                    continue
                print("Uyarı: JSON ayrıştırma hatası, varsayılan yanıt kullanılıyor.")
                return [{
                    "start_time": 0,
                    "end_time": min(30, duration),
                    "title": "Video Başlangıcı",
                    "reason": "Video içeriğinin başlangıç kısmı",
                    "speaker_detected": False,
                    "speaker_time": None,
                    "context": "Video içeriğinin başlangıç kısmı",
                    "sentence_start": 0
                }]
                
        except Exception as e:
            print(f"Beklenmeyen hata: {str(e)}")
            print("Hata detayları:")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                print(f"Yeniden deneniyor... (Deneme {attempt + 2}/{max_retries})")
                continue
            print("Uyarı: Beklenmeyen hata, varsayılan yanıt kullanılıyor.")
            return [{
                "start_time": 0,
                "end_time": min(30, duration),
                "title": "Video Başlangıcı",
                "reason": "Video içeriğinin başlangıç kısmı",
                "speaker_detected": False,
                "speaker_time": None,
                "context": "Video içeriğinin başlangıç kısmı",
                "sentence_start": 0
            }]

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

def filter_repeated_words(text, previous_words, min_word_length=3):
    """Tekrar eden kelimeleri filtreler"""
    # Metni kelimelere ayır
    words = text.lower().split()
    filtered_words = []
    
    for word in words:
        # Kelimeyi temizle (noktalama işaretlerini kaldır)
        clean_word = re.sub(r'[^\w\s]', '', word)
        
        # Çok kısa kelimeleri ve sayıları atla
        if len(clean_word) < min_word_length or clean_word.isdigit():
            filtered_words.append(word)
            continue
            
        # Eğer kelime önceki kelimelerde yoksa ekle
        if clean_word not in previous_words:
            filtered_words.append(word)
            previous_words.add(clean_word)
    
    return ' '.join(filtered_words), previous_words

def merge_similar_subtitles(subtitles):
    """Benzer altyazıları birleştirir"""
    if not subtitles:
        return subtitles
        
    merged = []
    current = subtitles[0]
    previous_words = set()  # Önceki kelimeleri takip et
    
    # İlk altyazıyı işle
    current['text'], previous_words = filter_repeated_words(current['text'], previous_words)
    
    for next_sub in subtitles[1:]:
        # Metinleri karşılaştır
        current_text = current['text'].strip().lower()
        next_text = next_sub['text'].strip().lower()
        
        # Eğer metinler çok benzer veya aynıysa
        if current_text in next_text or next_text in current_text:
            # Süreyi güncelle
            current['end'] = next_sub['end']
            # Metni birleştir (tekrar etmeden)
            if current_text in next_text:
                current['text'] = next_sub['text']
        else:
            # Yeni altyazıyı işle ve tekrar eden kelimeleri filtrele
            next_sub['text'], previous_words = filter_repeated_words(next_sub['text'], previous_words)
            merged.append(current)
            current = next_sub
    
    # Son altyazıyı da işle
    current['text'], _ = filter_repeated_words(current['text'], previous_words)
    merged.append(current)
    return merged

def parse_vtt_timestamps(vtt_content):
    """VTT dosyasından zaman damgalarını ve metinleri çıkarır"""
    subtitles = []
    current_subtitle = None
    
    for line in vtt_content.split('\n'):
        line = line.strip()
        
        if '-->' in line:
            if current_subtitle:
                # Altyazı süresini kontrol et ve gerekirse böl
                duration = current_subtitle['end'] - current_subtitle['start']
                if duration > 3:  # 3 saniyeden uzun altyazıları böl
                    mid_time = current_subtitle['start'] + duration / 2
                    first_half = {
                        'start': current_subtitle['start'],
                        'end': mid_time,
                        'text': current_subtitle['text']
                    }
                    second_half = {
                        'start': mid_time,
                        'end': current_subtitle['end'],
                        'text': current_subtitle['text']
                    }
                    subtitles.append(first_half)
                    subtitles.append(second_half)
                else:
                    subtitles.append(current_subtitle)
            
            try:
                # Zaman damgası satırını temizle
                time_line = line.split(' align:')[0]
                start_time, end_time = time_line.split(' --> ')
                current_subtitle = {
                    'start': convert_vtt_time_to_seconds(start_time),
                    'end': convert_vtt_time_to_seconds(end_time),
                    'text': ''
                }
            except ValueError as e:
                print(f"Geçersiz zaman damgası formatı: {line}")
                continue
                
        elif line and current_subtitle and not line.startswith('WEBVTT'):
            # HTML etiketlerini temizle
            text = re.sub(r'<[^>]+>', '', line)
            # Metni temizle ve birleştir
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                if current_subtitle['text']:
                    current_subtitle['text'] += ' ' + text
                else:
                    current_subtitle['text'] = text
    
    if current_subtitle:
        # Son altyazıyı da kontrol et ve gerekirse böl
        duration = current_subtitle['end'] - current_subtitle['start']
        if duration > 3:
            mid_time = current_subtitle['start'] + duration / 2
            first_half = {
                'start': current_subtitle['start'],
                'end': mid_time,
                'text': current_subtitle['text']
            }
            second_half = {
                'start': mid_time,
                'end': current_subtitle['end'],
                'text': current_subtitle['text']
            }
            subtitles.append(first_half)
            subtitles.append(second_half)
        else:
            subtitles.append(current_subtitle)
    
    # Benzer altyazıları birleştir
    merged_subtitles = merge_similar_subtitles(subtitles)
    
    print(f"\nToplam {len(merged_subtitles)} altyazı parçası bulundu")
    if merged_subtitles:
        print("İlk altyazı örneği:", merged_subtitles[0])
    
    return merged_subtitles

def convert_vtt_time_to_seconds(time_str):
    """VTT zaman formatını saniyeye çevirir"""
    try:
        # Ek bilgileri temizle (align:start position:0% gibi)
        time_str = time_str.split()[0]
        
        # Virgülü noktaya çevir
        time_str = time_str.replace(',', '.')
        
        # Saat, dakika ve saniye kısımlarını ayır
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return float(m) * 60 + float(s)
        else:
            return float(time_str)
    except Exception as e:
        print(f"Zaman dönüştürme hatası: {str(e)}")
        return 0.0

def create_text_image(text, width, height, font_size=90, main_font_path='DynaPuff/static/DynaPuff-Regular.ttf', output_folder=None):
    """PIL kullanarak metin görüntüsü oluşturur"""
    # try: # Geçici olarak kaldırıldı
        # Ana font dosyasının varlığını kontrol et
    if not os.path.exists(main_font_path):
        print(f"HATA: Ana font dosyası bulunamadı: {main_font_path}")
        raise FileNotFoundError(f"Ana font dosyası bulunamadı: {main_font_path}")

    emoji_font_path = 'Noto_Color_Emoji/NotoColorEmoji-Regular.ttf'
    emoji_font = None
    has_emojis = emoji.emoji_count(text) > 0
    
    # Emoji fontunu yüklemeye çalış
    if has_emojis and os.path.exists(emoji_font_path):
        try:
            # Emoji fontu ana font boyutuyla yüklensin
            emoji_font = ImageFont.truetype(emoji_font_path, font_size)
            print(f"Emoji fontu başarıyla yüklendi: {emoji_font_path}")
        except Exception as e:
            print(f"Emoji fontu yüklenirken hata: {str(e)}. Emoji fontu kullanılamayacak.")
            emoji_font = None # Yüklenemezse fallback
    else:
        print(f"Metindeki emoji sayısı: {emoji.emoji_count(text)}")
        print(f"Emoji fontu ({emoji_font_path}) var mı: {os.path.exists(emoji_font_path)}")
        if not has_emojis:
            print("Metinde emoji algılanmadı.")
        elif not os.path.exists(emoji_font_path):
            print("Emoji font dosyası bulunamadı.")

    current_font_size = font_size
    max_attempts = 10
    
    # Metin sığana kadar font boyutunu küçült (ana font ile ölçüm yaparak)
    main_font_for_sizing = None
    for attempt in range(max_attempts):
        try:
            main_font_for_sizing = ImageFont.truetype(main_font_path, current_font_size)
            
            # Metni mevcut ana font boyutuyla ölç
            wrapped_text = smart_wrap_text(text, main_font_for_sizing, width)
            lines = wrapped_text.split('\n')
            
            total_text_height = 0
            max_line_width = 0
            min_top_offset_current_attempt = 0 # Initialize for current attempt
            for line in lines:
                bbox = main_font_for_sizing.getbbox(line)
                line_height = bbox[3] - bbox[1]
                line_width = bbox[2] - bbox[0]
                total_text_height += line_height
                if line_width > max_line_width:
                    max_line_width = line_width
                
                # Update min_top_offset for the current line's bounding box
                # bbox[1] is the top coordinate, which can be negative if parts of the character go above the baseline
                if bbox[1] < min_top_offset_current_attempt:
                    min_top_offset_current_attempt = bbox[1]

            total_text_height += (len(lines) - 1) * 10 # Satır arası boşluk
            min_top_offset_overall = min_top_offset_current_attempt # Update for final use

            available_height_for_sizing = height - 40 # Add 20px padding top and bottom
            if max_line_width <= width and total_text_height <= available_height_for_sizing:
                print(f"Metin başarıyla sığdırıldı. Font Boyutu: {current_font_size}, Genişlik: {max_line_width}/{width}, Yükseklik: {total_text_height}/{available_height_for_sizing})")
                break
            else:
                if current_font_size > 10: # Minimum font boyutu
                    current_font_size -= 5
                    print(f"Metin sığmadı, font boyutu düşürülüyor: {current_font_size}")
                else:
                    print("Minimum font boyutuna ulaşıldı, metin hala sığmıyor.")
                    break
        except Exception as e:
            print(f"Deneme {attempt+1}: Font boyutlandırma sırasında hata: {str(e)}")
            if current_font_size > 10:
                current_font_size -= 5
                continue
            raise


    if main_font_for_sizing is None:
        raise Exception("Ana font yüklenemedi veya boyutlandırılamadı.")

    # Son seçilen font boyutuyla ana fontu ve emoji fontunu yeniden yükle
    final_main_font = ImageFont.truetype(main_font_path, current_font_size)
    final_emoji_font = None
    if has_emojis and os.path.exists(emoji_font_path):
            try:
                final_emoji_font = ImageFont.truetype(emoji_font_path, current_font_size)
            except Exception as e:
                print(f"Final emoji fontu yüklenirken hata: {str(e)}")


    # Son görüntüyü oluştur
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Metni dikeyde ortala ve ekstra boşluk bırak
    vertical_padding = 20 # Add 20px padding from top and bottom
    y_position = (height - total_text_height) // 2 
    
    # Adjust y_position based on the highest point above baseline to prevent clipping
    # Add absolute value of min_top_offset_overall to y_position to shift text down if ascenders are clipped
    y_position_adjusted = y_position - min_top_offset_overall # This effectively pushes the entire block down
    
    # Ensure minimum vertical padding from top
    if y_position_adjusted < vertical_padding:
        y_position_adjusted = vertical_padding

    print(f"DEBUG: Initial y_position: {y_position}, min_top_offset_overall: {min_top_offset_overall}, y_position_adjusted: {y_position_adjusted}")

    current_y = y_position_adjusted
    
    # Her satırı karakter karakter çiz
    for line in lines:
        # Satırın yatayda ortalanması için başlangıç noktası
        line_width = final_main_font.getbbox(line)[2] - final_main_font.getbbox(line)[0]
        x = (width - line_width) // 2
        
        current_x = x
        for char_index, char in enumerate(line):
            is_emoji_char = emoji.is_emoji(char)
            print(f"Processing char: '{char}', is_emoji: {is_emoji_char}, has_emojis: {has_emojis}, final_emoji_font: {final_emoji_font is not None}") # More detailed debug

            if is_emoji_char and final_emoji_font: # Eğer karakter emoji ise ve emoji fontu varsa
                selected_font = final_emoji_font
                print(f"Using emoji font for char: '{char}' at ({current_x}, {current_y})") # Debug
                # Draw emojis WITHOUT stroke, as stroke can interfere with color fonts
                draw.text((current_x, current_y), char, font=selected_font, fill='white') # Re-added fill='white' for emojis
            else: # Değilse veya emoji fontu yoksa ana fontu kullan
                selected_font = final_main_font
                print(f"Using main font for char: '{char}' at ({current_x}, {current_y})") # Debug
                draw.text((current_x, current_y), char, font=selected_font, fill='white', stroke_width=2, stroke_fill='black')
            
            char_bbox = selected_font.getbbox(char)
            char_width = char_bbox[2] - char_bbox[0]
            
            # Adjust y_position for each character if fonts have different baselines
            # This is complex and might not be needed for simple cases. For now, assume consistent baseline.
            
            current_x += char_width # Bir sonraki karakter için x konumunu ilerlet
        
        # Bir sonraki satır için y konumunu ilerlet
        current_y += (final_main_font.getbbox(line)[3] - final_main_font.getbbox(line)[1]) + 10 # Satır yüksekliği + boşluk

    # Görüntüyü kaydet (test için)
    test_image_path = 'test_text.png'
    if output_folder: # Eğer bir çıktı klasörü belirtilmişse, dosya yolunu bu klasörün içine ayarla
        test_image_path = os.path.join(output_folder, 'test_text.png')

    image.save(test_image_path)
    print(f"Test görüntüsü kaydedildi: {test_image_path}")
    print(f"Type of 'image' before np.array: {type(image)}") # DEBUG Print
        
    return np.array(image) # Numpy array olarak döndür
        
    # except Exception as e: # Geçici olarak kaldırıldı
    #     print(f"Metin görüntüsü oluşturulurken hata: {str(e)}")
    #     print("Hata detayları:")
    #     import traceback
    #     traceback.print_exc()
    #     raise # Hatanın tekrar fırlatılması
    
def create_shorts(video_path, viral_parts, show_subtitles=True):
    """Viral kısımlardan Shorts videoları oluşturur"""
    try:
        # Video uzantısını kontrol et ve gerekirse değiştir
        video_path_without_ext = os.path.splitext(video_path)[0]
        if not os.path.exists(video_path):
            # WEBM uzantısını dene
            webm_path = video_path_without_ext + '.webm'
            if os.path.exists(webm_path):
                video_path = webm_path
            else:
                # MP4 uzantısını dene
                mp4_path = video_path_without_ext + '.mp4'
                if os.path.exists(mp4_path):
                    video_path = mp4_path
                else:
                    # MOV uzantısını dene
                    mov_path = video_path_without_ext + '.mov'
                    if os.path.exists(mov_path):
                        video_path = mov_path
                    else:
                        raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")

        video = VideoFileClip(video_path)
        video_id = os.path.splitext(os.path.basename(video_path))[0]
        
        # Arka plan videosunu yükle
        bg_video = VideoFileClip("bg.mp4")
        bg_duration = bg_video.duration
        
        # Video boyutlarını al
        w, h = video.size
        target_w, target_h = 1080, 1920  # Shorts için hedef boyutlar
        
        # Viral kısımları sırala (en ilgi çekici olanlar önce)
        viral_parts.sort(key=lambda x: x.get('start_time', 0))
        
        for i, part in enumerate(viral_parts):
            try:
                # Viral kısımın başlangıç ve bitiş zamanlarını al
                start_time = part['start_time']
                end_time = part['end_time']
                clip_duration = end_time - start_time
                
                print(f"\nViral kısım {i+1} işleniyor:")
                print(f"Başlangıç: {start_time:.2f} saniye")
                print(f"Bitiş: {end_time:.2f} saniye")
                print(f"Süre: {clip_duration:.2f} saniye")
                print(f"Başlık: {part.get('title', 'Başlıksız')}")
                
                # Kısa video klibi oluştur
                clip = video.subclip(start_time, end_time)
                
                # Ses seviyesini %175'e çıkar
                clip = clip.volumex(1.75)
                
                # Arka plan videosunu hazırla
                repeat_count = int(clip_duration / bg_duration) + 1
                bg_clips = [bg_video] * repeat_count
                bg_combined = concatenate_videoclips(bg_clips)
                bg_combined = bg_combined.subclip(0, clip_duration)
                bg_combined = bg_combined.without_audio()
                
                # Arka plan videosunu dikey formata dönüştür
                bg_combined = bg_combined.resize(height=target_h)
                if bg_combined.w > target_w:
                    x_center = bg_combined.w / 2
                    x1 = int(x_center - target_w/2)
                    x2 = int(x_center + target_w/2)
                    bg_combined = bg_combined.crop(x1=x1, y1=0, x2=x2, y2=target_h)
                
                # Ana videoyu dikey formata dönüştür
                clip = clip.resize(height=int(target_h * 0.65))
                y_position = target_h - clip.h - 250
                clip = clip.set_position(('center', y_position))

                # Overlay kliplerini tutacak liste
                overlay_clips_for_this_short = []

                # Başlık ekle
                title = part.get('title', '')
                if title:
                    try:
                        # Başlık için güvenli bir dosya adı oluştur
                        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
                        # Çıktı klasörünü belirle
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_dir = os.path.join('.', f"shorts_output_{safe_title}_{timestamp}")
                        os.makedirs(output_dir, exist_ok=True)
                        print(f"Çıktı klasörü oluşturuldu: {output_dir}")

                        # Başlık için arka plan oluştur
                        title_bg_height = 180
                        title_bg = ColorClip(size=(target_w, title_bg_height), color=(0, 0, 0, 128))
                        title_bg = title_bg.set_duration(clip_duration)
                        title_bg = title_bg.set_position(('center', 50))

                        # PIL ile metin görüntüsü oluştur
                        text_image_np = create_text_image(
                            title,
                            target_w - 120, # Daha geniş alan bırak (her iki yandan 60px boşluk)
                            title_bg_height,
                            font_size=90,
                            main_font_path='DynaPuff/static/DynaPuff-Regular.ttf', # Ana fontu belirle
                            output_folder=output_dir # Test görüntüsünü kaydetmek için klasör yolunu ilet
                        )
                        print(f"Type of 'text_image_np' before ImageClip: {type(text_image_np)}") # DEBUG Print
                        
                        # Görüntüyü ImageClip'e dönüştür
                        txt_clip = ImageClip(text_image_np)
                        txt_clip = txt_clip.set_duration(clip_duration)
                        txt_clip = txt_clip.set_position(('center', 50))

                        # Fade efektleri
                        fade_duration = 0.5
                        txt_clip = txt_clip.crossfadein(fade_duration)
                        txt_clip = txt_clip.crossfadeout(fade_duration)
                        title_bg = title_bg.crossfadein(fade_duration)
                        title_bg = title_bg.crossfadeout(fade_duration)

                        # Önce arka planı, sonra metni ekle
                        overlay_clips_for_this_short.append(title_bg)
                        overlay_clips_for_this_short.append(txt_clip)

                    except Exception as e:
                        print(f"Başlık eklenirken hata oluştu: {str(e)}")
                        print("Hata detayları:")
                        import traceback
                        traceback.print_exc()
                        print("Başlık olmadan devam ediliyor...")

                # Tüm klipleri birleştir
                final_clips_list = [bg_combined, clip] + overlay_clips_for_this_short

                # CompositeVideoClip oluştur
                final_clip = CompositeVideoClip(
                    final_clips_list,
                    size=(target_w, target_h)
                ).set_duration(clip_duration)

                # Klibi kaydet
                # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") # Zaten yukarıda tanımlandı
                # Başlıktan güvenli bir dosya adı oluştur # Zaten yukarıda tanımlandı
                # output_path = f'{video_id}_{safe_title}_{timestamp}.mov' # Klasör yolunu da dahil et
                output_path = os.path.join(output_dir, f'{video_id}_{safe_title}_{timestamp}.mov')
                print(f"\nKısa video kaydediliyor: {output_path}")
                
                final_clip.write_videofile(
                    output_path,
                    codec='libx264',
                    bitrate='4000k',
                    audio_codec='aac',
                    audio_bitrate='192k',
                    preset='medium',
                    threads=4,
                    ffmpeg_params=[
                        '-crf', '23',
                        '-movflags', '+faststart'
                    ]
                )
                print(f"✓ Kısa video kaydedildi!")

            except Exception as e:
                print(f"\nKısa video oluşturulurken hata: {str(e)}")
                print("Hata detayları:")
                import traceback
                traceback.print_exc()
                continue
        
        video.close()
        bg_video.close()
        
    except Exception as e:
        print(f"Video işlenirken hata oluştu: {str(e)}")
        raise

def extract_hardcoded_subtitles(video_path):
    """Video içindeki hardcoded altyazıları çıkarmaya çalışır"""
    try:
        print("\nVideo içindeki altyazılar taranıyor...")
        video = cv2.VideoCapture(video_path)
        frames_with_text = []
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        
        # Her 1 saniyede bir kare al (fps'e göre)
        frame_interval = int(fps)
        current_frame = 0
        
        while True:
            ret, frame = video.read()
            if not ret:
                break
                
            if current_frame % frame_interval == 0:
                # Frame'i gri tonlamaya çevir
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Metin tespiti için threshold uygula
                _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
                
                # Konturları bul
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Metin içeren bölgeleri kontrol et
                for contour in contours:
                    x, y, w, h = cv2.boundingRect(contour)
                    # Sadece üst kısımdaki metinleri al (altyazı genelde üstte olur)
                    if y < frame.shape[0] * 0.3 and w > 50 and h > 10:
                        frames_with_text.append(current_frame / fps)
                        break
            
            current_frame += 1
            
            # İlerleme göster
            if current_frame % (frame_interval * 10) == 0:
                progress = (current_frame / total_frames) * 100
                print(f"\rİlerleme: %{progress:.1f}", end="")
        
        video.release()
        print("\n✓ Video taraması tamamlandı!")
        
        if frames_with_text:
            print(f"Altyazı içeren {len(frames_with_text)} kare bulundu")
            # Altyazı içeren karelerin zamanlarını döndür
            return str(frames_with_text)
        else:
            print("Video içinde altyazı bulunamadı")
            return ""
            
    except Exception as e:
        print(f"Altyazı çıkarma hatası: {str(e)}")
        return ""

def parse_ttml_content(ttml_content):
    """TTML içeriğini parse edip sadece altyazı metinlerini çıkarır"""
    try:
        # XML namespace'lerini tanımla
        namespaces = {
            'ttml': 'http://www.w3.org/ns/ttml',
            'ttm': 'http://www.w3.org/ns/ttml#metadata',
            'tts': 'http://www.w3.org/ns/ttml#styling',
            'ttp': 'http://www.w3.org/ns/ttml#parameter'
        }
        
        # XML içeriğini parse et
        root = ET.fromstring(ttml_content)
        
        # Tüm p elementlerini bul (altyazı metinleri)
        subtitles = []
        for p in root.findall('.//ttml:p', namespaces):
            text = p.text.strip() if p.text else ""
            if text:
                subtitles.append(text)
        
        # Altyazıları birleştir
        return " ".join(subtitles)
        
    except Exception as e:
        print(f"TTML parse hatası: {str(e)}")
        return ""

def check_ttml_subtitle(video_path):
    """Aynı isimde TTML altyazı dosyası var mı kontrol eder"""
    try:
        # Video dosyasının adını ve yolunu ayır
        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        ttml_path = os.path.join(video_dir, f"{video_name}.ttml")
        
        if os.path.exists(ttml_path):
            print(f"\nTTML altyazı dosyası bulundu: {ttml_path}")
            with open(ttml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # TTML içeriğini parse et
            parsed_content = parse_ttml_content(content)
            if parsed_content:
                print(f"✓ TTML altyazıları başarıyla parse edildi! (Uzunluk: {len(parsed_content)} karakter)")
                return parsed_content
            else:
                print("! TTML içeriği parse edilemedi")
                return None
        return None
    except Exception as e:
        print(f"TTML kontrol hatası: {str(e)}")
        return None

def process_local_video(video_path):
    """Yerel videoyu işler"""
    try:
        # Video bilgilerini al
        video = VideoFileClip(video_path)
        duration = video.duration
        video.close()
        
        # Altyazıları çıkar
        print("\n2. Altyazılar çıkarılıyor...")
        
        # Önce TTML dosyasını kontrol et
        subtitles = check_ttml_subtitle(video_path)
        
        # TTML yoksa hardcoded tarama yap
        if not subtitles:
            print("TTML altyazı dosyası bulunamadı, video içindeki altyazılar taranıyor...")
            subtitles = extract_hardcoded_subtitles(video_path)
        
        if subtitles:
            print(f"✓ Altyazılar çıkarıldı! (Uzunluk: {len(subtitles)} karakter)")
        else:
            print("! Altyazı bulunamadı, içerik analizi altyazısız yapılacak")
        
        # İçeriği analiz et
        print("\n3. İçerik analiz ediliyor...")
        print("OpenAI API'ye istek gönderiliyor...")
        viral_parts = analyze_content(subtitles, duration)
        print(f"✓ İçerik analiz edildi! {len(viral_parts)} viral kısım bulundu.")
        
        # Shorts videoları oluştur
        print("\n4. Shorts videoları oluşturuluyor...")
        create_shorts(video_path, viral_parts, False)
        print("✓ Shorts videoları oluşturuldu!")
        
    except Exception as e:
        print(f"Video işlenirken hata oluştu: {str(e)}")
        raise

def main():
    print("\n=== Video İşleme Programı ===")
    print("1. YouTube'dan video indir")
    print("2. Hazır videoyu işle")
    
    choice = input("\nSeçiminiz (1/2): ").strip()
    
    if choice == "1":
        # YouTube URL'sini al
        url = input("\nYouTube video URL'sini girin: ")
        
        # Altyazı seçeneği
        print("\nAltyazı seçenekleri:")
        print("1. Türkçe altyazı (varsa)")
        print("2. İngilizce altyazı (varsa)")
        print("3. Otomatik altyazı (varsa)")
        print("4. Konuşma altyazısı olmadan devam et")
        
        subtitle_choice = input("\nAltyazı seçiminiz (1/2/3/4): ").strip()
        
        # Videoyu indir
        print("\n1. Video indiriliyor...")
        video_path, info = download_video(url, subtitle_choice)
        print("✓ Video indirildi!")
        
        # Altyazıları çıkar
        print("\n2. Altyazılar çıkarılıyor...")
        subtitles, show_subtitles = extract_subtitles(info, subtitle_choice)
        print(f"✓ Altyazılar çıkarıldı! (Uzunluk: {len(subtitles)} karakter)")
        
        # İçeriği analiz et
        print("\n3. İçerik analiz ediliyor...")
        print("OpenAI API'ye istek gönderiliyor...")
        viral_parts = analyze_content(subtitles, info.get('duration', 0))
        print(f"✓ İçerik analiz edildi! {len(viral_parts)} viral kısım bulundu.")
        
        # Shorts videoları oluştur
        print("\n4. Shorts videoları oluşturuluyor...")
        create_shorts(video_path, viral_parts, show_subtitles)
        print("✓ Shorts videoları oluşturuldu!")
        
    elif choice == "2":
        # Yerel video dosyasını al
        video_path = input("\nVideo dosyasının adını girin (örn: video.mp4): ").strip()
        
        if not os.path.exists(video_path):
            print(f"Hata: {video_path} dosyası bulunamadı!")
            return
            
        print("\n1. Video dosyası kontrol ediliyor...")
        print("✓ Video dosyası bulundu!")
        
        # Videoyu işle
        process_local_video(video_path)
        
    else:
        print("Geçersiz seçim! Lütfen 1 veya 2 girin.")
        return
    
    print("\nİşlem tamamlandı!")

if __name__ == "__main__":
    print(os.path.exists('DynaPuff/static/DynaPuff-Regular.ttf'))
    main() 