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
import whisper
import torch
from faster_whisper import WhisperModel
import srt
import datetime as dt

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
       - Kesinlikle emoji kullanma!
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
    # Ana font dosyasının varlığını kontrol et
    if not os.path.exists(main_font_path):
        print(f"HATA: Ana font dosyası bulunamadı: {main_font_path}")
        raise FileNotFoundError(f"Ana font dosyası bulunamadı: {main_font_path}")

    current_font_size = font_size
    max_attempts = 10
    
    # Metin sığana kadar font boyutunu küçült (ana font ile ölçüm yaparak)
    main_font_for_sizing = None
    total_text_height = 0
    min_top_offset_overall = 0

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

            available_height_for_sizing = height - 80 # Increased padding
            if max_line_width <= width and total_text_height <= available_height_for_sizing:
                print(f"Metin başarıyla sığdırıldı. Font Boyutu: {current_font_size}, Genişlik: {max_line_width}/{width}, Yükseklik: {total_text_height}/{available_height_for_sizing})")
                break # Başarılı, döngüden çık
            else:
                print(f"DEBUG: Metin sığmadı - max_line_width: {max_line_width}/{width}, total_text_height: {total_text_height}/{available_height_for_sizing}")
                if current_font_size > 10:
                    current_font_size -= 5
                    print(f"Metin sığmadı, font boyutu düşürülüyor: {current_font_size}")
                    # Bir sonraki denemeye devam et
                else:
                    print("Minimum font boyutuna ulaşıldı, metin hala sığmıyor.")
                    break # Sığmıyor, döngüden çık

        except Exception as e:
            print(f"Deneme {attempt+1}: Font boyutlandırma sırasında hata: {str(e)}")
            if current_font_size > 10:
                current_font_size -= 5
                continue # Hata oluştu, fontu küçültüp tekrar dene
            raise # Minimum font boyutunda da hata, hatayı fırlat


    if main_font_for_sizing is None:
        raise Exception("Ana font yüklenemedi veya boyutlandırılamadı.")

    # Son seçilen font boyutuyla ana fontu yeniden yükle
    final_main_font = ImageFont.truetype(main_font_path, current_font_size)


    # Son görüntüyü oluştur
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Metni dikeyde ortala ve ekstra boşluk bırak
    vertical_padding = 80 # Increased padding
    y_position = (height - total_text_height) // 2 
    
    # Adjust y_position based on the highest point above baseline to prevent clipping
    # Add absolute value of min_top_offset_overall to y_position to shift text down if ascenders are clipped
    y_position_adjusted = y_position - min_top_offset_overall # This effectively pushes the entire block down
    
    # Ensure minimum vertical padding from top
    if y_position_adjusted < vertical_padding:
        y_position_adjusted = vertical_padding

    # Alt kısım için ekstra boşluk ekle
    bottom_padding = 40  # Alt kısım için ekstra boşluk
    y_position_adjusted = min(y_position_adjusted, height - total_text_height - bottom_padding)

    print(f"DEBUG: Initial y_position: {y_position}, min_top_offset_overall: {min_top_offset_overall}, y_position_adjusted: {y_position_adjusted}")

    current_y = y_position_adjusted
    
    # Her satırı ana font ile çiz
    for line in lines:
        # Satırın yatayda ortalanması için başlangıç noktası
        line_width = final_main_font.getbbox(line)[2] - final_main_font.getbbox(line)[0]
        x = (width - line_width) // 2
        
        draw.text((x, current_y), line, font=final_main_font, fill='white', stroke_width=2, stroke_fill='black')
        
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

def create_shorts(video_path, viral_parts, srt_path=None):
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
                title_full = part.get('title', '')
                if title_full:
                    try:
                        # Clean [] from title using re.sub for robustness
                        title_full = re.sub(r'\[|\]', '', title_full).strip() # Using re.sub for cleaner removal
                        print(f"DEBUG: Cleaned title_full: '{title_full}'") # Added this debug print

                        # Başlık için güvenli bir dosya adı oluştur
                        safe_title = re.sub(r'[^\w\s-]', '', title_full).strip().replace(' ', '_')
                        # Çıktı klasörünü belirle
                        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_dir = os.path.join('.', f"shorts_output_{safe_title}_{timestamp}")
                        os.makedirs(output_dir, exist_ok=True)
                        print(f"Çıktı klasörü oluşturuldu: {output_dir}")

                        # Başlık için arka plan oluştur
                        title_bg_height = 240 # Increased height again
                        title_bg = ColorClip(size=(target_w, title_bg_height), color=(0, 0, 0, 128))
                        title_bg = title_bg.set_duration(clip_duration)
                        title_bg = title_bg.set_position(('center', 50))

                        # Ana başlık metin görüntüsünü oluştur
                        text_image_np = create_text_image(
                            title_full, # Sadece metin kısmını gönder
                            target_w - 80, # Daha geniş alan bırak (her iki yandan 40px boşluk)
                            title_bg_height, # Yüksekliği arka plan yüksekliğiyle aynı tut
                            font_size=90,
                            main_font_path='DynaPuff/static/DynaPuff-Regular.ttf', # Ana fontu belirle
                            output_folder=output_dir # Test görüntüsünü kaydetmek için klasör yolunu ilet
                        )
                        txt_clip = ImageClip(text_image_np)
                        txt_clip = txt_clip.set_duration(clip_duration)
                        txt_clip = txt_clip.set_position(('center', 50))

                        # Fade efektleri
                        fade_duration = 0.5
                        txt_clip = txt_clip.crossfadein(fade_duration)
                        txt_clip = txt_clip.crossfadeout(fade_duration)
                        title_bg = title_bg.crossfadein(fade_duration)
                        title_bg = title_bg.crossfadeout(fade_duration)

                        overlay_clips_for_this_short.append(title_bg)
                        overlay_clips_for_this_short.append(txt_clip)

                    except Exception as e:
                        print(f"Başlık eklenirken hata oluştu: {str(e)}")
                        print("Hata detayları:")
                        import traceback
                        traceback.print_exc()
                        print("Başlık olmadan devam ediliyor...")
                        # Başlık olmadan devam etmek için varsayılan çıktı klasörü oluştur
                        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_dir = os.path.join('.', f"shorts_output_{timestamp}")
                        os.makedirs(output_dir, exist_ok=True)

                # Tüm klipleri birleştir
                final_clips_list = [bg_combined, clip] + overlay_clips_for_this_short

                # Altyazıları ekle (eğer srt_path varsa)
                if srt_path and os.path.exists(srt_path):
                    print(f"  Altyazılar {srt_path} dosyasından alınıyor...")
                    with open(srt_path, 'r', encoding='utf-8') as f:
                        full_subs = list(srt.parse(f.read()))

                    # Sadece mevcut klibin zaman aralığına düşen altyazıları filtrele
                    relevant_subs = [
                        sub for sub in full_subs
                        if not (sub.end.total_seconds() < start_time or sub.start.total_seconds() > end_time)
                    ]
                    print(f"  Klip için {len(relevant_subs)} altyazı segmenti bulundu.")

                    for sub in relevant_subs:
                        sub_start = sub.start.total_seconds() - start_time # Klibin başlangıcına göre ayarla
                        sub_end = sub.end.total_seconds() - start_time     # Klibin başlangıcına göre ayarla
                        
                        # Altyazı klibi oluşturma sırasında geçerli zaman aralığı kontrolü
                        if sub_end <= sub_start:
                            continue # Geçersiz süre, atla

                        # Metni MoviePy TextClip için yeniden paketle
                        wrapped_sub_text = textwrap.fill(sub.content, width=25) # Altyazı satır uzunluğunu 25 karakterle sınırla

                        # Altyazı için arka plan
                        sub_bg_height = 120 # Arka plan yüksekliğini arttırdık
                        sub_bg = ColorClip(size=(target_w, sub_bg_height), color=(0, 0, 0, 128))
                        sub_bg = sub_bg.set_duration(sub_end - sub_start)
                        sub_bg = sub_bg.set_start(sub_start)
                        sub_bg = sub_bg.set_position(('center', target_h - sub_bg_height - 150)) # Konumu daha da yukarı çektik
                        
                        sub_txt_clip = TextClip(
                            wrapped_sub_text,
                            fontsize=70, # Font boyutunu 70 yaptık
                            color='white',
                            font='Arial-Bold', # Kalın font stili
                            stroke_color='black',
                            stroke_width=2,
                            method='caption', # Metni daha iyi sarmak için
                            size=(target_w - 40, None) # Genişliği sınırla
                        )
                        sub_txt_clip = sub_txt_clip.set_duration(sub_end - sub_start)
                        sub_txt_clip = sub_txt_clip.set_start(sub_start)
                        sub_txt_clip = sub_txt_clip.set_position(('center', target_h - sub_bg_height - 150 + 10)) # Konumu daha da yukarı çektik
                        
                        # Animasyon ekle (fade in/out)
                        fade_duration = 0.2 # Hızlı geçiş
                        sub_bg = sub_bg.crossfadein(fade_duration).crossfadeout(fade_duration)
                        sub_txt_clip = sub_txt_clip.crossfadein(fade_duration).crossfadeout(fade_duration)

                        final_clips_list.append(sub_bg)
                        final_clips_list.append(sub_txt_clip)

                # CompositeVideoClip oluştur
                final_clip = CompositeVideoClip(
                    final_clips_list,
                    size=(target_w, target_h)
                ).set_duration(clip_duration)
                
                # Klibi kaydet
                output_path = os.path.join(output_dir, f'{video_id}_{safe_title}_{timestamp}.mov')
                print(f"\nKısa video kaydediliyor: {output_path}")
                
                # Önce NVIDIA NVENC ile kaydetmeyi dene
                try:
                    final_clip.write_videofile(
                        output_path.replace(".mov", "_nvenc.mov"), # Çıktı dosyası adı sonunda _nvenc olacak
                        codec='h264_nvenc', # NVIDIA GPU donanım kodlayıcısı
                        bitrate='4000k',
                        audio_codec='aac',
                        audio_bitrate='192k',
                        preset='p7', # NVENC için optimize edilmiş preset (hız ve kalite dengesi)
                        # threads=4, # Donanım kodlamada genellikle thread sayısı otomatik yönetilir.
                        ffmpeg_params=[
                            '-rc:v', 'vbr_hq', # Değişken bit oranı, yüksek kalite
                            '-cq:v', '23', # Kalite ayarı (CRF yerine)
                            '-movflags', '+faststart',
                            '-pix_fmt', 'yuv420p',
                            '-colorspace', 'bt709',
                            '-color_primaries', 'bt709',
                            '-color_trc', 'bt709',
                            '-color_range', 'tv'
                        ]
                    )
                    print(f"✓ Kısa video (NVIDIA NVENC ile) kaydedildi: {output_path.replace('.mov', '_nvenc.mov')}")
                except Exception as e:
                    print(f"Uyarı: NVIDIA NVENC ile video kaydedilirken hata oluştu: {str(e)}")
                    print("CPU tabanlı libx264 kodlayıcısına geri dönülüyor...")
                    # Hata durumunda CPU tabanlı libx264 kodlayıcısı ile kaydet
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
                            '-movflags', '+faststart',
                            '-pix_fmt', 'yuv420p',
                            '-vf', 'format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2',
                            '-colorspace', 'bt709',
                            '-color_primaries', 'bt709',
                            '-color_trc', 'bt709',
                            '-color_range', 'tv'
                        ]
                    )
                    print(f"✓ Kısa video (libx264 ile) kaydedildi: {output_path}")

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

def read_srt_file(file_path):
    """SRT dosyasını okur ve tüm metni birleştirir"""
    try:
        print(f"\nSRT dosyası okunuyor: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            subs = list(srt.parse(f.read()))
        
        full_text = " ".join([s.content for s in subs])
        print(f"SRT metin uzunluğu: {len(full_text)} karakter")
        return full_text
    except Exception as e:
        print(f"SRT dosyası okuma hatası: {str(e)}")
        return ""

def transcribe_audio(video_path, language=None):
    """Whisper kullanarak videodaki konuşmaları transkript eder"""
    try:
        print("\nKonuşmalar transkript ediliyor...")
        
        # Whisper modelini yükle
        model = WhisperModel("small", device="cuda" if torch.cuda.is_available() else "cpu", compute_type="float32")
        
        # Videodan ses dosyasını çıkar
        audio_path = "temp_audio.wav"
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(audio_path, codec='pcm_s16le')
        
        # Transkript yap
        print("\nSes transkripsiyonu başlatılıyor...")
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            word_timestamps=True
        )
        
        # SRT formatında altyazı oluştur
        subs = []
        for i, segment in enumerate(segments):
            print(f"  Segment {i+1} işleniyor: [{segment.start:.2f}s - {segment.end:.2f}s] - {segment.text[:50]}...") # Yeni satır
            start_time = dt.timedelta(seconds=segment.start)
            end_time = dt.timedelta(seconds=segment.end)
            
            sub = srt.Subtitle(
                index=i+1,
                start=start_time,
                end=end_time,
                content=segment.text.strip()
            )
            subs.append(sub)
        
        # SRT dosyasını kaydet
        srt_path = os.path.splitext(video_path)[0] + ".srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt.compose(subs))
        
        # Geçici ses dosyasını sil
        os.remove(audio_path)
        
        print(f"✓ Transkript tamamlandı! Altyazı dosyası kaydedildi: {srt_path}")
        return srt_path
        
    except Exception as e:
        print(f"Transkript hatası: {str(e)}")
        return None

def create_subtitle_clip(text, start_time, end_time, video_size):
    """Altyazı klibi oluşturur"""
    try:
        # Altyazı için arka plan
        bg_height = 80
        bg = ColorClip(size=(video_size[0], bg_height), color=(0, 0, 0, 128))
        bg = bg.set_duration(end_time - start_time)
        bg = bg.set_start(start_time)
        bg = bg.set_position(('center', video_size[1] - bg_height - 50))
        
        # Altyazı metni
        # Metni daha kısa satırlara böl (MoviePy'nin TextClip'i için)
        wrapped_text = textwrap.fill(text, width=40) # Satır uzunluğunu 40 karakterle sınırla
        
        txt_clip = TextClip(
            wrapped_text,
            fontsize=50, # Font boyutunu büyüttük
            color='white',
            font='Arial-Bold', # Kalın font stili
            stroke_color='black',
            stroke_width=2
        )
        txt_clip = txt_clip.set_duration(end_time - start_time)
        txt_clip = txt_clip.set_start(start_time)
        txt_clip = txt_clip.set_position(('center', video_size[1] - bg_height - 50 + 10)) # Konumu ayarladık
        
        # Animasyon ekle (fade in/out)
        fade_duration = 0.3 # Hızlı geçiş
        bg = bg.crossfadein(fade_duration).crossfadeout(fade_duration)
        txt_clip = txt_clip.crossfadein(fade_duration).crossfadeout(fade_duration)

        return [bg, txt_clip]
        
    except Exception as e:
        print(f"Altyazı klibi oluşturma hatası: {str(e)}")
        return []

def process_local_video(video_path):
    """Yerel videoyu işler"""
    try:
        # Video bilgilerini al
        video = VideoFileClip(video_path)
        duration = video.duration
        video.close()
        
        # Altyazı seçeneği zaten main fonksiyonunda sorulduğu için burada tekrar sormaya gerek yok.
        # Eğer ana fonksiyondan buraya altyazı_seçimi ve dil_seçimi bilgisi geliyorsa kullanılabilir.
        
        srt_path = None
        subtitles_text = ""

        # Eğer daha önce altyazı oluşturma seçeneği seçildiyse
        # Bu kısım main fonksiyonundan çağrıldığı için burada global bir değişkene veya fonksiyona parametreye ihtiyacımız var.
        # Basitlik için, bu fonksiyonu ana fonksiyondan çağırırken altyazı ve dil seçeneklerini doğrudan alacağız.

        # İçeriği analiz et
        print("\nİçerik analiz ediliyor...")
        print("OpenAI API'ye istek gönderiliyor...")

        # process_local_video fonksiyonu main fonksiyonundaki logic'e göre revize edildi.
        # Artık bu fonksiyon, altyazı oluşturma ve analiz etme adımlarını kendisi yapmayacak.
        # Bunun yerine, main fonksiyonu tarafından çağrıldığında altyazı metni zaten belirlenmiş olacak.
        # Bu nedenle, bu fonksiyonun parametrelerini ve çağrılma şeklini değiştirmemiz gerekecek.
        # Şimdilik bu fonksiyonu altyazı logic'inden ayırıyorum.

        # Sadece altyazısız veya var olan altyazıyla shorts oluşturma logic'i kalacak.
        # Bu kısım ana fonksiyonda tekrar düzenlenecek.
        print("\n3. İçerik analiz ediliyor...")
        print("OpenAI API'ye istek gönderiliyor...")
        viral_parts = analyze_content(subtitles_text, duration) # subtitles_text parametre olarak gelmeli
        print(f"✓ İçerik analiz edildi! {len(viral_parts)} viral kısım bulundu.")
        
        # Shorts videoları oluştur
        print("\n4. Shorts videoları oluşturuluyor...")
        create_shorts(video_path, viral_parts, srt_path=srt_path) # srt_path de buraya parametre olarak gelmeli
        print("✓ Shorts videoları oluşturuldu!")
        
    except Exception as e:
        print(f"Video işlenirken hata oluştu: {str(e)}")
        raise

def main():
    print("\n=== Video Processing Program ===")
    print("1. Download from YouTube")
    print("2. Exit")
    
    choice = input("\nYour choice (1/2): ").strip()
    
    if choice == "1":
        # Get YouTube URL
        url = input("\nEnter YouTube video URL: ")
        
        # Subtitle options
        print("\nSubtitle options:")
        print("1. Generate automatic subtitles with Whisper")
        print("2. Continue without subtitles")
        
        subtitle_choice = input("\nYour subtitle choice (1/2): ").strip()
        
        # Language selection
        selected_language = None
        if subtitle_choice == "1":
            print("\nLanguage options:")
            print("1. Auto-detect")
            print("2. Turkish")
            print("3. English")
            print("4. German")
            print("5. French")
            print("6. Spanish")
            print("7. Italian")
            print("8. Russian")
            print("9. Arabic")
            print("10. Japanese")
            print("11. Korean")
            print("12. Chinese")
            
            lang_choice = input("\nYour language choice (1-12): ").strip()
            
            language_map = {
                "2": "tr",
                "3": "en",
                "4": "de",
                "5": "fr",
                "6": "es",
                "7": "it",
                "8": "ru",
                "9": "ar",
                "10": "ja",
                "11": "ko",
                "12": "zh"
            }
            
            if lang_choice != "1":
                selected_language = language_map.get(lang_choice)
                if not selected_language:
                    print("Invalid language choice! Using auto-detection.")
        
        # Download video
        print("\n1. Downloading video...")
        video_path, info = download_video(url)
        print("✓ Video downloaded!")
        
        srt_path = None
        subtitles_text = ""

        if subtitle_choice == "1":
            # Generate transcript with Whisper
            print("\n2. Generating transcript...")
            srt_path = transcribe_audio(video_path, selected_language)
            
            if srt_path:
                # Read SRT text
                subtitles_text = read_srt_file(srt_path)
        
        # Analyze content
        print("\n3. Analyzing content...")
        print("Sending request to OpenAI API...")
        viral_parts = analyze_content(subtitles_text, info.get('duration', 0))
        print(f"✓ Content analyzed! Found {len(viral_parts)} viral segments.")
        
        # Create short videos
        print("\n4. Creating short videos...")
        create_shorts(video_path, viral_parts, srt_path=srt_path)
        print("✓ Short videos created!")
        
    elif choice == "2":
        print("Exiting program...")
        return
    else:
        print("Invalid choice! Please enter 1 or 2.")
        return
    
    print("\nProcess completed!")

if __name__ == "__main__":
    print(os.path.exists('DynaPuff/static/DynaPuff-Regular.ttf'))
    main() 