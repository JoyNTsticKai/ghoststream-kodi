# -*- coding: utf-8 -*-
"""Diagnostica: prova adesso le fonti e dice quale risponde.

Ogni riga e' una richiesta vera (o la lettura di una copia locale) con il suo
esito, non un'ipotesi: serve a distinguere in un colpo d'occhio un problema
di rete da una fonte che ha cambiato indirizzo, senza aprire il log di Kodi.

Solo libreria standard, come il resto dell'addon. Ogni prova di rete ha un
limite di tempo breve: la pagina deve aprirsi anche quando la rete e' lenta,
perche' chi la apre sta gia' cercando di capire cosa non va.
"""

import os
import urllib.request

import xbmc

from resources.lib import (archive_api, dirette, local, playlist, status,
                           tv, youtube)

TIMEOUT = 8


def reach(url, headers=None):
    """(ok, 'HTTP 302') per un link; (False, motivo) se non risponde."""
    request = urllib.request.Request(
        url, headers=dict(headers or {'User-Agent': playlist.USER_AGENT}))
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            code = response.getcode() or 200
    except Exception as exc:
        return False, str(exc) or exc.__class__.__name__
    return 200 <= code < 400, 'HTTP %d' % code


def row(name, ok, detail):
    """Una riga della pagina: nome del controllo, esito, cosa si e' visto."""
    return {'name': name, 'ok': bool(ok),
            'detail': (detail or '').strip() or ('ok' if ok else 'ko')}


def source(url):
    """Un link in rete o un file: le liste locali non si scaricano."""
    if not url:
        return False, 'nessuna fonte impostata'
    if playlist.is_remote(url):
        return reach(url)
    if os.path.isfile(url):
        return True, 'file locale'
    return False, 'file non trovato'


def archive():
    """Una ricerca vera su Internet Archive, con un risultato solo."""
    try:
        docs, total = archive_api.search('subject:"cartoni animati"', rows=1)
    except archive_api.ArchiveError as exc:
        return row('Internet Archive', False, str(exc))
    return row('Internet Archive', True, '%d risultati' % total)


def main_list():
    """La lista canali che l'addon userebbe adesso."""
    url = (tv.channel_sources() or [''])[0]
    ok, detail = source(url)
    return row('Lista canali', ok, detail)


def guide():
    """La guida TV: se la fonte non risponde la riga e' rossa lo stesso.

    La copia vecchia si continua a usare, e lo si dice, ma non si colora di
    verde una fonte muta: il verde qui vuol dire "risponde adesso".
    """
    age = tv.cache_age(tv.GUIDE_CACHE)
    cached = ('copia di %s' % status.age_text(age) if age is not None
              else 'nessuna copia')
    ok, detail = source((tv.guide_sources() or [''])[0])
    if ok:
        return row('Guida TV', True, cached)
    if age is not None:
        return row('Guida TV', False, '%s, si usa la %s' % (detail, cached))
    return row('Guida TV', False, detail)


def channels_cached():
    """Quanti canali ci sono gia' nella copia locale."""
    try:
        info = status.channels_info()
    except Exception as exc:
        return row('Canali salvati', False, str(exc))
    if not info['streams']:
        return row('Canali salvati', False, 'nessuna copia: apri la TV una volta')
    return row('Canali salvati', True, '%d canali, copia di %s'
               % (info['channels'], status.age_text(info['age'])))


def dirette_official():
    """Le dirette ufficiali Rai: il relinker deve rispondere con un rinvio.

    La prova usa lo UA dell'addon, che il relinker accetta: serve solo a
    sapere se la fonte risponde, non a preparare il flusso per il player (che
    usa il suo UA, vedi dirette.entries).
    """
    ok, detail = reach(dirette.probe_url())
    return row('Dirette ufficiali Rai', ok, detail)


def youtube_addon():
    """L'addon YouTube, che l'addon usa per la sua sezione."""
    ok = youtube.available()
    return row('Addon YouTube', ok, 'installato' if ok else 'non installato')


def adaptive():
    """inputstream.adaptive: senza, le dirette HLS vanno a scatti."""
    try:
        ok = bool(xbmc.getCondVisibility('System.HasAddon(inputstream.adaptive)'))
    except Exception as exc:
        return row('inputstream.adaptive', False, str(exc))
    return row('inputstream.adaptive', ok,
               'installato' if ok else 'non installato')


def local_folder(path):
    """La raccolta locale, se e' impostata."""
    if not path:
        return row('Raccolta locale', True, 'non impostata')
    if local.is_available(path):
        return row('Raccolta locale', True, 'raggiungibile')
    return row('Raccolta locale', False, 'cartella non raggiungibile')


def cache(memory, factor):
    """La cache video di Kodi: sotto 256 MB le puntate pesanti si bloccano."""
    if memory is None:
        return row('Cache di Kodi', False, 'non leggibile (webserver spento?)')
    if factor in (None, 0):
        rate = 'Adattivo'
    else:
        rate = '%.1fx' % (factor / 100.0)
    text = '%d MB, fattore %s' % (memory, rate)
    if memory < 256:
        return row('Cache di Kodi', False, text + ' (meglio 256 MB)')
    return row('Cache di Kodi', True, text)
