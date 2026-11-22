# -*- coding: utf-8 -*-
"""La mia lista: le voci scelte dall'utente, in cima al menu principale.

Un preferito non e' un link ma una voce intera: titolo, link, proprieta' della
voce e copertina. Cosi' si riapre uguale anche se la lista da cui viene cambia
indirizzo o sparisce, e nella pagina si vede il logo invece dell'icona
generica. Vive in favorites.json nella cartella dati dell'addon.
"""

import time

from resources.lib import playlist_store, progress

FILE = 'favorites.json'
MAX_ITEMS = 200

_CACHE = [None]


def reset():
    _CACHE[0] = None


def load():
    """Le voci scelte, dalla piu' recente."""
    if _CACHE[0] is None:
        stored = playlist_store.read_data(FILE)
        rows = stored.get('items') if isinstance(stored, dict) else None
        if not isinstance(rows, list):
            rows = []
        _CACHE[0] = [row for row in rows
                     if isinstance(row, dict) and row.get('key') and row.get('url')]
    return list(_CACHE[0])


def _save(rows):
    rows = list(rows)[:MAX_ITEMS]
    playlist_store.write_data(FILE, {'items': rows})
    _CACHE[0] = rows


def clean_art(art):
    """Solo le immagini che servono: copertina e sfondo."""
    art = art if isinstance(art, dict) else {}
    return {name: art[name] for name in ('thumb', 'fanart') if art.get(name)}


def find(title):
    """La voce scelta con quel titolo, oppure None."""
    name = progress.key(title)
    if not name:
        return None
    for row in load():
        if row.get('key') == name:
            return row
    return None


def has(title):
    return find(title) is not None


def count():
    return len(load())


def add(title, url='', extra='', art=None, plot='', kind='video', alt='',
        heavy=False):
    """Aggiunge (o rinnova) una voce scelta; lo stesso titolo resta uno solo.

    alt sono le altre copie dello stesso canale: restano appese alla voce
    cosi' il ripiego automatico funziona anche partendo da La mia lista.
    heavy segna le puntate che esistono solo in versione pesante, cosi' la
    domanda sulla cache arriva anche da qui.
    """
    name = progress.key(title)
    if not name or not url:
        return None
    rows = [row for row in load() if row.get('key') != name]
    row = {
        'key': name,
        'title': (title or '').strip(),
        'url': url,
        'extra': extra or '',
        'alt': alt or '',
        'heavy': bool(heavy),
        'art': clean_art(art),
        'plot': plot or '',
        'kind': kind,
        'added': int(time.time()),
    }
    rows.insert(0, row)
    _save(rows)
    return row


def remove(title):
    """Toglie la voce scelta. True se c'era."""
    name = progress.key(title)
    rows = load()
    rest = [row for row in rows if row.get('key') != name]
    if len(rest) == len(rows):
        return False
    _save(rest)
    return True
