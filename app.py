import os
import uuid
import asyncio
import shutil
import re
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
import yt_dlp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


async def _extract_douyin_info(url: str) -> Optional[Dict[str, Any]]:
    try:
        from curl_cffi import requests as curl_requests
        
        session = curl_requests.Session()
        
        DEFAULT_HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
        MOBILE_SHARE_HEADERS = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.douyin.com/',
        }
        
        session.headers.update(DEFAULT_HEADERS)
        
        final_url = url
        if 'v.douyin.com' in url:
            for attempt in range(3):
                try:
                    resp = session.get(url, impersonate='chrome', allow_redirects=True, timeout=30)
                    final_url = resp.url
                    break
                except Exception:
                    time.sleep(1)
        
        video_id_match = re.search(r'video/(\d+)', final_url)
        if not video_id_match:
            return None
        
        video_id = video_id_match.group(1)
        
        methods = [
            lambda: _try_api_method(session, video_id, url),
            lambda: _try_router_data_method(session, video_id, url),
            lambda: _try_aweme_api_method(session, video_id, url),
            lambda: _try_play_api_method(session, video_id, url),
        ]
        
        for method in methods:
            try:
                result = await method()
                if result:
                    return result
            except Exception:
                continue
        
        return None
    except Exception as e:
        return None


async def _try_api_method(session, video_id: str, original_url: str) -> Optional[Dict[str, Any]]:
    try:
        api_url = 'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/'
        params = {'item_ids': video_id}
        
        resp = session.get(api_url, impersonate='chrome', params=params, timeout=30)
        if resp.status_code != 200:
            return None
        
        try:
            data = resp.json()
        except json.JSONDecodeError:
            return None
        
        if data.get('status_code') not in (0, None):
            return None
        
        item_list = data.get('item_list', [])
        if not item_list:
            return None
        
        aweme_info = item_list[0]
        return _parse_aweme_info(aweme_info, video_id, original_url)
    except Exception:
        return None


async def _try_router_data_method(session, video_id: str, original_url: str) -> Optional[Dict[str, Any]]:
    try:
        share_url = f'https://www.iesdouyin.com/share/video/{video_id}/'
        mobile_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.douyin.com/',
        }
        
        resp = session.get(share_url, impersonate='chrome', headers=mobile_headers, timeout=30)
        if resp.status_code != 200:
            return None
        
        html = resp.text
        
        router_data_match = re.search(r'window\._ROUTER_DATA\s*=\s*(\{.+?\})\s*</script>', html, re.DOTALL)
        if not router_data_match:
            return None
        
        try:
            router_data = json.loads(router_data_match.group(1))
        except json.JSONDecodeError:
            return None
        
        video_info = _extract_from_router_data(router_data)
        if video_info:
            return {
                'title': video_info.get('title', f'抖音视频_{video_id}'),
                'thumbnail': video_info.get('thumbnail'),
                'duration': video_info.get('duration'),
                'description': None,
                'webpage_url': original_url,
                'formats': [{
                    'format_id': 'douyin_direct',
                    'ext': 'mp4',
                    'resolution': '高清',
                    'vcodec': 'h264',
                    'acodec': 'aac',
                    'filesize': None,
                    'url': video_info.get('play_url'),
                }],
                'is_douyin': True,
            }
        
        return None
    except Exception:
        return None


def _extract_from_router_data(router_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        loader_data = router_data.get('loaderData', {})
        for key, value in loader_data.items():
            if isinstance(value, dict):
                video_info_res = value.get('videoInfoRes')
                if video_info_res:
                    item_list = video_info_res.get('item_list', [])
                    if item_list:
                        return _parse_aweme_info(item_list[0], None, None)
                
                item_info = value.get('itemInfo')
                if item_info:
                    video_info = item_info.get('video')
                    if video_info:
                        return _extract_video_info(video_info, item_info.get('desc', ''))
        return None
    except Exception:
        return None


def _parse_aweme_info(aweme_info: Dict[str, Any], video_id: Optional[str], original_url: Optional[str]) -> Optional[Dict[str, Any]]:
    try:
        title = aweme_info.get('desc', f'抖音视频_{video_id}') if video_id else aweme_info.get('desc', '抖音视频')
        if not isinstance(title, str):
            title = f'抖音视频_{video_id}' if video_id else '抖音视频'
        
        duration = aweme_info.get('duration')
        if duration and isinstance(duration, int):
            duration = duration / 1000
        
        video_info = aweme_info.get('video')
        if not video_info or not isinstance(video_info, dict):
            return None
        
        return _extract_video_info(video_info, title, duration)
    except Exception:
        return None


def _extract_video_info(video_info: Dict[str, Any], title: str, duration: Optional[float] = None) -> Optional[Dict[str, Any]]:
    try:
        thumbnail = None
        cover_info = video_info.get('cover')
        if isinstance(cover_info, dict):
            url_list = cover_info.get('url_list')
            if isinstance(url_list, list) and url_list:
                thumbnail = url_list[0]
        
        play_addr = None
        play_info = video_info.get('play_addr')
        if isinstance(play_info, dict):
            url_list = play_info.get('url_list')
            if isinstance(url_list, list) and url_list:
                play_addr = url_list[0].replace('playwm', 'play')
        
        if not play_addr:
            download_info = video_info.get('download_addr')
            if isinstance(download_info, dict):
                url_list = download_info.get('url_list')
                if isinstance(url_list, list) and url_list:
                    play_addr = url_list[0].replace('playwm', 'play')
        
        if not play_addr:
            play_info_h264 = video_info.get('play_addr_h264')
            if isinstance(play_info_h264, dict):
                url_list = play_info_h264.get('url_list')
                if isinstance(url_list, list) and url_list:
                    play_addr = url_list[0].replace('playwm', 'play')
        
        if not play_addr:
            return None
        
        if not play_addr.startswith('http'):
            if play_addr.startswith('//'):
                play_addr = 'https:' + play_addr
            else:
                play_addr = 'https://' + play_addr
        
        return {
            'title': title,
            'thumbnail': thumbnail,
            'duration': duration,
            'play_url': play_addr,
        }
    except Exception:
        return None


async def _try_aweme_api_method(session, video_id: str, original_url: str) -> Optional[Dict[str, Any]]:
    try:
        api_url = f'https://aweme-hl.snssdk.com/aweme/v1/aweme/detail/?aweme_id={video_id}&device_platform=ios&app_name=aweme&aid=1128'
        resp = session.get(api_url, impersonate='chrome', timeout=30)
        if resp.status_code != 200:
            return None
        
        try:
            data = resp.json()
        except json.JSONDecodeError:
            return None
        
        if data.get('status_code') != 0:
            return None
        
        aweme_detail = data.get('aweme_detail')
        if not aweme_detail:
            return None
        
        return _parse_aweme_info(aweme_detail, video_id, original_url)
    except Exception:
        return None


async def _try_play_api_method(session, video_id: str, original_url: str) -> Optional[Dict[str, Any]]:
    try:
        share_url = f'https://www.douyin.com/video/{video_id}/'
        mobile_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.douyin.com/',
        }
        
        resp = session.get(share_url, impersonate='chrome', headers=mobile_headers, timeout=30)
        if resp.status_code != 200:
            return None
        
        html = resp.text
        
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>', html, re.DOTALL)
        if not match:
            match = re.search(r'window\._SSR_HYDRATED_DATA\s*=\s*(\{.+?\})\s*</script>', html, re.DOTALL)
        
        if not match:
            return None
        
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        
        videos = data.get('video', {}).get('video', {}).get('data')
        if videos and isinstance(videos, list) and videos:
            video_data = videos[0]
            title = video_data.get('desc', f'抖音视频_{video_id}')
            play_url = video_data.get('playUrl')
            if play_url:
                play_url = play_url.replace('playwm', 'play')
                if not play_url.startswith('http'):
                    play_url = 'https:' + play_url if play_url.startswith('//') else 'https://' + play_url
                
                thumbnail = video_data.get('coverUrl')
                duration = video_data.get('duration')
                
                return {
                    'title': title,
                    'thumbnail': thumbnail,
                    'duration': duration,
                    'webpage_url': original_url,
                    'formats': [{
                        'format_id': 'douyin_direct',
                        'ext': 'mp4',
                        'resolution': '高清',
                        'vcodec': 'h264',
                        'acodec': 'aac',
                        'filesize': None,
                        'url': play_url,
                    }],
                    'is_douyin': True,
                }
        
        return None
    except Exception:
        return None


def _is_douyin_url(url):
    return 'douyin.com' in url or 'v.douyin.com' in url



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
    if _is_douyin_url(req.url):
        douyin_info = await _extract_douyin_info(req.url)
        if douyin_info and douyin_info.get('formats'):
            formats = []
            for f in douyin_info.get('formats', []):
                formats.append(
                    FormatInfo(
                        format_id=f.get('format_id'),
                        ext=f.get('ext', 'mp4'),
                        resolution=f.get('resolution', '未知'),
                        filesize=f.get('filesize'),
                        vcodec=f.get('vcodec'),
                        acodec=f.get('acodec'),
                    )
                )
            return ParseResponse(
                title=douyin_info.get('title', '抖音视频'),
                thumbnail=douyin_info.get('thumbnail'),
                duration=douyin_info.get('duration'),
                description=douyin_info.get('description'),
                webpage_url=douyin_info.get('webpage_url'),
                formats=formats,
            )
    
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "extractor_args": {"generic": {"impersonate": ["chrome"]}},
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


def _sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
    filename = filename.replace('\0', '')
    if len(filename) > 200:
        filename = filename[:200]
    return filename.strip('_') or 'video'


@app.get("/api/download")
async def download_video(url: str, format_id: str, background_tasks: BackgroundTasks):
    logger.info(f"开始下载视频: {url}, 格式: {format_id}")
    task_id = str(uuid.uuid4())
    task_dir = DOWNLOADS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    if _is_douyin_url(url) and format_id == 'douyin_direct':
        douyin_info = await _extract_douyin_info(url)
        if douyin_info:
            for fmt in douyin_info.get('formats', []):
                if fmt.get('format_id') == format_id:
                    video_url = fmt.get('url')
                    if video_url:
                        raw_title = douyin_info.get('title', 'douyin_video')
                        safe_title = _sanitize_filename(raw_title)
                        filepath = task_dir / f"{safe_title}.mp4"
                        try:
                            from curl_cffi import requests as curl_requests
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                'Referer': url,
                            }
                            resp = curl_requests.get(video_url, impersonate='chrome', headers=headers, timeout=120)
                            if resp.status_code != 200:
                                _cleanup_dir(task_dir)
                                raise HTTPException(status_code=400, detail="下载失败: 视频获取失败")
                            with open(filepath, "wb") as f:
                                f.write(resp.content)
                            file_response = FileResponse(
                                str(filepath),
                                media_type="video/mp4",
                                filename=f"{safe_title}.mp4",
                            )
                            background_tasks.add_task(_cleanup_dir, task_dir)
                            return file_response
                        except Exception as e:
                            _cleanup_dir(task_dir)
                            raise HTTPException(status_code=400, detail=f"下载失败: {str(e)}")
            _cleanup_dir(task_dir)
            raise HTTPException(status_code=400, detail="下载失败: 未找到视频")
        else:
            _cleanup_dir(task_dir)
            raise HTTPException(status_code=400, detail="下载失败: 无法获取视频信息")

    common_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(task_dir / "%(title)s.%(ext)s"),
        "extractor_args": {"generic": {"impersonate": ["chrome"]}},
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

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
