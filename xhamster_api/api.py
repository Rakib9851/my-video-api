import os
import urllib
import logging
import chompjs
import asyncio
from dataclasses import dataclass
from functools import cached_property
from urllib.parse import urlencode, quote
from curl_cffi.requests import AsyncSession, Response
from selectolax.lexbor import LexborHTMLParser

# এরর এড়ানোর জন্য ইমপোর্ট হ্যান্ডেলিং
try:
    from base_api import BaseCore, setup_logger, Helper
except ImportError:
    class BaseCore:
        def __init__(self, *args, **kwargs): pass
        async def fetch(self, url): return ""
    def setup_logger(*args, **kwargs): return logging.getLogger("dummy")
    class Helper:
        def __init__(self, *args, **kwargs): pass
        async def iterator(self, *args, **kwargs): yield None

try:
    from base_api.modules.config import RuntimeConfig
except ImportError:
    class RuntimeConfig: pass

REGEX_M3U8 = r'https://[^"]*?_TPL_\.(?:h264|av1)\.mp4\.m3u8'
REGEX_THUMBNAIL = r'<meta property="og:image" content="(.*?)"/>'
headers = {"Referer": "https://www.xhamster.com/"}

class Video:
    def __init__(self, title, video_id, thumbnail, m3u8_base_url, uploader_name):
        self.title = title
        self.video_id = video_id
        self.thumbnail = thumbnail
        self.m3u8_base_url = m3u8_base_url
        self.uploader_name = uploader_name
        self.likes = 0

class Client(Helper):
    def __init__(self, core=None):
        self.session = AsyncSession()
        self.session.headers.update(headers)

    async def search_videos(self, query, pages=1):
        path = quote(str(query))
        url = f"https://xhamster.com/search/{path}"
        response = await self.session.get(url)
        content = response.text
        
        lexbor = LexborHTMLParser(content)
        # ভিডিও লিঙ্ক খুঁজে বের করা
        nodes = lexbor.css("a.role-pop.thumb-image-container")
        
        for node in nodes[:10]: # প্রথম ১০টি ভিডিও দেখাবে
            video_url = node.attributes.get("href")
            if video_url:
                try:
                    v_res = await self.session.get(video_url)
                    v_content = v_res.text
                    import re
                    title = re.search(r'<title>(.*?)</title>', v_content).group(1) if re.search(r'<title>(.*?)</title>', v_content) else "No Title"
                    m3u8 = re.search(REGEX_M3U8, v_content).group(0).replace("\\/", "/") if re.search(REGEX_M3U8, v_content) else ""
                    thumb = re.search(REGEX_THUMBNAIL, v_content).group(1) if re.search(REGEX_THUMBNAIL, v_content) else ""
                    
                    class Result: pass
                    res = Result()
                    res.video = Video(title=title, video_id=0, thumbnail=thumb, m3u8_base_url=m3u8, uploader_name="Unknown")
                    yield res
                except:
                    continue
