# Long to Short Video Converter

A powerful tool to convert long videos into engaging short-form content for TikTok, YouTube Shorts, and Instagram Reels. No CapCut or premium accounts required!

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/ramazanserifakbuz)

## 🌟 Features

- Convert long YouTube videos to short-form content
- Automatic subtitle generation with Whisper AI
- Smart content analysis using OpenAI GPT
- Multiple language support for subtitles
- Custom background video support
- Professional text overlays with animations
- No watermark or premium account required
- GPU acceleration support (NVIDIA)

## 📋 Requirements

- Python 3.8+
- FFmpeg
- ImageMagick
- NVIDIA GPU (optional, for faster processing)
- Background video (bg.mp4) in 1920x1080 resolution
- Logo file (logo.png) in 512x512 resolution

### Required Files
Place these files in the root directory of the project:
- `bg.mp4`: Background video (1920x1080) from [Pexels](https://www.pexels.com/search/videos/background/) or [Pixabay](https://pixabay.com/videos/search/background/)
- `logo.png`: Your logo file (512x512)

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/longtoshort.git
cd longtoshort
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg and ImageMagick:
- Windows: Download and install from official websites
- Linux: `sudo apt-get install ffmpeg imagemagick`
- macOS: `brew install ffmpeg imagemagick`

4. Create a `.env` file:
```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
```

## 🎥 Usage

1. Run the program:
```bash
python main.py
```

2. Choose your input method:
   - Download from YouTube
   - Use local video file

3. Select subtitle options:
   - Generate with Whisper AI
   - Continue without subtitles

4. Choose language for subtitles (if using Whisper)

5. Wait for processing:
   - Video download (if from YouTube)
   - Subtitle generation
   - Content analysis
   - Short video creation

## 🎬 Example

Input: [Long YouTube Video](https://www.youtube.com/watch?v=example)
Output: [TikTok Short](https://www.tiktok.com/@astrolojiyorumlari/video/7514114086037130497)

## 🔧 System Architecture

### Video Processing
- Downloads video in highest quality
- Extracts audio for subtitle generation
- Analyzes content for viral segments
- Creates short-form videos with:
  - Custom background
  - Positioned main video
  - Animated text overlays
  - Generated subtitles

### Background Video
- Uses a custom background video (bg.mp4)
- Automatically loops to match content length
- Resizes and crops for vertical format
- Applies professional transitions

### Video Positioning
- Main video positioned at bottom 65% of screen
- Text overlays at top and bottom
- Professional padding and spacing
- Smooth animations and transitions

### Subtitle Generation
- Uses Whisper AI for accurate transcription
- Supports multiple languages
- Automatic timing and positioning
- Professional styling with background

## 🌐 Supported Platforms

- YouTube to TikTok
- YouTube to Shorts
- YouTube to Reels
- Local video to short-form content

## ⚙️ Technical Details

### Video Output
- Resolution: 1080x1920 (9:16)
- Format: MOV
- Codec: H.264 (NVENC if available)
- Bitrate: 4000k
- Audio: AAC 192k

### Text Overlay
- Custom font support
- Professional animations
- Background blur
- Stroke effects

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ☕ Support

If you find this tool helpful, consider buying me a coffee:
[Buy Me A Coffee](https://buymeacoffee.com/ramazanserifakbuz)

## ⚠️ Known Issues

- Occasional translation errors may occur in certain video types
- Some subtitle timing issues might need manual adjustment
- Background video compatibility varies based on source

## 🚧 Upcoming Features ⏳

- [ ] Multi-output format support (TikTok, YouTube Shorts, Instagram Reels simultaneously)
- [ ] Local video processing improvements
- [ ] Script-based sharing automation
- [ ] Advanced automatic editing features
- [ ] Custom transition effects
- [ ] Batch processing support
- [ ] AI-powered content optimization
- [ ] Social media integration
- [ ] Custom watermark options
- [ ] Advanced subtitle styling 