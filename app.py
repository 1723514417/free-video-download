import os
import uuid
import asyncio
import shutil
from pathlib import Path
from typing import Optional

import httpx
import re
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
import yt_dlp

# 允许的图片域名白名单
ALLOWED_IMAGE_DOMAINS = {
    "i0.hdslb.com", "i1.hdslb.com", "i2.hdslb.com", "i3.hdslb.com",
    "hdslb.com", "bilibili.com",
    "p0.pstatp.com", "p1.pstatp.com", "p3.pstatp.com", "p6.pstatp.com",
    "p9.pstatp.com", "p26.pstatp.com", "p29.pstatp.com",
    "toutiao.com", "douyinpic.com", "douyinvod.com",
    "yt3.ggpht.com", "ytimg.com", "youtube.com",
    "twimg.com", "twvideo.com", "pbs.twimg.com",
    "cdninstagram.com", "fbcdn.net",
    "githubusercontent.com",
    "pstatp.com", "snssdk.com", "bytedance.com",
}

ALLOWED_IMAGE_SCHEMES = {"http", "https"}


def _is_url_allowed(url: str) -> bool:
    """检查 URL 是否在允许的域名白名单内，防止 SSRF"""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ALLOWED_IMAGE_SCHEMES:
            return False
        host = parsed.hostname
        if not host:
            return False
        # 禁止内网地址
        if re.match(r"^(127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|0\.|localhost)", host):
            return False
        # 检查白名单
        for domain in ALLOWED_IMAGE_DOMAINS:
            if host == domain or host.endswith("." + domain):
                return True
        return False
    except Exception:
        return False

DOWNLOADS_DIR = Path("downloads")


def _get_ffmpeg_path():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

FFMPEG_PATH = _get_ffmpeg_path()
DOWNLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="万能视频下载", docs_url=None, redoc_url=None)

frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")


class ParseRequest(BaseModel):
    url: str


class FormatInfo(BaseModel):
    format_id: str
    ext: str
    resolution: str
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    tbr: Optional[float] = None


class ParseResponse(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    description: Optional[str] = None
    uploader: Optional[str] = None
    webpage_url: Optional[str] = None
    formats: list[FormatInfo] = []


@app.post("/api/parse", response_model=ParseResponse)
async def parse_video(req: ParseRequest):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(req.url, download=False)

    try:
        info = await asyncio.get_event_loop().run_in_executor(None, _extract)
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=f"无法解析该视频: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析出错: {str(e)}")

    if info is None:
        raise HTTPException(status_code=400, detail="未获取到视频信息")

    formats = []
    seen_resolutions = set()
    for f in info.get("formats", []):
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        if vcodec == "none" and acodec == "none":
            continue

        height = f.get("height")
        if height and vcodec != "none":
            if height >= 2160:
                resolution = "4K"
            elif height >= 1440:
                resolution = "2K"
            elif height >= 1080:
                resolution = "1080p"
            elif height >= 720:
                resolution = "720p"
            elif height >= 480:
                resolution = "480p"
            elif height >= 360:
                resolution = "360p"
            else:
                resolution = f"{height}p"
        elif vcodec == "none" and acodec != "none":
            resolution = "音频"
        else:
            resolution = "未知"

        ext = f.get("ext", "mp4")
        key = f"{resolution}-{ext}-{vcodec[:10] if vcodec else 'none'}"
        if key in seen_resolutions:
            continue
        seen_resolutions.add(key)

        formats.append(
            FormatInfo(
                format_id=f["format_id"],
                ext=ext,
                resolution=resolution,
                filesize=f.get("filesize"),
                filesize_approx=f.get("filesize_approx"),
                vcodec=vcodec,
                acodec=acodec,
                tbr=f.get("tbr"),
            )
        )

    formats.sort(
        key=lambda x: (
            0 if x.vcodec != "none" else 1,
            -(parse_resolution_order(x.resolution)),
        )
    )

    return ParseResponse(
        title=info.get("title", "未知标题"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        description=info.get("description", "")[:200] if info.get("description") else None,
        uploader=info.get("uploader"),
        webpage_url=info.get("webpage_url"),
        formats=formats,
    )


@app.get("/api/proxy-image")
async def proxy_image(url: str):
    if not _is_url_allowed(url):
        raise HTTPException(status_code=403, detail="该图片域名不在白名单内")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="图片获取失败")
            content_type = resp.headers.get("content-type", "image/jpeg")
            return Response(content=resp.content, media_type=content_type)
        except httpx.HTTPError:
            raise HTTPException(status_code=400, detail="图片获取失败")


def parse_resolution_order(res: str) -> int:
    mapping = {"4K": 2160, "2K": 1440, "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
    return mapping.get(res, 0)


@app.get("/api/download")
async def download_video(url: str, format_id: str, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    task_dir = DOWNLOADS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    common_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(task_dir / "%(title)s.%(ext)s"),
    }
    if FFMPEG_PATH:
        common_opts["ffmpeg_location"] = FFMPEG_PATH

    ydl_opts = dict(common_opts)
    ydl_opts["format"] = f"{format_id}+bestaudio/best"
    ydl_opts["merge_output_format"] = "mp4"

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None
            return ydl.prepare_filename(info)

    def _download_fallback():
        fallback_opts = dict(common_opts)
        fallback_opts["format"] = "bestvideo+bestaudio/best"
        fallback_opts["merge_output_format"] = "mp4"
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None
            return ydl.prepare_filename(info)

    def _download_best():
        simple_opts = dict(common_opts)
        simple_opts["format"] = "best"
        with yt_dlp.YoutubeDL(simple_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None
            return ydl.prepare_filename(info)

    filepath = None
    for attempt in [_download, _download_fallback, _download_best]:
        try:
            filepath = await asyncio.get_event_loop().run_in_executor(None, attempt)
            if filepath and Path(filepath).exists():
                break
        except Exception:
            continue

    if filepath is None or not Path(filepath).exists():
        _cleanup_dir(task_dir)
        raise HTTPException(status_code=400, detail="下载失败: 无法获取视频文件")

    if filepath is None or not Path(filepath).exists():
        mp4_path = task_dir / "output.mp4"
        if mp4_path.exists():
            filepath = str(mp4_path)
        else:
            files = list(task_dir.iterdir())
            if files:
                filepath = str(files[0])
            else:
                _cleanup_dir(task_dir)
                raise HTTPException(status_code=400, detail="下载失败: 文件未找到")

    filepath = Path(filepath)

    def cleanup():
        _cleanup_dir(task_dir)

    background_tasks.add_task(cleanup)

    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type="application/octet-stream",
    )


def _cleanup_dir(directory: Path):
    try:
        shutil.rmtree(directory, ignore_errors=True)
    except Exception:
        pass


@app.get("/api/supported-sites")
async def supported_sites():
    return {
        "categories": [
            {
                "name": "视频平台",
                "sites": [
                    {"name": "YouTube", "icon": "youtube"},
                    {"name": "Bilibili", "icon": "bilibili"},
                    {"name": "抖音", "icon": "douyin"},
                    {"name": "TikTok", "icon": "tiktok"},
                    {"name": "优酷", "icon": "youku"},
                    {"name": "爱奇艺", "icon": "iqiyi"},
                    {"name": "腾讯视频", "icon": "tencent"},
                    {"name": "芒果TV", "icon": "mango"},
                    {"name": "西瓜视频", "icon": "xigua"},
                    {"name": "快手", "icon": "kuaishou"},
                    {"name": "微博", "icon": "weibo"},
                    {"name": "小红书", "icon": "xiaohongshu"},
                ],
            },
            {
                "name": "社交媒体",
                "sites": [
                    {"name": "Twitter/X", "icon": "twitter"},
                    {"name": "Instagram", "icon": "instagram"},
                    {"name": "Facebook", "icon": "facebook"},
                    {"name": "Reddit", "icon": "reddit"},
                    {"name": "Pinterest", "icon": "pinterest"},
                    {"name": "Tumblr", "icon": "tumblr"},
                ],
            },
            {
                "name": "更多平台",
                "sites": [
                    {"name": "Vimeo", "icon": "vimeo"},
                    {"name": "Dailymotion", "icon": "dailymotion"},
                    {"name": "Twitch", "icon": "twitch"},
                    {"name": "Niconico", "icon": "niconico"},
                    {"name": "SoundCloud", "icon": "soundcloud"},
                    {"name": "1800+ 更多", "icon": "more"},
                ],
            },
        ]
    }


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    file_path = frontend_dist / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse(
        {"message": "万能视频下载 API 正在运行。请先构建前端: cd frontend && npm run build"},
        status_code=200,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
