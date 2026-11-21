# -*- coding: utf-8 -*-
"""Sorgente A: canali YouTube ufficiali.

Qui non si risolve nessuno stream: si costruiscono solo URL del tipo
    plugin://plugin.video.youtube/channel/<ID>/
    plugin://plugin.video.youtube/playlist/<ID>/
    plugin://plugin.video.youtube/play/?video_id=<ID>
e la riproduzione la gestisce l'addon YouTube gia' installato in Kodi.
"""

import re
import urllib.parse
import urllib.request

YOUTUBE_ADDON = 'plugin.video.youtube'

# Canali ufficiali verificati (ID canale pubblico).
# Per aggiungerne altri senza toccare il codice: impostazioni -> yt_extra.
CURATED = (
    ('Rai Ragazzi - canale ufficiale', 'channel', 'UCD52LxgN5JlFr59Nvx2NSnw'),
    ('I tuoi abbonamenti YouTube', 'subscriptions', ''),
)

_CHANNEL_RE = re.compile(r'^UC[\w-]{10,}$')
_PLAYLIST_RE = re.compile(r'^(?:PL|UU|OL|FL)[\w-]{10,}$')
_VIDEO_RE = re.compile(r'^[\w-]{11}$')


def _base(path):
    return 'plugin://%s/%s' % (YOUTUBE_ADDON, path.lstrip('/'))


def channel_url(channel_id):
    return _base('channel/%s/' % channel_id)


def playlist_url(playlist_id):
    return _base('playlist/%s/' % playlist_id)


def video_url(video_id):
    return _base('play/?video_id=%s' % video_id)


def subscriptions_url():
    return _base('subscriptions/')


def available():
    """True se l'addon plugin.video.youtube e' installato."""
    import xbmcaddon

    try:
        xbmcaddon.Addon(YOUTUBE_ADDON)
        return True
    except Exception:
        return False


def _resolve_handle(handle):
    """Converte @nomecanale nell'ID canale UC... leggendo la pagina pubblica."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept-Language': 'it-IT,it;q=0.9',
    }
    for suffix in ('', '/about'):
        url = 'https://www.youtube.com/@%s%s' % (urllib.parse.quote(handle), suffix)
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=15) as response:
                html = response.read().decode('utf-8', 'replace')
        except Exception:
            continue
        match = (re.search(r'"externalId":"(UC[\w-]{10,})"', html)
                 or re.search(r'"channelId":"(UC[\w-]{10,})"', html))
        if match:
            return match.group(1)
    return None


def parse_entry(raw):
    """Accetta ID o link YouTube e restituisce (etichetta, url plugin) o None."""
    text = (raw or '').strip()
    if not text:
        return None

    if _CHANNEL_RE.match(text):
        return ('Canale %s' % text, channel_url(text))
    if _PLAYLIST_RE.match(text):
        return ('Playlist %s' % text, playlist_url(text))
    if _VIDEO_RE.match(text):
        return ('Video %s' % text, video_url(text))

    if 'list=' in text:
        playlist_id = urllib.parse.parse_qs(
            urllib.parse.urlparse(text).query).get('list', [''])[0]
        if _PLAYLIST_RE.match(playlist_id):
            return ('Playlist %s' % playlist_id, playlist_url(playlist_id))

    if '/channel/' in text:
        channel_id = text.split('/channel/')[-1].split('/')[0].split('?')[0]
        if _CHANNEL_RE.match(channel_id):
            return ('Canale %s' % channel_id, channel_url(channel_id))

    if '/@' in text:
        handle = text.split('/@')[-1].split('/')[0].split('?')[0]
        channel_id = _resolve_handle(handle)
        if channel_id:
            return ('@%s' % handle, channel_url(channel_id))

    if 'youtu.be/' in text or 'v=' in text:
        video_id = ''
        if 'youtu.be/' in text:
            video_id = text.split('youtu.be/')[-1].split('/')[0].split('?')[0]
        else:
            video_id = urllib.parse.parse_qs(
                urllib.parse.urlparse(text).query).get('v', [''])[0]
        if _VIDEO_RE.match(video_id):
            return ('Video %s' % video_id, video_url(video_id))

    return None


def entries(addon):
    """Elenca (etichetta, url) dei canali curati piu' quelli delle impostazioni."""
    items = []
    for label, kind, value in CURATED:
        if kind == 'subscriptions':
            items.append((label, subscriptions_url()))
        elif kind == 'channel':
            items.append((label, channel_url(value)))
        elif kind == 'playlist':
            items.append((label, playlist_url(value)))

    try:
        raw = addon.getSettingString('yt_extra') or ''
    except Exception:
        raw = addon.getSetting('yt_extra') or ''

    for chunk in re.split(r'[;,\n]+', raw):
        parsed = parse_entry(chunk)
        if parsed:
            items.append(parsed)
    return items
