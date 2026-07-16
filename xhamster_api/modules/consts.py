import re
from selectolax.lexbor import LexborHTMLParser
REGEX_M3U8 = re.compile(r'https://[^"]*?_TPL_\.(?:h264|av1)\.mp4\.m3u8')
REGEX_THUMBNAIL = re.compile(r'<meta property="og:image" content="(.*?)"/>')
REGEX_AUTHOR = re.compile(r'class="author".*?>(.*?)</a>')
REGEX_AVATAR = re.compile(r"background-image: url\('(.*?)'\)")
headers = {"Referer": "https://www.xhamster.com/"}
def build_page_url(url, is_search, idx):
    if is_search: return f"{url}&page={idx}" if "?" in url else f"{url}?page={idx}"
    return url if idx == 1 else f"{url}/{idx}"
extractor_shorts = lambda c: [n.attributes.get("href") for n in LexborHTMLParser(c).css("a") if n.attributes.get("href")]
