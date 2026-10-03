"""Narration script from DeepSeek: sentences plus one visual search query per sentence."""
import json
import os
import re

import requests

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
WORDS_PER_MIN = {"en": 145, "tr": 115}
LANG_NAME = {"en": "English", "tr": "Turkish"}

PROMPT = """You write narration for a faceless YouTube storytelling channel. The video shows
archival, copyright-free footage behind a deep narrator voice, like popular mafia/history channels.

Theme / world: {theme}
Style: {style}
Topic the viewer asked for: {topic}
Language of the narration: {lang}
Length: about {words} words of narration (that is {minutes} minutes when read aloud).

Rules:
- Strong hook in the first two sentences, then build tension, end with a memorable line.
- Short, spoken sentences (8-22 words). No headings, no stage directions, no emojis.
- Stick to facts when the topic is historical; if it is fiction (a film or series), say so naturally.
- For EVERY sentence give "visual": an ENGLISH search query of 2-5 words that would find a matching
  public-domain or Creative Commons photo or video on Wikimedia Commons or the Internet Archive.
  Use real places, eras, people, objects (e.g. "Mulberry Street 1940s", "Lucky Luciano mugshot",
  "Sicily lemon grove", "1950s Cadillac"). Never name the copyrighted film or show in "visual".

Return only JSON:
{{"title": "...", "description": "two sentence YouTube description",
  "music": "2-3 word search query for fitting public-domain instrumental music",
  "sentences": [{{"text": "...", "visual": "..."}}]}}"""


def load_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    for path in (".env", os.path.join(os.path.dirname(__file__), "..", ".env")):
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                m = re.match(r"\s*DEEPSEEK_API_KEY\s*=\s*['\"]?([^'\"\s]+)", line)
                if m:
                    return m.group(1)
    raise SystemExit("DEEPSEEK_API_KEY bulunamadı: ortam değişkeni olarak ya da .env dosyasına yaz.")


def write_script(theme: dict, topic: str, minutes: float, lang: str) -> dict:
    words = int(minutes * WORDS_PER_MIN.get(lang, 140))
    prompt = PROMPT.format(theme=theme["name"], style=theme["style_hint"], topic=topic,
                           lang=LANG_NAME.get(lang, lang), words=words, minutes=minutes)
    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {load_key()}"},
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.9,
            "max_tokens": 8000,
        },
        timeout=300,
    )
    resp.raise_for_status()
    data = json.loads(resp.json()["choices"][0]["message"]["content"])
    data["sentences"] = [s for s in data.get("sentences", []) if s.get("text", "").strip()]
    if not data["sentences"]:
        raise RuntimeError("DeepSeek boş metin döndürdü")
    return data
