# -*- coding: utf-8 -*-
"""Controllo aggiornamenti contro il repository dell'addon.

Kodi sa aggiornare da solo gli addon presi da un repository, ma solo se
l'utente ha acceso "Aggiorna automaticamente" e dopo il suo giro periodico.
Qui si guarda la versione pubblicata all'apertura del Ghost: se e' piu'
nuova si installa subito.

Qui non si legge mai la versione installata: l'unica che conta e' quella che
Kodi ha in memoria, e arriva da check_update (ADDON.getAddonInfo). Leggerla
anche dall'addon.xml su disco voleva dire due fonti che divergono appena i
file si copiano con Kodi aperto.

La rete non si tocca a ogni disegno del menu: Kodi rilancia lo script ogni
volta che si torna alla cartella principale, quindi l'esito resta in
update.json. Giro riuscito: si riprova dopo OK_AGE. Giro fallito (rete muta,
addons.xml illeggibile): dopo RETRY, cosi' un box senza rete non paga il
timeout a ogni clic e non resta comunque fermo mezza giornata.
"""

import time
import urllib.request
import xml.etree.ElementTree as ET

from resources.lib import playlist_store

FILE = 'update.json'
OK_AGE = 30 * 60      # dopo un giro riuscito
RETRY = 15 * 60       # dopo un giro fallito
ADDONS_XML = ('https://raw.githubusercontent.com/JoyNTsticKai/'
              'ghoststream-kodi/main/repo/addons.xml')
USER_AGENT = 'plugin.video.ghoststream (Kodi addon)'


def parse(text):
    """(1, 9, 18) da '1.9.18'; tupla vuota se non e' una versione."""
    parts = []
    for chunk in str(text or '').strip().split('.'):
        digits = ''.join(char for char in chunk if char.isdigit())
        if not digits:
            return ()
        parts.append(int(digits))
    return tuple(parts)


def newer(candidate, current):
    """True se candidate e' piu' recente di current (confronto numerico)."""
    left, right = parse(candidate), parse(current)
    if not left or not right:
        return False
    size = max(len(left), len(right))
    left += (0,) * (size - len(left))
    right += (0,) * (size - len(right))
    return left > right


def version_in(text, addon_id):
    """La versione dell'addon dentro addons.xml; '' se manca o e' rotto."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return ''
    for node in root.iter('addon'):
        if node.get('id') == addon_id:
            return (node.get('version') or '').strip()
    return ''


def fetch(timeout=6):
    """Il testo di addons.xml, oppure '' se la rete non risponde."""
    request = urllib.request.Request(ADDONS_XML,
                                     headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(512 * 1024).decode('utf-8', 'replace')
    except Exception:
        return ''


def when_text(stamp):
    """'23/11 18:40'; 'mai' se non c'e' stato nessun controllo."""
    stamp = int(stamp or 0)
    if not stamp:
        return 'mai'
    return time.strftime('%d/%m %H:%M', time.localtime(stamp))


def age_text(seconds):
    """'12 min', '3 h': fra quanto si riprova (si arrotonda per eccesso)."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return 'adesso'
    minuti = (seconds + 59) // 60
    if minuti < 60:
        return '%d min' % minuti
    ore = (minuti + 59) // 60
    if ore < 48:
        return '%d h' % ore
    return '%d giorni' % (ore // 24)


def next_at():
    """Quando tocca il prossimo controllo (epoch). 0 = subito.

    OK_AGE dopo un giro riuscito, RETRY dopo uno fallito.
    """
    data = playlist_store.read_data(FILE)
    try:
        last = int(data.get('checked') or 0)
    except (TypeError, ValueError):
        return 0
    if not last:
        return 0
    return last + (OK_AGE if data.get('ok', True) else RETRY)


def due():
    """True se e' ora di guardare il server."""
    return time.time() >= next_at()


def report():
    """Per la pagina Stato: quando, cosa si e' visto, quando si riprova."""
    data = playlist_store.read_data(FILE)
    try:
        last = int(data.get('checked') or 0)
    except (TypeError, ValueError):
        last = 0
    quando = next_at()
    adesso = time.time()
    # Senza nessun controllo fatto non c'e' niente di fallito: si dice "mai".
    riuscito = True if not last else bool(data.get('ok', True))
    return {'checked': last,
            'checked_text': when_text(last),
            'seen': str(data.get('seen') or '').strip(),
            'ok': riuscito,
            'next': quando,
            'next_text': ('adesso' if quando <= adesso
                          else age_text(quando - adesso))}


def mark(version='', ok=True):
    """Segna il controllo di adesso, la versione vista e se e' andato bene.

    ok=False (niente rete, addons.xml illeggibile) fa riprovare dopo RETRY.
    """
    try:
        playlist_store.write_data(FILE, {'checked': int(time.time()),
                                         'seen': version or '',
                                         'ok': bool(ok)})
    except playlist_store.StoreError:
        pass
