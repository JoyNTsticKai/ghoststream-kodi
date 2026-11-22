# -*- coding: utf-8 -*-
"""Sorgente D: una lista incollata a mano (link M3U/M3U8, file locale o flusso).

Si accetta quello che l'utente scrive nella tastiera dell'addon: un link a una
lista M3U/M3U8, un percorso di file locale, oppure un link diretto a un video o
flusso (che viene riprodotto cosi' com'e', senza scaricarlo).

Solo testo M3U standard: righe #EXTINF (nome dopo l'ultima virgola, attributi
tvg-name / tvg-logo / group-title) e l'URL che segue.
"""

import os
import re
import unicodedata
import urllib.parse
import urllib.request

USER_AGENT = 'plugin.video.ghoststream/1.9.3 (Kodi addon)'

PLAYLIST_EXTENSIONS = ('.m3u', '.m3u8')
# Con l'estensione di un video non si legge nulla: si riproduce e basta.
DIRECT_EXTENSIONS = ('.mp4', '.m4v', '.mkv', '.webm', '.avi', '.mov', '.mpg',
                     '.mpeg', '.ts', '.m2ts', '.mpd')

PLAYLIST_LIMIT = 8 * 1024 * 1024   # una lista lunga sta abbondantemente qui
SNIFF_LIMIT = 256 * 1024           # per i link senza estensione

_ATTRS = re.compile(r'([\w-]+)="([^"]*)"')
_SCHEME = re.compile(r'^[a-zA-Z][\w+.-]*://')
_WINDOWS_PATH = re.compile(r'^[a-zA-Z]:[\\/]')
_NUMBERS = re.compile(r'(\d+)')
_BRACKETS = re.compile(r'\[[^\]]*\]')

# Valori con cui molte liste dichiarano "nessun gruppo": non meritano una
# parentesi accanto al nome (la lista italiana di iptv-org scrive "Undefined").
_JUNK_GROUPS = frozenset(('undefined', 'undef', 'unknown', 'none', 'null',
                          'n/d', 'n/a', 'na', '-', '--', '?', 'nd'))

# Bollini di stato che finiscono dentro il nome: "Canale 5 [Geo-blocked]".
_NOISE_TAGS = re.compile(
    r'\s*\[(geo[- ]?blocked|not 24/7|not 24-7|offline|deprecated)\]', re.I)


def clean_group(value):
    """Gruppo vuoto quando la lista scrive 'Undefined' o simili."""
    text = (value or '').strip()
    return '' if text.lower() in _JUNK_GROUPS else text


def clean_name(value):
    """Toglie dal nome i bollini di stato tipo '[Geo-blocked]'."""
    return _NOISE_TAGS.sub('', value or '').strip()

# "Il", "La", "The": in un elenco di canali non contano per l'ordine.
_ARTICLES = ('il ', 'lo ', 'la ', 'i ', 'gli ', 'le ', "l'", 'l\u2019',
             'un ', 'uno ', 'una ', 'the ', 'a ', 'an ')

# #EXTVLCOPT utile non ha un equivalente Kodi: diventa un header HTTP.
_EXTVLC_HEADERS = {'http-user-agent': 'User-Agent',
                   'http-referrer': 'Referer'}


class PlaylistError(Exception):
    """Lista non leggibile: rete, file mancante o testo vuoto."""


def _channel_number(value):
    """tvg-chno puo' essere assente o non numerico."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def is_live(link, group):
    """Canale in diretta, oppure film/serie messi in lista (regola di WLTV)."""
    group = (group or '').strip().lower()
    link = (link or '').lower()
    if group.startswith(('film', 'movie', 'serie', 'vod')):
        return group.startswith('live')
    return '/movie/' not in link and '/series/' not in link


def fold(text):
    """Minuscolo senza accenti: 'Citta' e 'Citt\u00e0' restano vicini."""
    text = _BRACKETS.sub(' ', text or '')
    text = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).lower().strip()


def order_key(text):
    """Chiave alfabetica: ignora articoli e tag Kodi, numeri a larghezza fissa."""
    folded = fold(text)
    for article in _ARTICLES:
        if folded.startswith(article):
            folded = folded[len(article):]
            break
    return _NUMBERS.sub(lambda match: match.group(1).zfill(6), folded.strip())


SORT_ORDERS = ('az', 'group', 'number', 'file')


def has_groups(entries):
    return any(clean_group(entry.get('group')) for entry in entries or [])


def groups(entries):
    """[(nome, quanti)] in ordine alfabetico, i canali senza gruppo in fondo."""
    counts = {}
    for entry in entries or []:
        name = clean_group(entry.get('group'))
        counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda pair: (not pair[0], order_key(pair[0])))


def in_group(entries, group):
    """Voci di un gruppo; group=None lascia tutto."""
    if group is None:
        return list(entries or [])
    return [entry for entry in entries or []
            if clean_group(entry.get('group')) == group]


def sort_entries(entries, order='az'):
    """Ordina i canali: alfabetico, per gruppo, per numero o come nel file."""
    items = list(entries or [])
    if order == 'file':
        return items
    if order == 'group':
        return sorted(items, key=lambda entry: (
            fold(clean_group(entry.get('group'))), order_key(entry.get('name'))))
    if order == 'number':
        return sorted(items, key=lambda entry: (
            entry.get('number') or 0, order_key(entry.get('name'))))
    return sorted(items, key=lambda entry: order_key(entry.get('name')))


def normalize(raw):
    """Ripulisce il testo incollato: spazi, virgolette, http:// mancante."""
    text = (raw or '').strip().strip('"\'').strip()
    if not text:
        return ''
    if _SCHEME.match(text) or _WINDOWS_PATH.match(text):
        return text
    if text.startswith(('/', '\\\\')):
        return text
    return 'http://' + text


def is_remote(target):
    return target.lower().startswith(('http://', 'https://'))


def _extension(target):
    return os.path.splitext(urllib.parse.urlparse(target).path.lower())[1]


def _read(target, limit, timeout=25):
    """Legge al massimo `limit` byte, da URL o da file locale."""
    if is_remote(target):
        request = urllib.request.Request(target, headers={'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(limit)
        except Exception as exc:
            raise PlaylistError('richiesta fallita: %s' % exc)

    if not os.path.isfile(target):
        raise PlaylistError('file non trovato: %s' % target)
    try:
        with open(target, 'rb') as handle:
            return handle.read(limit)
    except OSError as exc:
        raise PlaylistError('lettura fallita: %s' % exc)


def decode(data):
    """UTF-8, con ripiego su cp1252 per le liste salvate su Windows."""
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('cp1252', 'replace')


def guess_name(url):
    """Nome di ripiego quando #EXTINF non lo fornisce."""
    parsed = urllib.parse.urlparse(url)
    stem = urllib.parse.unquote(parsed.path.rstrip('/').rsplit('/', 1)[-1])
    return os.path.splitext(stem)[0].replace('_', ' ').strip() or parsed.netloc or url


def _directive(line, props, headers):
    """Legge #KODIPROP / #EXTVLCOPT. True se la riga era una direttiva."""
    upper = line.upper()
    if upper.startswith('#KODIPROP'):
        body = line.split(':', 1)[1] if ':' in line else ''
        key, sep, value = body.partition('=')
        key = key.strip()
        if sep and key:
            if key.lower() == 'inputstreamaddon':
                key = 'inputstream'
            props[key] = value.strip()
        return True
    if upper.startswith('#EXTVLCOPT'):
        body = line.split(':', 1)[1] if ':' in line else ''
        option, sep, value = body.partition('=')
        header = _EXTVLC_HEADERS.get(option.strip().lower())
        if sep and header:
            headers[header] = value.strip()
        return True
    return False


def directives(text):
    """Direttive del testo, per i flussi riprodotti senza elenco."""
    props = {}
    headers = {}
    for raw in (text or '').splitlines():
        line = raw.strip()
        if line.startswith('#'):
            _directive(line, props, headers)
    return props, headers


def parse(text):
    """Estrae le voci della lista: nome mostrato, url, logo e gruppo."""
    entries = []
    name = ''
    logo = ''
    group = ''
    attrs = {}
    props = {}
    headers = {}

    for raw in (text or '').splitlines():
        line = raw.strip()
        if not line:
            continue

        if _directive(line, props, headers):
            continue

        if line.upper().startswith('#EXTINF'):
            body = line.split(':', 1)[1] if ':' in line else ''
            attrs = dict(_ATTRS.findall(body))
            # Il nome mostrato e' la parte dopo l'ultima virgola.
            tail = body.rsplit(',', 1)[-1].strip() if ',' in body else ''
            name = tail or (attrs.get('tvg-name') or '').strip()
            logo = (attrs.get('tvg-logo') or '').strip()
            group = clean_group(attrs.get('group-title'))
            continue

        if line.startswith('#'):
            continue

        entries.append({
            'name': clean_name(name) or guess_name(line),
            'url': line,
            'logo': logo,
            'group': group,
            'tvg_id': (attrs.get('tvg-id') or '').strip(),
            'number': _channel_number(attrs.get('tvg-chno')),
            'live': is_live(line, group),
            'props': dict(props),
            'headers': dict(headers),
        })
        name = ''
        logo = ''
        group = ''
        attrs = {}
        props = {}
        headers = {}

    return entries


def load(raw, timeout=25):
    """Restituisce {'stream': bool, 'entries': list, 'url': str}.

    stream=True  -> il link non e' una lista: va riprodotto cosi' com'e'.
    stream=False -> ci sono le voci da mostrare nel menu.
    """
    target = normalize(raw)
    if not target:
        raise PlaylistError('link vuoto')

    extension = _extension(target)
    if extension in DIRECT_EXTENSIONS:
        return {'stream': True, 'entries': [], 'url': target,
                'props': {}, 'headers': {}}

    limit = PLAYLIST_LIMIT if extension in PLAYLIST_EXTENSIONS else SNIFF_LIMIT
    text = decode(_read(target, limit, timeout=timeout))
    if not text.strip():
        raise PlaylistError('lista vuota')

    upper = text.upper()
    # Playlist HLS (segmenti o varianti): e' un flusso, non un elenco.
    if '#EXT-X-TARGETDURATION' in upper or '#EXT-X-STREAM-INF' in upper:
        props, headers = directives(text)
        return {'stream': True, 'entries': [], 'url': target,
                'props': props, 'headers': headers}

    if '#EXTM3U' not in upper and '#EXTINF' not in upper:
        props, headers = directives(text)
        return {'stream': True, 'entries': [], 'url': target,
                'props': props, 'headers': headers}

    entries = parse(text)
    if not entries:
        # Una lista dichiarata M3U ma senza voci e' un errore, non un flusso:
        # cosi' non viene salvata tra le sorgenti una riga che non funziona.
        raise PlaylistError('nessuna voce nella lista')
    return {'stream': False, 'entries': entries, 'url': target,
            'props': {}, 'headers': {}}
