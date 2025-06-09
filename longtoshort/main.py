import os
from dotenv import load_dotenv
import yt_dlp
from openai import OpenAI
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, TextClip, ColorClip, concatenate_videoclips
import json
import re
import cv2
import numpy as np
from PIL import Image
import io
from moviepy.config import change_settings
import textwrap
from xml.etree import ElementTree as ET
from datetime import datetime
import subprocess

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
os.environ['IMAGEMAGICK_FONT'] = font_path
os.environ['IMAGEMAGICK_FONT_PATH'] = os.path.dirname(font_path)

# MoviePy font ayarlarını güncelle
change_settings({
    "IMAGEMAGICK_BINARY": IMAGEMAGICK_BINARY,
    "IMAGEMAGICK_FONT": font_path,
    "IMAGEMAGICK_FONT_PATH": os.path.dirname(font_path)
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

def smart_wrap_text(text, max_chars=30):
    """Metni akıllıca satırlara böler"""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        word_length = len(word)
        # Eğer kelime çok uzunsa, kendisi bir satır olsun
        if word_length > max_chars:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = []
                current_length = 0
            lines.append(word)
            continue
            
        # Eğer mevcut satıra eklenirse max_chars'ı aşmayacaksa
        if current_length + word_length + len(current_line) <= max_chars:
            current_line.append(word)
            current_length += word_length
        else:
            # Mevcut satırı kaydet ve yeni satıra başla
            lines.append(' '.join(current_line))
            current_line = [word]
            current_length = word_length
    
    # Son satırı ekle
    if current_line:
        lines.append(' '.join(current_line))
    
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
       - İçerikle tamamen ilgili olmalı
       - İlgi çekici ve tıklama isteği uyandırmalı
       - Kısa ve öz olmalı (en fazla 50 karakter)
       - Clickbait tarzında ama yanıltıcı olmamalı
       - Merak uyandırmalı
       - Emoji kullanabilirsin (en fazla 2 tane)
       - Türkçe karakterler kullan (ç, ş, ı, ğ, ü, ö)
       - Büyük harfle başla
    4. Her kısım için açıklama şu özelliklere sahip olmalı:
       - Kısımda ne anlatıldığını özetle
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

def create_subtitle_clip(text, start_time, end_time, target_w, target_h, clip_duration, font_path):
    """Altyazı klibi oluşturur"""
    # Metni akıllıca satırlara böl
    wrapped_text = smart_wrap_text(text, max_chars=30)  # Daha kısa satırlar
    
    # Eğer metin çok kısaysa, minimum süre uygula
    min_duration = 1.5  # Minimum 1.5 saniye
    if end_time - start_time < min_duration:
        end_time = start_time + min_duration
    
    try:
        # Font dosyasının varlığını kontrol et
        if not os.path.exists(font_path):
            print(f"Uyarı: Font dosyası bulunamadı: {font_path}")
            raise FileNotFoundError(f"Font dosyası bulunamadı: {font_path}")
            
        # Font dosyasını kullan
        txt_clip = TextClip(
            wrapped_text,
            fontsize=75,
            color='white',
            font='ITCKRIST',  # Font adını kullan
            stroke_color='white',
            stroke_width=0,
            method='caption',
            align='center',
            size=(target_w - 100, None)
        )
        print(f"Altyazı klibi oluşturuldu, font: ITCKRIST")
    except Exception as e:
        print(f"Altyazı klibi oluşturulurken hata: {str(e)}")
        print(f"Kullanılan font: ITCKRIST")
        raise

    # Altyazı klibinin süresini ayarla
    actual_duration = end_time - start_time
    txt_clip = txt_clip.set_duration(actual_duration)

    # Altyazıyı ana videonun altına yerleştir
    subtitle_bottom_offset = 80 # Alttan 80px yukarıda (daha aşağıda)
    y_position = target_h - subtitle_bottom_offset - txt_clip.h

    # Altyazıyı doğru zamanda başlat
    txt_clip = txt_clip.set_start(start_time)
    txt_clip = txt_clip.set_position(('center', y_position))

    # Fade efekti için süreleri ayarla
    fade_duration = 0.2  # Fade süresi

    # Giriş ve çıkış fade efektlerini uygula
    txt_clip = txt_clip.crossfadein(fade_duration)
    txt_clip = txt_clip.crossfadeout(fade_duration)

    return txt_clip

def create_shorts(video_path, viral_parts, show_subtitles=True):
    """Viral kısımlardan Shorts videoları oluşturur"""
    try:
        # Font dosyasının tam yolunu belirle ve kontrol et
        font_path = os.path.abspath('DynaPuff.ttf')
        if not os.path.exists(font_path):
            print(f"Uyarı: Font dosyası bulunamadı: {font_path}")
            print("Mevcut dizindeki dosyalar:")
            print(os.listdir('.'))
            raise FileNotFoundError(f"Font dosyası bulunamadı: {font_path}")
        print(f"Kullanılan font dosyası: {font_path}")
        
        # ImageMagick için font adını ayarla
        font_name = "DynaPuff"  # ImageMagick için font adı
        
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
        
        for i, part in enumerate(viral_parts):
            try:
                # Cümlenin başladığı zamandan başla
                start_time = part.get('sentence_start', part['start_time'])
                end_time = part['end_time']
                clip_duration = end_time - start_time
                
                # Kısa video klibi oluştur
                clip = video.subclip(start_time, end_time)
                
                # Ses seviyesini %175'e çıkar
                clip = clip.volumex(1.75)
                
                # Arka plan videosunu hazırla
                # Gerekli tekrar sayısını hesapla
                repeat_count = int(clip_duration / bg_duration) + 1
                bg_clips = []
                
                for _ in range(repeat_count):
                    bg_clips.append(bg_video)
                
                # Arka plan videolarını birleştir
                bg_combined = concatenate_videoclips(bg_clips)
                # Kırp
                bg_combined = bg_combined.subclip(0, clip_duration)
                
                # Arka plan videosunun sesini kapat
                bg_combined = bg_combined.without_audio()
                
                # Arka plan videosunu dikey formata dönüştür
                bg_combined = bg_combined.resize(height=target_h)
                if bg_combined.w > target_w:
                    x_center = bg_combined.w / 2
                    x1 = int(x_center - target_w/2)
                    x2 = int(x_center + target_w/2)
                    bg_combined = bg_combined.crop(x1=x1, y1=0, x2=x2, y2=target_h)
                
                # Ana videoyu dikey formata dönüştür
                # Videoyu hedef yüksekliğin %65'ine göre yeniden boyutlandır
                clip = clip.resize(height=int(target_h * 0.65))
                
                # Videoyu alttan başlayarak ortala ve biraz daha yukarı taşı
                y_position = target_h - clip.h - 250  # Ana video dikey pozisyonu
                clip = clip.set_position(('center', y_position))

                # Bu kısa video klibi için overlay kliplerini (başlık) tutacak liste
                overlay_clips_for_this_short = []

                # Başlık ekle
                title = part.get('title', '')
                if title:
                    try:
                        # Başlığı akıllıca satırlara böl
                        wrapped_title = smart_wrap_text(title)
                        lines = wrapped_title.count('\n') + 1

                        # Başlık metni klibini oluştur
                        try:
                            # Font dosyasını kullan
                            txt_clip = TextClip(
                                wrapped_title,
                                fontsize=75,
                                color='white',
                                font='ITCKRIST',  # Font adını kullan
                                stroke_color='black',
                                stroke_width=0,
                                method='caption',
                                align='center',
                                size=(target_w - 100, None)
                            )
                            print(f"Başlık klibi oluşturuldu, font: ITCKRIST")
                        except Exception as e:
                            print(f"Başlık klibi oluşturulurken hata: {str(e)}")
                            print(f"Kullanılan font: ITCKRIST")
                            raise

                        # Başlık metninin kendi dikey pozisyonunu belirle (ana video tuvaline göre)
                        if lines == 1:
                            txt_clip_y = 50 # Konumu ayarladık
                        elif lines == 2:
                            txt_clip_y = 75 # Konumu ayarladık
                        else:
                            txt_clip_y = 100 # Konumu ayarladık

                        # Başlık arka planı yüksekliğini ve dikey pozisyonunu belirle (ana video tuvaline göre)
                        bg_padding = 75  # Üstten ve alttan eklenecek boşluk miktarı
                        bg_height = txt_clip.h + (bg_padding * 2)
                        bg_y_position = txt_clip_y - bg_padding # Metnin başlangıcından 75px yukarıda başla

                        # Başlık için arka plan oluştur
                        title_bg = ColorClip(size=(target_w, bg_height), color=(0, 0, 0, 60))
                        title_bg = title_bg.set_duration(clip_duration) # Arka plan süresini ayarla

                        # Başlık metni ve arka planı overlay listesine ekle
                        # Önce arka planı ekle, sonra metni ekle (arka plan altta kalmalı)
                        overlay_clips_for_this_short.append(title_bg.set_position(('center', bg_y_position)))
                        overlay_clips_for_this_short.append(txt_clip.set_position(('center', txt_clip_y)).set_duration(clip_duration)) # Metin süresini ayarla

                    except Exception as e:
                        print(f"Başlık eklenirken hata oluştu: {str(e)}")
                        import traceback
                        traceback.print_exc() # Hata detaylarını görmek için eklendi
                        print("Başlık olmadan devam ediliyor...")

                # Tüm klipleri birleştir
                # Kliplerin sıralaması önemli: arka plan videosu, ana video klibi, overlay klipleri (başlık)
                final_clips_list = [bg_combined, clip] + overlay_clips_for_this_short

                print(f"\nKısa video {i+1} için klipler hazırlanıyor...")
                print(f"Toplam klip sayısı: {len(final_clips_list)}")
                for idx, cl in enumerate(final_clips_list):
                    print(f"Klip {idx}: {type(cl).__name__}, Süre: {cl.duration if hasattr(cl, 'duration') else 'Bilinmiyor'}")

                try:
                    # CompositeVideoClip oluşturulmadan önce tüm kliplerin süresini kontrol et
                    for i, cl in enumerate(final_clips_list):
                        if cl.duration is None:
                            print(f"Hata: CompositeVideoClip oluşturulmadan önce {i}. klibin süresi None.")
                            print(f"Klip türü: {type(cl)}")
                            if hasattr(cl, 'filename'): 
                                print(f"Dosya adı: {cl.filename}")
                            raise ValueError(f"Klip {i} (tipi: {type(cl).__name__}) için süre ayarlanmadı")

                    print("\nCompositeVideoClip oluşturuluyor...")
                    # CompositeVideoClip oluşturulurken süreyi belirtelim
                    final_clip = CompositeVideoClip(
                        final_clips_list,
                        size=(target_w, target_h)
                    )

                    # CompositeVideoClip'in süresi bazen otomatik ayarlanmayabilir, manuel olarak belirleyelim
                    final_clip = final_clip.set_duration(clip_duration)
                    print("CompositeVideoClip başarıyla oluşturuldu!")
                
                    # Klibi kaydet
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = f'{video_id}_short_{i+1}_{timestamp}.mov'
                    print(f"\nKısa video {i+1} kaydediliyor: {output_path}")
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
                    print(f"✓ Kısa video {i+1} kaydedildi!")

                except Exception as e:
                    print(f"\nKısa video {i+1} oluşturulurken hata: {str(e)}")
                    print("Hata detayları:")
                    import traceback
                    traceback.print_exc()
                    print("\nKliplerin durumu:")
                    for idx, cl in enumerate(final_clips_list):
                        print(f"Klip {idx}: {type(cl).__name__}")
                        if hasattr(cl, 'duration'):
                            print(f"  Süre: {cl.duration}")
                        if hasattr(cl, 'size'):
                            print(f"  Boyut: {cl.size}")
                    continue

            except Exception as e:
                print(f"Kısa video {i+1} oluşturulurken hata: {str(e)}")
                import traceback
                traceback.print_exc() # Hata detaylarını görmek için eklendi
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
    main() 