# VideoSaver - Universal Video Downloader

> An online video downloading tool based on yt-dlp, supporting over 1800 platforms, one-click parsing and downloading, compatible with both mobile and desktop devices.

## ✨ Features

- 🚀 **Fast Download** — Multithreading acceleration, supports high-definition videos
- 🌐 **1800+ Platforms** — YouTube, Bilibili, Douyin, TikTok, Twitter/X, Instagram, Kuaishou, Weibo, Xiaohongshu, etc.
- 🎬 **High-definition and Ad-free** — Supports 4K/2K/1080P, original quality
- 📱 **Mobile Compatibility** — Responsive design, can be used directly in mobile browsers
- 🎵 **Audio Extraction** — Supports extracting pure audio (MP3/M4A)
- 🎯 **Multiple Format Selection** — Free to choose resolution and file format

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| Backend   | Python 3.9+ / FastAPI / yt-dlp |
| Frontend  | Vue 3 / Vite |
| Video/Audio Processing | ffmpeg (automatically integrated through imageio-ffmpeg) |
| Anti-Crawling Bypass | curl_cffi (browser fingerprint simulation) |

## 📦 Project Structure

```
free-video-download/
├── app.py                  # FastAPI backend main program
├── start.py                # Startup script (automatically sets UTF-8 encoding)
├── start.sh                # Linux/Mac startup script
├── requirements.txt        # Python dependencies
├── .gitignore
├── README.md
└── frontend/               # Vue 3 frontend
    ├── package.json
    ├── vite.config.js
    ├── index.html
    ├── public/
    │   └── vite.svg
    └── src/
        ├── main.js         # Vue entry
        └── App.vue         # Main component (UI + interaction logic)
```

## 🚀 Quick Start

### Environment Requirements

- Python 3.9+
- Node.js 18+ (required only for frontend development)

### 1. Clone the Project

```bash
git clone https://github.com/1723514417/free-video-download.git
cd free-video-download
```

### 2. Install Backend Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# Windows (CMD):
venv\Scripts\activate
# Windows (Git Bash):
source venv/Scripts/activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Start the Backend Service

**Method 1: Using the Startup Script (recommended, automatically sets UTF-8 encoding)**

```bash
# Windows:
python start.py

# macOS/Linux:
bash start.sh
```

**Method 2: Directly Starting**

```bash
python app.py
```

After starting successfully, you will see the following logs:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

Then, open **http://localhost:8000** in your browser to use it.

### 4. (Optional) Frontend Development

If you need to modify the frontend UI:

```bash
cd frontend

# Install frontend dependencies
npm install

# Start the development server (with hot update, API requests automatically proxied to the backend)
npm run dev

# Build production version
npm run build
```

The frontend development server runs on `http://localhost:5173` and automatically proxies `/api` requests to the backend `http://localhost:8000`.

After building, you need to restart the backend service to load the latest frontend files.

## 📖 API Interface

### Parse Video Information

```
POST /api/parse
Content-Type: application/json

Request Body:
{
  "url": "https://www.bilibili.com/video/BV1hmQ4BdEQf"
}

Response:
{
  "title": "Video Title",
  "thumbnail": "Thumbnail URL",
  "duration": 120.5,
  "uploader": "Uploader",
  "description": "Video description...",
  "webpage_url": "Original URL",
  "formats": [
    {
      "format_id": "xxx",
      "ext": "mp4",
      "resolution": "1080p",
      "filesize": 52428800,
      "vcodec": "avc1",
      "acodec": "mp4a"
    }
  ]
}
```

### Download Video

```
GET /api/download?url=VideoURL&format_id=FormatID

Return: Video file (binary stream)
```

### Image Proxy (Bypass防盗链)

```
GET /api/proxy-image?url=ImageURL

Return: Image file
```

### Get List of Supported Platforms

```
GET /api/supported-sites

Return: Platform category list
```

## ⚠️ Notes

1. **ffmpeg**: Automatically installed through `imageio-ffmpeg`, no manual configuration required. Bilibili and other DASH format platforms require ffmpeg to merge audio and video streams.
2. **Video without sound**: If the downloaded video has no sound, it is usually due to ffmpeg not loading correctly. Check the backend startup logs for the ffmpeg path.
3. **Anti-hotlinking**: Thumbnails are loaded through backend proxy, bypassing Referer anti-hotlinking checks by platforms like Bilibili.
4. **Temporary files**: Downloaded video files are saved in the `downloads/` directory and are automatically cleaned up after downloading.
5. **Encoding issues**: If Git Bash has Chinese character garbling, please use `python start.py` to start, which will automatically set UTF-8 encoding.
6. **For learning and exchange only**: Please comply with local laws and regulations and respect the copyrights of video creators.

## 📄 Open Source License

This project is built based on [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense license).