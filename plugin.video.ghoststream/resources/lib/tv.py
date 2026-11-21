# -*- coding: utf-8 -*-
"""TV in chiaro: canali da una lista pubblica e guida TV XMLTV.

La lista predefinita e' quella italiana di iptv-org (canali in chiaro, con
logo, group-title e tvg-id); la guida predefinita unisce piu' XMLTV italiani
pubblici (open-epg per i nazionali, epgshare per Sky e gli altri), perche' una
sola guida copre solo una parte dei canali. Entrambe si possono sostituire
dalle impostazioni e restano in cache nella cartella dati, cosi' la sezione si
apre anche senza rete. Le TV locali non hanno una guida pubblica: per quelle
resta solo il nome del canale.

L'elenco segue il numero di canale del telecomando (Rai 1, Rai 2, Rai 3, Rete 4,
Canale 5, Italia 1...): l'ordine alfabetico della lista M3U non c'entra con
quello che si vede sul televisore. I canali senza un numero nazionale (le TV
locali, le web TV) vanno in fondo, in ordine di nome.
"""

import calendar
import gzip
import json
import os
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
# Sorgenti scelte dall'interfaccia Tkinter (_gui_tk.py): liste e guide in piu'
# e canali singoli, senza toccare le impostazioni di Kodi.
SOURCES_FILE = 'sources.json'
# Sorgenti predefinite che viaggiano dentro l'addon: stanno nello zip, quindi
# arrivano a tutti con l'aggiornamento della repository. L'utente puo' sempre
# aggiungere le sue, che si sommano a queste.
BUILTIN_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'resources', 'sources.json')
CHANNELS_MAX_AGE = 12 * 3600
GUIDE_MAX_AGE = 8 * 3600
DOWNLOAD_LIMIT = 12 * 1024 * 1024
TIMEOUT = 25

_SUFFIX = re.compile(r'\.(?:it|de|fr|es|uk|us|ch|at)$')
_PARENTHESIS = re.compile(r'\([^)]*\)')
_TIME = re.compile(r'^(\d{14})(?:\s*([+-])(\d{2})(\d{2}))?')
# Qualita' nel nome: 'Rai 1 HD (1080p)' e 'Rai 1' sono lo stesso canale.
_QUALITY = re.compile(r'\b(?:hd|sd|fhd|uhd|4k|hq)\b')
_BRACKETS = re.compile(r'\[[^\]]*\]')

# Numero di canale italiano (LCN): l'ordine del telecomando. Solo i nazionali
# hanno un numero fisso; le TV locali cambiano da regione a regione e restano
# fuori da questa tabella.
NUMBERS = {
    'rai1': 1, 'rai2': 2, 'rai3': 3,
    'rete4': 4, 'canale5': 5, 'italia1': 6,
    'la7': 7, 'tv8': 8, 'nove': 9,
    '20': 20, '20mediaset': 20,
    'rai4': 21, 'iris': 22, 'rai5': 23, 'raimovie': 24, 'raipremium': 25,
    'cielo': 26, 'twentyseven': 27, 'tv2000': 28, 'la7d': 29, 'la5': 30,
    'realtime': 31, 'qvc': 32, 'foodnetwork': 33, 'cine34': 34, 'focus': 35,
    'rtl1025tv': 36, 'radioitalia': 37, 'giallo': 38, 'topcrime': 39,
    'boing': 40, 'k2': 41, 'cartoonito': 42, 'raigulp': 43, 'raiyoyo': 44,
    'super': 47, 'rainews24': 48, 'tgcom24': 51, 'dmax': 52,
    'deejaytv': 53, 'raistoria': 54, 'mediasetextra': 55, 'hgtv': 56,
    'raiscuola': 57, 'discoverychannel': 58, 'motortrend': 59,
    'sportitalia': 60, 'supertennis': 64, 'italia2': 66,
}
UNNUMBERED = 9999


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
    """Voci di tutte le liste canali, dalla cache se fresca o dalla rete."""
    urls = channel_sources(url)
    cache = playlist_store.read_data(CHANNEL_CACHE)
    entries = cache.get('entries') or []
    fresh = (list(cache.get('urls') or []) == urls and
             time.time() - (cache.get('fetched') or 0) < CHANNELS_MAX_AGE)
    if entries and fresh and not force:
        return sort_channels(list(entries) + custom_channels(entries))
    found = []
    errors = []
    seen = set()
    for source in urls:
        try:
            result = playlist.load(source)
        except playlist.PlaylistError as exc:
            errors.append('%s (%s)' % (source, exc))
            continue
        if result['stream'] or not result['entries']:
            errors.append('%s (nessun canale)' % source)
            continue
        for entry in result['entries']:
            link = entry.get('url')
            if not link or link in seen:
                continue
            seen.add(link)
            found.append(entry)
    if not found:
        if entries:
            return sort_channels(list(entries) + custom_channels(entries))
        raise TvError('lista canali non leggibile: %s'
                      % ('; '.join(errors) or 'nessuna fonte'))
    try:
        playlist_store.write_data(CHANNEL_CACHE, {
            'urls': urls, 'fetched': int(time.time()), 'entries': found})
    except playlist_store.StoreError:
        pass
    return sort_channels(found + custom_channels(found))


def builtin_sources():
    """Sorgenti predefinite dell'addon (resources/sources.json), se ci sono."""
    try:
        with open(BUILTIN_FILE, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def sources():
    """Sorgenti: quelle dentro l'addon piu' quelle scelte dall'interfaccia.

    Le predefinite arrivano con l'aggiornamento dell'addon; quelle dell'utente
    (sources.json nella cartella dati) si sommano e, se indicano la lista o la
    guida principale, vincono sulle predefinite.
    """
    data = dict(builtin_sources())
    mine = playlist_store.read_data(SOURCES_FILE)
    if not isinstance(mine, dict):
        return data
    for key in ('tv_url', 'epg_url'):
        value = str(mine.get(key) or '').strip()
        if value:
            data[key] = value
    for key in ('tv_urls', 'epg_urls'):
        extra = _clean_urls(mine.get(key) or [])
        if extra:
            data[key] = _clean_urls((data.get(key) or []) + extra)
    if mine.get('channels'):
        data['channels'] = (list(data.get('channels') or []) +
                            list(mine.get('channels') or []))
    return data


def _clean_urls(values):
    """Link in ordine, senza doppioni e senza righe vuote."""
    urls = []
    for value in values or ():
        url = str(value or '').strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def channel_sources(url=''):
    """Liste dei canali: la scelta dell'utente piu' quelle aggiunte.

    Senza una lista scelta resta quella pubblica italiana, cosi' aggiungere
    una lista non fa sparire i canali nazionali.
    """
    data = sources()
    primary = _clean_urls([url, data.get('tv_url')])
    extras = _clean_urls(data.get('tv_urls') or [])
    return _clean_urls((primary or [LIST_URL]) + extras)


def guide_sources(url=''):
    """Guide TV: la scelta dell'utente piu' quelle aggiunte, o le pubbliche."""
    data = sources()
    primary = _clean_urls([url, data.get('epg_url')])
    extras = _clean_urls(data.get('epg_urls') or [])
    return tuple(_clean_urls((primary or list(GUIDE_URLS)) + extras))


def custom_channels(existing=()):
    """Canali singoli aggiunti a mano dall'interfaccia."""
    known = {entry.get('url') for entry in existing or ()}
    entries = []
    for item in sources().get('channels') or []:
        if not isinstance(item, dict):
            continue
        link = str(item.get('url') or '').strip()
        if not link or link in known:
            continue
        known.add(link)
        entries.append({'name': str(item.get('name') or '').strip() or link,
                        'url': link,
                        'logo': str(item.get('logo') or ''),
                        'group': str(item.get('group') or '')})
    return entries


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
    fresh = (list(cache.get('sources') or []) == list(sources) and
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


def plain_name(name):
    """'Rai 1 HD (1080p)' -> 'rai 1': via qualita' e parentesi dal nome."""
    text = _BRACKETS.sub(' ', _PARENTHESIS.sub(' ', name or ''))
    return _QUALITY.sub(' ', text.lower()).strip()


def channel_number(name='', number=0):
    """Numero di canale: tvg-chno della lista, altrimenti il LCN italiano."""
    try:
        fixed = int(number or 0)
    except (TypeError, ValueError):
        fixed = 0
    return fixed or NUMBERS.get(channel_key(plain_name(name)), 0)


def sort_channels(entries):
    """Nazionali in ordine di numero di canale, poi gli altri per nome.

    Le copie portano con se' 'number', cosi' anche l'ordine "per numero di
    canale" delle liste mostra gli stessi numeri.
    """
    items = []
    for entry in entries or ():
        item = dict(entry)
        item['number'] = channel_number(item.get('name'), item.get('number'))
        items.append(item)
    return sorted(items, key=lambda entry: (
        entry['number'] or UNNUMBERED, playlist.order_key(entry.get('name') or '')))


_QUALITY_WORD = re.compile(r'\b(fhd|uhd|hd|sd|4k)\b', re.I)
_QUALITY_TAG = re.compile(r'\((\d{3,4}p)\)', re.I)


def variant_label(name):
    """Cosa distingue una copia dello stesso canale: 'HD 1080p', '720p'.

    Serve al sottomenu SD/HD: senza etichetta le due voci sarebbero identiche.
    """
    text = (name or '').strip()
    parts = []
    word = _QUALITY_WORD.search(text)
    if word:
        parts.append(word.group(1).upper())
    size = _QUALITY_TAG.search(text)
    if size:
        parts.append(size.group(1).lower())
    return ' '.join(parts)


def _quality_rank(entry):
    """Copie migliori per prime, ma il flusso principale le precede.

    La copia senza sigla (spesso 'Rai 1' accanto a 'Rai 1 HD') e' quasi
    sempre quella scelta dall'elenco come principale: in fondo alla lista
    sembrava l'ultima arrivata.
    """
    label = (entry.get('variant') or '').lower()
    if not label:
        return 6
    for score, words in ((5, ('2160', '4k', 'uhd')), (4, ('1080', 'fhd')),
                         (3, ('720',)), (2, ('hd',)), (1, ('sd',))):
        if any(word in label for word in words):
            return score
    return 0


def group_channels(entries):
    """Una voce sola per canale, con i flussi dentro 'variants'.

    'Rai 1 (1080p)' e 'Rai 1 HD (720p)' diventano un canale solo: il
    sottomenu mostra le copie, invece di due doppioni in elenco.
    """
    order = []
    merged = {}
    for entry in entries or ():
        item = dict(entry)
        key = (channel_key(plain_name(item.get('name'))) or
               channel_key(item.get('name')) or 'url:' + (item.get('url') or ''))
        item['key'] = key
        item['variant'] = variant_label(item.get('name'))
        base = merged.get(key)
        if base is None:
            item['variants'] = [item]
            merged[key] = item
            order.append(key)
            continue
        base['variants'].append(item)
        # La guida puo' esserci su una copia sola: vale per tutto il canale.
        for field in ('epg', 'epg_next', 'plot', 'epg_ok'):
            if item.get(field) and not base.get(field):
                base[field] = item[field]
    channels = [merged[key] for key in order]
    for channel in channels:
        channel['variants'].sort(key=_quality_rank, reverse=True)
    return channels


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
    """Copia delle voci con 'epg' (in onda), 'epg_next' (il dopo) e 'plot'.

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
            if following:
                item['epg_next'] = '%s %s' % (clock(following[0]),
                                              following[2][:40])
            if current:
                item['epg'] = '%s %s' % (clock(current[0]), current[2][:40])
                plot = 'In onda: %s (%s-%s)' % (current[2], clock(current[0]),
                                                clock(current[1]))
                if following:
                    plot += '\nDopo: %s (%s)' % (following[2],
                                                 clock(following[0]))
                item['plot'] = plot
            elif following:
                item['plot'] = 'Dopo: %s (%s)' % (following[2],
                                                  clock(following[0]))
        decorated.append(item)
    return decorated
