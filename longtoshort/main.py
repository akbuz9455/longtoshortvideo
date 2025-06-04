import os
from dotenv import load_dotenv
import yt_dlp
from openai import OpenAI
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, TextClip, ColorClip
import json
import re
import cv2
import numpy as np
from PIL import Image
import io
from moviepy.config import change_settings
import textwrap
from xml.etree import ElementTree as ET

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
        'format': 'best',  # En iyi kaliteyi otomatik seç
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
        'skip_download': False,
        'keepvideo': True,
        'verbose': True  # Daha detaylı hata ayıklama için
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("\nVideo bilgileri alınıyor...")
            info = ydl.extract_info(url, download=True)
            print("\nVideo bilgileri:")
            print(f"Başlık: {info.get('title', 'Bilinmiyor')}")
            print(f"Süre: {info.get('duration', 'Bilinmiyor')} saniye")
            print(f"Altyazı dilleri: {list(info.get('subtitles', {}).keys())}")
            print(f"Otomatik altyazı dilleri: {list(info.get('automatic_captions', {}).keys())}")
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
            'verbose': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return output_template, info

def read_vtt_file(file_path):
    """VTT dosyasını okur ve metni çıkarır"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # VTT başlığını ve zaman damgalarını kaldır
        lines = content.split('\n')
        text_lines = []
        for line in lines:
            # Zaman damgası satırlarını atla
            if '-->' in line:
                continue
            # Boş satırları atla
            if not line.strip():
                continue
            # VTT başlığını atla
            if line.startswith('WEBVTT'):
                continue
            text_lines.append(line.strip())
            
        return ' '.join(text_lines)
    except Exception as e:
        print(f"VTT dosyası okuma hatası: {str(e)}")
        return ""

def extract_subtitles(info):
    """Video bilgilerinden altyazıları çıkarır"""
    try:
        print("\nMevcut altyazı dilleri:", list(info.get('subtitles', {}).keys()))
        print("Mevcut otomatik altyazı dilleri:", list(info.get('automatic_captions', {}).keys()))
        
        video_id = info.get('id', '')
        if not video_id:
            raise Exception("Video ID bulunamadı!")
            
        # Önce Türkçe VTT dosyasını dene
        tr_vtt = f"{video_id}.tr.vtt"
        if os.path.exists(tr_vtt):
            print(f"Türkçe VTT dosyası bulundu: {tr_vtt}")
            text = read_vtt_file(tr_vtt)
            if len(text) > 100:
                return text
                
        # Türkçe yoksa İngilizce VTT dosyasını dene
        en_vtt = f"{video_id}.en.vtt"
        if os.path.exists(en_vtt):
            print(f"İngilizce VTT dosyası bulundu: {en_vtt}")
            text = read_vtt_file(en_vtt)
            if len(text) > 100:
                return text
        
        # Hiçbiri yoksa orijinal yöntemi dene
        if 'tr' in info.get('subtitles', {}):
            subtitles = info['subtitles']['tr']
            if isinstance(subtitles, list) and len(subtitles) > 0:
                if 'data' in subtitles[0]:
                    return subtitles[0]['data']
                elif 'ext' in subtitles[0]:
                    return subtitles[0]['ext']
        
        if 'en' in info.get('subtitles', {}):
            subtitles = info['subtitles']['en']
            if isinstance(subtitles, list) and len(subtitles) > 0:
                if 'data' in subtitles[0]:
                    return subtitles[0]['data']
                elif 'ext' in subtitles[0]:
                    return subtitles[0]['ext']
        
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
    if not text:
        raise Exception("Altyazı metni boş!")
        
    print(f"\nAltyazı metni uzunluğu: {len(text)} karakter")
    print("İlk 500 karakter:", text[:500])
    
    if len(text) < 100:
        raise Exception("Altyazı metni çok kısa! En az 100 karakter olmalı.")
    
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
    3. Başlıklar içerikle ilgili ve ilgi çekici olmalı
    4. Sadece JSON array döndür, başka açıklama ekleme

    Altyazı:
    {text}
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Sen bir video içerik analisti ve başlık uzmanısın. Verilen metni analiz edip en ilgi çekici kısımları bulacak ve her kısım için içerikle tamamen ilgili, özgün başlıklar oluşturacaksın. Yanıtını KESİNLİKLE JSON array formatında ver, başka hiçbir açıklama ekleme."},
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
                raise Exception("ChatGPT geçersiz bir JSON array döndürdü!")
                
            if len(result) == 0:
                raise Exception("ChatGPT boş bir liste döndürdü!")
                
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
            raise Exception("ChatGPT yanıtı geçerli bir JSON değil!")
            
    except Exception as e:
        print(f"Beklenmeyen hata: {str(e)}")
        print("Hata detayları:")
        import traceback
        traceback.print_exc()
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
                # Cümlenin başladığı zamandan başla
                start_time = part.get('sentence_start', part['start_time'])
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
                # Önce videoyu hedef yüksekliğe göre yeniden boyutlandır
                clip = clip.resize(height=target_h)
                
                # Eğer genişlik hedef genişlikten büyükse, kırp
                if clip.w > target_w:
                    # Merkezi hesapla
                    x_center = clip.w / 2
                    # Kırpma koordinatlarını hesapla
                    x1 = int(x_center - target_w/2)
                    x2 = int(x_center + target_w/2)
                    clip = clip.crop(x1=x1, y1=0, x2=x2, y2=target_h)
                # Eğer genişlik hedef genişlikten küçükse, siyah arka plan ekle
                elif clip.w < target_w:
                    # Siyah arka plan oluştur
                    background = ColorClip(size=(target_w, target_h), color=(0, 0, 0))
                    background = background.set_duration(clip.duration)
                    
                    # Videoyu merkeze yerleştir
                    clip = clip.set_position(('center', 'center'))
                    
                    # Arka plan ve videoyu birleştir
                    clip = CompositeVideoClip([background, clip])
                
                # Başlık ekle
                title = part.get('title', '')
                if title:
                    try:
                        # Başlığı akıllıca satırlara böl
                        wrapped_title = smart_wrap_text(title)
                        lines = wrapped_title.count('\n') + 1
                        
                        # Başlık için arka plan oluştur (daha şeffaf ve daha uzun)
                        bg_height = 350 if lines > 1 else 250  # Yüksekliği artırdım
                        title_bg = ColorClip(size=(target_w, bg_height), color=(0, 0, 0, 120))  # Alpha değeri 120 (yarı şeffaf)
                        title_bg = title_bg.set_duration(clip.duration)
                        
                        # Başlık metnini oluştur
                        txt_clip = TextClip(
                            wrapped_title,
                            fontsize=70,
                            color='white',
                            font='Arial-Bold',
                            stroke_color='black',
                            stroke_width=2,
                            method='label',
                            align='center'
                        )
                        
                        # Başlık pozisyonunu ayarla (daha üstte)
                        if lines > 1:
                            txt_clip = txt_clip.set_position(('center', 75))  # Pozisyonu biraz aşağı çektim
                        else:
                            txt_clip = txt_clip.set_position(('center', 50))  # Pozisyonu biraz aşağı çektim
                        
                        txt_clip = txt_clip.set_duration(clip.duration)
                        
                        # Arka plan ve başlığı birleştir
                        title_composite = CompositeVideoClip([title_bg, txt_clip])
                        title_composite = title_composite.set_position(('center', 0))
                        
                        # Tüm klipleri birleştir
                        clip = CompositeVideoClip([clip, title_composite])
                        
                    except Exception as e:
                        print(f"Başlık eklenirken hata oluştu: {str(e)}")
                        print("Başlık olmadan devam ediliyor...")
                
                # Klibi kaydet
                output_path = f'{video_id}_short_{i+1}.mp4'
                clip.write_videofile(output_path, codec='libx264', bitrate='8000k')
                
            except Exception as e:
                print(f"Kısa video {i+1} oluşturulurken hata: {str(e)}")
                continue
        
        video.close()
        
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
        create_shorts(video_path, viral_parts)
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
        viral_parts = analyze_content(subtitles, info.get('duration', 0))
        print(f"✓ İçerik analiz edildi! {len(viral_parts)} viral kısım bulundu.")
        
        # Shorts videoları oluştur
        print("\n4. Shorts videoları oluşturuluyor...")
        create_shorts(video_path, viral_parts)
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