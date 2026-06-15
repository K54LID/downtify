from __future__ import annotations
import json
from pathlib import Path
from typing import Dict

LOCALES_DIR = Path(__file__).parent
SUPPORTED = ["en", "ru", "tr", "ar"]
DEFAULT = "en"

_translations: Dict[str, Dict[str, str]] = {}


def _load() -> None:
    if _translations:
        return
    for code in SUPPORTED:
        with (LOCALES_DIR / f"{code}.json").open("r", encoding="utf-8") as f:
            _translations[code] = json.load(f)


class I18n:
    def __init__(self, language: str = DEFAULT) -> None:
        _load()
        self.language = language if language in SUPPORTED else DEFAULT

    def t(self, key: str, **kwargs) -> str:
        text = _translations.get(self.language, {}).get(key)
        if text is None:
            text = _translations[DEFAULT].get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text


def t(language: str, key: str, **kwargs) -> str:
    return I18n(language).t(key, **kwargs)
