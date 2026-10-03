"""Theme presets: what to search for, how the picture is graded, which transitions and music fit.

Any theme name works. Unknown themes fall back to DEFAULT and DeepSeek still writes
theme-specific search queries per sentence; a preset only sharpens the look.
"""

DEFAULT = {
    "fallback_queries": ["city at night", "old street", "archival footage"],
    "grade": "eq=contrast=1.06:saturation=0.9,vignette=PI/5",
    "transitions": ["fade", "fadeblack", "dissolve"],
    "hard_cut_ratio": 0.35,
    "music_queries": ["piano music", "ambient music"],
    "voice": {"en": "am_onyx", "tr": "tr-TR-AhmetNeural"},
    "subtitle_font": "DejaVu Serif",
}

THEMES = {
    "godfather": {
        "style_hint": "The Godfather era: 1940s-50s New York, Little Italy, Sicily, Five Families, "
                      "old-world honor, quiet threats. Slow, grave, cinematic narration.",
        "fallback_queries": [
            "Little Italy New York 1940s", "Mulberry Street", "Sicily village", "Corleone Sicily",
            "Lucky Luciano", "New York 1940s street", "Palermo", "Ellis Island immigrants",
            "1950s New York night", "Apalachin meeting",
        ],
        # warm, low saturation, heavy vignette, film grain
        "grade": "eq=contrast=1.12:saturation=0.55:gamma=0.95,"
                 "colorbalance=rs=0.08:gs=0.02:bs=-0.08:rm=0.05:bm=-0.05,"
                 "vignette=PI/4,noise=alls=7:allf=t",
        "transitions": ["fadeblack", "dissolve", "fade"],
        "hard_cut_ratio": 0.2,
        "music_queries": ["mandolin", "Sicilian folk music", "tarantella", "waltz"],
        "voice": {"en": "am_onyx", "tr": "tr-TR-AhmetNeural"},
    },
    "sopranos": {
        "style_hint": "The Sopranos: modern New Jersey mob, 1990s-2000s, suburbs, Newark, strip clubs, "
                      "waste management, therapy, family dinners. Wry, dark humour.",
        "fallback_queries": [
            "Newark New Jersey", "New Jersey Turnpike", "Meadowlands", "Pulaski Skyway",
            "New Jersey suburb", "Lincoln Tunnel", "North Caldwell", "Kearny New Jersey",
            "John Gotti", "New Jersey diner",
        ],
        "grade": "eq=contrast=1.08:saturation=0.8,colorbalance=bs=0.05:rs=-0.02,vignette=PI/5,noise=alls=4:allf=t",
        "transitions": ["fade", "fadeblack"],
        "hard_cut_ratio": 0.55,
        "music_queries": ["blues guitar", "jazz", "rock instrumental"],
        "voice": {"en": "am_michael", "tr": "tr-TR-AhmetNeural"},
    },
    "peaky blinders": {
        "style_hint": "Birmingham 1920s, razor gangs, factories, smoke, horses, post-WWI.",
        "fallback_queries": ["Birmingham 1920s", "Black Country factory", "1920s England street",
                             "canal Birmingham", "World War I soldiers"],
        "grade": "eq=contrast=1.15:saturation=0.45,colorbalance=bs=0.06:rs=-0.03,vignette=PI/4,noise=alls=8:allf=t",
        "transitions": ["fadeblack", "dissolve"],
        "hard_cut_ratio": 0.3,
        "music_queries": ["cello", "dark ambient"],
        "voice": {"en": "bm_george", "tr": "tr-TR-AhmetNeural"},
    },
}

ALIASES = {"baba": "godfather", "the godfather": "godfather", "the sopranos": "sopranos"}


def get_theme(name: str) -> dict:
    key = ALIASES.get(name.strip().lower(), name.strip().lower())
    theme = dict(DEFAULT)
    theme.update(THEMES.get(key, {}))
    theme["name"] = name
    theme.setdefault("style_hint", f"Theme: {name}.")
    return theme
