"""Resolve permitted public YouTube sources without saving video."""
import re
from urllib.parse import urlsplit,parse_qs
from html.parser import HTMLParser
class Embed(HTMLParser):
    def __init__(self):
        super().__init__();self.src=""
    def handle_starttag(self,tag,attrs):
        if tag=="iframe":self.src=dict(attrs).get("src","")
def youtube_url(value):
    value=value.strip()
    if value.startswith("<iframe"):
        p=Embed();p.feed(value);value=p.src
    u=urlsplit(value)
    if u.scheme not in ("http","https") or u.hostname not in ("youtube.com","www.youtube.com","m.youtube.com","youtu.be"):raise ValueError("Invalid YouTube URL")
    parts=u.path.strip("/").split("/")
    if u.hostname=="youtu.be":vid=parts[0]
    elif u.path=="/watch":vid=parse_qs(u.query).get("v",[""])[0]
    elif len(parts)==2 and parts[0] in ("embed","live","shorts"):vid=parts[1]
    else:raise ValueError("Use a video or live URL")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}",vid):raise ValueError("Invalid video ID")
    return "https://www.youtube.com/watch?v="+vid
def resolve(value,height):
    import yt_dlp
    limit=int(height) if height!="Auto" else 1080
    options={"quiet":True,"no_warnings":True,"noplaylist":True,"skip_download":True,"socket_timeout":15,"retries":1,"extractor_retries":1,"format":f"best[height<={limit}][vcodec!=none]/bestvideo[height<={limit}]"}
    with yt_dlp.YoutubeDL(options) as y:
        info=y.extract_info(youtube_url(value),download=False)
    if not info or not info.get("url"):raise RuntimeError("No accessible video stream")
    return info["url"],bool(info.get("is_live"))
