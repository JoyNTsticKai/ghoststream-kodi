# -*- coding: utf-8 -*-
"""Posizioni di visione: 'Continua a guardare' e segno di visto.

La posizione si salva per titolo e non per link: lo stesso episodio resta uno
solo anche se il flusso cambia indirizzo, e le copie SD/HD dello stesso video
condividono il segno. Vive in progress.json nella cartella dati dell'addon:

    {"items": {"<chiave>": {"title", "url", "extra", "position", "total",
                            "finished", "updated"}},
     "now": {"title", "url", "extra", "start", "since"}}

Chi salva la posizione e' il servizio in sottofondo (service.py): qui sta solo
la logica, senza Kodi, cosi' si puo' provare senza aprire il programma.
"""

import hashlib
import time

from resources.lib import playlist_store

FILE = 'progress.json'
MAX_ITEMS = 80
KEEP_SECONDS = 60 * 60 * 24 * 60   # due mesi: oltre, la voce non serve piu'
MIN_TOTAL = 60        # sotto il minuto non e' un video: e' una diretta
MIN_POSITION = 30     # pochi secondi non meritano una riga 'Riprendi'
SAVE_EVERY = 15       # secondi di video tra un salvataggio e il successivo
FINISHED_RATIO = 0.9  # oltre il 90% il video e' visto
END_GAP = 90          # o quando mancano meno di 90 secondi alla fine

_CACHE = [None]


def key(title):
    """Chiave stabile del titolo: maiuscole e spazi non contano."""
    text = ' '.join((title or '').lower().split())
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12] if text else ''


def reset():
    """Dopo una scrittura di un altro processo la copia in memoria non vale piu'."""
    _CACHE[0] = None


def _data():
    if _CACHE[0] is None:
        stored = playlist_store.read_data(FILE)
        items = stored.get('items')
        _CACHE[0] = {
            'items': items if isinstance(items, dict) else {},
            'now': stored.get('now') if isinstance(stored.get('now'), dict) else {},
        }
    return _CACHE[0]


def _prune(items):
    """Tiene le voci piu' recenti e scarta quelle troppo vecchie."""
    now = int(time.time())
    rows = [(name, item) for name, item in items.items()
            if isinstance(item, dict)]
    rows.sort(key=lambda pair: -int(pair[1].get('updated') or 0))
    kept = {}
    for name, item in rows[:MAX_ITEMS]:
        if now - int(item.get('updated') or 0) > KEEP_SECONDS:
            continue
        kept[name] = item
    return kept


def _save(data):
    data['items'] = _prune(data.get('items') or {})
    playlist_store.write_data(FILE, data)
    _CACHE[0] = data


def get(name):
    """Voce salvata per chiave, oppure None."""
    item = _data()['items'].get(name or '')
    return dict(item, key=name) if isinstance(item, dict) else None


def find(title):
    """Voce salvata per titolo, oppure None."""
    name = key(title)
    return get(name) if name else None


def resume(title):
    """Secondi da cui ripartire: 0 se non c'e' niente da riprendere."""
    item = find(title)
    if not item or item.get('finished'):
        return 0
    position = float(item.get('position') or 0)
    return int(position) if position >= MIN_POSITION else 0


def watched(title):
    item = find(title)
    return bool(item and item.get('finished'))


def _clean_art(art):
    """Copertina e sfondo della voce: bastano per la riga di Continua."""
    art = art if isinstance(art, dict) else {}
    return {name: art[name] for name in ('thumb', 'fanart') if art.get(name)}


def store(title, url='', extra='', position=0, total=0, art=None):
    """Salva la posizione raggiunta; ignora le dirette (durata sconosciuta)."""
    name = key(title)
    if not name or not total or float(total) < MIN_TOTAL:
        return None
    reset()
    data = _data()
    total = float(total)
    position = max(0.0, min(float(position or 0), total))
    finished = (position >= total * FINISHED_RATIO) or (total - position <= END_GAP)
    item = dict(data['items'].get(name) or {})
    item.update({
        'title': (title or '').strip() or item.get('title', ''),
        'url': url or item.get('url', ''),
        'extra': extra or item.get('extra', ''),
        'art': _clean_art(art) or item.get('art') or {},
        'position': round(position, 1),
        'total': round(total, 1),
        'finished': bool(finished),
        'updated': int(time.time()),
    })
    data['items'][name] = item
    _save(data)
    return dict(item, key=name)


def set_watched(name, seen=True, title='', url='', extra=''):
    """Segna come visto (o non visto) senza riprodurre niente."""
    name = name or key(title)
    if not name:
        return False
    reset()
    data = _data()
    item = dict(data['items'].get(name) or {})
    if not item and not title:
        return False
    if title:
        item.setdefault('title', title.strip())
    if url:
        item['url'] = url
    if extra:
        item['extra'] = extra
    if seen:
        item.setdefault('position', 0)
        item.setdefault('total', 0)
    else:
        # Non visto: riparte dall'inizio, non dalla fine.
        item['position'] = 0
    item['finished'] = bool(seen)
    item['updated'] = int(time.time())
    data['items'][name] = item
    _save(data)
    return True


def forget(name):
    reset()
    data = _data()
    if (name or '') not in data['items']:
        return False
    del data['items'][name]
    _save(data)
    return True


def continued(limit=20):
    """Voci da riprendere, dalla piu' recente."""
    rows = []
    for name, item in _data()['items'].items():
        if not isinstance(item, dict) or item.get('finished'):
            continue
        if float(item.get('position') or 0) < MIN_POSITION:
            continue
        if not item.get('url'):
            continue
        rows.append(dict(item, key=name))
    rows.sort(key=lambda entry: -int(entry.get('updated') or 0))
    return rows[:limit]


def time_text(seconds):
    seconds = int(max(0, float(seconds or 0)))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return '%d:%02d:%02d' % (hours, minutes, secs)
    return '%d:%02d' % (minutes, secs)


# --------------------------------------------------------------------------
# Riproduzione in corso: la segue il servizio, non la pagina dell'addon
# --------------------------------------------------------------------------
def begin(title, url='', extra='', start=0, art=None):
    """Segna cosa sta partendo, cosi' il servizio sa cosa seguire."""
    if not title:
        return False
    reset()
    data = _data()
    data['now'] = {'title': title.strip(), 'url': url or '',
                   'extra': extra or '', 'start': int(start or 0),
                   'art': _clean_art(art), 'since': int(time.time())}
    try:
        _save(data)
    except playlist_store.StoreError:
        return False
    return True


def now():
    return dict(_data().get('now') or {})


def end_now():
    """Toglie il segno di 'in riproduzione'."""
    reset()
    data = _data()
    if data.get('now'):
        data['now'] = {}
        try:
            _save(data)
        except playlist_store.StoreError:
            pass


def track_step(player):
    """Un giro del servizio: salva la posizione del video in corso.

    Restituisce 'play' quando sta salvando, 'stop' quando la riproduzione e'
    finita (il segno viene tolto), '' se non c'e' niente da seguire.
    """
    reset()
    marker = _data().get('now') or {}
    title = marker.get('title') or ''
    if not title or player is None:
        return ''
    try:
        playing = bool(player.isPlaying())
    except Exception:
        playing = False

    if not playing:
        return 'stop' if _close(player, title, marker) else ''

    try:
        position = float(player.getTime() or 0)
        total = float(player.getTotalTime() or 0)
    except Exception:
        return ''

    start = int(marker.get('start') or 0)
    if start and not marker.get('seeked') and position + 20 < start:
        # Kodi non ha rispettato StartOffset: si sposta qui, una volta sola.
        try:
            player.seekTime(start)
            marker['seeked'] = True
            data = _data()
            data['now'] = marker
            _save(data)
        except Exception:
            pass

    if total < MIN_TOTAL or position <= 0:
        # Diretta o durata sconosciuta: niente 'Continua' per i canali.
        return 'play'
    saved = float((_data()['items'].get(key(title)) or {}).get('position') or 0)
    finished = position >= total * FINISHED_RATIO
    if position - saved < SAVE_EVERY and not (finished and saved < position):
        return 'play'
    store(title, marker.get('url', ''), marker.get('extra', ''), position, total,
          marker.get('art'))
    return 'play'


def _close(player, title, marker):
    """Riproduzione fermata: salva l'ultima posizione buona e chiude."""
    position = total = 0.0
    try:
        position = float(player.getTime() or 0)
        total = float(player.getTotalTime() or 0)
    except Exception:
        position = total = 0.0
    if total < MIN_TOTAL or position <= 0:
        # A video fermo il player risponde 0: vale l'ultima posizione salvata.
        item = _data()['items'].get(key(title)) or {}
        position = float(item.get('position') or 0)
        total = float(item.get('total') or 0)
    if total >= MIN_TOTAL and position > 0:
        store(title, marker.get('url', ''), marker.get('extra', ''),
              position, total, marker.get('art'))
    end_now()
    return True
