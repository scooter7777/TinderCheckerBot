"""Tinder profile checker — shieracc API + web scrape hybrid."""

import json
import enum
import re
import time
import typing
import datetime
import urllib.request
import urllib.error


_API_URL = "https://vip.shieracc.com/api/execute"
_API_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Origin": "https://vip.shieracc.com",
    "Referer": "https://vip.shieracc.com/",
}
_WEB_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_INTERVAL = 1.5


class LookupStatus(enum.Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    ERROR = "error"


class LookupResult:
    def __init__(self, status: LookupStatus,
                 profile: typing.Optional['TinderProfile'] = None,
                 message: str = ""):
        self.status = status
        self.profile = profile
        self.message = message


class TinderProfile:
    def __init__(self, username: str, name: str, age: typing.Union[int, str],
                 reg_date: typing.Optional[datetime.datetime],
                 status_text: str,
                 photo_urls: typing.Optional[typing.List[str]] = None):
        self.username = username
        self.name = name
        self.age = age
        self.reg_date = reg_date
        self.status_text = status_text
        self.photo_urls = photo_urls or []


class TinderClient:
    def __init__(self):
        self._last = 0.0

    def _wait(self):
        now = time.monotonic()
        el = now - self._last
        if el < _INTERVAL:
            time.sleep(_INTERVAL - el)
        self._last = time.monotonic()

    # ── Public ───────────────────────────────────────────────────────

    def lookup(self, username: str) -> LookupResult:
        self._wait()

        # 1. Try shieracc API first
        result = self._call_api(username)

        # 2. If API returned error (限流), try web scrape for details
        if result.status == LookupStatus.FOUND:
            profile = result.profile
            if profile.status_text == "Restricted (Cannot Match)" and not profile.reg_date:
                web = self._scrape_web(username)
                if web:
                    profile.name = web.name
                    profile.reg_date = web.reg_date
                    profile.age = web.age
                    if not profile.photo_urls:
                        profile.photo_urls = web.photo_urls

        return result

    # ── shieracc API ─────────────────────────────────────────────────

    def _call_api(self, username: str) -> LookupResult:
        payload = json.dumps({
            "action": "单项用户名查活",
            "username": username,
            "login_code": "", "proxy": "", "coordinates": "",
            "age_range": "", "max_matches": "", "promo_code": "",
            "gender": "", "extra_data": ""
        }).encode()

        req = urllib.request.Request(
            _API_URL, data=payload, headers=_API_HEADERS
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError:
            return LookupResult(LookupStatus.ERROR, message="API server unavailable")
        except (urllib.error.URLError, OSError) as e:
            return LookupResult(LookupStatus.ERROR, message=f"Network: {e}")

        api_status = body.get("status", "")
        message = body.get("message", "")
        pdata = body.get("profile") or {}

        if api_status == "success":
            status_text = "Active, Normal Matching"
        elif api_status == "error":
            if "查活失败" in message:
                status_text = "Restricted (Cannot Match)"
            else:
                status_text = pdata.get("status", "检测异常")
        else:
            status_text = pdata.get("status", "检测异常")

        name = pdata.get("name", username)
        age_raw = pdata.get("age")
        try:
            age = int(age_raw) if age_raw is not None else "-"
        except (ValueError, TypeError):
            age = "-"

        reg_str = pdata.get("regDate", "")
        reg_date = None
        if reg_str:
            try:
                reg_date = datetime.datetime.strptime(reg_str, "%Y-%m-%d %H:%M:%S")
                reg_date = reg_date.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                pass

        images = pdata.get("images") or []

        profile = TinderProfile(
            username=username, name=name, age=age,
            reg_date=reg_date, status_text=status_text,
            photo_urls=images,
        )
        return LookupResult(LookupStatus.FOUND, profile=profile)

    # ── Web scrape fallback ──────────────────────────────────────────

    def _scrape_web(self, username: str) -> typing.Optional[TinderProfile]:
        """Scrape tinder.com/@username for name + reg date + photos."""
        url = f"https://tinder.com/@{username}"
        req = urllib.request.Request(url, headers={"User-Agent": _WEB_UA})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read(500_000).decode("utf-8", errors="replace")
        except Exception:
            return None

        match = re.search(r"window\.__data\s*=\s*({.*?});", html, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

        u = data.get("webProfile", {}).get("user")
        if not u or not u.get("_id"):
            return None

        uid = u["_id"]
        created = datetime.datetime.fromtimestamp(
            int(uid[:8], 16), tz=datetime.timezone.utc
        )

        bd_str = u.get("birth_date")
        calc_age = "-"
        if bd_str:
            try:
                bd = datetime.datetime.fromisoformat(bd_str.replace("Z", "+00:00"))
                now = datetime.datetime.now(tz=datetime.timezone.utc)
                calc_age = now.year - bd.year - ((now.month, now.day) < (bd.month, bd.day))
            except (ValueError, TypeError):
                pass

        photos = []
        for ph in u.get("photos", []):
            files = ph.get("processedFiles", [])
            if files:
                photos.append(files[0].get("url", ""))

        return TinderProfile(
            username=username,
            name=u.get("name", username),
            age=calc_age,
            reg_date=created,
            status_text="-",
            photo_urls=photos,
        )
