# -*- coding: utf-8 -*-
"""Canali e gruppi nascosti: per non scorrere 348 voci ogni volta.

Si nasconde per titolo (lo stesso titolo che usano posizione e La mia lista) e
per nome di gruppo. La lista non viene toccata: e' solo la visualizzazione a
saltare le voci, e si possono rimettere con la pagina dei nascosti.
Vive in hidden.json nella cartella dati:

    {"channels": {"<chiave>": {"title", "updated"}},
     "groups": {"<chiave>": {"title", "updated"}}}
"""

import time

from resources.lib import playlist_store, progress

FILE = 'hidden.json'
KINDS = ('channels', 'groups')

_CACHE = [None]


def reset():
    _CACHE[0] = None


def _data():
    if _CACHE[0] is None:
        stored = playlist_store.read_data(FILE)
        _CACHE[0] = {}
        for kind in KINDS:
            rows = stored.get(kind)
            _CACHE[0][kind] = rows if isinstance(rows, dict) else {}
    return _CACHE[0]


def _save(data):
    playlist_store.write_data(FILE, data)
    _CACHE[0] = data


def key(title):
    """Stessa chiave del titolo usata altrove: maiuscole e spazi non contano."""
    return progress.key(title)


def has(title, kind='channels'):
    name = key(title)
    return bool(name) and name in _data()[kind]


def has_channel(title):
    return has(title, 'channels')


def has_group(name):
    return has(name, 'groups')


def hide(title, kind='channels'):
    name = key(title)
    if not name:
        return False
    data = _data()
    data[kind][name] = {'title': (title or '').strip(),
                        'updated': int(time.time())}
    _save(data)
    return True


def hide_channel(title):
    return hide(title, 'channels')


def hide_group(name):
    return hide(name, 'groups')


def show(name, kind='channels'):
    """Rimette visibile una voce. True se c'era."""
    data = _data()
    if (name or '') not in data[kind]:
        return False
    del data[kind][name]
    _save(data)
    return True


def rows(kind='channels'):
    items = [dict(row, key=name) for name, row in _data()[kind].items()
             if isinstance(row, dict)]
    items.sort(key=lambda row: -int(row.get('updated') or 0))
    return items


def channels():
    return rows('channels')


def groups():
    return rows('groups')


def count():
    data = _data()
    return len(data['channels']) + len(data['groups'])


def clear():
    _save({'channels': {}, 'groups': {}})
