# -*- coding: utf-8 -*-
"""Liste M3U salvate: indice JSON e copia locale delle voci.

Nella cartella dati dell'addon (ADDON.getAddonInfo('profile')) stanno:

    lists.json      indice delle sorgenti (id, nome, link, tipo, logo, data)
    <id>.json       voci lette l'ultima volta (nome, url, logo, gruppo)

La copia locale permette di aprire una lista salvata anche a rete spenta, e
tiene il menu principale veloce: non serve rileggere il link a ogni avvio.
"""

import hashlib
import json
import os
import time

INDEX_FILE = 'lists.json'
MAX_LISTS = 20

_ROOT = ['']


class StoreError(Exception):
    """Cartella dati, indice o copia locale non leggibili."""


def set_root(path):
    """Cartella dati dell'addon (in Kodi: special://profile/addon_data/<id>)."""
    _ROOT[0] = path or ''


def _folder():
    folder = _ROOT[0]
    if not folder:
        raise StoreError('cartella dati non impostata')
    if not os.path.isdir(folder):
        try:
            os.makedirs(folder)
        except OSError as exc:
            raise StoreError('cartella dati non creata: %s' % exc)
    return folder


def _path(name):
    return os.path.join(_folder(), name)


def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    """Scrive su un file di appoggio e poi lo sposta al suo posto.

    Cosi' chi legge (l'addon) non trova mai un file scritto a meta' mentre il
    servizio in sottofondo sta aggiornando la stessa cache.
    """
    temporary = path + '.tmp'
    try:
        with open(temporary, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise StoreError('scrittura fallita: %s' % exc)


def make_id(target):
    """Identificativo stabile: lo stesso link resta una sola sorgente."""
    return hashlib.sha1((target or '').encode('utf-8')).hexdigest()[:12]


def load():
    """Indice delle liste salvate, nell'ordine in cui vanno mostrate."""
    try:
        path = _path(INDEX_FILE)
    except StoreError:
        return []
    items = _read_json(path, [])
    if not isinstance(items, list):
        return []
    return [item for item in items
            if isinstance(item, dict) and item.get('id') and item.get('url')]


def save(items):
    _write_json(_path(INDEX_FILE), list(items)[:MAX_LISTS])


def find(list_id):
    for item in load():
        if item.get('id') == list_id:
            return item
    return None


def entries(list_id):
    """Voci salvate dell'ultima lettura (vuote se manca la copia locale)."""
    try:
        path = _path('%s.json' % list_id)
    except StoreError:
        return []
    data = _read_json(path, [])
    if not isinstance(data, list):
        return []
    return [entry for entry in data
            if isinstance(entry, dict) and entry.get('url')]


def save_entries(list_id, entries, logo=None):
    """Aggiorna la copia locale e, se indicato, la copertina nell'indice."""
    _write_json(_path('%s.json' % list_id), list(entries or []))
    if logo is not None:
        items = load()
        for item in items:
            if item['id'] == list_id:
                item['logo'] = logo
                item['updated'] = int(time.time())
        save(items)


def add(name, target, kind='list', logo='', entries=None, props=None,
        headers=None):
    """Aggiunge o sostituisce una sorgente (stesso link = stessa voce)."""
    list_id = make_id(target)
    items = [item for item in load() if item.get('id') != list_id]
    item = {
        'id': list_id,
        'name': (name or '').strip() or target,
        'url': target,
        'kind': 'stream' if kind == 'stream' else 'list',
        'logo': logo or '',
        'updated': int(time.time()),
    }
    # Direttive della lista (#KODIPROP, header) valgono anche da menu.
    if props:
        item['props'] = dict(props)
    if headers:
        item['headers'] = dict(headers)
    items.insert(0, item)
    save(items)
    if kind != 'stream':
        save_entries(list_id, entries)
    return find(list_id)


def remove(list_id):
    """Toglie la sorgente e la sua copia locale. True se c'era."""
    items = load()
    remaining = [item for item in items if item.get('id') != list_id]
    save(remaining)
    try:
        os.remove(_path('%s.json' % list_id))
    except OSError:
        pass
    return len(remaining) != len(items)


def read_data(name):
    """Dati accessori (cache TV, guida) tenuti nella cartella dati."""
    try:
        path = _path(name)
    except StoreError:
        return {}
    data = _read_json(path, {})
    return data if isinstance(data, dict) else {}


def write_data(name, data):
    _write_json(_path(name), dict(data or {}))


ORDER_FILE = 'order.json'
DEFAULT_ORDER = 'az'


def load_order():
    """Ordine scelto per le liste, ricordato nella cartella dati (non nei setting)."""
    try:
        path = _path(ORDER_FILE)
    except StoreError:
        return DEFAULT_ORDER
    data = _read_json(path, {})
    if not isinstance(data, dict):
        return DEFAULT_ORDER
    return str(data.get('order') or DEFAULT_ORDER)


def save_order(order):
    _write_json(_path(ORDER_FILE), {'order': order or DEFAULT_ORDER})


SESSION_FILE = 'session.json'


def save_session(target, entries=None, autoplay=False):
    """Lista appena incollata: serve alla pagina che la mostra."""
    _write_json(_path(SESSION_FILE), {
        'url': target or '',
        'entries': list(entries or []),
        'autoplay': bool(autoplay),
    })


def load_session():
    try:
        path = _path(SESSION_FILE)
    except StoreError:
        return {}
    data = _read_json(path, {})
    if not isinstance(data, dict) or not data.get('url'):
        return {}
    return data
