# -*- coding: utf-8 -*-
"""Ordinamento naturale e lettura di stagione/puntata dai nomi dei file.

Serve a due cose:
  * ordinare "Episodio 2" prima di "Episodio 10" (e non dopo "Episodio 100");
  * ricavare numero di puntata e titolo pulito da nomi come
        "05 - La rinascita.mp4", "Episodio 12.mkv", "S01E07 - Titolo.avi".
"""

import os
import re

_NUMBERS = re.compile(r'(\d+)')
_SEPARATORS = re.compile(r'[\s._\-–—]+')
_SPACES = re.compile(r'\s{2,}')

# (espressione, contiene_la_stagione)
_PATTERNS = (
    (re.compile(r'\bs(?:ta(?:gione)?)?\s*(\d{1,2})\s*[ex]\s*(\d{1,3})\b', re.I), True),
    (re.compile(r'\b(\d{1,2})x(\d{1,3})\b'), True),
    (re.compile(r'\b(?:ep|episodio|puntata|parte)[\s._-]*(\d{1,3})\b', re.I), False),
    (re.compile(r'(?<![\w])(\d{1,3})(?![\w])'), False),
)


def natural_key(text):
    """Chiave di ordinamento in cui i numeri contano come numeri."""
    return [int(part) if part.isdigit() else part.lower()
            for part in _NUMBERS.split(text or '')]


def _clean(text):
    text = text.replace('_', ' ')
    text = _SEPARATORS.sub(' ', text)
    text = text.strip(' -–—.,')
    return _SPACES.sub(' ', text).strip()


def episode_info(name):
    """Restituisce (stagione, puntata, titolo) ricavati dal nome del file."""
    base = os.path.splitext(os.path.basename(name or ''))[0]
    base = base.replace('_', ' ').strip()
    for pattern, has_season in _PATTERNS:
        match = pattern.search(base)
        if not match:
            continue
        if has_season:
            season, episode = int(match.group(1)), int(match.group(2))
        else:
            season, episode = None, int(match.group(1))
        rest = _clean(base[:match.start()] + ' ' + base[match.end():])
        return season, episode, rest or _clean(base)
    return None, None, _clean(base)


def number_width(episodes):
    """Larghezza minima per zero-paddare i numeri di puntata."""
    values = [episode for episode in episodes if episode]
    return max(2, len(str(max(values)))) if values else 2


def episode_label(episode, title, width):
    """'007. Titolo' - il padding rende giusto anche l'ordine alfabetico di Kodi."""
    if not episode:
        return title
    return '%s. %s' % (str(episode).zfill(width), title)


def human_size(size):
    """'12.4 MB' a partire da un numero di byte."""
    try:
        size = float(size)
    except (TypeError, ValueError):
        return ''
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            return '%.0f %s' % (size, unit) if unit == 'B' else '%.1f %s' % (size, unit)
        size /= 1024.0
    return ''
