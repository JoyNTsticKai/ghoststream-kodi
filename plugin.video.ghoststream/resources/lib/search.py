# -*- coding: utf-8 -*-
"""Ricerca unificata: una parola e si guarda in tutto l'hub.

Le parole si confrontano senza maiuscole e senza accenti (playlist.fold), e
devono comparire tutte: 'rai telegiornale' trova 'Rai 1' solo se il nome del
canale contiene entrambe. Non si inventa niente: si filtrano le voci che le
sorgenti gia' espongono (canali TV in cache, liste salvate, file locali) e si
passa la query alla ricerca pubblica di Internet Archive.
"""

from resources.lib import local, playlist

MAX_RESULTS = 40      # righe per provenienza, per non fare pagine infinite
MAX_LOCAL_FILES = 400  # quanti file della raccolta si guardano al massimo
MAX_DEPTH = 4         # cartelle annidate che si aprono nella raccolta


def words(query):
    return [word for word in playlist.fold(query).split() if word]


def matches(text, terms):
    """Tutte le parole devono comparire nel testo, in qualsiasi ordine."""
    if not terms:
        return False
    folded = playlist.fold(text)
    return all(term in folded for term in terms)


def filter_entries(entries, query, limit=MAX_RESULTS):
    """Voci (canali, liste) il cui nome contiene tutte le parole cercate."""
    terms = words(query)
    if not terms or limit <= 0:
        return []
    found = []
    for entry in entries or []:
        if matches(entry.get('name') or '', terms):
            found.append(entry)
            if len(found) >= limit:
                break
    return found


def find_local(root, query, limit=MAX_RESULTS, budget=MAX_LOCAL_FILES):
    """Video della raccolta locale che corrispondono, cartelle comprese."""
    terms = words(query)
    if not terms or limit <= 0 or not local.is_available(root):
        return []
    found = []
    seen = 0
    pending = [(root, 0)]
    while pending and seen < budget and len(found) < limit:
        folder, depth = pending.pop(0)
        try:
            folders, videos = local.scan(folder)
        except OSError:
            continue
        seen += len(folders) + len(videos)
        for video in videos:
            # Conta anche la cartella: 'Ken il Guerriero/Episodio 01.mp4'.
            text = video.get('title') or video.get('label') or ''
            if matches(text, terms) or matches(video.get('path') or '', terms):
                found.append(video)
                if len(found) >= limit:
                    break
        if depth < MAX_DEPTH:
            pending.extend((item['path'], depth + 1) for item in folders)
    return found[:limit]
