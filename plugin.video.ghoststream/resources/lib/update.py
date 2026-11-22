# -*- coding: utf-8 -*-
"""Controllo aggiornamenti contro il repository dell'addon.

Kodi sa aggiornare da solo gli addon presi da un repository, ma solo se
l'utente ha acceso "Aggiorna automaticamente" e dopo il suo giro periodico.
Qui si guarda la versione pubblicata all'apertura del Ghost: se e' piu'
nuova si chiede se installarla subito.

La rete non si tocca a ogni apertura: l'esito resta in update.json nella
cartella dati e vale per mezza giornata. Cosi' un TV box senza rete non
aspetta niente a ogni clic.
"""

import time
import urllib.request
import xml.etree.ElementTree as ET

from resources.lib import playlist_store

FILE = 'update.json'
MAX_AGE = 12 * 3600
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


def due():
    """True se l'ultimo controllo e' vecchio (o non c'e')."""
    data = playlist_store.read_data(FILE)
    try:
        last = int(data.get('checked') or 0)
    except (TypeError, ValueError):
        return True
    return time.time() - last >= MAX_AGE


def mark(version=''):
    """Segna il controllo di adesso e la versione vista."""
    try:
        playlist_store.write_data(FILE, {'checked': int(time.time()),
                                         'seen': version or ''})
    except playlist_store.StoreError:
        pass
