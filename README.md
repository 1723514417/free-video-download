# VideoSaver - 万能视频下载

> 基于 yt-dlp 的在线视频下载工具，支持 1800+ 平台，一键解析下载，手机电脑都能用。

## ✨ 功能特性

- 🚀 **极速下载** — 多线程加速，支持高清视频
- 🌐 **1800+ 平台** — YouTube、B站、抖音、TikTok、Twitter/X、Instagram、快手、微博、小红书等
- 🎬 **高清无水印** — 支持 4K/2K/1080P，原始画质
- 📱 **手机也能用** — 响应式设计，手机浏览器直接打开
- 🎵 **音频提取** — 支持提取纯音频（MP3/M4A）
- 🎯 **多格式选择** — 自由选择分辨率和文件格式

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.9+ / FastAPI / yt-dlp |
| 前端 | Vue 3 / Vite |
| 音视频处理 | ffmpeg (通过 imageio-ffmpeg 自动集成) |

## 📦 项目结构

```
free-video-download/
├── app.py                  # FastAPI 后端主程序
├── requirements.txt        # Python 依赖
├── .gitignore
├── README.md
└── frontend/               # Vue 3 前端
    ├── package.json
    ├── vite.config.js
    ├── index.html
    ├── public/
    │   └── vite.svg        # Logo
    └── src/
        ├── main.js         # Vue 入口
        └── App.vue         # 主组件（UI + 交互逻辑）
```

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+（仅前端开发时需要）

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/free-video-download.git
cd free-video-download
```

### 2. 安装后端依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 启动后端服务

```bash
python app.py
```

后端服务将在 `http://localhost:8000` 启动。

> 如果你只修改了后端代码，不需要构建前端，FastAPI 会直接托管已有的 `frontend/dist` 静态文件。

### 4.（可选）前端开发

如果需要修改前端 UI：

```bash
cd frontend

# 安装前端依赖
npm install

# 启动开发服务器（带热更新，API 请求自动代理到后端）
npm run dev

# 构建生产版本
npm run build
```

前端开发服务器运行在 `http://localhost:5173`，会自动将 `/api` 请求代理到后端 `http://localhost:8000`。

构建后需要重启后端服务以加载最新的前端文件。

## 📖 API 接口

### 解析视频信息

```
POST /api/parse
Content-Type: application/json

请求体：
{
  "url": "https://www.bilibili.com/video/BV1hmQ4BdEQf"
}

响应：
{
  "title": "视频标题",
  "thumbnail": "缩略图URL",
  "duration": 120.5,
  "uploader": "上传者",
  "description": "视频简介...",
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

### 下载视频

```
GET /api/download?url=视频URL&format_id=格式ID

返回：视频文件（二进制流）
```

### 图片代理（绕过防盗链）

```
GET /api/proxy-image?url=图片URL

返回：图片文件
```

### 获取支持平台列表

```
GET /api/supported-sites

返回：平台分类列表
```

## ⚠️ 注意事项

1. **ffmpeg**：通过 `imageio-ffmpeg` 自动安装，无需手动配置。B站等 DASH 格式平台需要 ffmpeg 合并音视频流。
2. **视频无声音**：如果下载的视频没有声音，通常是 ffmpeg 未正确加载。检查后端启动日志是否包含 ffmpeg 路径。
3. **防盗链**：缩略图通过后端代理加载，绕过 B站 等平台的 Referer 防盗链检查。
4. **临时文件**：下载的视频文件保存在 `downloads/` 目录，下载完成后自动清理。
5. **仅供学习交流**：请遵守当地法律法规，尊重视频创作者的版权。

## 📄 开源协议

本项目基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp)（Unlicense 协议）构建。
