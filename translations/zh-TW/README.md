# VideoSaver - 項尖视频下載

> 基於yt-dlp的線上视频下載工具，支持1800+平台，一鍵解析下載，手機電腦都能用。

## ✨ 功能特性

- 🚀 **極速下載** — 多線程加速，支持高清视频
- 🌐 **1800+ 平台** — YouTube、B站、抖音、TikTok、Twitter/X、Instagram、快手、微博、小红书等
- 🎬 **高清無水印** — 支持 4K/2K/1080P，原始畫質
- 📱 **手機也能用** — 响應式設計，手機瀏覽器直接打開
- 🎵 **音頻提取** — 支持提取純音頻（MP3/M4A）
- 🎯 **多格式選擇** — 自由選擇分辨率和文件格式

## 🛠 技術堆疊

| 組件 | 技术 |
|------|------|
| 後端 | Python 3.9+ / FastAPI / yt-dlp |
| 前端 | Vue 3 / Vite |
| 音頻視頻處理 | ffmpeg (通過 imageio-ffmpeg 自動集成) |
| 反爬繞過 | curl_cffi (瀏覽器指紋模擬) |

## 📦 專案結構

```
free-video-download/
├── app.py                  # FastAPI 後端主程序
├── start.py                # 启動腳本（自動設置 UTF-8 编码）
├── start.sh                # Linux/Mac 启動腳本
├── requirements.txt        # Python 依賴
├── .gitignore
├── README.md
└── frontend/               # Vue 3 前端
    ├── package.json
    ├── vite.config.js
    ├── index.html
    ├── public/
    │   └── vite.svg
    └── src/
        ├── main.js         # Vue 入口
        └── App.vue         # 主組件（UI + 互動邏輯）
```

## 🚀 快速開始

### 環境要求

- Python 3.9+
- Node.js 18+（僅前端開發時需要）

### 1. 克隆專案

```bash
git clone https://github.com/1723514417/free-video-download.git
cd free-video-download
```

### 2. 安裝後端依賴

```bash
# 創建虛擬環境（推薦）
python -m venv venv

# 激活虛擬環境
# Windows (CMD):
venv\Scripts\activate
# Windows (Git Bash):
source venv/Scripts/activate
# macOS/Linux:
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

### 3. 启動後端服務

**方式一：使用啟動腳本（推薦，自動設置 UTF-8 编码）**

```bash
# Windows:
python start.py

# macOS/Linux:
bash start.sh
```

**方式二：直接啟動**

```bash
python app.py
```

啟動成功後會看到以下日誌：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

然後在瀏覽器打開 **http://localhost:8000** 即可使用。

### 4.（選擇性）前端開發

如果需要修改前端 UI：

```bash
cd frontend

# 安裝前端依賴
npm install

# 启動開發服務器（帶熱更新，API 請求自動代理到後端）
npm run dev

# 构建生產版本
npm run build
```

前端開發服務器運行在 `http://localhost:5173`，會自動將 `/api` 請求代理到後端 `http://localhost:8000`。

構建後需要重启後端服務以加载最新的前端文件。

## 📖 API 接口

### 解析视频信息

```
POST /api/parse
Content-Type: application/json

請求體：
{
  "url": "https://www.bilibili.com/video/BV1hmQ4BdEQf"
}

回應：
{
  "title": "视频標題",
  "thumbnail": "縮略圖URL",
  "duration": 120.5,
  "uploader": "上傳者",
  "description": "视频簡介...",
  "webpage_url": "原始URL",
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

### 下載视频

```
GET /api/download?url=视频URL&format_id=格式ID

返回：视频文件（二進制流）
```

### 圖片代理（繞過防盜鏈）

```
GET /api/proxy-image?url=圖片URL

返回：圖片文件
```

### 获取支持平台列表

```
GET /api/supported-sites

返回：平台分類列表
```

## ⚠️ 注意事項

1. **ffmpeg**：通過 `imageio-ffmpeg` 自動安裝，無需手動配置。B站等 DASH 格式平台需要 ffmpeg 合並音頻視頻流。
2. **视频無聲音**：如果下載的视频沒有聲音，通常是 ffmpeg 未正確加載。檢查後端啟動日誌是否包含 ffmpeg 路徑。
3. **防盜鏈**：縮略圖通過後端代理加載，繞過 B站 等平台的 Referer 防盜鏈檢查。
4. **暫時文件**：下載的视频文件保存在 `downloads/` 目錄，下載完成後自動清理。
5. **編碼問題**：如果 Git Bash 出現中文亂碼，請使用 `python start.py` 啟動，它會自動設置 UTF-8 编码。
6. **僅供學習交流**：請遵守當地法律法規，尊重视频創作者的版權。

## 📄 開源協議

本项目基於 [yt-dlp](https://github.com/yt-dlp/yt-dlp)（Unlicense 協議）構建。