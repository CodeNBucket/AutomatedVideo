"""Copyright-free footage: Wikimedia Commons (free licences / public domain only) and
Internet Archive films marked public domain or from the Prelinger collection.

Videos are preferred; when nothing moving matches, a photo gets a slow Ken Burns move.
Every asset keeps its author and licence for credits.txt.
"""
import hashlib
import json
import random
import re
from pathlib import Path

import requests

from .ff import ffmpeg, duration, frame_brightness

UA = {"User-Agent": "AutomatedVideo/2.0 (https://github.com/CodeNBucket/AutomatedVideo)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"
STRIP_TAGS = re.compile(r"<[^>]+>")


def _clean(html) -> str:
    return STRIP_TAGS.sub("", str(html or "")).strip()


class Library:
    def __init__(self, cache: Path, theme: dict, prefer_video: bool = True, offline: bool = False):
        self.cache = cache
        (cache / "media").mkdir(parents=True, exist_ok=True)
        self.theme = theme
        self.prefer_video = prefer_video
        self.offline = offline
        self.used = {}          # asset id -> times used
        self.search_cache_file = cache / "search.json"
        try:
            self.search_cache = json.loads(self.search_cache_file.read_text(encoding="utf-8"))
        except Exception:
            self.search_cache = {}
        self.credits = {}

    # ---------- search ----------
    def _cached(self, key, fn):
        if key not in self.search_cache:
            try:
                self.search_cache[key] = fn()
            except Exception as e:
                print(f"  arama hatası ({key}): {e}")
                return []
            self.search_cache_file.write_text(json.dumps(self.search_cache), encoding="utf-8")
        return self.search_cache[key]

    def _commons(self, query: str, kind: str):
        def run():
            params = {
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                "gsrsearch": f"{query} filetype:{'video' if kind == 'video' else 'bitmap'}",
                "gsrlimit": 25, "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 2400,
                "iiextmetadatafilter": "LicenseShortName|Artist|UsageTerms",
            }
            if kind == "video":
                params["prop"] = "imageinfo|videoinfo"
                params["viprop"] = "derivatives"
            r = requests.get(COMMONS, params=params, headers=UA, timeout=40)
            r.raise_for_status()
            pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
            out = []
            for p in pages:
                info = (p.get("imageinfo") or [{}])[0]
                meta = info.get("extmetadata", {})
                w, h = info.get("width", 0), info.get("height", 0)
                if kind == "image":
                    if w < 900 or h < 500 or w < h * 0.9:
                        continue
                    url = info.get("thumburl") or info.get("url")
                else:
                    if (info.get("duration") or 99) < 3:
                        continue
                    ders = [d for d in (p.get("videoinfo") or [{}])[0].get("derivatives", [])
                            if d.get("type", "").startswith("video/") and 360 <= int(d.get("height", 0) or 0) <= 1080]
                    ders.sort(key=lambda d: abs(int(d.get("height", 0)) - 720))
                    url = ders[0]["src"] if ders else info.get("url")
                    if not ders and info.get("size", 0) > 400e6:
                        continue
                if not url:
                    continue
                out.append({
                    "id": f"commons:{p['title']}", "kind": kind, "url": url,
                    "credit": f"{p['title'].removeprefix('File:')} | {_clean(meta.get('Artist', {}).get('value')) or 'unknown'}"
                              f" | {_clean(meta.get('LicenseShortName', {}).get('value')) or 'see Commons'}"
                              f" | https://commons.wikimedia.org/wiki/{p['title'].replace(' ', '_')}",
                })
            return out
        return self._cached(f"commons|{kind}|{query}", run)

    def _archive(self, query: str):
        def run():
            q = (f"({query}) AND mediatype:(movies) AND "
                 f"(licenseurl:(*publicdomain*) OR collection:(prelinger))")
            r = requests.get("https://archive.org/advancedsearch.php",
                             params={"q": q, "fl[]": ["identifier", "title", "licenseurl"], "rows": 8,
                                     "output": "json"}, headers=UA, timeout=40)
            r.raise_for_status()
            out = []
            for doc in r.json().get("response", {}).get("docs", []):
                ident = doc["identifier"]
                m = requests.get(f"https://archive.org/metadata/{ident}", headers=UA, timeout=40).json()
                files = [f for f in m.get("files", []) if f.get("name", "").lower().endswith(".mp4")]
                files.sort(key=lambda f: (0 if f.get("format") in ("h.264", "h.264 IA") else 1,
                                          int(f.get("size", 0) or 0)))
                if not files:
                    continue
                f = files[0]
                length = f.get("length", "0")
                if ":" in str(length):
                    parts = [float(x) for x in str(length).split(":")]
                    length = sum(v * 60 ** i for i, v in enumerate(reversed(parts)))
                out.append({
                    "id": f"archive:{ident}", "kind": "film",
                    "url": f"https://archive.org/download/{ident}/{f['name']}",
                    "length": float(length or 0),
                    "credit": f"{doc.get('title', ident)} | Internet Archive | "
                              f"{doc.get('licenseurl') or 'Prelinger Archives (public domain)'}"
                              f" | https://archive.org/details/{ident}",
                })
            return out
        return self._cached(f"archive|{query}", run)

    def music(self, queries):
        """A public-domain / CC instrumental from Commons, at least a minute long."""
        def run(q):
            r = requests.get(COMMONS, params={
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                "gsrsearch": f"{q} filetype:audio", "gsrlimit": 15, "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist",
            }, headers=UA, timeout=40)
            r.raise_for_status()
            out = []
            for p in r.json().get("query", {}).get("pages", {}).values():
                info = (p.get("imageinfo") or [{}])[0]
                meta = info.get("extmetadata", {})
                if info.get("size", 0) < 600_000 or "midi" in info.get("mime", ""):
                    continue
                out.append({"id": f"commons:{p['title']}", "kind": "audio", "url": info["url"],
                            "credit": f"Music: {p['title'].removeprefix('File:')} | "
                                      f"{_clean(meta.get('Artist', {}).get('value')) or 'unknown'} | "
                                      f"{_clean(meta.get('LicenseShortName', {}).get('value'))} | "
                                      f"https://commons.wikimedia.org/wiki/{p['title'].replace(' ', '_')}"})
            return out
        for q in queries:
            pool = self._cached(f"commons|audio|{q}", lambda q=q: run(q))
            random.shuffle(pool)
            for a in pool:
                try:
                    path = self.local(a)
                except Exception:
                    continue
                if duration(path) >= 60:
                    self.credits[a["id"]] = a["credit"]
                    return path
        return None

    # ---------- choose ----------
    def candidates(self, query: str):
        kinds = []
        if self.prefer_video:
            kinds += self._commons(query, "video") + self._archive(query)
        kinds += self._commons(query, "image")
        return kinds

    def _usable(self, a):
        n = self.used.get(a["id"], 0)
        limit = 6 if a["kind"] == "film" else 1
        return n < limit

    def pick(self, query: str):
        if self.offline:
            return None
        queries = [query]
        words = query.split()
        if len(words) > 2:
            queries.append(" ".join(words[:-1]))
            queries.append(" ".join(words[:2]))
        fallbacks = list(self.theme["fallback_queries"])
        random.shuffle(fallbacks)
        for q in queries + fallbacks:
            pool = [a for a in self.candidates(q) if self._usable(a)]
            if pool:
                # keep the search ranking but add a little variety
                a = random.choice(pool[:3])
                self.used[a["id"]] = self.used.get(a["id"], 0) + 1
                self.credits[a["id"]] = a["credit"]
                return a
        return None

    # ---------- fetch ----------
    def local(self, asset) -> Path:
        ext = Path(asset["url"].split("?")[0]).suffix or (".jpg" if asset["kind"] == "image" else ".webm")
        path = self.cache / "media" / (hashlib.sha1(asset["url"].encode()).hexdigest()[:16] + ext)
        if not path.exists():
            tmp = path.with_suffix(path.suffix + ".part")
            with requests.get(asset["url"], headers=UA, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            tmp.replace(path)
        return path

    def source_for(self, asset, need: float):
        """Return (input path or url, start offset in seconds) for a shot of `need` seconds."""
        if asset["kind"] == "image":
            return self.local(asset), 0.0
        if asset["kind"] == "film":
            src, total = asset["url"], asset.get("length") or 0
        else:
            src = self.local(asset)
            total = duration(src)
        if total <= need + 1:
            return src, 0.0
        lo, hi = total * 0.08, max(total * 0.08, total * 0.92 - need)
        best, best_t = -1, lo
        for _ in range(4):           # avoid black frames and title cards
            t = random.uniform(lo, hi)
            b = frame_brightness(src, t + need / 2)
            if 35 < b < 215:
                return src, t
            if b > best:
                best, best_t = b, t
        return src, best_t
