import asyncio
from urllib.robotparser import RobotFileParser

from starlette.requests import Request

from web.routes.seo import robots_txt


def _parser() -> RobotFileParser:
    req = Request({"type": "http", "method": "GET", "path": "/robots.txt", "scheme": "https",
                   "server": ("transparenciapb.org", 443), "headers": [(b"host", b"transparenciapb.org")]})
    body = asyncio.run(robots_txt(req)).body.decode()
    rp = RobotFileParser()
    rp.parse(body.splitlines())
    return rp


def test_robots_bloqueia_crawlers_comerciais():
    rp = _parser()
    for ua in ("ShapBot/0.1.0", "AhrefsBot/7.0", "SemrushBot/7~bl", "PetalBot"):
        assert not rp.can_fetch(ua, "https://transparenciapb.org/cidade/patos"), ua


def test_robots_mantem_buscadores():
    rp = _parser()
    for ua in ("Googlebot/2.1", "bingbot/2.0", "OAI-SearchBot/1.4", "Mozilla/5.0"):
        assert rp.can_fetch(ua, "https://transparenciapb.org/cidade/patos"), ua
