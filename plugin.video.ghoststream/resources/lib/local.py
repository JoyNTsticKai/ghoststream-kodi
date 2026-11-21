# -*- coding: utf-8 -*-
"""Sorgente C: la raccolta locale (disco o NAS).

Nessuna rete: si leggono solo cartelle e file gia' presenti.
"""

import os

from . import naming

VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.m4v', '.mov', '.webm', '.mpg',
                    '.mpeg', '.wmv', '.ts', '.iso')

POSTER_NAMES = ('poster.jpg', 'folder.jpg', 'cover.jpg', 'poster.png', 'folder.png')
FANART_NAMES = ('fanart.jpg', 'fanart.png', 'backdrop.jpg')


def is_available(path):
    return bool(path) and os.path.isdir(path)


def _art(folder):
    """Copertina e sfondo della cartella, se ci sono file immagine."""
    art = {}
    for name in POSTER_NAMES:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            art['thumb'] = candidate
            art['icon'] = candidate
            break
    for name in FANART_NAMES:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            art['fanart'] = candidate
            break
    return art


def _pretty(name):
    label = os.path.splitext(name)[0]
    return label.replace('_', ' ').replace('.', ' ').strip() or label


def scan(path):
    """Restituisce (cartelle, video) come dizionari pronti per il menu."""
    with os.scandir(path) as iterator:
        entries = [entry for entry in iterator if not entry.name.startswith('.')]

    folder_art = _art(path)
    folders = []
    videos = []
    for entry in entries:
        try:
            if entry.is_dir():
                folders.append({
                    'label': entry.name,
                    'path': entry.path,
                    'art': _art(entry.path),
                })
            elif entry.is_file() and entry.name.lower().endswith(VIDEO_EXTENSIONS):
                season, episode, title = naming.episode_info(entry.name)
                try:
                    size = naming.human_size(os.path.getsize(entry.path))
                except OSError:
                    size = ''
                videos.append({
                    'label': _pretty(entry.name),
                    'path': entry.path,
                    'art': folder_art,
                    'title': title,
                    'season': season,
                    'episode': episode,
                    'size': size,
                })
        except OSError:
            continue

    folders.sort(key=lambda item: naming.natural_key(item['label']))
    videos.sort(key=lambda item: (item['episode'] is None,
                                 item['episode'] or 0,
                                 naming.natural_key(item['label'])))
    return folders, videos
