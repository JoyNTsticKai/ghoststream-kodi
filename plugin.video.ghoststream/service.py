# -*- coding: utf-8 -*-
"""Rinnovo in sottofondo di lista canali e guida TV, e posizioni di visione.

Kodi avvia questo file all'avvio (extension point xbmc.service): il ciclo
resta in attesa e ogni tanto riscarica quello che sta invecchiando. Cosi' la
sezione TV si apre sempre dalla copia salvata, senza aspettare la rete, che
sui TV box significa decine di secondi e la sensazione che la lista non
carichi (si finiva per uscire e rientrare).

Il download e il parsing delle guide (diversi MB di XMLTV) costano: meglio
farli qui, mentre nessuno sta aspettando una cartella di Kodi.

Un secondo filo segue il video in riproduzione e ne salva la posizione: cosi'
'Continua a guardare' riprende da dove si era rimasti anche se la pagina
dell'addon si e' chiusa subito dopo l'avvio del flusso.
"""

import threading
import traceback

import xbmc
import xbmcaddon
import xbmcvfs

from resources.lib import playlist_store, progress, status, tv, views

ADDON_ID = 'plugin.video.ghoststream'
# Primo controllo dopo l'avvio: Kodi ha finito di caricare, la TV non e' ancora
# stata aperta.
FIRST_WAIT = 30
# Poi un giro ogni tre ore: canali e guida si rinnovano molto prima di scadere.
EVERY = 3 * 3600
# Ogni quanto il secondo filo guarda la riproduzione in corso.
POLL = 5
# Ogni quanto il terzo filo guarda se c'e' una vista da applicare: la cartella
# dell'addon va disegnata prima, altrimenti Kodi ignora il cambio di vista.
VIEW_POLL = 0.4


def log(message):
    xbmc.log('[%s] servizio: %s' % (ADDON_ID, message), xbmc.LOGINFO)


def profile_path():
    """Cartella dati dell'addon, dove stanno le cache di canali e guida."""
    try:
        raw = xbmcaddon.Addon(ADDON_ID).getAddonInfo('profile') or ''
    except Exception:
        return ''
    try:
        return xbmcvfs.translatePath(raw) or raw
    except Exception:
        return raw


def refresh():
    """Rinnova canali e guida se sono invecchiati; non solleva mai."""
    playlist_store.set_root(profile_path())
    try:
        renewed = tv.warm()
    except Exception:
        log(traceback.format_exc())
        return []
    try:
        # La pagina Stato legge questo segno: quando e' girato e cos'ha fatto.
        status.mark_service(renewed)
    except playlist_store.StoreError as exc:
        log('giro del servizio non segnato: %s' % exc)
    if renewed:
        log('rinnovati: %s' % ', '.join(renewed))
    return renewed


def watcher():
    """Segue la riproduzione in corso e salva la posizione per titolo."""
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    while not monitor.abortRequested():
        if monitor.waitForAbort(POLL):
            return
        try:
            progress.track_step(player)
        except Exception:
            log(traceback.format_exc())


def view_watcher():
    """Applica la vista chiesta dall'addon appena la cartella e' quella giusta."""
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(VIEW_POLL):
            return
        try:
            applicata = views.apply_pending(
                xbmc.getInfoLabel('Container.FolderPath'))
            if applicata:
                log('vista %d applicata alla cartella aperta' % applicata)
        except Exception:
            log(traceback.format_exc())


def main():
    playlist_store.set_root(profile_path())
    # I fili partono subito: le posizioni e le viste servono prima del rinnovo.
    for target, name in ((watcher, 'ghoststream-position'),
                         (view_watcher, 'ghoststream-view')):
        thread = threading.Thread(target=target, name=name)
        thread.daemon = True
        thread.start()

    monitor = xbmc.Monitor()
    wait = FIRST_WAIT
    while not monitor.abortRequested():
        if monitor.waitForAbort(wait):
            break
        wait = EVERY
        refresh()
    log('fine')


if __name__ == '__main__':
    main()
