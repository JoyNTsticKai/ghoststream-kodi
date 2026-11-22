# -*- coding: utf-8 -*-
"""Vista delle cartelle (lista, icone, wall...) ricordata tra un avvio e l'altro.

Kodi salva la vista scelta per ogni cartella nella sua ViewModes#.db, ma quella
riga puo' sparire (per esempio quando l'addon viene aggiornato) e la cartella
riparte dalla lista. Qui la vista letta da Kodi viene copiata nella cartella
dati dell'addon e riapplicata quando la stessa cartella si riapre, con la pausa
che serve: senza, Kodi applica la vista alla cartella precedente (bug noto di
Container.SetViewMode).

Conta sempre per prima la vista che Kodi ha adesso: se ne scegli un'altra, la
copia locale si allinea a quella. La copia serve solo come rete di sicurezza
quando la riga di Kodi non c'e' piu'.
"""

import glob
import os

import xbmc
import xbmcvfs

from resources.lib import playlist_store

STORE_FILE = 'views.json'
DB_TIMEOUT = 0.5
APPLY_DELAY = 100


def database():
    """Il ViewModes#.db piu' recente, o '' se non c'e'."""
    try:
        folder = xbmcvfs.translatePath('special://database')
    except Exception:
        return ''
    found = sorted(glob.glob(os.path.join(folder, 'ViewModes*.db')))
    return found[-1] if found else ''


def stored_view(path, skin=''):
    """Id della vista che Kodi ha salvato per questa cartella (0 se manca).

    sqlite3 si importa solo qui: costa tempo a ogni apertura di menu e serve
    soltanto la prima volta che una cartella si vede.
    """
    import sqlite3

    db = database()
    if not db or not path:
        return 0
    queries = []
    if skin:
        queries.append(('select viewMode from view where path=? and skin=? '
                        'order by idView desc limit 1', (path, skin)))
    queries.append(('select viewMode from view where path=? '
                    'order by idView desc limit 1', (path,)))
    try:
        connection = sqlite3.connect(db, timeout=DB_TIMEOUT)
    except sqlite3.Error:
        return 0
    try:
        for sql, params in queries:
            for row in connection.execute(sql, params):
                try:
                    return int(row[0])
                except (TypeError, ValueError):
                    return 0
    except sqlite3.Error:
        return 0
    finally:
        connection.close()
    return 0


def remember(path, view):
    """Copia la vista nella cartella dati, dove nessun aggiornamento la tocca."""
    try:
        data = playlist_store.read_data(STORE_FILE)
        data[path] = int(view)
        playlist_store.write_data(STORE_FILE, data)
    except (playlist_store.StoreError, TypeError, ValueError):
        return False
    return True


def apply(target):
    """Riapplica la vista scelta per la cartella appena riempita.

    Restituisce l'id applicato, o 0 se questa cartella non ha una vista sua.
    """
    try:
        saved = int(playlist_store.read_data(STORE_FILE).get(target) or 0)
    except (TypeError, ValueError):
        saved = 0
    try:
        skin = xbmc.getSkinDir()
    except Exception:
        skin = ''
    # Quella di Kodi e' la scelta piu' recente (l'utente puo' aver cambiato
    # vista): la copia locale vale solo se Kodi non ha piu' la riga.
    view = stored_view(target, skin)
    if not view:
        view = saved
    elif view != saved:
        remember(target, view)
    if not view:
        return 0
    try:
        xbmc.sleep(APPLY_DELAY)
        xbmc.executebuiltin('Container.SetViewMode(%d)' % view)
    except Exception:
        return 0
    return view
