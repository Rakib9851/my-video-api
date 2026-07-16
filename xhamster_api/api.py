from __future__ import annotations

import os
import urllib
import logging
import chompjs
import asyncio

from dataclasses import dataclass
from functools import cached_property
from urllib.parse import urlencode, quote
from curl_cffi import AsyncSession, Response
from selectolax.lexbor import LexborHTMLParser

# base_api ইমপোর্ট করার সময় এরর হ্যান্ডেল করা
try:
    from base_api import DownloadConfigHLS, ScrapeResult, BaseCore, setup_logger, Helper
except ImportError:
    from base_api import ScrapeResult, BaseCore, setup_logger, Helper
    class DownloadConfigHLS: pass

try:
    from base_api.modules.config import RuntimeConfig
    from base_api.modules.type_hints import DownloadReport
except ImportError:
    class RuntimeConfig: pass
    class DownloadReport: pass

from base_api.modules.errors import NetworkRequestError, BotProtectionDetected, UnknownError, InvalidProxy, ResourceGone

from xhamster_api.modules.errors import (NetworkError, UnknownNetworkError, NotFound, BotDetection, ProxyError,
                                         DownloadFailed)
from xhamster_api.modules.consts import (build_page_url, extractor_shorts, headers, REGEX_AVATAR, REGEX_M3U8,
                                        REGEX_THUMBNAIL, REGEX_AUTHOR)
from xhamster_api.modules.type_hints import on_error_hint


async def on_error(url: str, error: Exception, attempt: int) -> bool:
    print(f"URL: {url}, ERROR: {error}, Attempt: {attempt}")
    if isinstance(error, ResourceGone):
        return False
    return True

async def get_html_content(core: BaseCore, url: str) -> str | None | dict:
    try:
        content = await core.fetch(url)
        if isinstance(content, str):
            return content
        if isinstance(content, Response):
            if content.status_code == 404:
                raise NotFound(f"Server returned 404 for: {url}")
    except NetworkRequestError as e:
        raise NetworkError(str(e)) from e
    except InvalidProxy as e:
        raise ProxyError(str(e)) from e
    except BotProtectionDetected as e:
        raise BotDetection(str(e)) from e
    except UnknownError as e:
        raise UnknownNetworkError(str(e)) from e


@dataclass(slots=True)
class ShortMetadata:
    title: str
    author: str
    likes: int
    dislikes: int
    views: int
    comments: int
    duration: int
    video_id: int
    created_at: int
    tags: list[str]
    author_subscribers: int
    author_logo: str
    author_link: str
    thumb_url: str
    poster_url: str
    m3u8_bas_url: str


class Something(Helper):
    def __init__(self, lexbor: LexborHTMLParser, url: str, core: BaseCore,
                 html_content: str):
        super().__init__(core, video_constructor=VideoBuilder, log_level=logging.ERROR, alternative_constructor=ShortBuilder)
        self.url = url
        self.html_content = html_content
        self.lexbor: LexborHTMLParser = lexbor

    @classmethod
    async def init(cls, url: str, core: BaseCore, html_content: str | None = None) -> Something:
        if not html_content:
            response = await core.fetch(url)
            if response is None:
                html_content = ""
            elif not isinstance(response, str):
                html_content = getattr(response, "text", str(response))
            else:
                html_content = response
        lexbor = LexborHTMLParser(html_content)
        return cls(lexbor=lexbor, url=url, core=core, html_content=html_content)

    def _find_text(self, name: str, index: int = 0) -> str:
        tag = self.lexbor.css(name)[index]
        return tag.text(strip=True) if tag else ""

    @cached_property
    def name(self) -> str:
        return self._find_text("h1.h3-bold-8643e.primary-8643e.landing-info__user-title")

    @cached_property
    def avatar_url(self) -> str:
        return REGEX_AVATAR.search(self.html_content).group(1)

class ShortBuilder:
    def __init__(self, url: str, core: BaseCore, html_content: str | None = None):
        self.core = core
        self.url = url
        self.logger = setup_logger(name="XHamster API - [Short]")
        self.html_content = html_content

    async def init(self) -> Short:
        if not self.html_content:
            self.html_content = await get_html_content(core=self.core, url=self.url)
        return await asyncio.to_thread(self._extract_from_html)

    def _extract_from_html(self):
        meta = ShortMetadata(
            title=self.title, dislikes=self.dislikes, tags=self.tags, thumb_url=self.thumb_url,
            video_id=self.video_id, comments=self.comments, duration=self.duration,
            created_at=self.created_at, poster_url=self.poster_url, author_link=self.author_link,
            author_logo=self.author_logo, m3u8_bas_url=self.m3u8_base_url, likes=self.likes,
            views=self.views, author_subscribers=self.author_subscribers, author=self.author,
        )
        return Short(metadata=meta, core=self.core)

    @cached_property
    def data(self) -> dict:
        lexbor = LexborHTMLParser(self.html_content)
        script = lexbor.css_first("script#initials-script").text()
        json_text = script.split("window.initials=", 1)[-1].strip().rstrip(";")
        return chompjs.parse_js_object(json_text)

    @property
    def title(self): return self.data.get('layoutPage', {}).get('momentProps', {}).get('title', '')
    @property
    def author(self): return self.data.get('layoutPage', {}).get('momentProps', {}).get('landing', {}).get('name', '')
    @property
    def likes(self): return int(self.data.get('layoutPage', {}).get('momentProps', {}).get('ratingModel', {}).get('likes', 0))
    @property
    def dislikes(self): return int(self.data.get('layoutPage', {}).get('momentProps', {}).get('ratingModel', {}).get('dislikes', 0))
    @property
    def views(self): return int(self.data.get('layoutPage', {}).get('momentProps', {}).get('views', 0))
    @property
    def comments(self): return int(self.data.get('layoutPage', {}).get('momentProps', {}).get('comments', 0))
    @property
    def duration(self): return int(self.data.get('xplayerSettings', {}).get('duration', 0))
    @property
    def video_id(self): return int(self.data.get('xplayerSettings', {}).get('videoId', 0))
    @property
    def created_at(self): return int(self.data.get('layoutPage', {}).get('momentProps', {}).get('created', 0))
    @property
    def tags(self): return [tag.get('name') for tag in self.data.get('layoutPage', {}).get('momentProps', {}).get('tags', [])]
    @property
    def author_subscribers(self): return int(self.data.get('layoutPage', {}).get('momentProps', {}).get('landing', {}).get('subscribers', 0))
    @property
    def author_logo(self): return self.data.get('layoutPage', {}).get('momentProps', {}).get('landing', {}).get('logo', '')
    @property
    def author_link(self): return self.data.get('layoutPage', {}).get('momentProps', {}).get('landing', {}).get('link', '')
    @property
    def thumb_url(self): return self.data.get('layoutPage', {}).get('momentProps', {}).get('thumbUrl', '')
    @property
    def poster_url(self): return self.data.get('layoutPage', {}).get('momentProps', {}).get('posterUrl', '')
    @property
    def m3u8_base_url(self): return str(self.data.get('xplayerSettings', {}).get('sources', {}).get('hls', {}).get('h264', {}).get('url', ''))

class Short:
    def __init__(self, metadata, core):
        self.metadata = metadata
        self.core = core

@dataclass(slots=True)
class VideoMetadata:
    title: str
    video_id: int | None
    rating_percentage: int
    likes: int
    dislikes: int
    uploader_name: str
    uploader_subscribers: int
    categories: list[str]
    tags: list[str]
    pornstars: list[str]
    thumbnail: str
    m3u8_base_url: str

class Video:
    def __init__(self, metadata: VideoMetadata, core: BaseCore):
        self.metadata = metadata
        self.core = core
    @property
    def title(self): return self.metadata.title
    @property
    def video_id(self): return self.metadata.video_id
    @property
    def likes(self): return self.metadata.likes
    @property
    def uploader_name(self): return self.metadata.uploader_name
    @property
    def thumbnail(self): return self.metadata.thumbnail
    @property
    def m3u8_base_url(self): return self.metadata.m3u8_base_url

class VideoBuilder:
    def __init__(self, url: str, core: BaseCore, html_content: str | None = None):
        self.core = core
        self.url = url
        self.logger = setup_logger(name="XHamster API - [Video]")
        self.html_content = html_content

    async def init(self) -> Video:
        if not self.html_content:
            self.html_content = await get_html_content(core=self.core, url=self.url)
        return await asyncio.to_thread(self._extract_from_html)

    def _extract_from_html(self) -> Video:
        meta = VideoMetadata(
            title=self.title, video_id=self.video_id, rating_percentage=self.rating_percentage,
            dislikes=self.dislikes, likes=self.likes, uploader_name=self.uploader_name,
            uploader_subscribers=self.uploader_subscribers, pornstars=self.pornstars,
            thumbnail=self.thumbnail, categories=self.categories,
            m3u8_base_url=self.m3u8_base_url, tags=self.tags,
        )
        return Video(metadata=meta, core=self.core)

    @cached_property
    def data(self) -> dict:
        lexbor = LexborHTMLParser(self.html_content)
        script = lexbor.css_first("script#initials-script").text()
        json_text = script.split("window.initials=", 1)[-1].strip().rstrip(";")
        return chompjs.parse_js_object(json_text)

    @property
    def video_id(self): return self.data.get("videoTagsComponent", {}).get("videoId")
    @property
    def title(self): return self.data.get("videoTagsComponent", {}).get("title", "No Title")
    @property
    def rating_percentage(self): return self.data.get("ratingComponent", {}).get("ratingModel", {}).get("value", 0)
    @property
    def likes(self): return self.data.get("ratingComponent", {}).get("ratingModel", {}).get("likes", 0)
    @property
    def dislikes(self): return self.data.get("ratingComponent", {}).get("ratingModel", {}).get("dislikes", 0)
    @property
    def uploader_name(self): 
        tags = self.data.get("videoTagsComponent", {}).get("tags", [])
        for tag in tags:
            if tag.get("isUser"): return tag.get("name", "")
        return ""
    @property
    def uploader_subscribers(self): return 0
    @property
    def categories(self): return []
    @property
    def tags(self): return []
    @property
    def pornstars(self): return []
    @property
    def thumbnail(self): return REGEX_THUMBNAIL.search(self.html_content).group(1) if REGEX_THUMBNAIL.search(self.html_content) else ""
    @property
    def m3u8_base_url(self):
        match = REGEX_M3U8.search(self.html_content)
        return match.group(0).replace("\\/", "/") if match else ""

class Client(Helper):
    def __init__(self, core: BaseCore = BaseCore(RuntimeConfig())):
        super().__init__(core=core, video_constructor=VideoBuilder)
        self.core.initialize_session()
        self.core.session.headers.update(headers)

    async def get_video(self, url: str) -> Video:
        video = VideoBuilder(url, core=self.core)
        return await video.init()

    async def search_videos(self, query: str, pages: int = 1, videos_concurrency: int = 1, pages_concurrency: int = 1, on_video_error=on_error, on_page_error=None, keep_original_order=False):
        path = quote(str(query), safe="")
        final_url = f"https://xhamster.com/search/{path}"
        page_urls = [build_page_url(url=final_url, is_search=True, idx=page) for page in range(1, pages + 1)]
        async for scrape_result in self.iterator(use_alternative_constructor=True, video_link_extractor=extractor_shorts, target_page_urls=page_urls,
                                 max_video_concurrency=videos_concurrency, max_page_concurrency=pages_concurrency,
                                         on_video_error=on_video_error, on_page_error=on_page_error,
                                         keep_original_order=keep_original_order):
            yield scrape_result
