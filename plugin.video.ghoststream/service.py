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

from resources.lib import playlist_store, progress, status, tv

ADDON_ID = 'plugin.video.ghoststream'
# Primo controllo dopo l'avvio: Kodi ha finito di caricare, la TV non e' ancora
# stata aperta.
FIRST_WAIT = 30
# Poi un giro ogni tre ore: canali e guida si rinnovano molto prima di scadere.
EVERY = 3 * 3600
# Ogni quanto il secondo filo guarda la riproduzione in corso.
POLL = 5


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


def main():
    playlist_store.set_root(profile_path())
    # Il filo delle posizioni parte subito: serve anche prima del primo rinnovo.
    thread = threading.Thread(target=watcher, name='ghoststream-position')
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
