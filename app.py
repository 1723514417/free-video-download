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

BASE_DIR = Path(__file__).resolve().parent
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k, _v = _k.strip(), _v.strip()
        if _k and _k not in os.environ:
            os.environ[_k] = _v

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


def _is_youtube_shorts_url(url):
    return 'youtube.com/shorts/' in url or 'youtu.be/' in url


def _is_bilibili_url(url):
    return 'bilibili.com' in url or 'b23.tv' in url


_BILIBILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://www.bilibili.com",
}


async def _get_bilibili_cookies_via_playwright() -> Optional[str]:
    try:
        import asyncio
        from playwright.async_api import async_playwright
        import os
        
        headless_mode = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless_mode, timeout=60000)
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto("https://www.bilibili.com/", timeout=30000)
            
            await page.wait_for_selector('.header-login-btn', timeout=30000)
            await page.click('.header-login-btn')
            
            logger.info("请在弹出的浏览器窗口中完成 B 站登录（扫码或账号密码），登录成功后会自动关闭")
            
            for i in range(30):
                cookies = await context.cookies()
                bili_jct = next((c['value'] for c in cookies if c['name'] == 'bili_jct'), None)
                sessdata = next((c['value'] for c in cookies if c['name'] == 'SESSDATA'), None)
                
                if bili_jct and sessdata:
                    cookie_str = f"bili_jct={bili_jct}; SESSDATA={sessdata}"
                    await browser.close()
                    return cookie_str
                
                await asyncio.sleep(2)
            
            await browser.close()
            logger.info("登录超时")
            return None
            
    except Exception as e:
        logger.error(f"Playwright 登录失败: {e}")
        return None

async def _extract_bilibili_info(url: str, use_playwright_login: bool = False) -> Optional[Dict]:
    try:
        import re
        match = re.search(r'/BV([a-zA-Z0-9]+)', url)
        if not match:
            match = re.search(r'/av(\d+)', url)
            if not match:
                return None

        headers = dict(_BILIBILI_HEADERS)
        
        if use_playwright_login:
            cookies = await _get_bilibili_cookies_via_playwright()
            if cookies:
                headers["Cookie"] = cookies
                logger.info("已通过 Playwright 获取登录 Cookie")
        
        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            if '/BV' in url:
                bvid = 'BV' + re.search(r'/BV([a-zA-Z0-9]+)', url).group(1)
                resp = await client.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
            else:
                aid = re.search(r'/av(\d+)', url).group(1)
                resp = await client.get(f"https://api.bilibili.com/x/web-interface/view?aid={aid}")

            if resp.status_code != 200:
                logger.error(f"B站API返回: {resp.status_code}")
                return None

            data = resp.json()
            if data.get("code") != 0:
                logger.error(f"B站API错误: {data.get('message')}")
                return None

            vinfo = data["data"]

            cid = vinfo.get("cid", "")
            aid = vinfo.get("aid", "")
            bvid = vinfo.get("bvid", "")

            formats = []

            resp2 = await client.get(
                f"https://api.bilibili.com/x/player/playurl?avid={aid}&cid={cid}&qn=127&fnver=0&fnval=16&fourk=1"
            )
            play_data = resp2.json() if resp2.status_code == 200 else None

            if play_data and play_data.get("code") == 0:
                video_info = play_data["data"]
                accept_quality = video_info.get("accept_quality", [])
                desc_quality = {127: "4K", 120: "4K", 116: "1080P 高码率", 112: "1080P 高码率", 80: "1080P", 74: "720P 高码率", 64: "720P", 48: "720P", 32: "480P", 16: "360P"}

                seen = set()
                for q in accept_quality:
                    label = desc_quality.get(q, f"{q}P")
                    if label not in seen:
                        seen.add(label)
                        formats.append({
                            "format_id": str(q),
                            "ext": "mp4",
                            "resolution": label,
                            "filesize": None,
                            "vcodec": "h264",
                            "acodec": "aac",
                        })

                dash = video_info.get("dash", {})
                if dash:
                    for stream in dash.get("video", []):
                        q = stream.get("id", 0)
                        w = stream.get("width", 0)
                        h = stream.get("height", 0)
                        label = desc_quality.get(q, f"{h}p")
                        codecs = stream.get("codecs", "avc")
                        key = f"{label}-{codecs}"
                        if key not in seen:
                            seen.add(key)
                            formats.append({
                                "format_id": str(q),
                                "ext": "mp4",
                                "resolution": label,
                                "filesize": stream.get("fileSize"),
                                "vcodec": codecs,
                                "acodec": "aac",
                            })

            if not formats:
                formats = [
                    {"format_id": "80", "ext": "mp4", "resolution": "1080P", "vcodec": "h264", "acodec": "aac"},
                    {"format_id": "64", "ext": "mp4", "resolution": "720P", "vcodec": "h264", "acodec": "aac"},
                    {"format_id": "32", "ext": "mp4", "resolution": "480P", "vcodec": "h264", "acodec": "aac"},
                    {"format_id": "16", "ext": "mp4", "resolution": "360P", "vcodec": "h264", "acodec": "aac"},
                ]

            subtitle_info = {"manual": [], "auto": []}
            need_login_subtitle = False
            try:
                sub_resp = await client.get(f"https://api.bilibili.com/x/player/wbi/v2?aid={aid}&cid={cid}")
                if sub_resp.status_code == 200:
                    sub_data = sub_resp.json()
                    if sub_data.get("code") == 0:
                        sub_info = sub_data.get("data", {}).get("subtitle", {})
                        need_login_subtitle = sub_info.get("need_login", False)
                        subtitles_list = sub_info.get("subtitles", [])
                        for sub in subtitles_list:
                            lang_code = sub.get("lan", "")
                            lang_name_map = {"zh-CN": "中文(简体)", "zh-Hans": "中文(简体)", "zh-Hant": "中文(繁体)", "en": "英文", "ja": "日文"}
                            is_auto = sub.get("ai_status", 0) > 0
                            category = "auto" if is_auto else "manual"
                            sub_url = sub.get("subtitle_url", "")
                            if sub_url:
                                sub_url = "https:" + sub_url
                            subtitle_info[category].append({
                                "lang": lang_name_map.get(lang_code, lang_code),
                                "lang_code": lang_code,
                                "count": 1,
                                "url": sub_url,
                                "need_login": sub.get("need_login", False) or need_login_subtitle,
                            })
            except Exception as e:
                logger.warning(f"B站字幕获取失败: {e}")

            has_subtitle = bool(subtitle_info["manual"] or subtitle_info["auto"])

            return {
                "title": vinfo.get("title", ""),
                "thumbnail": vinfo.get("pic", ""),
                "duration": vinfo.get("duration", 0),
                "description": vinfo.get("desc", ""),
                "uploader": vinfo.get("owner", {}).get("name", ""),
                "need_login_subtitle": need_login_subtitle,
                "webpage_url": url,
                "formats": formats,
                "has_subtitle": has_subtitle,
                "subtitle_info": subtitle_info if has_subtitle else None,
                "aid": aid,
                "cid": cid,
                "bvid": bvid,
            }

    except Exception as e:
        logger.error(f"B站专用解析失败: {e}")
        return None



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
    has_subtitle: bool = False
    subtitle_info: Optional[Dict[str, Any]] = None


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
                has_subtitle=False,
            )

    if _is_bilibili_url(req.url):
        bilibili_info = await _extract_bilibili_info(req.url)
        if bilibili_info and bilibili_info.get('formats'):
            formats = []
            for f in bilibili_info.get('formats', []):
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
                title=bilibili_info.get('title', ''),
                thumbnail=bilibili_info.get('thumbnail'),
                duration=bilibili_info.get('duration'),
                description=bilibili_info.get('description'),
                uploader=bilibili_info.get('uploader'),
                webpage_url=bilibili_info.get('webpage_url'),
                formats=formats,
                has_subtitle=bilibili_info.get('has_subtitle', False),
                subtitle_info=bilibili_info.get('subtitle_info'),
            )

    is_shorts = _is_youtube_shorts_url(req.url)
    is_bilibili = 'bilibili.com' in req.url or 'b23.tv' in req.url
    logger.info(f"开始解析视频: {req.url}, is_shorts={is_shorts}, is_bilibili={is_bilibili}")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": 60,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 5,
        "file_access_retries": 5,
        "nocheckcertificate": True,
    }

    if is_bilibili:
        ydl_opts.update({
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        })
    elif is_shorts:
        ydl_opts.update({
            "extractor_args": {
                "youtube": {
                    "player_client": ["android"],
                    "player_skip": ["configs", "webpage", "js"],
                }
            },
            "format": "best",
        })
    else:
        ydl_opts.update({
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip": ["configs", "webpage", "js"],
                },
                "generic": {"impersonate": ["chrome"]},
            },
        })

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(req.url, download=False)

    import time
    start_time = time.time()

    try:
        info = await asyncio.get_event_loop().run_in_executor(None, _extract)
        elapsed = time.time() - start_time
        logger.info(f"视频解析完成: {req.url}, 耗时: {elapsed:.2f}秒")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="视频解析超时，请稍后重试")
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

    has_subtitle = False
    subtitle_info = None

    subtitles = info.get("subtitles", {})
    auto_captions = info.get("automatic_captions", {})

    if subtitles or auto_captions:
        subtitle_info = {"manual": [], "auto": []}
        for lang_code, lang_name in {
            "zh-Hans": "中文(简体)",
            "zh-CN": "中文(简体)",
            "zh": "中文",
            "zh-Hant": "中文(繁体)",
            "en": "英文",
            "ja": "日文",
            "ko": "韩文"
        }.items():
            if lang_code in subtitles:
                subtitle_info["manual"].append({
                    "lang": lang_name,
                    "lang_code": lang_code,
                    "count": len(subtitles[lang_code])
                })
            if lang_code in auto_captions:
                subtitle_info["auto"].append({
                    "lang": lang_name,
                    "lang_code": lang_code,
                    "count": len(auto_captions[lang_code])
                })

        has_subtitle = bool(subtitle_info["manual"] or subtitle_info["auto"])
        if not has_subtitle:
            subtitle_info = None

    return ParseResponse(
        title=info.get("title", "未知标题"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        description=info.get("description", "")[:200] if info.get("description") else None,
        uploader=info.get("uploader"),
        webpage_url=info.get("webpage_url"),
        formats=formats,
        has_subtitle=has_subtitle,
        subtitle_info=subtitle_info,
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
        "socket_timeout": 60,
        "retries": 10,
        "nocheckcertificate": True,
    }

    is_bilibili_dl = 'bilibili.com' in url or 'b23.tv' in url
    if is_bilibili_dl:
        common_opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    else:
        common_opts["extractor_args"] = {"generic": {"impersonate": ["chrome"]}}

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


class CheckSubtitleRequest(BaseModel):
    url: str


class CheckSubtitleResponse(BaseModel):
    has_subtitle: bool
    subtitle_info: Optional[Dict[str, Any]] = None
    message: str = ""


@app.post("/api/check-subtitle", response_model=CheckSubtitleResponse)
async def check_subtitle(req: CheckSubtitleRequest):
    logger.info(f"检查字幕: {req.url}")

    if _is_douyin_url(req.url):
        return CheckSubtitleResponse(
            has_subtitle=False,
            message="抖音视频通常没有CC字幕，无法使用AI总结功能"
        )

    result = await _check_subtitle_available(req.url)

    if not result["has_subtitle"]:
        return CheckSubtitleResponse(
            has_subtitle=False,
            message="该视频没有可用的字幕（手动或自动生成）"
        )

    manual_count = len(result["subtitle_info"].get("manual", []))
    auto_count = len(result["subtitle_info"].get("auto", []))

    message_parts = []
    if manual_count > 0:
        manual_langs = ", ".join([s["lang"] for s in result["subtitle_info"]["manual"]])
        message_parts.append(f"手动字幕: {manual_langs}")
    if auto_count > 0:
        auto_langs = ", ".join([s["lang"] for s in result["subtitle_info"]["auto"]])
        message_parts.append(f"自动字幕: {auto_langs}")

    return CheckSubtitleResponse(
        has_subtitle=True,
        subtitle_info=result["subtitle_info"],
        message="; ".join(message_parts)
    )


LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-4-flash")


async def _check_subtitle_available(url: str) -> Dict[str, Any]:
    try:
        def _extract_info():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": 60,
                "extract_flat": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "web"],
                        "player_skip": ["configs", "webpage", "js"],
                    }
                },
                "retries": 10,
                "fragment_retries": 10,
                "extractor_retries": 5,
                "nocheckcertificate": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await asyncio.get_event_loop().run_in_executor(None, _extract_info)
        except asyncio.TimeoutError:
            logger.warning(f"字幕检查超时: {url}")
            return {"has_subtitle": False, "subtitle_info": None, "error": "timeout"}

        if not info:
            return {"has_subtitle": False, "subtitle_info": None}

        subtitles = info.get("subtitles", {})
        auto_captions = info.get("automatic_captions", {})

        subtitle_info = {
            "manual": [],
            "auto": []
        }

        for lang_code, lang_name in {
            "zh-Hans": "中文(简体)",
            "zh-CN": "中文(简体)",
            "zh": "中文",
            "zh-Hant": "中文(繁体)",
            "en": "英文",
            "ja": "日文",
            "ko": "韩文"
        }.items():
            if lang_code in subtitles:
                subtitle_info["manual"].append({
                    "lang": lang_name,
                    "lang_code": lang_code,
                    "count": len(subtitles[lang_code])
                })
            if lang_code in auto_captions:
                subtitle_info["auto"].append({
                    "lang": lang_name,
                    "lang_code": lang_code,
                    "count": len(auto_captions[lang_code])
                })

        has_subtitle = bool(subtitle_info["manual"] or subtitle_info["auto"])

        return {
            "has_subtitle": has_subtitle,
            "subtitle_info": subtitle_info if has_subtitle else None
        }
    except Exception as e:
        logger.error(f"字幕检查失败: {e}")
        return {"has_subtitle": False, "subtitle_info": None, "error": str(e)}


async def _get_subtitle_text_async(url: str) -> Optional[str]:
    try:
        def _extract_info():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["zh", "zh-Hans", "zh-CN", "en", "ja"],
                "skip_download": True,
                "socket_timeout": 20,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "web"],
                        "player_skip": ["configs", "webpage", "js"],
                    }
                },
                "retries": 2,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await asyncio.get_event_loop().run_in_executor(None, _extract_info)
        except asyncio.TimeoutError:
            logger.warning(f"字幕提取超时: {url}")
            return None

        if not info:
            return None

        subtitles = info.get("subtitles", {})
        auto_captions = info.get("automatic_captions", {})

        sub_url = None
        sub_ext = None

        for lang in ["zh-Hans", "zh-CN", "zh", "en", "ja"]:
            for source in [subtitles, auto_captions]:
                subs = source.get(lang, [])
                for sub in subs:
                    ext = sub.get("ext", "")
                    url_val = sub.get("url", "")
                    if ext in ("vtt", "srt", "srv1", "srv2", "srv3", "ttml") and url_val:
                        sub_url = url_val
                        sub_ext = ext
                        break
                    elif ext == "json3" and url_val and not sub_url:
                        sub_url = url_val
                        sub_ext = ext
                if sub_url:
                    break
            if sub_url:
                break

        if not sub_url:
            logger.info("未找到字幕 URL")
            return None

        logger.info(f"找到字幕: lang={lang}, ext={sub_ext}")
        content = await _download_subtitle_content(sub_url)
        if not content:
            return None

        return _parse_subtitle_content(content, sub_ext)
    except Exception as e:
        logger.error(f"字幕提取失败: {e}")
        return None


async def _download_subtitle_content(sub_url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(sub_url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.error(f"字幕下载失败: {e}")
    return None


def _parse_subtitle_content(content: str, ext: str) -> Optional[str]:
    try:
        text_lines = []

        if ext == "json3":
            try:
                data = json.loads(content)
                for event in data.get("events", []):
                    segs = event.get("segs", [])
                    line_text = "".join(s.get("utf8", "") for s in segs).strip()
                    if line_text:
                        text_lines.append(line_text)
            except json.JSONDecodeError:
                pass
        elif ext in ("srv1", "srv2", "srv3"):
            try:
                data = json.loads(content)
                for item in data:
                    if isinstance(item, dict):
                        text = item.get("text") or item.get("content", "")
                        if text:
                            text_lines.append(text.strip())
                    elif isinstance(item, list):
                        for sub in item:
                            if isinstance(sub, dict):
                                text = sub.get("text") or sub.get("content", "")
                                if text:
                                    text_lines.append(text.strip())
            except json.JSONDecodeError:
                pass
        else:
            lines = content.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("WEBVTT") or line.startswith("NOTE"):
                    continue
                if "-->" in line:
                    continue
                if line.isdigit():
                    continue
                if "<" in line and ">" in line:
                    line = re.sub(r'<[^>]+>', '', line)
                if line:
                    text_lines.append(line)

        seen = set()
        unique_lines = []
        for line in text_lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)

        return " ".join(unique_lines).strip() or None
    except Exception:
        return None


class StreamSummarizeRequest(BaseModel):
    url: str


@app.post("/api/ai-summarize-stream")
async def ai_summarize_stream(req: StreamSummarizeRequest):
    if not LLM_API_KEY:
        raise HTTPException(status_code=400, detail="未配置 AI 服务，请在 .env 中设置 LLM_API_KEY")

    from starlette.responses import StreamingResponse
    from openai import AsyncOpenAI

    logger.info(f"收到 SSE 流式总结请求: {req.url}")

    video_title = "未知标题"
    duration = None
    subtitle_text = None

    if _is_douyin_url(req.url):
        douyin_info = await _extract_douyin_info(req.url)
        if douyin_info:
            video_title = douyin_info.get("title", "抖音视频")
            duration = douyin_info.get("duration")
            desc = douyin_info.get("description") or ""
            if desc and len(desc.strip()) >= 50:
                subtitle_text = desc.strip()
        if not subtitle_text:
            async def _no_subtitle_douyin():
                yield f"data: {json.dumps({'type': 'error', 'message': '抖音视频暂不支持 AI 总结'})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(_no_subtitle_douyin(), media_type="text/event-stream")
    else:
        is_bilibili_sse = 'bilibili.com' in req.url or 'b23.tv' in req.url
        
        if is_bilibili_sse:
            bilibili_info = await _extract_bilibili_info(req.url)
            if not bilibili_info:
                raise HTTPException(status_code=400, detail="无法获取 B 站视频信息")
            
            video_title = bilibili_info.get("title", "未知标题")
            duration = bilibili_info.get("duration")
            
            subtitle_info = bilibili_info.get("subtitle_info", {})
            need_login = bilibili_info.get("need_login_subtitle", False)
            
            if subtitle_info:
                subtitle_url = None
                need_login_sub = False
                for category in ["manual", "auto"]:
                    for sub in subtitle_info.get(category, []):
                        if sub.get("url"):
                            subtitle_url = sub["url"]
                            need_login_sub = sub.get("need_login", False) or need_login
                            break
                    if subtitle_url:
                        break
                
                if subtitle_url:
                    if need_login_sub:
                        logger.info("字幕需要登录，尝试使用 Playwright 登录")
                        bilibili_info_with_login = await _extract_bilibili_info(req.url, use_playwright_login=True)
                        if bilibili_info_with_login:
                            subtitle_info_login = bilibili_info_with_login.get("subtitle_info", {})
                            for category in ["manual", "auto"]:
                                for sub in subtitle_info_login.get(category, []):
                                    if sub.get("url"):
                                        subtitle_url = sub["url"]
                                        break
                                if subtitle_url:
                                    break
                    
                    content = await _download_subtitle_content(subtitle_url)
                    if content:
                        subtitle_text = _parse_subtitle_content(content, "json3")
            
            if not subtitle_text or len(subtitle_text.strip()) < 50:
                description = bilibili_info.get("description", "")
                if description and len(description.strip()) >= 50:
                    subtitle_text = description.strip()
                    logger.info(f"使用视频描述作为字幕替代，长度: {len(subtitle_text)} 字符")
        else:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "socket_timeout": 60,
                "retries": 10,
                "nocheckcertificate": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "web"],
                        "player_skip": ["configs", "webpage", "js"],
                    },
                    "generic": {"impersonate": ["chrome"]},
                },
            }

            def _get_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(req.url, download=False)

            try:
                info = await asyncio.get_event_loop().run_in_executor(None, _get_info)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"无法获取视频信息: {str(e)}")

            if not info:
                raise HTTPException(status_code=400, detail="未获取到视频信息")

            video_title = info.get("title", "未知标题")
            duration = info.get("duration")

            subtitle_text = await _get_subtitle_text_async(req.url)

    if not subtitle_text or len(subtitle_text.strip()) < 50:
        async def _no_subtitle():
            yield f"data: {json.dumps({'type': 'no_subtitle', 'message': '该视频没有可用的字幕或字幕内容过少，暂时无法生成 AI 总结。'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_no_subtitle(), media_type="text/event-stream")

    logger.info(f"SSE 字幕提取成功，长度: {len(subtitle_text)} 字符")

    truncated_text = subtitle_text[:30000] if len(subtitle_text) > 30000 else subtitle_text

    stream_system_prompt = """你是一个专业的视频内容分析助手。你需要根据视频的字幕文本，生成结构化的视频总结。

请严格按照以下 Markdown 格式输出：

## 📝 内容概述
（用100-200字概括视频的主要内容）

## 🔑 核心要点
1. 要点1
2. 要点2
3. 要点3
（列出5-10个核心知识点或要点）

## 📖 章节大纲
### 1. 章节标题
章节摘要

### 2. 章节标题
章节摘要
（按内容逻辑分为3-8个章节）

## 🧠 思维导图
```mermaid
mindmap
  root((视频标题))
    主题1
      子主题1
      子主题2
    主题2
      子主题3
      子主题4
```

要求：
1. 内容概述：用100-200字概括视频主要内容
2. 核心要点：提取5-10个核心知识点
3. 章节大纲：按内容逻辑分为3-8个章节
4. 思维导图：生成 mermaid mindmap 格式的思维导图数据"""

    user_prompt = f"视频标题：{video_title}\n\n视频字幕文本：\n{truncated_text}\n\n请分析以上视频内容，生成总结。"

    async def _stream_generate():
        try:
            client = AsyncOpenAI(
                api_key=LLM_API_KEY,
                base_url=LLM_API_BASE,
            )

            yield f"data: {json.dumps({'type': 'start', 'title': video_title, 'duration': duration})}\n\n"

            stream = await client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": stream_system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
                stream=True,
            )

            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield f"data: {json.dumps({'type': 'delta', 'content': content})}\n\n"

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"SSE 流式总结失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'AI 总结失败: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class ExportSubtitleRequest(BaseModel):
    url: str
    format: str = "srt"


@app.post("/api/export-subtitle")
async def export_subtitle(req: ExportSubtitleRequest):
    if _is_douyin_url(req.url):
        raise HTTPException(status_code=400, detail="抖音视频暂不支持字幕导出")

    def _extract_subtitle_info():
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["zh", "zh-Hans", "zh-CN", "en", "ja"],
            "skip_download": True,
            "socket_timeout": 60,
            "retries": 10,
            "nocheckcertificate": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip": ["configs", "webpage", "js"],
                }
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(req.url, download=False)

    try:
        info = await asyncio.get_event_loop().run_in_executor(None, _extract_subtitle_info)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取视频信息失败: {str(e)}")

    if not info:
        raise HTTPException(status_code=400, detail="未获取到视频信息")

    subtitles = info.get("subtitles", {})
    auto_captions = info.get("automatic_captions", {})

    sub_url = None
    sub_ext = None

    for lang in ["zh-Hans", "zh-CN", "zh", "en", "ja"]:
        for source in [subtitles, auto_captions]:
            subs = source.get(lang, [])
            for sub in subs:
                ext = sub.get("ext", "")
                url_val = sub.get("url", "")
                if ext in ("vtt", "srt", "srv1", "srv2", "srv3", "ttml") and url_val:
                    sub_url = url_val
                    sub_ext = ext
                    break
                elif ext == "json3" and url_val and not sub_url:
                    sub_url = url_val
                    sub_ext = ext
            if sub_url:
                break
        if sub_url:
            break

    if not sub_url:
        raise HTTPException(status_code=400, detail="该视频没有可用的字幕")

    content = await _download_subtitle_content(sub_url)
    if not content:
        raise HTTPException(status_code=400, detail="字幕下载失败")

    video_title = info.get("title", "video")
    safe_title = _sanitize_filename(video_title)

    export_format = req.format.lower()

    if export_format == "txt":
        text_content = _parse_subtitle_content(content, sub_ext)
        if not text_content:
            raise HTTPException(status_code=400, detail="字幕解析失败")
        return Response(
            content=text_content,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_title}.txt"
            },
        )
    elif export_format == "srt":
        srt_content = _convert_to_srt(content, sub_ext)
        return Response(
            content=srt_content,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_title}.srt"
            },
        )
    else:
        vtt_content = _convert_to_vtt(content, sub_ext)
        return Response(
            content=vtt_content,
            media_type="text/vtt; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_title}.vtt"
            },
        )


def _convert_to_srt(content: str, source_ext: str) -> str:
    if source_ext == "json3":
        return _json3_to_srt(content)
    elif source_ext.startswith("srv"):
        return _srv_to_srt(content)
    elif source_ext == "srt":
        return content
    elif source_ext == "vtt":
        return _vtt_to_srt(content)
    return content


def _convert_to_vtt(content: str, source_ext: str) -> str:
    if source_ext == "json3":
        srt = _json3_to_srt(content)
        return _srt_to_vtt(srt)
    elif source_ext.startswith("srv"):
        srt = _srv_to_srt(content)
        return _srt_to_vtt(srt)
    elif source_ext == "vtt":
        return content
    elif source_ext == "srt":
        return _srt_to_vtt(content)
    return "WEBVTT\n\n" + content


def _json3_to_srt(content: str) -> str:
    try:
        data = json.loads(content)
        segments = []
        idx = 1
        for event in data.get("events", []):
            start_ms = event.get("tStartMs", 0)
            duration_ms = event.get("dDurationMs", 0)
            if duration_ms <= 0:
                continue
            segs = event.get("segs", [])
            text = "".join(s.get("utf8", "") for s in segs).strip()
            if not text:
                continue
            end_ms = start_ms + duration_ms
            segments.append(f"{idx}\n{_ms_to_srt_time(start_ms)} --> {_ms_to_srt_time(end_ms)}\n{text}\n")
            idx += 1
        return "\n".join(segments)
    except Exception:
        return content


def _srv_to_srt(content: str) -> str:
    try:
        data = json.loads(content)
        segments = []
        idx = 1
        items = data if isinstance(data, list) else data.get("events", [])
        for item in items:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content", "")
                start = item.get("tStartMs", item.get("start", 0))
                duration = item.get("dDurationMs", item.get("duration", 0))
                if text and duration > 0:
                    end = start + duration
                    segments.append(f"{idx}\n{_ms_to_srt_time(start)} --> {_ms_to_srt_time(end)}\n{text.strip()}\n")
                    idx += 1
        return "\n".join(segments)
    except Exception:
        return content


def _vtt_to_srt(content: str) -> str:
    lines = content.strip().split("\n")
    result = []
    idx = 1
    for line in lines:
        line = line.strip()
        if line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if "-->" in line:
            time_line = line.replace(".", ",")
            result.append(f"{idx}\n{time_line}")
            idx += 1
        elif line and not line.isdigit():
            result.append(line)
    srt = []
    i = 0
    while i < len(result):
        line = result[i]
        if "-->" in line:
            srt.append(line)
            i += 1
            while i < len(result) and "-->" not in result[i]:
                srt.append(result[i])
                i += 1
            srt.append("")
        else:
            i += 1
    return "\n".join(srt)


def _srt_to_vtt(srt_content: str) -> str:
    lines = srt_content.strip().split("\n")
    result = ["WEBVTT\n"]
    for line in lines:
        if line.strip().isdigit() and len(line.strip()) < 5:
            result.append("")
            continue
        if "-->" in line:
            result.append(line.replace(",", "."))
        else:
            result.append(line)
    return "\n".join(result) + "\n"


def _ms_to_srt_time(ms: int) -> str:
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


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
