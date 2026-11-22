# -*- coding: utf-8 -*-
"""Stato delle copie locali: cosa c'e' senza dover leggere il log.

Nessuna rete: legge solo i file della cartella dati (canali, guida, ultimo
giro del servizio) e li riduce a poche righe leggibili. Serve soprattutto sul
TV box, dove un rinnovo che non e' passato non si vede altrimenti.
"""

import time

from resources.lib import playlist_store, tv

SERVICE_FILE = 'service.json'


def age_text(seconds):
    """'adesso', '5 min', '2 h', '3 giorni'; 'mai' se la copia non c'e'."""
    if seconds is None:
        return 'mai'
    seconds = int(max(0, seconds))
    if seconds < 60:
        return 'adesso'
    minutes = seconds // 60
    if minutes < 60:
        return '%d min' % minutes
    hours = minutes // 60
    if hours < 48:
        return '%d h' % hours
    return '%d giorni' % (hours // 24)


def when_text(stamp):
    """Data e ora leggibili; 'mai' se il servizio non ha ancora fatto un giro."""
    stamp = int(stamp or 0)
    if not stamp:
        return 'mai'
    return time.strftime('%d/%m %H:%M', time.localtime(stamp))


def channels_info():
    """Canali, flussi e eta' della copia salvata (solo file locali)."""
    entries = playlist_store.read_data(tv.CHANNEL_CACHE).get('entries') or []
    grouped = tv.group_channels(entries) if entries else []
    return {'channels': len(grouped), 'streams': len(entries),
            'age': tv.cache_age(tv.CHANNEL_CACHE)}


def guide_info():
    """Canali con guida ed eta' della copia salvata."""
    guide = playlist_store.read_data(tv.GUIDE_CACHE).get('guide') or {}
    programmes = guide.get('programmes') or {}
    return {'channels': len(programmes), 'age': tv.cache_age(tv.GUIDE_CACHE)}


def service_run():
    """Quando il servizio ha fatto l'ultimo giro e cosa ha rinnovato."""
    data = playlist_store.read_data(SERVICE_FILE)
    return {'when': int(data.get('when') or 0),
            'renewed': [str(part) for part in (data.get('renewed') or [])]}


def mark_service(renewed=None):
    """Il servizio scrive qui l'ora del giro: la pagina Stato la mostra."""
    playlist_store.write_data(SERVICE_FILE, {
        'when': int(time.time()),
        'renewed': [str(part) for part in (renewed or [])],
    })
