# -*- coding: utf-8 -*-
"""Ghost-Stream - router dell'addon.

Ogni voce di menu e' un URL:
    plugin://plugin.video.ghoststream/?mode=<modo>&<parametri>

Per aggiungere una nuova sorgente:
  1. un modulo in resources/lib/ che restituisce etichette + URL;
  2. una funzione show_<nome>() qui sotto;
  3. un ramo nel main() e una voce in show_root().
"""

import json
import os
import re
import shutil
import sys
import time
import traceback
import urllib.parse
import xml.etree.ElementTree as ET

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

from resources.lib import (archive_api, favorites, hidden, local, naming,
                           playlist, playlist_store, progress, search, tv,
                           views, youtube)

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = ADDON.getAddonInfo('path')


def profile_path():
    """Cartella dati: Kodi la espone come special://, va tradotta in un percorso vero."""
    raw = ADDON.getAddonInfo('profile') or ''
    try:
        return xbmcvfs.translatePath(raw) or raw
    except Exception:
        return raw


# Liste salvate: indice e copia locale dentro la cartella dati dell'addon.
playlist_store.set_root(profile_path())

# Nome precedente dell'addon: i suoi dati si portano dietro una volta sola.
OLD_ADDON_ID = 'plugin.video.cartonitalia'
MIGRATION_MARKER = 'migrated.json'
MIGRATED_SETTINGS = ('source_load', 'source_youtube', 'source_archive',
                     'source_local', 'source_tv', 'm3u_url', 'tv_url',
                     'epg_url', 'yt_extra', 'ia_rows', 'local_path')

BASE_URL = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
PARAMS = dict(urllib.parse.parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}

# Nomi nuovi delle immagini: un percorso gia' in cache non si aggiorna da solo.
ICON = os.path.join(ADDON_PATH, 'resources', 'ghost-icon.png')
FANART = os.path.join(ADDON_PATH, 'resources', 'ghost-fanart.jpg')
ICONS_DIR = os.path.join(ADDON_PATH, 'resources', 'icons')

ITEM_COUNT = [0]

LABELS = {
    30000: 'YouTube ufficiale',
    30001: 'Internet Archive',
    30002: 'La mia raccolta',
    30003: 'Cerca su Internet Archive...',
    30004: 'Nessun risultato',
    30005: 'Pagina successiva',
    30006: 'Errore di rete: controlla la connessione.',
    30007: 'Imposta la cartella della raccolta nelle impostazioni.',
    30008: 'Nessun file video riproducibile.',
    30009: "L'addon YouTube non risulta installato.",
    30010: "La cartella non esiste o non e' accessibile.",
    30011: 'Carica un link (M3U o video)',
    30012: 'Incolla il link della lista M3U/M3U8 o del video (Ctrl+V per incollare)',
    30013: "Incolla il link di una lista M3U/M3U8 o di un video: l'addon lo legge "
           'e mostra i canali o gli episodi.',
    30015: 'Link non valido, lista vuota o file non leggibile.',
    30016: 'consigliato',
    30017: 'Nome della lista',
    30018: 'Salvare questa lista tra le mie sorgenti?',
    30019: 'Lista salvata',
    30020: 'Aggiorna la lista',
    30021: 'Rimuovi la lista',
    30022: 'Rimuovere "%s" dalle mie sorgenti?',
    30023: 'Elenco aggiornato',
    30024: 'Aggiornamento non riuscito: uso la copia salvata.',
    30025: 'Ordine dei canali',
    30026: 'Alfabetico (A-Z)',
    30027: 'Per gruppo',
    30028: 'Numero del canale',
    30029: 'Come nel file',
    30030: 'Tutti i canali',
    30031: 'Senza gruppo',
    30032: 'TV in chiaro',
    30033: 'Canali in chiaro da una lista pubblica, con loghi e guida TV.',
    30034: 'Elenco canali non disponibile: controlla la connessione.',
    30035: 'Nessun canale in questa lista.',
    30036: 'Solo canali con guida TV',
    30037: 'Tutti i canali',
    30038: 'In onda',
    30039: 'Dopo',
    30040: 'Guida TV non disponibile: premi "Aggiorna la lista" per riprovare.',
    30041: 'Principale',
    30042: 'Riprendi da',
    30043: 'Continua a guardare',
    30044: 'Niente da riprendere: i video lasciati a meta compaiono qui.',
    30045: 'Segna come visto',
    30046: 'Segna come non visto',
    30047: 'Togli da Continua',
    30048: 'Segnato come visto',
    30049: 'Tolto da Continua',
    30050: 'Riprendi i video da dove li avevi lasciati.',
    30051: 'visto',
    30052: 'Segnato come non visto',
    30053: 'Aggiungi a La mia lista',
    30054: 'Togli da La mia lista',
    30055: 'La mia lista',
    30056: 'Aggiunto a La mia lista',
    30057: 'Tolto da La mia lista',
    30058: 'La mia lista e vuota: aggiungi una voce dal menu contestuale.',
    30059: 'Le voci che hai scelto, in cima al menu.',
    30060: 'Nascondi questo canale',
    30061: 'Nascondi il gruppo "%s"',
    30062: 'Voci nascoste',
    30063: 'Mostra di nuovo',
    30064: 'Nascosto',
    30065: 'Di nuovo visibile',
    30066: 'Niente di nascosto.',
    30067: 'Canali e gruppi che hai nascosto, per ritrovarli.',
    30068: 'gruppo',
    30069: 'canale',
    30070: 'Mostra tutti',
    30071: 'Cerca',
    30072: 'Cerca in tutto: canali TV, le tue liste, la raccolta locale e '
           'Internet Archive.',
    30073: 'Nessun risultato per "%s".',
    30074: 'Cerca su YouTube',
    30075: 'Canali TV',
    30076: 'Le tue liste',
    30077: 'La mia raccolta',
    30078: 'Internet Archive',
    30079: 'Cerca una parola',
    30080: 'Niente nei canali TV, nelle liste e nella raccolta.',
}

# Caratteri che la vista lista disegna prima di tagliare la riga: oltre,
# il programma successivo sparirebbe fuori schermo.
LABEL_WIDTH = 84
AFTER_MARK = u'\u2192'
_MARKUP = re.compile(r'\[/?COLOR[^\]]*\]')


def guide_label(base, entry, width=LABEL_WIDTH):
    """Nome del canale con 'In onda' e 'Dopo' nella stessa riga.

    La vista lista mostra solo la label (la Label2 non viene disegnata): il
    programma successivo va quindi qui, altrimenti resta invisibile. Il
    programma in onda non si accorcia mai: se lo spazio finisce si taglia
    solo quello dopo, partendo dal titolo e tenendone l'orario.
    """
    text = base
    used = len(_MARKUP.sub('', base))
    now = entry.get('epg') or ''
    if now:
        chunk = '%s: %s' % (t(30038), now)
        text += '  [COLOR=grey]%s[/COLOR]' % chunk
        used += 2 + len(chunk)
    after = entry.get('epg_next') or ''
    if after:
        room = width - used - 3
        if room >= 7:
            tail = after
            if len(tail) > room:
                tail = tail[:room - 1].rstrip() + u'\u2026'
            text += '  [COLOR=grey]%s %s[/COLOR]' % (AFTER_MARK, tail)
    return text


# --------------------------------------------------------------------------
# Utilita'
# --------------------------------------------------------------------------
def log(message):
    xbmc.log('[%s] %s' % (ADDON_ID, message), xbmc.LOGINFO)


def t(string_id):
    """Stringa localizzata con fallback italiano se il .po non e' caricato."""
    try:
        text = ADDON.getLocalizedString(string_id)
    except Exception:
        text = ''
    return text or LABELS.get(string_id, '')


def notify(message, error=False):
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    try:
        xbmcgui.Dialog().notification(ADDON_NAME, message, icon, 5000)
    except Exception:
        log('notifica non disponibile: %s' % message)


def setting_bool(key, default=False):
    try:
        return ADDON.getSettingBool(key)
    except Exception:
        return (ADDON.getSetting(key) or str(default)).lower() == 'true'


def setting_int(key, default):
    try:
        return ADDON.getSettingInt(key) or default
    except Exception:
        try:
            return int(ADDON.getSetting(key))
        except (TypeError, ValueError):
            return default


def setting_text(key, default=''):
    try:
        return ADDON.getSettingString(key) or default
    except Exception:
        return ADDON.getSetting(key) or default


def url(**params):
    return BASE_URL + '?' + urllib.parse.urlencode(params)


def source_art(name):
    """Icona dedicata della sorgente, con fallback a quella dell'addon."""
    path = os.path.join(ICONS_DIR, '%s.png' % name)
    if os.path.isfile(path):
        return {'thumb': path, 'icon': path}
    return {}


def add_item(label, target, art=None, info=None, playable=False, context=None,
             second=None, track=True, source=None):
    """Una voce di elenco, con il segno di visto e 'Riprendi da' se ci sono.

    La posizione si cerca col titolo che la riproduzione ricevera' (il
    parametro title dello stesso link), cosi' lettura e salvataggio non possono
    riferirsi a due titoli diversi.
    """
    info = dict(info or {})
    query = play_params(target) if playable else {}
    if source:
        # Riga che apre un sottomenu (TV con piu' flussi): per La mia lista
        # vale il flusso principale, altrimenti la voce non si potrebbe salvare.
        query = {'mode': 'play', 'u': source.get('url', ''),
                 'title': source.get('title') or ''}
        if source.get('extra'):
            query['p'] = source['extra']
    title = query.get('title', '') if query.get('mode') == 'play' else ''
    # Le dirette (track=False) non hanno posizione: niente 'Riprendi da'.
    marker = progress.find(title) if (title and track) else None
    if marker and marker.get('finished'):
        info['playcount'] = 1
        label = '%s  [COLOR=green](%s)[/COLOR]' % (label, t(30051))
    elif marker:
        # Ancora a meta: si dice da dove riparte, senza togliere altro.
        info['playcount'] = 0
        label = '%s  [COLOR=grey]%s %s[/COLOR]' % (
            label, t(30042), progress.time_text(marker.get('position')))
    item = xbmcgui.ListItem(label=label, offscreen=True)
    if second:
        # Seconda riga della voce: in Kodi e' label2, quella sotto il nome.
        item.setLabel2(second)
    item_art = {'icon': ICON, 'thumb': ICON, 'fanart': FANART}
    if art:
        item_art.update({key: value for key, value in art.items() if value})
    item.setArt(item_art)
    if title:
        # Prima le azioni della voce (scelta, segno di visto, Continua), poi
        # quelle della pagina che la mostra (nascondi canale o gruppo).
        own = favorite_menu(title, query, item_art, info)
        if track:
            own += progress_menu(title, marker, query)
            # La copertina viaggia col link: la pagina Continua la mostrera'.
            target = with_art(target, item_art)
        context = own + list(context or [])
    if info:
        item.setInfo('video', info)
    if playable:
        item.setProperty('IsPlayable', 'true')
    if context:
        item.addContextMenuItems(context, replaceItems=False)
    added = xbmcplugin.addDirectoryItem(HANDLE, target, item, isFolder=not playable)
    if added:
        ITEM_COUNT[0] += 1
    return added


def end(content=None):
    if content:
        xbmcplugin.setContent(HANDLE, content)
    log('elenco completato: %d voci' % ITEM_COUNT[0])
    ITEM_COUNT[0] = 0
    # La cartella resta in cache: tornando indietro Kodi la ridisegna invece
    # di rifare tutto il lavoro, che su un TV box sono secondi di attesa.
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=True)
    # La vista scelta (lista, icone...) resta anche dopo un aggiornamento.
    view = views.apply(sys.argv[0])
    if view:
        log('vista riapplicata: %d' % view)


def redirect(target):
    """Sostituisce la cartella corrente: la pagina del link non torna piu'.

    Il parametro 'v' cambia sempre, cosi' la pagina arriva appena costruita e
    non dalla cache di Kodi: ordine nuovo e liste riscaricate si vedono subito.
    """
    fresh = '%s%sv=%d' % (target, '&' if '?' in target else '?',
                          int(time.time() * 1000))
    log('redirect: %s' % fresh)
    try:
        xbmc.executebuiltin('Container.Update(%s)' % fresh)
    except Exception:
        log('Container.Update non disponibile')
    ITEM_COUNT[0] = 0
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False,
                              cacheToDisc=False)


def confirm(message):
    try:
        return xbmcgui.Dialog().yesno(ADDON_NAME, message)
    except Exception:
        log('dialogo non disponibile: %s' % message)
        return False


def ask_text(heading, default=''):
    keyboard = xbmc.Keyboard(default, heading)
    keyboard.doModal()
    return keyboard.getText().strip() if keyboard.isConfirmed() else ''


def suggest_name(target):
    """'La mia lista' di ripiego: il nome del file o dell'ultimo pezzo del link."""
    path = urllib.parse.urlparse(target).path or target
    stem = path.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]
    stem = os.path.splitext(urllib.parse.unquote(stem))[0]
    return stem.replace('_', ' ').strip() or target


def first_logo(entries):
    for entry in entries:
        if entry.get('logo'):
            return entry['logo']
    return ''


def logo_art(logo):
    """Copertina di una voce: logo della lista, se c'e'."""
    if not logo:
        return {}
    return {'thumb': logo, 'icon': logo, 'fanart': logo}


def entry_title(entry):
    return entry['title'] or entry['label']


def entry_extra(entry):
    """Proprieta' della voce (KODIPROP, header) da passare alla riproduzione."""
    extra = {key: entry[key] for key in ('props', 'headers') if entry.get(key)}
    return json.dumps(extra, separators=(',', ':')) if extra else ''


def play_params(target):
    """Parametri di una voce riproducibile (titolo, link, proprieta')."""
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(target or '').query)
    except ValueError:
        return {}
    return {name: values[0] for name, values in query.items() if values}


def progress_menu(title, marker, query):
    """Righe del menu contestuale: segno di visto e 'Continua'."""
    name = progress.key(title)
    if not name:
        return []
    rows = []
    if marker and marker.get('finished'):
        rows.append((t(30046), 'RunPlugin(%s)' % url(
            mode='progress', k=name, t=title, a='unwatch')))
    else:
        rows.append((t(30045), 'RunPlugin(%s)' % url(
            mode='progress', k=name, t=title, a='watch',
            u=query.get('u', ''), p=query.get('p', ''))))
    if marker:
        # 'Togli da Continua' solo se c'e' una posizione da togliere.
        rows.append((t(30047), 'RunPlugin(%s)' % url(
            mode='progress', k=name, t=title, a='forget')))
    return rows


def hide_menu(title, group=''):
    """Righe del menu contestuale per togliere di mezzo canali e gruppi."""
    rows = []
    if title:
        rows.append((t(30060), 'RunPlugin(%s)' % url(
            mode='hide', a='channel', k=hidden.key(title), t=title)))
    if group:
        rows.append((t(30061) % group, 'RunPlugin(%s)' % url(
            mode='hide', a='group', k=hidden.key(group), t=group)))
    return rows


def with_art(target, art):
    """Copertina nel link: chi riproduce la salva insieme alla posizione."""
    params = {}
    for name, value in (('at', (art or {}).get('thumb')),
                        ('af', (art or {}).get('fanart'))):
        # L'icona generica dell'addon non e' una copertina: non si salva.
        if value and value not in (ICON, FANART):
            params[name] = value
    if not params:
        return target
    return '%s%s%s' % (target, '&' if '?' in target else '?',
                       urllib.parse.urlencode(params))


def favorite_menu(title, query, art, info):
    """Riga del menu contestuale: aggiungi o togli da La mia lista."""
    name = progress.key(title)
    if not name:
        return []
    params = {'mode': 'favorite', 'k': name, 't': title,
              'u': query.get('u', ''), 'p': query.get('p', '')}
    thumb = (art or {}).get('thumb')
    fanart = (art or {}).get('fanart')
    # L'icona generica non e' una copertina: meglio lasciarla fuori.
    if thumb and thumb != ICON:
        params['i'] = thumb
    if fanart and fanart != FANART:
        params['f'] = fanart
    plot = (info or {}).get('plot')
    if plot:
        params['pl'] = plot
    if favorites.has(title):
        return [(t(30054), 'RunPlugin(%s)' % url(a='remove', **params))]
    return [(t(30053), 'RunPlugin(%s)' % url(a='add', **params))]


def entry_url(entry):
    params = {'mode': 'play', 'u': entry['url'],
              'title': playlist.clean_name(entry['name'])}
    extra = entry_extra(entry)
    if extra:
        params['p'] = extra
    return url(**params)


def details_label(label, *parts):
    """'Titolo  [COLOR=grey](h.264 · 136.0 MB)[/COLOR]', se c'e' qualcosa da dire."""
    details = ' \u00b7 '.join(part for part in parts if part)
    return '%s  [COLOR=grey](%s)[/COLOR]' % (label, details) if details else label


# Ordine dei canali, come le liste TV (World Live TV): si sceglie dalla lista.
ORDER_KEYS = ('az', 'group', 'number', 'file')


def list_order():
    order = playlist_store.load_order()
    return order if order in ORDER_KEYS else 'az'


def order_label(order):
    return {'az': t(30026), 'group': t(30027), 'number': t(30028),
            'file': t(30029)}.get(order, t(30026))


def choose_order(back='', groups=False, current=''):
    """Tastiera di scelta dell'ordine; poi si torna alla stessa lista.

    Senza group-title nella lista l'opzione "Per gruppo" non viene offerta.
    """
    keys = list(ORDER_KEYS) if groups else ['az', 'number', 'file']
    labels = [order_label(key) for key in keys]
    preset = current if current in keys else list_order()
    if preset not in keys:
        preset = 'az'
    try:
        index = xbmcgui.Dialog().select(t(30025), labels,
                                        preselect=keys.index(preset))
    except Exception:
        log('scelta dell\'ordine non disponibile')
        index = -1
    if index >= 0:
        try:
            playlist_store.save_order(keys[index])
        except playlist_store.StoreError as exc:
            log('ordine non salvato: %s' % exc)
    redirect(back or url(mode='loaded'))


# --------------------------------------------------------------------------
# Menu principale
# --------------------------------------------------------------------------
def show_root():
    show_favorites_row()
    show_continue_row()
    add_item(t(30071), url(mode='search'), art=source_art('search'),
             info={'plot': t(30072), 'mediatype': 'video'})
    if setting_bool('source_load', True):
        add_item(t(30011), url(mode='load'), art=source_art('load'),
                 info={'plot': t(30013), 'mediatype': 'video'})
        show_saved_lists()
    if setting_bool('source_youtube', True):
        add_item(t(30000), url(mode='youtube'), art=source_art('youtube'),
                 info={'plot': 'Canali ufficiali e i tuoi abbonamenti, '
                               'riprodotti con l\'addon YouTube.',
                       'mediatype': 'video'})
    if setting_bool('source_archive', True):
        add_item(t(30001), url(mode='archive'), art=source_art('archive'),
                 info={'plot': 'Film, cartoni e documentari in italiano di pubblico '
                               'dominio o con licenza libera.',
                       'mediatype': 'video'})
    if setting_bool('source_tv', True):
        add_item(t(30032), url(mode='tv'), art=source_art('tv'),
                 info={'plot': t(30033), 'mediatype': 'video'})
    if setting_bool('source_local', False):
        add_item(t(30002), url(mode='local', path=''), art=source_art('local'),
                 info={'plot': 'I tuoi file video, su disco o su NAS.',
                       'mediatype': 'video'})
    show_hidden_row()
    end()


def show_saved_lists():
    """Una riga per lista salvata, subito nel menu principale."""
    try:
        items = playlist_store.load()
    except playlist_store.StoreError as exc:
        log('indice delle liste non letto: %s' % exc)
        return

    for entry in items:
        art = logo_art(entry.get('logo')) or source_art('lists')
        remove = (t(30021),
                  'RunPlugin(%s)' % url(mode='list_remove', id=entry['id']))
        info = {'title': entry['name'], 'plot': entry['url'],
                'mediatype': 'video'}
        if entry.get('kind') == 'stream':
            add_item(entry['name'], entry_url(entry),
                     art=art, info=info, playable=True, context=[remove])
        else:
            add_item(entry['name'], url(mode='list', id=entry['id']),
                     art=art, info=info, context=[remove])


# --------------------------------------------------------------------------
# Ricerca unificata
# --------------------------------------------------------------------------
def show_search():
    """Una parola sola e la ricerca guarda in tutte le sorgenti."""
    text = ask_text(t(30079), '')
    if not text:
        end()
        return
    redirect(url(mode='search_results', q=text))


def search_section(label, count, query, art=None):
    """Titolo di sezione nei risultati; premendolo si rifa' la ricerca."""
    add_item('%s  [COLOR=grey](%d)[/COLOR]' % (label, count),
             url(mode='search_results', q=query), art=art,
             info={'title': label, 'mediatype': 'video'})


def show_search_results(query):
    """Risultati divisi per provenienza, in una pagina sola."""
    query = (query or '').strip()
    if not query:
        end()
        return

    found_any = 0

    # 1. Canali TV (dalla copia locale, con la guida gia' scaricata).
    if setting_bool('source_tv', True):
        try:
            channels = tv.group_channels(tv.channels(setting_text('tv_url', '')))
        except tv.TvError as exc:
            log('ricerca TV non disponibile: %s' % exc)
            channels = []
        hits = search.filter_entries(channels, query)
        if hits:
            try:
                hits = tv.with_guide(hits, tv.guide(setting_text('epg_url', '')))
            except tv.TvError as exc:
                log('guida non disponibile per la ricerca: %s' % exc)
            search_section(t(30075), len(hits), query, source_art('tv'))
            for entry in hits:
                name = playlist.clean_name(entry.get('name') or '')
                variants = entry.get('variants') or []
                info = {'title': name,
                        'plot': entry.get('plot') or entry['url'],
                        'mediatype': 'video'}
                if len(variants) > 1:
                    add_item(guide_label(name, entry),
                             url(mode='tv_var', k=entry.get('key')),
                             art=logo_art(entry.get('logo')), info=info,
                             track=False,
                             source={'title': name,
                                     'url': variants[0]['url'],
                                     'extra': entry_extra(variants[0])})
                else:
                    add_item(guide_label(name, entry), entry_url(entry),
                             art=logo_art(entry.get('logo')), info=info,
                             playable=True, track=False)
            found_any += len(hits)

    # 2. Le liste salvate (copia locale, nessuna pagina da aprire).
    hits = []
    try:
        for saved in playlist_store.load():
            hits.extend(search.filter_entries(
                playlist_store.entries(saved['id']), query,
                limit=search.MAX_RESULTS - len(hits)))
            if len(hits) >= search.MAX_RESULTS:
                break
    except playlist_store.StoreError as exc:
        log('liste non lette per la ricerca: %s' % exc)
    if hits:
        search_section(t(30076), len(hits), query, source_art('lists'))
        for entry in hits:
            name = playlist.clean_name(entry.get('name') or '')
            add_item(name, entry_url(entry), art=logo_art(entry.get('logo')),
                     info={'title': name,
                           'plot': entry.get('plot') or entry['url'],
                           'mediatype': 'video'}, playable=True)
        found_any += len(hits)

    # 3. La mia raccolta locale (cartelle comprese, senza rete).
    if setting_bool('source_local', False):
        videos = search.find_local(setting_text('local_path', ''), query)
        if videos:
            search_section(t(30077), len(videos), query, source_art('local'))
            width = naming.number_width([item['episode'] for item in videos])
            for item in videos:
                label = naming.episode_label(item['episode'], item['title'], width)
                add_item(label, url(mode='play', u=item['path'], title=label),
                         art=item['art'],
                         info={'title': item['title'], 'sorttitle': label,
                               'plot': item['path'], 'mediatype': 'episode'},
                         playable=True)
            found_any += len(videos)

    # 4. Internet Archive ha una pagina sua: la ricerca sul web puo' metterci
    #    secondi, e chi cerca un canale o un file locale non deve aspettarla.
    if setting_bool('source_archive', True):
        add_item('%s: "%s"' % (t(30078), query),
                 url(mode='archive_list', q=query, page=1),
                 art=source_art('archive'),
                 info={'plot': 'Film, cartoni e documentari di pubblico dominio '
                               'o con licenza libera.', 'mediatype': 'video'})

    # 5. YouTube, se l'addon c'e': la ricerca la fa lui.
    if youtube.available():
        add_item('%s: "%s"' % (t(30074), query), youtube.search_url(query),
                 info={'plot': t(30072), 'mediatype': 'video'})

    if not found_any:
        notify(t(30080))
    end('videos')


# --------------------------------------------------------------------------
# Canali e gruppi nascosti
# --------------------------------------------------------------------------
def show_hidden_row():
    """Riga per ritrovare quello che si e' nascosto."""
    try:
        total = hidden.count()
    except playlist_store.StoreError as exc:
        log('voci nascoste non lette: %s' % exc)
        return
    if not total:
        return
    add_item('%s  [COLOR=grey](%d)[/COLOR]' % (t(30062), total),
             url(mode='hidden'),
             info={'plot': t(30067), 'mediatype': 'video'})


def hide_action():
    """Nasconde un canale o un gruppo, poi ridisegna la pagina."""
    action = PARAMS.get('a', '')
    title = PARAMS.get('t', '')
    log('nascondo %s: %s' % (action, title))
    try:
        if action == 'channel':
            hidden.hide_channel(title)
        elif action == 'group':
            hidden.hide_group(title)
    except playlist_store.StoreError as exc:
        log('nascosto non salvato: %s' % exc)
        notify(t(30015), True)
        end()
        return

    notify(t(30064))
    try:
        xbmc.executebuiltin('Container.Refresh')
    except Exception:
        log('aggiornamento della pagina non disponibile')
    end()


def show_hidden():
    """Le voci nascoste: premendone una torna visibile."""
    try:
        rows = ([dict(row, kind='channel') for row in hidden.channels()] +
                [dict(row, kind='group') for row in hidden.groups()])
    except playlist_store.StoreError as exc:
        log('voci nascoste non lette: %s' % exc)
        rows = []
    if not rows:
        notify(t(30066))
        end()
        return

    for row in rows:
        kind = t(30068) if row['kind'] == 'group' else t(30069)
        label = '%s  [COLOR=grey](%s)[/COLOR]' % (row.get('title') or '', kind)
        add_item(label, url(mode='unhide', k=row.get('key'), tipo=row['kind']),
                 info={'title': row.get('title') or '', 'plot': t(30063),
                       'mediatype': 'video'})
    add_item(t(30070), url(mode='unhide', tipo='all'),
             info={'plot': t(30063), 'mediatype': 'video'})
    end('videos')


def unhide_action():
    """Rimette visibile una voce (o tutte) e riapre l'elenco dei nascosti."""
    kind = PARAMS.get('tipo', '')
    name = PARAMS.get('k', '')
    try:
        if kind == 'all':
            hidden.clear()
        elif kind == 'group':
            hidden.show(name, 'groups')
        else:
            hidden.show(name, 'channels')
    except playlist_store.StoreError as exc:
        log('nascosto non aggiornato: %s' % exc)
        notify(t(30015), True)
        end()
        return

    notify(t(30065))
    redirect(url(mode='hidden'))


# --------------------------------------------------------------------------
# La mia lista (preferiti)
# --------------------------------------------------------------------------
def show_favorites_row():
    """Riga in cima al menu: le voci scelte."""
    try:
        rows = favorites.load()
    except playlist_store.StoreError as exc:
        log('la mia lista non letta: %s' % exc)
        return
    if not rows:
        return
    add_item('%s  [COLOR=grey](%d)[/COLOR]' % (t(30055), len(rows)),
             url(mode='favorites'),
             info={'plot': t(30059), 'mediatype': 'video'})


def show_favorites():
    """Le voci scelte, con la loro copertina e il loro link."""
    try:
        rows = favorites.load()
    except playlist_store.StoreError as exc:
        log('la mia lista non letta: %s' % exc)
        rows = []
    if not rows:
        notify(t(30058))
        end()
        return

    for row in rows:
        title = row.get('title') or ''
        params = {'mode': 'play', 'u': row.get('url') or '', 'title': title}
        if row.get('extra'):
            params['p'] = row['extra']
        # Il 'Togli da La mia lista' lo aggiunge add_item: una riga sola.
        info = {'title': title, 'plot': row.get('plot') or t(30059),
                'mediatype': 'video'}
        add_item(title, url(**params), art=row.get('art'), info=info,
                 playable=True)
    end('videos')


def favorite_action():
    """Aggiunge o toglie una voce da La mia lista, poi ridisegna la pagina."""
    action = PARAMS.get('a', '')
    title = PARAMS.get('t', '')
    log('la mia lista %s: %s' % (action, title))
    art = {}
    if PARAMS.get('i'):
        art['thumb'] = PARAMS['i']
    if PARAMS.get('f'):
        art['fanart'] = PARAMS['f']
    try:
        if action == 'add':
            favorites.add(title, PARAMS.get('u', ''), PARAMS.get('p', ''),
                          art, PARAMS.get('pl', ''))
            notify(t(30056))
        elif action == 'remove':
            favorites.remove(title)
            notify(t(30057))
    except playlist_store.StoreError as exc:
        log('la mia lista non aggiornata: %s' % exc)
        notify(t(30015), True)

    try:
        xbmc.executebuiltin('Container.Refresh')
    except Exception:
        log('aggiornamento della pagina non disponibile')
    end()


# --------------------------------------------------------------------------
# Continua a guardare
# --------------------------------------------------------------------------
def show_continue_row():
    """Riga in cima al menu: i video lasciati a meta."""
    try:
        rows = progress.continued()
    except playlist_store.StoreError as exc:
        log('posizioni non lette: %s' % exc)
        return
    if not rows:
        return
    add_item('%s  [COLOR=grey](%d)[/COLOR]' % (t(30043), len(rows)),
             url(mode='continue'),
             info={'plot': t(30050), 'mediatype': 'video'})


def show_continue():
    """I video da riprendere, dal piu' recente; ripartono dalla posizione."""
    try:
        rows = progress.continued()
    except playlist_store.StoreError as exc:
        log('posizioni non lette: %s' % exc)
        rows = []
    if not rows:
        notify(t(30044))
        end()
        return

    for entry in rows:
        params = {'mode': 'play', 'u': entry.get('url') or '',
                  'title': entry.get('title') or ''}
        if entry.get('extra'):
            params['p'] = entry['extra']
        info = {'title': entry.get('title') or '', 'plot': t(30050),
                'mediatype': 'video'}
        add_item(entry.get('title') or '', url(**params),
                 art=entry.get('art') or {}, info=info, playable=True)
    end('videos')


def progress_action():
    """Segna visto / non visto / togli da Continua, poi ridisegna la pagina."""
    name = PARAMS.get('k', '')
    action = PARAMS.get('a', '')
    log('posizione %s: %s' % (action, PARAMS.get('t', name)))
    try:
        if action == 'watch':
            progress.set_watched(name, True, PARAMS.get('t', ''),
                                 PARAMS.get('u', ''), PARAMS.get('p', ''))
            notify(t(30048))
        elif action == 'unwatch':
            progress.set_watched(name, False, PARAMS.get('t', ''))
            notify(t(30052))
        elif action == 'forget':
            progress.forget(name)
            notify(t(30049))
    except playlist_store.StoreError as exc:
        log('posizione non aggiornata: %s' % exc)
        notify(t(30015), True)

    # La pagina aperta deve mostrare subito il segno nuovo.
    try:
        xbmc.executebuiltin('Container.Refresh')
    except Exception:
        log('aggiornamento della pagina non disponibile')
    end()


# --------------------------------------------------------------------------
# Sorgente A: YouTube (delegata a plugin.video.youtube)
# --------------------------------------------------------------------------
def show_youtube():
    if not youtube.available():
        notify(t(30009), True)
        end()
        return

    entries = youtube.entries(ADDON)
    if not entries:
        notify('Nessun canale configurato: aggiungine uno nelle impostazioni.', True)

    for label, target in entries:
        add_item(label, target, info={'plot': 'Canale o playlist gestiti dall\'addon YouTube.'})
    end()


# --------------------------------------------------------------------------
# Sorgente B: Internet Archive
# --------------------------------------------------------------------------
def show_archive_menu():
    add_item(t(30003), url(mode='archive_search'), art=source_art('search'))
    for label, query in archive_api.SUGGESTED_QUERIES:
        add_item(label, url(mode='archive_list', q=query, page=1))
    end()


def show_archive_search():
    text = ask_text(t(30003))
    if text:
        show_archive_list(text, 1)
    else:
        end()


def show_archive_list(query, page=1):
    rows = max(1, setting_int('ia_rows', 30))
    try:
        docs, total = archive_api.search(query, page=page, rows=rows)
    except archive_api.ArchiveError as exc:
        log('ricerca fallita: %s' % exc)
        notify(t(30006), True)
        end()
        return

    if not docs:
        notify(t(30004))

    for doc in docs:
        identifier = doc.get('identifier')
        if not identifier:
            continue
        title = doc.get('title') or identifier
        info = {'title': title, 'plot': (doc.get('description') or '')[:1500]}
        year = str(doc.get('year') or '')
        if year.isdigit():
            info['year'] = int(year)
        thumb = archive_api.thumbnail_url(identifier)
        info['mediatype'] = 'video'
        add_item(title,
                 url(mode='archive_item', id=identifier),
                 art={'thumb': thumb, 'fanart': thumb},
                 info=info)

    if page * rows < total:
        add_item(t(30005), url(mode='archive_list', q=query, page=page + 1))

    end('videos')


def episode_info(entry, show_title, meta, plot):
    """Metadati comuni alle schede di una puntata."""
    info = {
        'title': entry['title'] or entry['label'],
        'tvshowtitle': show_title,
        'plot': plot or ('%s - %s' % (show_title, entry['format'] or 'video')),
        'mediatype': 'episode',
    }
    if entry['season']:
        info['season'] = entry['season']
    if entry['episode']:
        info['episode'] = entry['episode']
    if entry['duration']:
        info['duration'] = entry['duration']
    if meta.get('creator'):
        info['studio'] = meta['creator']
    if meta.get('year'):
        info['year'] = meta['year']
    return info


def episode_details(entry):
    """'h.264 · 136.0 MB' accanto al titolo della puntata."""
    return ' \u00b7 '.join(part for part in (entry['format'], entry['size']) if part)


def show_archive_item(identifier):
    try:
        episodes, meta = archive_api.episodes(identifier)
    except archive_api.ArchiveError as exc:
        log('metadata fallita: %s' % exc)
        notify(t(30006), True)
        end()
        return

    if not episodes:
        notify(t(30008), True)
        end()
        return

    thumb = archive_api.thumbnail_url(identifier)
    width = naming.number_width([group['episode'] for group in episodes])
    show_title = meta.get('title') or identifier
    base_plot = meta.get('plot') or ''

    for group in episodes:
        files = group['files']
        preferred = files[0]
        title = entry_title(preferred)
        label = naming.episode_label(group['episode'], title, width)
        label = details_label(label, episode_details(preferred),
                              '%d versioni' % len(files) if len(files) > 1 else '')

        info = episode_info(preferred, show_title, meta, base_plot)
        info['sorttitle'] = label
        art = {'thumb': thumb, 'fanart': thumb}

        if len(files) > 1:
            # Una riga per puntata: le copie in altri formati stanno nel sottomenu.
            add_item(label,
                     url(mode='archive_versions', id=identifier,
                         ep=group['episode'], s=group['season'] or ''),
                     art=art, info=info)
        else:
            add_item(label, url(mode='play', u=preferred['url'], title=title),
                     art=art, info=info, playable=True)
    end('episodes')


def show_archive_versions(identifier, episode, season=None):
    try:
        files, meta = archive_api.episode_versions(identifier, episode, season)
    except archive_api.ArchiveError as exc:
        log('versioni non disponibili: %s' % exc)
        notify(t(30006), True)
        end()
        return

    if not files:
        notify(t(30008), True)
        end()
        return

    thumb = archive_api.thumbnail_url(identifier)
    width = naming.number_width([episode])
    show_title = meta.get('title') or identifier
    base_plot = meta.get('plot') or ''

    for index, entry in enumerate(files):
        title = entry_title(entry)
        label = naming.episode_label(entry['episode'], title, width)
        label = details_label(label, episode_details(entry),
                              t(30016) if index == 0 else '')

        info = episode_info(entry, show_title, meta, base_plot)
        info['sorttitle'] = label
        add_item(label, url(mode='play', u=entry['url'], title=title),
                 art={'thumb': thumb, 'fanart': thumb}, info=info,
                 playable=True)
    end('episodes')


# --------------------------------------------------------------------------
# Sorgente C: raccolta locale
# --------------------------------------------------------------------------
def show_local(path=''):
    root = path or setting_text('local_path', '')
    if not root:
        notify(t(30007), True)
        end()
        return
    if not local.is_available(root):
        notify('%s (%s)' % (t(30010), root), True)
        end()
        return

    try:
        folders, videos = local.scan(root)
    except OSError as exc:
        log('scansione fallita: %s' % exc)
        notify('%s (%s)' % (t(30010), root), True)
        end()
        return

    width = naming.number_width([item['episode'] for item in videos])

    for item in folders:
        add_item(item['label'], url(mode='local', path=item['path']), art=item['art'],
                 info={'title': item['label'], 'plot': item['path'],
                       'mediatype': 'tvshow'})

    for item in videos:
        label = naming.episode_label(item['episode'], item['title'], width)
        info = {
            'title': item['title'],
            'sorttitle': label,
            'plot': item['path'],
            'mediatype': 'episode',
        }
        if item['season']:
            info['season'] = item['season']
        if item['episode']:
            info['episode'] = item['episode']
        if item['size']:
            info['plot'] = '%s\n%s' % (item['path'], item['size'])
        add_item(label, url(mode='play', u=item['path'], title=label),
                 art=item['art'], info=info, playable=True)

    if not folders and not videos:
        notify('Cartella vuota: %s' % root)

    end('videos')


# --------------------------------------------------------------------------
# Sorgente D: liste M3U incollate e liste salvate permanenti
# --------------------------------------------------------------------------
def show_load():
    text = ask_text(t(30012), setting_text('m3u_url', ''))
    if not text:
        end()
        return
    try:
        ADDON.setSetting('m3u_url', text)
    except Exception:
        log('impostazione m3u_url non salvata')

    try:
        result = playlist.load(text)
    except playlist.PlaylistError as exc:
        log('lista non caricata (%s): %s' % (text, exc))
        notify(t(30015), True)
        end()
        return

    if result['stream']:
        entries = [{'name': suggest_name(result['url']), 'url': result['url'],
                    'logo': '', 'group': '',
                    'props': result.get('props') or {},
                    'headers': result.get('headers') or {}}]
        ask_save(result['url'], kind='stream',
                 props=result.get('props'), headers=result.get('headers'))
        autoplay = True
    else:
        entries = result['entries']
        ask_save(result['url'], entries=entries)
        autoplay = False

    try:
        playlist_store.save_session(result['url'], entries, autoplay=autoplay)
    except playlist_store.StoreError as exc:
        log('lista non tenuta in memoria: %s' % exc)
        notify(t(30015), True)
        end()
        return

    # L'elenco vive in una pagina sua: chiudendo un canale si torna li' e non
    # alla tastiera che chiede di nuovo il link.
    redirect(url(mode='loaded'))


def show_session():
    """La pagina dell'ultima lista incollata, riletta dalla copia locale."""
    try:
        session = playlist_store.load_session()
    except playlist_store.StoreError as exc:
        log('sessione non letta: %s' % exc)
        session = {}

    if not session:
        log('nessuna lista in memoria')
        notify(t(30015), True)
        end()
        return

    if session.get('autoplay') and session.get('url'):
        target = session['url']
        extra = entry_extra((session.get('entries') or [{}])[0])
        try:
            playlist_store.save_session(target, session.get('entries'),
                                        autoplay=False)
        except playlist_store.StoreError as exc:
            log('sessione non aggiornata: %s' % exc)
        play(target, extra=extra)
        return

    entries = session.get('entries') or []
    if not entries:
        notify(t(30015), True)
        end()
        return

    group = PARAMS.get('g')
    if group is not None:
        entries = playlist.in_group(entries, None if group == '*' else group)
        if not entries:
            notify(t(30015), True)
            end()
            return

    show_entries(entries, group=group)
    end('videos')


def ask_save(target, kind='list', entries=None, props=None, headers=None):
    """Tiene il link tra le sorgenti permanenti, con un nome scelto dall'utente."""
    if not confirm(t(30018)):
        return None
    name = ask_text(t(30017), suggest_name(target)) or suggest_name(target)
    try:
        saved = playlist_store.add(name, target, kind=kind,
                                   logo=first_logo(entries or []),
                                   entries=entries, props=props,
                                   headers=headers)
    except playlist_store.StoreError as exc:
        log('lista non salvata: %s' % exc)
        notify(t(30015), True)
        return None
    notify(t(30019))
    return saved


def show_entries(entries, refresh_target=None, page=None, group=None,
                 extra_rows=None, order=None, order_row=True, track=True):
    page = dict(page or {'mode': 'loaded'})
    order = order or list_order()
    grouped = playlist.has_groups(entries)

    if group is None and order == 'group' and grouped:
        show_group_rows(entries, page)
        current = 'group'
    else:
        # Senza group-title non si finge un raggruppamento: si mostra
        # l'elenco alfabetico e la riga dichiara l'ordine vero.
        shown = 'az' if order == 'group' else order
        current = shown
        for entry in playlist.sort_entries(entries, shown):
            # Nome e gruppo si ripuliscono anche qui e non solo al caricamento:
            # le copie in cache contengono ancora i valori sporchi delle liste
            # pubbliche ('[Geo-blocked]', 'Undefined').
            label = playlist.clean_name(entry.get('name') or '')
            entry_group = playlist.clean_group(entry.get('group'))
            if hidden.has_channel(label):
                # Nascosto dall'utente: la lista resta, la riga no.
                continue
            if entry_group and hidden.has_group(entry_group):
                continue
            hide_rows = hide_menu(label, entry_group)
            if entry_group and group is None:
                label += '  [COLOR=grey](%s)[/COLOR]' % entry_group
            variants = entry.get('variants') or []
            if len(variants) > 1:
                # Stesso canale con piu' flussi: si sceglie nel sottomenu.
                label += '  [COLOR=grey](%d)[/COLOR]' % len(variants)
                label = guide_label(label, entry)
                add_item(label, url(mode='tv_var', k=entry.get('key')),
                         art=logo_art(entry['logo']),
                         info={'title': label,
                               'plot': entry.get('plot') or entry['url'],
                               'mediatype': 'video'}, track=track,
                         context=hide_rows,
                         source={'title': playlist.clean_name(entry.get('name')),
                                 'url': variants[0]['url'],
                                 'extra': entry_extra(variants[0])})
                continue
            label = guide_label(label, entry)
            second = ''
            if entry.get('epg_next'):
                second = '%s: %s' % (t(30039), entry['epg_next'])
            add_item(label, entry_url(entry), art=logo_art(entry['logo']),
                     info={'title': playlist.clean_name(entry['name']),
                           'plot': entry.get('plot') or entry['url'],
                           'mediatype': 'video'},
                     playable=True, second=second, track=track,
                     context=hide_rows)

    if order_row:
        order_params = {'mode': 'order', 'back': url(**page), 'cur': current}
        if grouped:
            order_params['groups'] = '1'
        add_item('%s: %s' % (t(30025), order_label(current)),
                 url(**order_params))

    # Righe in coda alla sezione (per la TV: il filtro dei canali con guida).
    for label, target, art in extra_rows or []:
        add_item(label, target, art=art)

    if refresh_target:
        add_item(t(30020), refresh_target, art=source_art('lists'))

    show_hidden_row()


def show_group_rows(entries, page):
    """Elenco dei gruppi con quanti canali, piu' la voce per vederli tutti."""
    add_item('%s  [COLOR=grey](%d)[/COLOR]' % (t(30030), len(entries)),
             url(g='*', **page), info={'mediatype': 'video'})
    for name, count in playlist.groups(entries):
        if name and hidden.has_group(name):
            continue
        label = name or t(30031)
        add_item('%s  [COLOR=grey](%d)[/COLOR]' % (label, count),
                 url(g=name, **page),
                 info={'title': label, 'mediatype': 'video'},
                 context=hide_menu('', name))


def show_saved_list(list_id):
    entry = playlist_store.find(list_id)
    if not entry:
        log('lista salvata non trovata: %s' % list_id)
        notify(t(30015), True)
        end()
        return

    entries = playlist_store.entries(list_id)
    if not entries:
        # Prima apertura o copia locale persa: la lista si rilegge una volta.
        try:
            result = playlist.load(entry['url'])
        except playlist.PlaylistError as exc:
            log('lista salvata non riletta (%s): %s' % (entry['url'], exc))
            result = None
        if result and not result['stream'] and result['entries']:
            entries = result['entries']
            try:
                playlist_store.save_entries(list_id, entries,
                                            logo=first_logo(entries))
            except playlist_store.StoreError as exc:
                log('copia locale non aggiornata: %s' % exc)

    if not entries:
        notify(t(30015), True)
        end()
        return

    group = PARAMS.get('g')
    if group is not None:
        entries = playlist.in_group(entries, None if group == '*' else group)
        if not entries:
            notify(t(30015), True)
            end()
            return

    show_entries(entries, refresh_target=url(mode='list_refresh', id=list_id),
                 group=group, page={'mode': 'list', 'id': list_id})
    end('videos')


def refresh_list(list_id):
    entry = playlist_store.find(list_id)
    if not entry:
        show_saved_list(list_id)
        return

    try:
        result = playlist.load(entry['url'])
    except playlist.PlaylistError as exc:
        log('aggiornamento fallito (%s): %s' % (entry['url'], exc))
        notify(t(30024), True)
        show_saved_list(list_id)
        return

    if result['stream']:
        notify(t(30024), True)
        show_saved_list(list_id)
        return

    entries = result['entries']
    try:
        playlist_store.save_entries(list_id, entries, logo=first_logo(entries))
    except playlist_store.StoreError as exc:
        log('copia locale non aggiornata: %s' % exc)
        notify(t(30024), True)
    else:
        notify(t(30023))

    group = PARAMS.get('g')
    shown = playlist.in_group(entries, None if group in (None, '*') else group)
    show_entries(shown, refresh_target=url(mode='list_refresh', id=list_id),
                 group=group, page={'mode': 'list', 'id': list_id})
    end('videos')


def remove_list(list_id):
    entry = playlist_store.find(list_id)
    if entry and confirm(t(30022) % entry['name']):
        try:
            playlist_store.remove(list_id)
        except playlist_store.StoreError as exc:
            log('lista non rimossa: %s' % exc)
        else:
            notify(t(30021))
            xbmc.executebuiltin('Container.Refresh')
    end()


# --------------------------------------------------------------------------
# Sorgente E: TV in chiaro (lista pubblica + guida TV)
# --------------------------------------------------------------------------
def show_tv():
    """Canali in chiaro con logo e programma in onda, dalla lista pubblica."""
    started = time.time()
    try:
        entries = tv.channels(setting_text('tv_url', ''))
    except tv.TvError as exc:
        log('TV non disponibile: %s' % exc)
        notify(t(30034), True)
        end()
        return

    group = PARAMS.get('g')
    if group is not None:
        entries = playlist.in_group(entries, None if group == '*' else group)
        if not entries:
            notify(t(30035))
            end()
            return

    only = 'epg' if PARAMS.get('only') == 'epg' else ''
    try:
        guide = tv.guide(setting_text('epg_url', ''))
    except tv.TvError as exc:
        log('guida TV non disponibile: %s' % exc)
        guide = {}
    entries = tv.with_guide(entries, guide)
    # Le copie dello stesso canale (SD/HD/720p) stanno sotto una voce sola.
    entries = tv.group_channels(entries)
    guided = [entry for entry in entries if entry.get('epg_ok')]
    if not guided:
        # Meglio dirlo che mostrare 359 canali senza nemmeno una scritta.
        notify(t(30040), True)

    page = {'mode': 'tv'}
    if group is not None:
        page['g'] = group
    extra = []
    if only:
        if not guided:
            notify(t(30035))
            end()
            return
        # Torna all'elenco completo, senza il filtro.
        extra.append((t(30037), url(**page), source_art('tv')))
        entries = guided
        page['only'] = 'epg'
    elif guided:
        label = '%s  [COLOR=grey](%d)[/COLOR]' % (t(30036), len(guided))
        extra.append((label, url(only='epg', **page), source_art('tv')))

    # La TV segue l'ordine del telecomando (tv.channels lo ha gia' messo in
    # fila): niente riga "Ordine dei canali", che ripartirebbe dall'alfabetico.
    show_entries(entries, refresh_target=url(mode='tv_refresh'),
                 page=page, group=group, extra_rows=extra, order='file',
                 order_row=False, track=False)
    end('videos')
    log('TV: %d canali in %.2fs' % (len(entries), time.time() - started))


def show_tv_variants():
    """Sottomenu SD/HD di un canale che nella lista ha piu' flussi."""
    key = PARAMS.get('k', '')
    try:
        entries = tv.channels(setting_text('tv_url', ''))
    except tv.TvError as exc:
        log('TV non disponibile: %s' % exc)
        notify(t(30034), True)
        end()
        return
    try:
        guide = tv.guide(setting_text('epg_url', ''))
    except tv.TvError as exc:
        log('guida TV non disponibile: %s' % exc)
        guide = {}

    channels = tv.group_channels(tv.with_guide(entries, guide))
    channel = None
    for item in channels:
        if item.get('key') == key:
            channel = item
            break
    if not channel:
        notify(t(30035))
        end()
        return

    for variant in channel.get('variants') or []:
        # Il flusso senza sigla e' quello principale: se restasse senza nome
        # non si capirebbe cosa si sta per scegliere.
        label = variant.get('variant') or t(30041)
        label = guide_label(label, variant)
        second = ''
        if variant.get('epg_next'):
            second = '%s: %s' % (t(30039), variant['epg_next'])
        add_item(label, entry_url(variant), art=logo_art(variant.get('logo')),
                 info={'title': variant.get('name') or label,
                       'plot': variant.get('plot') or variant.get('url'),
                       'mediatype': 'video'},
                 playable=True, second=second, track=False)
    end('videos')


def refresh_tv():
    """Riscarica elenco canali e guida, poi torna alla sezione."""
    ok = True
    try:
        tv.channels(setting_text('tv_url', ''), force=True)
    except tv.TvError as exc:
        log('canali TV non aggiornati: %s' % exc)
        ok = False
    try:
        tv.guide(setting_text('epg_url', ''), force=True)
    except tv.TvError as exc:
        log('guida TV non aggiornata: %s' % exc)
    notify(t(30023) if ok else t(30024), not ok)
    redirect(url(mode='tv'))


# --------------------------------------------------------------------------
# Riproduzione
# --------------------------------------------------------------------------
MANIFEST_TYPES = (('.m3u8', 'hls'), ('.mpd', 'dash'), ('.ism', 'ism'))
MIME_TYPES = {'hls': 'application/vnd.apple.mpegurl',
              'dash': 'application/dash+xml'}
ADAPTIVE = 'inputstream.adaptive'


def manifest_type(target):
    path = urllib.parse.urlparse(target).path.lower()
    for extension, kind in MANIFEST_TYPES:
        if path.endswith(extension):
            return kind
    return ''


def migrate_settings(old, new):
    """Porta i valori delle impostazioni dal vecchio nome (una volta sola)."""
    source = os.path.join(old, 'settings.xml')
    if not os.path.isfile(source):
        return 0
    try:
        root = ET.parse(source).getroot()
    except (ET.ParseError, OSError) as exc:
        log('impostazioni del vecchio nome non lette: %s' % exc)
        return 0
    applied = 0
    for node in root.iter('setting'):
        key = node.get('id') or ''
        value = node.get('value')
        if key not in MIGRATED_SETTINGS or value is None:
            continue
        try:
            ADDON.setSetting(key, value)
            applied += 1
        except Exception as exc:
            log('impostazione %s non copiata: %s' % (key, exc))
    return applied


def migrate_profile():
    """Copia liste, sessione, ordine e impostazioni dal vecchio nome."""
    try:
        old = xbmcvfs.translatePath('special://profile/addon_data/' + OLD_ADDON_ID)
    except Exception:
        return
    new = profile_path()
    if not old or not new or not os.path.isdir(old):
        return
    copied = 0
    try:
        if not os.path.isdir(new):
            os.makedirs(new)
        for name in os.listdir(old):
            if not name.endswith('.json'):
                continue
            source = os.path.join(old, name)
            target = os.path.join(new, name)
            if os.path.isfile(source) and not os.path.exists(target):
                shutil.copyfile(source, target)
                copied += 1
    except OSError as exc:
        log('migrazione dal vecchio nome non riuscita: %s' % exc)
        return
    marker = os.path.join(new, MIGRATION_MARKER)
    applied = 0
    if not os.path.isfile(marker):
        applied = migrate_settings(old, new)
        try:
            with open(marker, 'w', encoding='utf-8') as handle:
                json.dump({'from': OLD_ADDON_ID}, handle)
        except OSError as exc:
            log('segno di migrazione non scritto: %s' % exc)

    if copied or applied:
        log('dal vecchio nome: %d file, %d impostazioni' % (copied, applied))


def read_setup(extra):
    """(proprieta', header) trasportati nel parametro p della voce."""
    setup = {}
    if extra:
        try:
            setup = json.loads(extra)
        except ValueError:
            log('proprieta illeggibili: %s' % extra[:80])
    return dict(setup.get('props') or {}), (setup.get('headers') or {})


def use_adaptive():
    """Flussi HLS/DASH all'addon adaptive, se c'e' e non e' spento."""
    if not setting_bool('isa_manifests', True):
        return False
    try:
        return bool(xbmc.getCondVisibility('System.HasAddon(%s)' % ADAPTIVE))
    except Exception:
        return False


def apply_stream_props(item, target, extra):
    """Adatta la voce al manifest; restituisce il link da riprodurre."""
    props, headers = read_setup(extra)

    # Un #KODIPROP:inputstream=... puo' scegliere l'addon (o un altro).
    explicit = props.pop('inputstream', '')
    kind = props.get('inputstream.adaptive.manifest_type') or manifest_type(target)
    if (not explicit and kind and use_adaptive() and
            target.startswith(('http://', 'https://'))):
        # Manifest di rete senza direttive: adaptive tiene il buffer a
        # segmenti e rilegge il manifest live; il demuxer predefinito no, e
        # le dirette vanno a scatti.
        explicit = ADAPTIVE

    if not explicit and not kind:
        # Solo #EXTVLCOPT su un file diretto: niente adaptive. Il player
        # predefinito prende gli header in coda al link (come World Live TV).
        if headers:
            log('header nel link: %s' % target)
            target = '%s|%s' % (target, '&'.join('%s=%s' % pair
                                                 for pair in headers.items()))
        return target

    if not props and not headers and not explicit:
        # Manifest senza direttive e adaptive spento: player predefinito.
        return target

    item.setContentLookup(False)
    if explicit:
        item.setProperty('inputstream', explicit)
    for key, value in props.items():
        item.setProperty(key, value)
    if kind:
        item.setProperty('inputstream.adaptive.manifest_type', kind)
        if kind in MIME_TYPES:
            item.setMimeType(MIME_TYPES[kind])
    if headers:
        item.setProperty('inputstream.adaptive.stream_headers',
                         '&'.join('%s=%s' % pair for pair in headers.items()))
    return target


def play(target, title='', extra=''):
    log('riproduco: %s' % target)
    source = target
    item = xbmcgui.ListItem(path=target, offscreen=True)
    if title:
        item.setInfo('video', {'title': title})
    start = progress.resume(title) if title else 0
    if start:
        # Kodi legge StartOffset prima di aprire il flusso: il video riparte
        # da dove era rimasto, senza un salto visibile a riproduzione avviata.
        item.setProperty('StartOffset', str(int(start)))
        log('riprendo da %s: %s' % (progress.time_text(start), title))
    target = apply_stream_props(item, target, extra)
    item.setPath(target)
    chosen = item.getProperty('inputstream') or 'predefinito (demuxer Kodi)'
    manifest = item.getProperty('inputstream.adaptive.manifest_type') or '-'
    log('player scelto: %s | manifest: %s' % (chosen, manifest))
    xbmcplugin.setResolvedUrl(HANDLE, True, item)
    if title:
        # Copertina arrivata col link: si salva con la posizione, cosi' la
        # pagina Continua mostra il logo invece dell'icona generica.
        art = {}
        if PARAMS.get('at'):
            art['thumb'] = PARAMS['at']
        if PARAMS.get('af'):
            art['fanart'] = PARAMS['af']
        # Il servizio in sottofondo segue la riproduzione e salva la posizione:
        # questa pagina puo' chiudersi subito, la posizione non si perde.
        try:
            progress.begin(title, PARAMS.get('u') or source, extra, start, art)
        except playlist_store.StoreError as exc:
            log('posizione non seguita: %s' % exc)


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------
def main():
    migrate_profile()
    mode = PARAMS.get('mode', 'root')
    log('mode=%s params=%s' % (mode, PARAMS))

    if mode == 'root':
        show_root()
    elif mode == 'youtube':
        show_youtube()
    elif mode == 'archive':
        show_archive_menu()
    elif mode == 'archive_search':
        show_archive_search()
    elif mode == 'archive_list':
        show_archive_list(PARAMS.get('q', ''), int(PARAMS.get('page', 1) or 1))
    elif mode == 'archive_item':
        show_archive_item(PARAMS.get('id', ''))
    elif mode == 'archive_versions':
        show_archive_versions(PARAMS.get('id', ''),
                              int(PARAMS.get('ep', 0) or 0),
                              int(PARAMS.get('s') or 0) or None)
    elif mode == 'local':
        show_local(PARAMS.get('path', ''))
    elif mode == 'load':
        show_load()
    elif mode == 'loaded':
        show_session()
    elif mode == 'list':
        show_saved_list(PARAMS.get('id', ''))
    elif mode == 'list_refresh':
        refresh_list(PARAMS.get('id', ''))
    elif mode == 'list_remove':
        remove_list(PARAMS.get('id', ''))
    elif mode == 'tv':
        show_tv()
    elif mode == 'tv_var':
        show_tv_variants()
    elif mode == 'tv_refresh':
        refresh_tv()
    elif mode == 'favorites':
        show_favorites()
    elif mode == 'favorite':
        favorite_action()
    elif mode == 'hide':
        hide_action()
    elif mode == 'hidden':
        show_hidden()
    elif mode == 'unhide':
        unhide_action()
    elif mode == 'search':
        show_search()
    elif mode == 'search_results':
        show_search_results(PARAMS.get('q', ''))
    elif mode == 'continue':
        show_continue()
    elif mode == 'progress':
        progress_action()
    elif mode == 'order':
        choose_order(PARAMS.get('back', ''), PARAMS.get('groups') == '1',
                     PARAMS.get('cur', ''))
    elif mode == 'play':
        play(PARAMS.get('u', ''), PARAMS.get('title', ''), PARAMS.get('p', ''))
    else:
        log('modo sconosciuto: %s' % mode)
        show_root()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        log(traceback.format_exc())
        notify('Errore: %s' % error, True)
        try:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        except Exception:
            pass
