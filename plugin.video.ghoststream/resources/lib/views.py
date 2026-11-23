# -*- coding: utf-8 -*-
"""Vista delle cartelle (lista, icone, wall...) ricordata tra un avvio e l'altro.

Kodi salva la vista scelta per ogni cartella nella sua ViewModes#.db, ma quella
riga puo' sparire (per esempio quando l'addon viene aggiornato) e la cartella
riparte dalla lista. Qui la vista letta da Kodi viene copiata nella cartella
dati dell'addon e riapplicata quando la stessa cartella si riapre.

Due trappole, trovate sul campo:

* Kodi salva la vista con un flag nei bit alti (66036 e' la vista 500 con il
  flag): Container.SetViewMode vuole il solo id, altrimenti lo ignora e la
  cartella resta in elenco. Da qui clean().
* Da uno script di plugin il container non e' ancora costruito: il builtin
  finisce nel vuoto o sulla cartella precedente. Da qui la richiesta che il
  servizio riapplica appena la cartella aperta e' quella giusta.

Conta sempre per prima la vista che Kodi ha adesso: se ne scegli un'altra, la
copia locale si allinea a quella. Le impostazioni dell'addon (elenco o griglia
di copertine) danno solo la vista di partenza di una cartella che non ne ha
ancora una sua: appena scegli una vista a mano, vale quella.
"""

import glob
import os
import re
import time

import xbmc
import xbmcvfs

from resources.lib import playlist_store

STORE_FILE = 'views.json'
PENDING_FILE = 'view_pending.json'
DB_TIMEOUT = 0.5
APPLY_DELAY = 100
# Una richiesta vecchia non deve riaprire una cartella a caso.
PENDING_TTL = 30

# Kodi tiene la vista nei primi 16 bit e i suoi flag sopra.
VIEW_MASK = 0xFFFF

# Id delle viste come li numera Estuary (Confluence e le altre skin usano
# numeri loro, ma si leggono dal file della skin): 52 e' la griglia di icone,
# 500 il muro di poster, 54, 51 e 53 le altre griglie; 50 e' l'elenco.
COVER_VIEWS = (52, 500, 54, 51, 53)
LIST_VIEW = 50

# Dove le skin tengono i loro xml: Estuary in xml/, Confluence in 1080p/.
NAV_FILE = 'MyVideoNav.xml'
SKIN_FOLDERS = ('xml', '1080p', '720p', '16x9', 'resources')
WARN_KEY = '_unsupported'
UNSUPPORTED_MESSAGE = ('Questa skin non dichiara una vista a icone: scegli tu '
                       "la vista che preferisci, l'addon la ricordera'.")


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

    Torna il valore grezzo del database: i flag di Kodi si tolgono con clean().
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


def clean(view):
    """Id della vista senza i flag di Kodi (0 se non e' un numero)."""
    try:
        return int(view) & VIEW_MASK
    except (TypeError, ValueError):
        return 0


def remember(path, view):
    """Copia la vista nella cartella dati, dove nessun aggiornamento la tocca."""
    try:
        data = playlist_store.read_data(STORE_FILE)
        data[path] = clean(view)
        playlist_store.write_data(STORE_FILE, data)
    except (playlist_store.StoreError, TypeError, ValueError):
        return False
    return True


def skin_views(skin=''):
    """Id delle viste che la skin dichiara per le cartelle video.

    Ogni skin scrive l'elenco nella finestra dei video, <views>50,51,52...</>:
    cosi' si sa quali id esistono davvero, invece di fidarsi di un numero
    pensato per Estuary. La cartella cambia da skin a skin (xml/, 1080p/...).
    """
    if not skin:
        try:
            skin = xbmc.getSkinDir() or ''
        except Exception:
            return set()
    try:
        root = xbmcvfs.translatePath('special://home/addons/%s' % skin)
    except Exception:
        return set()
    for name in SKIN_FOLDERS:
        path = os.path.join(root, name, NAV_FILE)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                text = handle.read()
        except OSError:
            continue
        found = re.search(r'<views>\s*([0-9,\s]+)\s*</views>', text)
        if not found:
            continue
        return set(int(part) for part in re.findall(r'\d+', found.group(1)))
    return set()


def default_view(prefer, skin=''):
    """Vista di partenza di una cartella senza scelta salvata (0 = niente).

    'covers' cerca la prima griglia che la skin dichiara, 'list' l'elenco. Se
    la skin non si legge si prova comunque l'id di Estuary: al massimo Kodi lo
    ignora e resta la vista che c'e' gia'.
    """
    if prefer not in ('covers', 'list'):
        return 0
    known = skin_views(skin)
    if prefer == 'list':
        if not known or LIST_VIEW in known:
            return LIST_VIEW
        return 0
    if not known:
        return COVER_VIEWS[0]
    for candidate in COVER_VIEWS:
        if candidate in known:
            return candidate
    return 0


def warn_unsupported(skin=''):
    """Avvisa una volta per skin che le icone non si possono applicare."""
    try:
        data = playlist_store.read_data(STORE_FILE)
    except playlist_store.StoreError:
        data = {}
    if data.get(WARN_KEY) == (skin or ''):
        return False
    data[WARN_KEY] = skin or ''
    try:
        playlist_store.write_data(STORE_FILE, data)
    except playlist_store.StoreError:
        pass
    try:
        xbmc.log('[views] skin senza vista a icone riconosciuta: %s' % skin,
                 xbmc.LOGINFO)
    except Exception:
        pass
    try:
        import xbmcgui
        xbmcgui.Dialog().notification('Ghost-Stream', UNSUPPORTED_MESSAGE,
                                      xbmcgui.NOTIFICATION_INFO, 8000)
    except Exception:
        pass
    return True


def resolved(target, prefer=''):
    """Id da applicare alla cartella: la scelta salvata o quella di partenza."""
    try:
        saved = clean(playlist_store.read_data(STORE_FILE).get(target))
    except playlist_store.StoreError:
        saved = 0
    try:
        skin = xbmc.getSkinDir()
    except Exception:
        skin = ''
    # Quella di Kodi e' la scelta piu' recente (l'utente puo' aver cambiato
    # vista): la copia locale vale solo se Kodi non ha piu' la riga.
    view = clean(stored_view(target, skin))
    if not view:
        view = saved
    elif view != saved:
        remember(target, view)
    if view:
        return view
    view = default_view(prefer, skin)
    if not view and prefer:
        warn_unsupported(skin)
    return view


def same_path(atteso, attuale):
    """Le due cartelle sono la stessa? Kodi a volte toglie la barra finale."""
    atteso = (atteso or '').rstrip('/')
    attuale = (attuale or '').rstrip('/')
    return bool(atteso) and atteso == attuale


def request(target, view):
    """Lascia al servizio la vista da applicare appena la cartella e' pronta."""
    if not view or not target:
        return False
    try:
        playlist_store.write_data(PENDING_FILE, {'path': target,
                                                 'view': int(view),
                                                 'when': int(time.time())})
    except playlist_store.StoreError:
        return False
    return True


def pending():
    """Richiesta di vista ancora valida ({} se non c'e' o e' scaduta)."""
    try:
        data = playlist_store.read_data(PENDING_FILE)
    except playlist_store.StoreError:
        return {}
    view = clean(data.get('view'))
    path = data.get('path') or ''
    if not view or not path:
        return {}
    try:
        if time.time() - int(data.get('when') or 0) > PENDING_TTL:
            return {}
    except (TypeError, ValueError):
        return {}
    return {'path': path, 'view': view}


def apply_pending(current_path):
    """Applica la vista richiesta se la cartella aperta e' proprio quella.

    La chiama il servizio: qui la cartella e' gia' disegnata, quindi il
    builtin arriva al container giusto.
    """
    data = pending()
    if not data or not same_path(data['path'], current_path):
        return 0
    try:
        xbmc.executebuiltin('Container.SetViewMode(%d)' % data['view'])
    except Exception:
        return 0
    try:
        playlist_store.write_data(PENDING_FILE, {})
    except playlist_store.StoreError:
        pass
    return data['view']


def apply(target, prefer=''):
    """Applica la vista della cartella appena riempita.

    Vale sempre la scelta fatta a mano; prefer ('' / 'covers' / 'list') decide
    solo da quale vista parte una cartella che non ne ha ancora una. Restituisce
    l'id applicato, o 0.
    """
    view = resolved(target, prefer)
    if not view:
        return 0
    try:
        xbmc.sleep(APPLY_DELAY)
        xbmc.executebuiltin('Container.SetViewMode(%d)' % view)
    except Exception:
        return 0
    # Il servizio riprova quando la cartella e' davvero quella aperta: da qui
    # il container puo' non essere ancora costruito.
    request(target, view)
    return view
