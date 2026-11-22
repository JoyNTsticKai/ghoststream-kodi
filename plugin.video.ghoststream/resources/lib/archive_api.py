# -*- coding: utf-8 -*-
"""Sorgente B: Internet Archive (pubblico dominio / licenze libere).

Solo libreria standard: urllib + json. Nessuna dipendenza da installare.
"""

import json
import urllib.parse
import urllib.request

from . import naming

SEARCH_URL = 'https://archive.org/advancedsearch.php'
METADATA_URL = 'https://archive.org/metadata/%s'
DOWNLOAD_URL = 'https://archive.org/download/%s/%s'
THUMB_URL = 'https://archive.org/services/img/%s'
USER_AGENT = 'plugin.video.ghoststream/1.9.6 (Kodi addon)'

VIDEO_EXTENSIONS = ('.mp4', '.m4v', '.webm', '.mkv', '.ogv', '.m3u8')

SUGGESTED_QUERIES = (
    ("Cartoni animati", 'subject:"cartoni animati"'),
    ("Animazione giapponese", 'subject:"anime" AND (language:ita OR language:Italian)'),
    ("Film d'epoca", '(language:ita OR language:Italian) AND mediatype:movies AND year:[1900 TO 1960]'),
    ("Documentari", 'subject:"documentari" AND (language:ita OR language:Italian)'),
)


class ArchiveError(Exception):
    """Errore di rete o di risposta delle API archive.org."""


def _fetch_json(url, timeout=25):
    request = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode('utf-8', 'replace')
    except Exception as exc:
        raise ArchiveError('richiesta fallita: %s' % exc)

    try:
        return json.loads(payload)
    except ValueError as exc:
        raise ArchiveError('risposta non JSON: %s' % exc)


def thumbnail_url(identifier):
    return THUMB_URL % urllib.parse.quote(identifier, safe='')


def search(query, page=1, rows=30):
    """Restituisce (documenti, totale) per una query Solr su archive.org."""
    query = (query or '').strip()
    if not query:
        raise ArchiveError('query vuota')
    if 'mediatype:' not in query:
        query = '(%s) AND mediatype:movies' % query

    params = [
        ('q', query),
        ('rows', str(rows)),
        ('page', str(page)),
        ('output', 'json'),
        ('fl[]', 'identifier'),
        ('fl[]', 'title'),
        ('fl[]', 'year'),
        ('fl[]', 'description'),
        ('fl[]', 'creator'),
        ('fl[]', 'subject'),
        ('fl[]', 'downloads'),
        ('sort[]', 'downloads desc'),
    ]
    data = _fetch_json(SEARCH_URL + '?' + urllib.parse.urlencode(params))
    response = data.get('response') or {}
    return response.get('docs') or [], int(response.get('numFound') or 0)


def _priority(entry):
    name = (entry.get('name') or '').lower()
    fmt = (entry.get('format') or '').lower()
    if name.endswith('.m3u8') or fmt == 'hls':
        return 1
    if 'h.264' in fmt:
        return 3
    if 'mpeg4' in fmt or name.endswith('.mp4'):
        return 2
    return 0


def _seconds(value):
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def _text(value):
    """Alcuni campi di archive.org sono liste: si uniscono in una stringa."""
    if isinstance(value, (list, tuple)):
        value = ' '.join(str(part) for part in value if part)
    return ' '.join(str(value or '').split())


def item_info(data):
    """Titolo, trama, anno e autore dell'item (per le schede della lista)."""
    meta = data.get('metadata') or {}
    year = _text(meta.get('year'))
    info = {
        'title': _text(meta.get('title')),
        'plot': _text(meta.get('description'))[:2000],
        'creator': _text(meta.get('creator')),
    }
    if year.isdigit():
        info['year'] = int(year)
    return info


def playable_files(identifier):
    """Restituisce (file, info_item): tutti i file video dell'item."""
    data = _fetch_json(METADATA_URL % urllib.parse.quote(identifier, safe=''))
    files = []
    for entry in data.get('files') or []:
        name = (entry.get('name') or '').strip()
        if not name or not name.lower().endswith(VIDEO_EXTENSIONS):
            continue
        if '/_thumb' in name or name.startswith('__'):
            continue
        label = name.rsplit('/', 1)[-1]
        season, episode, title = naming.episode_info(label)
        files.append({
            'name': name,
            'label': label,
            'title': title,
            'season': season,
            'episode': episode,
            'format': entry.get('format') or '',
            'size': naming.human_size(entry.get('size')),
            'duration': _seconds(entry.get('length')),
            'priority': _priority(entry),
            'url': DOWNLOAD_URL % (
                urllib.parse.quote(identifier, safe=''),
                urllib.parse.quote(name, safe='/'),
            ),
        })

    return files, item_info(data)


def episodes(identifier):
    """Restituisce (puntate, info_item).

    Una voce per puntata: le copie dello stesso episodio in formati diversi
    finiscono nello stesso gruppo, con la piu' adatta per prima.
    """
    files, meta = playable_files(identifier)
    groups = []
    index = {}
    for entry in files:
        key = None
        if entry['episode']:
            key = (entry['season'], entry['episode'])
        group = index.get(key) if key else None
        if group is None:
            group = {
                'season': entry['season'],
                'episode': entry['episode'],
                'title': entry['title'],
                'files': [],
            }
            if key:
                index[key] = group
            groups.append(group)
        group['files'].append(entry)

    for group in groups:
        group['files'].sort(key=lambda item: (-item['priority'],
                                             naming.natural_key(item['label'])))

    groups.sort(key=lambda item: (
        item['episode'] is None,
        item['episode'] or 0,
        naming.natural_key(item['title'] or item['files'][0]['label']),
    ))
    return groups, meta


def episode_versions(identifier, episode, season=None):
    """Le versioni di una singola puntata, quella preferita per prima."""
    groups, meta = episodes(identifier)
    for group in groups:
        if group['episode'] != episode:
            continue
        if season is not None and group['season'] != season:
            continue
        return group['files'], meta
    return [], meta
