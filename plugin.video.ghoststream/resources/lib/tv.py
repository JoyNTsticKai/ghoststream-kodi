# -*- coding: utf-8 -*-
"""TV in chiaro: canali da una lista pubblica e guida TV XMLTV.

La lista predefinita e' quella italiana di iptv-org (canali in chiaro, con
logo, group-title e tvg-id); la guida predefinita unisce piu' XMLTV italiani
pubblici (open-epg per i nazionali, epgshare per Sky e gli altri), perche' una
sola guida copre solo una parte dei canali. Entrambe si possono sostituire
dalle impostazioni e restano in cache nella cartella dati, cosi' la sezione si
apre anche senza rete. Le TV locali non hanno una guida pubblica: per quelle
resta solo il nome del canale.
"""

import calendar
import gzip
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

from resources.lib import playlist, playlist_store

LIST_URL = 'https://iptv-org.github.io/iptv/countries/it.m3u'
# Prima le guide dei nazionali, poi quella che copre Sky e le altre pay TV.
GUIDE_URLS = (
    'https://www.open-epg.com/files/italy3.xml',
    'https://www.open-epg.com/files/italy2.xml',
    'https://www.open-epg.com/files/italy1.xml',
    'https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz',
)
CHANNEL_CACHE = 'tv.json'
GUIDE_CACHE = 'epg.json'
CHANNELS_MAX_AGE = 12 * 3600
GUIDE_MAX_AGE = 8 * 3600
DOWNLOAD_LIMIT = 12 * 1024 * 1024
TIMEOUT = 25

_SUFFIX = re.compile(r'\.(?:it|de|fr|es|uk|us|ch|at)$')
_PARENTHESIS = re.compile(r'\([^)]*\)')
_TIME = re.compile(r'^(\d{14})(?:\s*([+-])(\d{2})(\d{2}))?')


class TvError(Exception):
    """Lista canali o guida TV non disponibili."""


def _download(url):
    request = urllib.request.Request(url,
                                     headers={'User-Agent': playlist.USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = response.read(DOWNLOAD_LIMIT)
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    return data


def channels(url='', force=False):
    """Voci della lista canali, dalla cache se fresca o dalla rete."""
    url = url or LIST_URL
    cache = playlist_store.read_data(CHANNEL_CACHE)
    entries = cache.get('entries') or []
    fresh = (cache.get('url') == url and
             time.time() - (cache.get('fetched') or 0) < CHANNELS_MAX_AGE)
    if entries and fresh and not force:
        return entries
    try:
        result = playlist.load(url)
    except playlist.PlaylistError as exc:
        if entries:
            return entries
        raise TvError('lista canali non leggibile: %s' % exc)
    if result['stream'] or not result['entries']:
        if entries:
            return entries
        raise TvError('la lista non contiene canali')
    try:
        playlist_store.write_data(CHANNEL_CACHE, {
            'url': url, 'fetched': int(time.time()),
            'entries': result['entries']})
    except playlist_store.StoreError:
        pass
    return result['entries']


def guide_sources(url=''):
    """Una sola guida se l'utente la indica, altrimenti tutte quelle pubbliche."""
    url = (url or '').strip()
    return (url,) if url else GUIDE_URLS


def merge_guides(parts):
    """Unisce piu' guide: per ogni canale vince la prima fonte che lo conosce."""
    merged = {'aliases': {}, 'programmes': {}}
    for part in parts or []:
        for alias, main in (part.get('aliases') or {}).items():
            merged['aliases'].setdefault(alias, main)
        for key, items in (part.get('programmes') or {}).items():
            if items and key not in merged['programmes']:
                merged['programmes'][key] = items
    return merged


def guide(url='', force=False):
    """Guida TV: {'aliases': {...}, 'programmes': {canale: [[inizio, fine, titolo]]}}.

    Se una fonte non risponde si usano le altre: una guida parziale e' meglio di
    nessun programma. Solo se non arriva niente si tiene la copia vecchia.
    """
    sources = guide_sources(url)
    cache = playlist_store.read_data(GUIDE_CACHE)
    data = cache.get('guide') or {}
    fresh = (tuple(cache.get('sources') or ()) == sources and
             time.time() - (cache.get('fetched') or 0) < GUIDE_MAX_AGE)
    if data and fresh and not force:
        return data
    parts = []
    errors = []
    for source in sources:
        try:
            parts.append(parse_guide(_download(source)))
        except Exception as exc:
            errors.append('%s (%s)' % (source, exc))
    merged = merge_guides(parts)
    if not merged['programmes']:
        if data:
            return data
        raise TvError('guida TV non scaricata: %s'
                      % ('; '.join(errors) or 'nessuna fonte'))
    try:
        playlist_store.write_data(GUIDE_CACHE, {
            'sources': list(sources), 'fetched': int(time.time()),
            'guide': merged})
    except playlist_store.StoreError:
        pass
    return merged


def channel_key(value):
    """'Rai1.it@SD' e 'Rai 1.it' diventano la stessa chiave: 'rai1'."""
    text = _PARENTHESIS.sub(' ', (value or '').strip().lower())
    text = text.split('@')[0]
    text = _SUFFIX.sub('', text.strip())
    return re.sub(r'[^a-z0-9]+', '', text)


def parse_time(value):
    """'20261121180000 +0100' -> epoch UTC; 0 se illeggibile."""
    match = _TIME.match((value or '').strip())
    if not match:
        return 0
    try:
        moment = time.strptime(match.group(1), '%Y%m%d%H%M%S')
    except ValueError:
        return 0
    stamp = calendar.timegm(moment)
    if match.group(2):
        offset = int(match.group(3)) * 3600 + int(match.group(4)) * 60
        stamp -= offset if match.group(2) == '+' else -offset
    return stamp


def clock(stamp):
    try:
        return time.strftime('%H:%M', time.localtime(int(stamp)))
    except (TypeError, ValueError, OSError):
        return ''


def parse_guide(data):
    """Legge un XMLTV: canali, alias dei nomi e programmi in ordine di ora."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    if data[:3] == b'\xef\xbb\xbf':   # BOM UTF-8: c'e' chi lo mette davanti
        data = data[3:]
    try:
        root = ET.fromstring(data.strip())
    except ET.ParseError as exc:
        raise TvError('guida TV illeggibile: %s' % exc)

    aliases = {}
    for node in root.findall('channel'):
        main = channel_key(node.get('id'))
        for name in node.findall('display-name'):
            alias = channel_key(name.text)
            if main and alias and alias != main:
                aliases[alias] = main

    programmes = {}
    for node in root.findall('programme'):
        key = channel_key(node.get('channel'))
        start = parse_time(node.get('start'))
        if not key or not start:
            continue
        title_node = node.find('title')
        title = (title_node.text or '').strip() if title_node is not None else ''
        programmes.setdefault(key, []).append(
            [start, parse_time(node.get('stop')) or start, title])
    for items in programmes.values():
        items.sort(key=lambda item: item[0])
    return {'aliases': aliases, 'programmes': programmes}


def keys_for(guide_data, tvg_id='', name=''):
    """Chiavi con cui cercare un canale nella guida: id, alias e nome."""
    aliases = (guide_data or {}).get('aliases') or {}
    keys = [channel_key(tvg_id)]
    alias = aliases.get(keys[0])
    if alias and alias != keys[0]:
        keys.append(alias)
    keys.append(channel_key(name))
    return [key for key in keys if key]


def _pair(items, moment):
    """(in onda adesso, prossimo) dentro i programmi gia' ordinati."""
    for index, item in enumerate(items):
        if item[0] <= moment < item[1]:
            return item, items[index + 1] if index + 1 < len(items) else None
    for item in items:
        if item[0] > moment:
            return None, item
    return None, None


def _programmes_of(guide_data, tvg_id='', name=''):
    """Programmi del primo id/alias/nome che la guida conosce, o None."""
    programmes = (guide_data or {}).get('programmes') or {}
    for key in keys_for(guide_data, tvg_id, name):
        items = programmes.get(key)
        if items:
            return items
    return None


def now_and_next(guide_data, tvg_id='', name='', at=None):
    """(in onda adesso, prossimo) per un canale; (None, None) se manca."""
    items = _programmes_of(guide_data, tvg_id, name)
    return _pair(items, int(at or time.time())) if items else (None, None)


def with_guide(entries, guide_data, at=None):
    """Copia delle voci con 'epg' (programma in onda) e 'plot' arricchito.

    'epg_ok' dice se il canale compare nella guida, anche quando adesso non ha
    niente in onda: serve al filtro dei canali con la guida.
    """
    moment = int(at or time.time())
    decorated = []
    for entry in entries or []:
        item = dict(entry)
        items = _programmes_of(guide_data, item.get('tvg_id'), item.get('name'))
        if items:
            item['epg_ok'] = True
            current, following = _pair(items, moment)
            if current:
                item['epg'] = '%s %s' % (clock(current[0]), current[2][:40])
                plot = 'In onda: %s (%s-%s)' % (current[2], clock(current[0]),
                                                clock(current[1]))
                if following:
                    plot += '\nOra: %s (%s)' % (following[2], clock(following[0]))
                item['plot'] = plot
        decorated.append(item)
    return decorated
