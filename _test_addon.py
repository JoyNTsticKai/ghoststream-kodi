# -*- coding: utf-8 -*-
"""Prove dell'addon senza Kodi: stub minimi + rete reale.

    python _test_addon.py
"""

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import types
import urllib.parse

try:
    # Le etichette TV contengono la freccia del 'Dopo': la console Windows
    # in cp1252 non saprebbe scriverla e la prova si fermerebbe.
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ITEMS = []
RESOLVED = []
SETTINGS = {
    'source_load': 'true',
    'source_youtube': 'false',
    'source_archive': 'false',
    'source_local': 'false',
    'ia_rows': '30',
    'local_path': '',
    'm3u_url': '',
    'yt_extra': '',
    'source_tv': 'false',
    'tv_url': '',
    'epg_url': '',
}

PROFILE = 'special://profile/addon_data/plugin.video.ghoststream/'
PROFILE_ROOT = ''
BUILTINS = []


class ListItem(object):
    def __init__(self, label='', offscreen=False, path=''):
        self.label = label
        self.label2 = ''
        self.path = path
        self.art = {}
        self.info = {}
        self.props = {}
        self.context = []
        self.mime = ''
        self.content_lookup = True

    def setContentLookup(self, enabled):
        self.content_lookup = enabled

    def setMimeType(self, mime):
        self.mime = mime

    def setLabel2(self, text):
        self.label2 = text

    def setArt(self, art):
        self.art.update(art)

    def setInfo(self, kind, info):
        self.info.update(info)

    def setPath(self, path):
        self.path = path

    def setProperty(self, key, value):
        self.props[key] = value

    def getProperty(self, key):
        return self.props.get(key, '')

    def addContextMenuItems(self, items, replaceItems=False):
        self.context = list(items)


class Keyboard(object):
    TEXT = ''
    QUEUE = []

    def __init__(self, default='', heading='', hidden=False):
        self._text = default
        self.heading = heading

    def doModal(self):
        self._text = Keyboard.QUEUE.pop(0) if Keyboard.QUEUE else Keyboard.TEXT

    def isConfirmed(self):
        return bool(self._text)

    def getText(self):
        return self._text


class Dialog(object):
    ANSWER = False
    SELECT = -1
    OPTIONS = []

    def notification(self, *args, **kwargs):
        pass

    def yesno(self, *args, **kwargs):
        return Dialog.ANSWER

    def select(self, heading, options, **kwargs):
        Dialog.OPTIONS = list(options)
        return Dialog.SELECT


xbmc = types.ModuleType('xbmc')
xbmc.LOGINFO = 1
xbmc.LOGERROR = 4
LOGS = []
xbmc.log = lambda message, *args, **kwargs: LOGS.append(message)
xbmc.Keyboard = Keyboard
xbmc.executebuiltin = lambda command, *args, **kwargs: BUILTINS.append(command)
xbmc.sleep = lambda milliseconds: None
xbmc.getSkinDir = lambda: 'skin.test'
xbmc.getCondVisibility = (lambda condition: 'inputstream.adaptive' in condition)

xbmcgui = types.ModuleType('xbmcgui')
xbmcgui.ListItem = ListItem
xbmcgui.Dialog = Dialog
xbmcgui.NOTIFICATION_INFO = 'info'
xbmcgui.NOTIFICATION_ERROR = 'error'

xbmcplugin = types.ModuleType('xbmcplugin')


def addDirectoryItem(handle, target, item, isFolder=True):
    ITEMS.append({'label': item.label, 'label2': item.label2, 'url': target,
                  'folder': isFolder,
                  'art': dict(item.art), 'info': dict(item.info),
                  'context': list(item.context)})
    return True


def setResolvedUrl(handle, succeeded, item):
    RESOLVED.append({'ok': succeeded, 'path': item.path, 'label': item.label,
                     'props': dict(item.props), 'mime': item.mime,
                     'content_lookup': item.content_lookup})


END = []


def endOfDirectory(*args, **kwargs):
    END.append(kwargs)


xbmcplugin.addDirectoryItem = addDirectoryItem
xbmcplugin.endOfDirectory = endOfDirectory
xbmcplugin.setContent = lambda *args, **kwargs: None
xbmcplugin.setResolvedUrl = setResolvedUrl

xbmcaddon = types.ModuleType('xbmcaddon')


class Addon(object):
    def __init__(self, *args, **kwargs):
        pass

    def getAddonInfo(self, key):
        return {
            'id': 'plugin.video.ghoststream',
            'name': 'Cartoni',
            'path': os.path.abspath('plugin.video.ghoststream'),
            'profile': PROFILE,
        }.get(key, '')

    def getLocalizedString(self, string_id):
        return ''

    def getSetting(self, key):
        return SETTINGS.get(key, '')

    def getSettingString(self, key):
        return SETTINGS.get(key, '')

    def getSettingBool(self, key):
        return SETTINGS.get(key, 'true').lower() == 'true'

    def getSettingInt(self, key):
        try:
            return int(SETTINGS.get(key, '0'))
        except (TypeError, ValueError):
            return 0

    def setSetting(self, key, value):
        SETTINGS[key] = value


xbmcaddon.Addon = Addon

xbmcvfs = types.ModuleType('xbmcvfs')


def translatePath(path):
    return path.replace(
        'special://database', os.path.join(workdir, 'database')).replace(
        'special://profile/addon_data/plugin.video.ghoststream/',
        PROFILE_ROOT).replace(
        'special://profile/addon_data/plugin.video.cartonitalia',
        os.path.join(PROFILE_ROOT, 'plugin.video.cartonitalia'))


xbmcvfs.translatePath = translatePath

sys.modules['xbmc'] = xbmc
sys.modules['xbmcgui'] = xbmcgui
sys.modules['xbmcplugin'] = xbmcplugin
sys.modules['xbmcaddon'] = xbmcaddon
sys.modules['xbmcvfs'] = xbmcvfs

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'plugin.video.ghoststream'))

from resources.lib import (archive_api, playlist, playlist_store, tv,  # noqa: E402
                           views)


def run(param=''):
    ITEMS[:] = []
    RESOLVED[:] = []
    BUILTINS[:] = []
    END[:] = []
    sys.argv = ['plugin://plugin.video.ghoststream/', '7', param]
    import default
    importlib.reload(default)
    default.main()


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('  ok  %s' % message)


workdir = tempfile.mkdtemp(prefix='cartoni-')
PROFILE_ROOT = os.path.join(workdir, 'addon_data') + '/'

print('1) menu principale')
SETTINGS['source_youtube'] = 'false'
SETTINGS['source_archive'] = 'false'
run('')
labels = [item['label'] for item in ITEMS]
check(labels == ['Carica un link (M3U o video)'], 'voce Carica nel menu: %s' % labels)
check(ITEMS[0]['art']['thumb'].endswith('load.png'), 'icona dedicata load.png')

print('2) lista locale caricata a mano')
lista = os.path.join(workdir, 'mia lista.m3u')
with open(lista, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n')
    handle.write('#EXTINF:-1 tvg-logo="http://example.com/ken.png" '
                 'group-title="Cartoni",Ken il Guerriero - Ep 1\n')
    handle.write('http://example.com/ken1.mp4\n')
    handle.write('#KODIPROP:inputstream=foo\n')
    handle.write('#EXTINF:-1 tvg-name="Solo nome",\n')
    handle.write('http://example.com/solo.m3u8\n')
Keyboard.QUEUE = [lista]
run('?mode=load')
check(any('mode=loaded' in command for command in BUILTINS),
      'dopo il link si passa alla pagina della lista, non si resta sulla tastiera')
check(len(ITEMS) == 0, 'la pagina del link non elenca nulla')
check(SETTINGS['m3u_url'] == lista, 'ultimo link salvato')
run('?mode=loaded')
print('   voci: %s' % [item['label'] for item in ITEMS])
check(len(ITEMS) == 3, 'due voci e la riga dell ordine, righe # ignorate')
check(ITEMS[0]['label'].startswith('Ken il Guerriero - Ep 1'), 'nome dopo la virgola')
check(ITEMS[0]['art']['thumb'] == 'http://example.com/ken.png', 'logo tvg-logo usato')
check('(Cartoni)' in ITEMS[0]['label'], 'gruppo accanto al nome')
check(ITEMS[1]['label'] == 'Solo nome', 'tvg-name usato quando il nome manca')
check(ITEMS[0]['folder'] is False and ITEMS[1]['folder'] is False, 'voci riproducibili')

print('3) playlist HLS -> riproduzione diretta')
hls = os.path.join(workdir, 'flusso.m3u8')
with open(hls, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\nsegment0.ts\n')
Keyboard.QUEUE = [hls]
run('?mode=load')
run('?mode=loaded')
check(len(ITEMS) == 0 and len(RESOLVED) == 1 and RESOLVED[0]['path'] == hls,
      'la playlist HLS viene riprodotta, non elencata')
run('?mode=loaded')
check(len(ITEMS) == 2 and ITEMS[0]['folder'] is False,
      'chiudendo il flusso si torna alla sua voce, non alla tastiera')

print('4) link diretti e testo cp1252')
check(playlist.load('https://archive.org/download/Ken/x.mp4')['stream'] is True,
      'un .mp4 non viene scaricato')
check(playlist.load('https://example.com/film.mpd')['stream'] is True, 'un .mpd e diretto')
check(playlist.normalize(' www.esempio.it/lista.m3u') == 'http://www.esempio.it/lista.m3u',
      'link senza schema completato')
check(playlist.normalize('C:\\liste\\mia.m3u') == 'C:\\liste\\mia.m3u', 'percorso Windows intatto')
entries = playlist.parse(playlist.decode(b'#EXTINF:-1,Citt\xe0 mia\nhttp://x/y.mp4\n'))
check(entries[0]['name'] == 'Citt\xe0 mia', 'lista cp1252 decodificata')

print('5) raggruppamento puntate su archive.org (dati reali)')
try:
    groups, meta = archive_api.episodes('Ken_il-Guerriero')
    print('   puntate: %d, versioni nella prima: %s'
          % (len(groups), [entry['format'] for entry in groups[0]['files']]))
    check(len(groups) > 50, 'puntate raggruppate')
    check(len(groups[0]['files']) > 1, 'copie dello stesso episodio nello stesso gruppo')
    check(len({group['episode'] for group in groups}) == len(groups), 'nessuna puntata doppia')
except archive_api.ArchiveError as exc:
    print('  --  rete non disponibile, prova saltata: %s' % exc)

print('6) elenco a una riga per puntata')
FAKE = [
    {'title': 'Il ritorno', 'label': 'ep01.mkv', 'season': None, 'episode': 1,
     'format': 'Matroska', 'size': '516.0 MB', 'duration': 1456, 'priority': 0,
     'url': 'http://example.com/01.mkv'},
    {'title': 'Il ritorno', 'label': 'ep01.mp4', 'season': None, 'episode': 1,
     'format': 'h.264', 'size': '136.0 MB', 'duration': 1456, 'priority': 3,
     'url': 'http://example.com/01.mp4'},
    {'title': 'La sfida', 'label': 'ep02.mp4', 'season': None, 'episode': 2,
     'format': 'h.264', 'size': '140.0 MB', 'duration': 1440, 'priority': 3,
     'url': 'http://example.com/02.mp4'},
    {'title': 'La fine', 'label': 'ep10.mp4', 'season': None, 'episode': 10,
     'format': 'h.264', 'size': '141.0 MB', 'duration': 1440, 'priority': 3,
     'url': 'http://example.com/10.mp4'},
]
META = {'title': 'Ken il Guerriero', 'plot': 'Trama.', 'creator': 'Autore', 'year': 1986}
archive_api.playable_files = lambda identifier: ([dict(entry) for entry in FAKE], dict(META))

SETTINGS['source_archive'] = 'true'
run('?mode=archive_item&id=Ken')
print('   voci: %s' % [item['label'] for item in ITEMS])
check(len(ITEMS) == 3, 'tre puntate, non quattro file')
check('(h.264' in ITEMS[0]['label'] and '2 versioni' in ITEMS[0]['label'],
      'formato preferito e numero di versioni sulla riga')
check(ITEMS[0]['folder'] is True, 'la puntata con piu formati apre il sottomenu')
check('mode=archive_versions' in ITEMS[0]['url'] and 'ep=1' in ITEMS[0]['url'],
      'il sottomenu porta alla puntata giusta')
check(ITEMS[1]['folder'] is False and 'mode=play' in ITEMS[1]['url'],
      'la puntata con un solo formato si riproduce subito')
check([item['info'].get('episode') for item in ITEMS] == [1, 2, 10], 'puntate in ordine')
check('516' not in ITEMS[0]['label'], 'la copia pesante non compare in elenco')

print('7) sottomenu delle versioni')
run('?mode=archive_versions&id=Ken&ep=1')
print('   voci: %s' % [item['label'] for item in ITEMS])
check(len(ITEMS) == 2, 'due versioni della puntata 1')
check(ITEMS[0]['label'].startswith('01. Il ritorno'), 'etichetta con numero di puntata')
check('h.264' in ITEMS[0]['label'] and 'consigliato' in ITEMS[0]['label'],
      'la versione preferita e segnalata')
check('u=http://example.com/01.mp4' in urllib.parse.unquote(ITEMS[0]['url']),
      'la preferita e il file piccolo')
check('Matroska' in ITEMS[1]['label'] and 'consigliato' not in ITEMS[1]['label'],
      'le altre versioni sono sotto, senza etichetta')
check(all(item['folder'] is False for item in ITEMS), 'ogni versione e riproducibile')

run('?mode=archive_versions&id=Ken&ep=99')
check(len(ITEMS) == 0, 'puntata inesistente: elenco vuoto, nessun errore')

print('8) liste salvate permanenti')
Dialog.ANSWER = True
SETTINGS['source_archive'] = 'false'
Keyboard.QUEUE = [lista, 'La mia lista']
run('?mode=load')
run('?mode=loaded')
check(len(ITEMS) == 3, 'la lista incollata mostra le sue voci e l ordine')
check(os.path.isfile(os.path.join(PROFILE_ROOT, 'lists.json')),
      'indice scritto nella cartella dati tradotta (special://)')

run('')
labels = [item['label'] for item in ITEMS]
print('   menu: %s' % labels)
check(labels == ['Carica un link (M3U o video)', 'La mia lista'],
      'la lista salvata compare nel menu principale')
check(ITEMS[1]['folder'] is True, 'la lista salvata apre un elenco')
check(ITEMS[1]['art']['thumb'] == 'http://example.com/ken.png',
      'logo della prima voce come copertina')
check(ITEMS[1]['context'] and 'list_remove' in ITEMS[1]['context'][0][1],
      'voce Rimuovi nel menu contestuale')

list_id = urllib.parse.parse_qs(
    urllib.parse.urlparse(ITEMS[1]['url']).query)['id'][0]
run('?mode=list&id=%s' % list_id)
print('   voci: %s' % [item['label'] for item in ITEMS])
check(len(ITEMS) == 4, 'due canali, ordine e comando Aggiorna')
check(ITEMS[-1]['label'] == 'Aggiorna la lista' and ITEMS[-1]['folder'] is True,
      'in fondo la riga per rileggere il link')

original_load = playlist.load


def broken_load(*args, **kwargs):
    raise playlist.PlaylistError('rete spenta')


playlist.load = broken_load
run('?mode=list&id=%s' % list_id)
check(len(ITEMS) == 4, 'la lista si apre dalla copia locale, anche senza rete')
playlist.load = original_load

with open(lista, 'a', encoding='utf-8') as handle:
    handle.write('#EXTINF:-1,Nuovo canale\nhttp://example.com/nuovo.mp4\n')
run('?mode=list_refresh&id=%s' % list_id)
check(len(ITEMS) == 5, 'dopo Aggiorna c e la voce nuova')
run('?mode=list&id=%s' % list_id)
check(len(ITEMS) == 5, 'la copia locale e stata riscritta')

Keyboard.QUEUE = ['http://example.com/film.mp4', 'Film intero']
run('?mode=load')
run('?mode=loaded')
check(len(RESOLVED) == 1 and RESOLVED[0]['path'] == 'http://example.com/film.mp4',
      'un video singolo parte subito')
run('?mode=loaded')
check(len(ITEMS) == 2 and ITEMS[0]['folder'] is False,
      'chiudendo il video si torna alla sua riga, non alla tastiera')
run('')
labels = [item['label'] for item in ITEMS]
print('   menu: %s' % labels)
check('Film intero' in labels, 'anche il video singolo resta tra le sorgenti')
film = [item for item in ITEMS if item['label'] == 'Film intero'][0]
check(film['folder'] is False and 'mode=play' in film['url'],
      'la riga del video e riproducibile')
check(film['art']['thumb'].endswith('lists.png'), 'icona lists.png se manca un logo')

run('?mode=list_remove&id=%s' % list_id)
run('')
labels = [item['label'] for item in ITEMS]
check('La mia lista' not in labels, 'la lista rimossa sparisce dal menu')
check('Film intero' in labels, 'le altre sorgenti restano')

print('9) KODIPROP e inputstream.adaptive')
Dialog.ANSWER = False
testo = ('#EXTM3U\n'
         '#EXTINF:-1,Canale HLS\n'
         '#KODIPROP:inputstream.adaptive.manifest_type=hls\n'
         '#KODIPROP:inputstream.adaptive.license_type=clearkey\n'
         '#EXTVLCOPT:http-user-agent=TestUA\n'
         '#EXTVLCOPT:http-referrer=http://example.com/\n'
         'http://example.com/live/index.m3u8\n'
         '#EXTINF:-1,Canale normale\n'
         'http://example.com/altro.m3u8\n')
entries = playlist.parse(testo)
check(entries[0]['props']['inputstream.adaptive.manifest_type'] == 'hls',
      'manifest_type letto dal KODIPROP')
check(entries[0]['props']['inputstream.adaptive.license_type'] == 'clearkey',
      'altre proprieta KODIPROP conservate')
check(entries[0]['headers'] == {'User-Agent': 'TestUA',
                                'Referer': 'http://example.com/'},
      'EXTVLCOPT trasformato in header')
check(entries[1]['props'] == {} and entries[1]['headers'] == {},
      'le direttive non passano alla voce successiva')

misto = os.path.join(workdir, 'adaptive.m3u')
with open(misto, 'w', encoding='utf-8') as handle:
    handle.write(testo)
Keyboard.QUEUE = [misto]
run('?mode=load')
run('?mode=loaded')
check(len(ITEMS) == 3, 'lista con KODIPROP elencata')
urls = [urllib.parse.urlparse(item['url']).query for item in ITEMS]
check('p=' in urls[0], 'le proprieta viaggiano con la voce')
run('?' + urls[0])
resolved = RESOLVED[-1]
check(resolved['props'].get('inputstream') == 'inputstream.adaptive',
      'riproduzione affidata a inputstream.adaptive')
check(resolved['props'].get('inputstream.adaptive.manifest_type') == 'hls',
      'manifest_type hls')
check(resolved['props'].get('inputstream.adaptive.license_type') == 'clearkey',
      'license_type passato')
check(resolved['props'].get('inputstream.adaptive.stream_headers') ==
      'User-Agent=TestUA&Referer=http://example.com/', 'header HTTP passati')
check(resolved['mime'] == 'application/vnd.apple.mpegurl' and
      resolved['content_lookup'] is False, 'mime HLS e lookup disattivato')

query = urls[1]
run('?' + query)
check(RESOLVED[-1]['props'].get('inputstream') == 'inputstream.adaptive' and
      RESOLVED[-1]['mime'] == 'application/vnd.apple.mpegurl',
      'un manifest di rete senza direttive va al buffer di adaptive')
check([line for line in LOGS if 'player scelto' in line],
      'il log della riproduzione dice quale player e stato scelto')
check(any('player scelto: inputstream.adaptive' in line for line in LOGS),
      'il log nomina inputstream.adaptive quando lo usa')

SETTINGS['isa_manifests'] = 'false'
run('?' + query)
check(RESOLVED[-1]['props'] == {} and RESOLVED[-1]['content_lookup'] is True,
      'con la spunta tolta il manifest torna al player predefinito')
SETTINGS['isa_manifests'] = 'true'

hls_direct = os.path.join(workdir, 'con-kodiprop.m3u8')
with open(hls_direct, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n#KODIPROP:inputstream.adaptive.manifest_type=hls\n')
    handle.write('#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\nseg0.ts\n')
result = playlist.load(hls_direct)
check(result['stream'] and
      result['props'].get('inputstream.adaptive.manifest_type') == 'hls',
      'KODIPROP conservato anche per un flusso HLS diretto')
Keyboard.QUEUE = [hls_direct]
run('?mode=load')
run('?mode=loaded')
check(RESOLVED[-1]['props'].get('inputstream.adaptive.manifest_type') == 'hls',
      'anche il flusso incollato parte con inputstream.adaptive')

print('10) direttive su file diretti: adaptive solo con un manifest')
for nome in ('film.mp4', 'flusso.ts'):
    diretto = os.path.join(workdir, 'header-' + nome.replace('.', '-') + '.m3u')
    with open(diretto, 'w', encoding='utf-8') as handle:
        handle.write('#EXTM3U\n#EXTINF:-1,Voce\n')
        handle.write('#EXTVLCOPT:http-user-agent=TestUA\n')
        handle.write('http://example.com/%s\n' % nome)
    Keyboard.QUEUE = [diretto]
    run('?mode=load')
    run('?mode=loaded')
    query = urllib.parse.urlparse(ITEMS[0]['url']).query
    run('?' + query)
    check(RESOLVED[-1]['props'] == {} and RESOLVED[-1]['content_lookup'] is True,
          '%s con soli #EXTVLCOPT: player predefinito' % nome)
    check(RESOLVED[-1]['path'].endswith('|User-Agent=TestUA'),
          '%s: header in coda al link (stile World Live TV)' % nome)

esplicito = os.path.join(workdir, 'esplicito.m3u')
with open(esplicito, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n#EXTINF:-1,Voce\n')
    handle.write('#KODIPROP:inputstream=inputstream.adaptive\n')
    handle.write('#EXTVLCOPT:http-user-agent=TestUA\n')
    handle.write('http://example.com/film.mp4\n')
Keyboard.QUEUE = [esplicito]
run('?mode=load')
run('?mode=loaded')
query = urllib.parse.urlparse(ITEMS[0]['url']).query
run('?' + query)
check(RESOLVED[-1]['props'].get('inputstream') == 'inputstream.adaptive' and
      RESOLVED[-1]['props'].get('inputstream.adaptive.stream_headers') ==
      'User-Agent=TestUA',
      'KODIPROP inputstream esplicito: adaptive anche su un file diretto')

print('11) sorgente video singolo con direttive')
Dialog.ANSWER = True
Keyboard.QUEUE = [hls_direct, 'HLS con proprieta']
run('?mode=load')
run('')
labels = [item['label'] for item in ITEMS]
check('HLS con proprieta' in labels, 'la sorgente compare nel menu')
voce = [item for item in ITEMS if item['label'] == 'HLS con proprieta'][0]
query = urllib.parse.urlparse(voce['url']).query
check('p=' in query, 'la riga salvata porta con se le proprieta')
run('?' + query)
check(RESOLVED[-1]['props'].get('inputstream.adaptive.manifest_type') == 'hls',
      'riaprendo la sorgente si riproduce con le stesse proprieta')

print('12) ordine dei canali (alfabetico, gruppi, numero)')
playlist_store.save_order('az')
canali = os.path.join(workdir, 'canali.m3u')
with open(canali, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n')
    handle.write('#EXTINF:-1 tvg-chno="12" group-title="Rai",Il Telegiornale\n')
    handle.write('http://example.com/tg.m3u8\n')
    handle.write('#EXTINF:-1 tvg-chno="2" group-title="Rai",Zeta Uno\n')
    handle.write('http://example.com/zeta.m3u8\n')
    handle.write('#EXTINF:-1 tvg-chno="7" group-title="Sport",Alfa Sport\n')
    handle.write('http://example.com/alfa.m3u8\n')

voci = playlist.parse(open(canali, encoding='utf-8').read())
check([voce['number'] for voce in voci] == [12, 2, 7], 'tvg-chno letto')
check(all(voce['live'] for voce in voci), 'canali riconosciuti come dirette')
check([voce['name'] for voce in playlist.sort_entries(voci, 'az')]
      == ['Alfa Sport', 'Il Telegiornale', 'Zeta Uno'],
      'sort_entries alfabetico con articoli ignorati')

Dialog.ANSWER = False
Keyboard.QUEUE = [canali]
run('?mode=load')
run('?mode=loaded')
labels = [item['label'] for item in ITEMS]
print('   voci: %s' % labels)
check(labels[:3] == ['Alfa Sport  [COLOR=grey](Sport)[/COLOR]',
                     'Il Telegiornale  [COLOR=grey](Rai)[/COLOR]',
                     'Zeta Uno  [COLOR=grey](Rai)[/COLOR]'],
      'lista in ordine alfabetico')
check(labels[3].startswith('Ordine dei canali: Alfabetico'),
      'riga per scegliere l\'ordine')

playlist_store.save_order('group')
run('?mode=loaded')
labels = [item['label'] for item in ITEMS]
print('   gruppi: %s' % labels)
check(labels[:3] == ['Tutti i canali  [COLOR=grey](3)[/COLOR]',
                     'Rai  [COLOR=grey](2)[/COLOR]',
                     'Sport  [COLOR=grey](1)[/COLOR]'],
      'gruppi con conteggio, in ordine alfabetico')
query = urllib.parse.urlparse(ITEMS[1]['url']).query
check('g=Rai' in query, 'la riga del gruppo porta il nome')
run('?' + query)
labels = [item['label'] for item in ITEMS]
check(labels[:2] == ['Il Telegiornale', 'Zeta Uno'],
      'dentro il gruppo solo i suoi canali')

playlist_store.save_order('number')
run('?mode=loaded')
names = [item['label'].split('  ')[0] for item in ITEMS[:3]]
check(names == ['Zeta Uno', 'Alfa Sport', 'Il Telegiornale'],
      'ordine per numero di canale')

playlist_store.save_order('file')
run('?mode=loaded')
names = [item['label'].split('  ')[0] for item in ITEMS[:3]]
check(names == ['Il Telegiornale', 'Zeta Uno', 'Alfa Sport'],
      'ordine come nel file')

playlist_store.save_order('az')
run('?mode=loaded')
row = [item for item in ITEMS if item['label'].startswith('Ordine dei canali')][0]
Dialog.SELECT = 1
run('?' + urllib.parse.urlparse(row['url']).query)
check(playlist_store.load_order() == 'group', 'scelta dell\'ordine salvata')
check(any('mode=loaded' in command for command in BUILTINS),
      'dopo la scelta si torna alla lista')
Dialog.SELECT = -1

Dialog.ANSWER = True
Keyboard.QUEUE = [canali, 'Canali TV']
run('?mode=load')
run('')
voce = [item for item in ITEMS if item['label'] == 'Canali TV'][0]
run('?' + urllib.parse.urlparse(voce['url']).query)
print('   salvata: %s' % [item['label'] for item in ITEMS])
check(len(ITEMS) == 5 and ITEMS[1]['label'].startswith('Rai'),
      'lista salvata: gruppi in ordine')
query = urllib.parse.urlparse(ITEMS[2]['url']).query
run('?' + query)
check(len(ITEMS) == 3 and ITEMS[0]['label'] == 'Alfa Sport',
      'gruppo di una lista salvata filtrato')

print('13) lista senza group-title')
playlist_store.save_order('az')
senza = os.path.join(workdir, 'senza-gruppi.m3u')
with open(senza, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n')
    handle.write('#EXTINF:-1 tvg-chno="5",Rete Uno\nhttp://example.com/uno.m3u8\n')
    handle.write('#EXTINF:-1,Il Canale Due\nhttp://example.com/due.m3u8\n')
Dialog.ANSWER = False
Keyboard.QUEUE = [senza]
run('?mode=load')
run('?mode=loaded')
labels = [item['label'] for item in ITEMS]
check(labels[:2] == ['Il Canale Due', 'Rete Uno'], 'alfabetico anche senza gruppi')
check(labels[2].startswith('Ordine dei canali: Alfabetico'),
      'la riga dichiara l\'ordine vero')

playlist_store.save_order('group')
run('?mode=loaded')
labels = [item['label'] for item in ITEMS]
print('   voci: %s' % labels)
check(len(labels) == 3, 'nessun finto raggruppamento senza group-title')
check(labels[:2] == ['Il Canale Due', 'Rete Uno'], 'l elenco resta alfabetico')
check(labels[2].endswith('Alfabetico (A-Z)'), 'la riga non finge Per gruppo')
check('groups=' not in ITEMS[2]['url'], 'niente gruppi da scegliere se non ci sono')

Dialog.SELECT = -1
Dialog.OPTIONS = []
run('?' + urllib.parse.urlparse(ITEMS[2]['url']).query)
check(Dialog.OPTIONS == ['Alfabetico (A-Z)', 'Numero del canale', 'Come nel file'],
      'senza gruppi la scelta non offre Per gruppo')

Keyboard.QUEUE = [canali]
run('?mode=load')
run('?mode=loaded')
row = [item for item in ITEMS if item['label'].startswith('Ordine dei canali')][0]
check('groups=1' in row['url'], 'con i gruppi la scelta li offre')
Dialog.OPTIONS = []
run('?' + urllib.parse.urlparse(row['url']).query)
check(len(Dialog.OPTIONS) == 4 and 'Per gruppo' in Dialog.OPTIONS,
      'lista con group-title: quattro modi di ordinare')
playlist_store.save_order('az')

print('14) dati del vecchio nome')
legacy = os.path.join(PROFILE_ROOT, 'plugin.video.cartonitalia')
os.makedirs(legacy, exist_ok=True)
with open(os.path.join(legacy, 'legacy-only.json'), 'w', encoding='utf-8') as handle:
    json.dump([], handle)
with open(os.path.join(legacy, 'order.json'), 'w', encoding='utf-8') as handle:
    json.dump({'order': 'number'}, handle)
with open(os.path.join(legacy, 'settings.xml'), 'w', encoding='utf-8') as handle:
    handle.write('<settings><category label="Sorgenti">'
                 '<setting id="source_local" value="true"/>'
                 '<setting id="local_path" value="D:\\Cartoni"/>'
                 '<setting id="m3u_url" value="http://example.com/vecchia.m3u"/>'
                 '<setting id="list_order" value="number"/>'
                 '</category></settings>')
run('')
check(os.path.isfile(os.path.join(PROFILE_ROOT, 'legacy-only.json')),
      'i file del vecchio id arrivano nella nuova cartella dati')
check(playlist_store.load_order() == 'az',
      'i file gia presenti non vengono sovrascritti')
check(SETTINGS.get('source_local') == 'true'
      and SETTINGS.get('local_path') == 'D:\\Cartoni'
      and SETTINGS.get('m3u_url') == 'http://example.com/vecchia.m3u',
      'impostazioni del vecchio nome copiate')
check('list_order' not in SETTINGS, 'impostazioni sconosciute non copiate')

SETTINGS['local_path'] = 'nuovo percorso'
run('')
check(SETTINGS['local_path'] == 'nuovo percorso',
      'le impostazioni si copiano una volta sola')

print('15) TV in chiaro: canali, loghi e guida')
tv_list = os.path.join(workdir, 'tv.m3u')
with open(tv_list, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n')
    handle.write('#EXTINF:-1 tvg-id="Rai1.it@SD" '
                 'tvg-logo="http://example.com/rai1.png" group-title="Rai",Rai 1\n')
    handle.write('http://example.com/rai1.m3u8\n')
    handle.write('#EXTINF:-1 tvg-id="Rai2.it@SD" '
                 'tvg-logo="http://example.com/rai2.png" group-title="Rai",Rai 2\n')
    handle.write('http://example.com/rai2.m3u8\n')
    handle.write('#EXTINF:-1 group-title="Altri",Canale Senza Guida\n')
    handle.write('http://example.com/senza.m3u8\n')
SETTINGS['source_tv'] = 'true'
SETTINGS['tv_url'] = tv_list

now = int(time.time())


def _stamp(offset):
    return time.strftime('%Y%m%d%H%M%S', time.gmtime(now + offset)) + ' +0000'


xmltv = ('<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
         '<channel id="Rai 1.it"><display-name>Rai 1</display-name></channel>\n'
         '<channel id="Rai 2.it"><display-name>Rai 2</display-name></channel>\n'
         '<programme start="%s" stop="%s" channel="Rai 1.it">'
         '<title>Telegiornale</title></programme>\n'
         '<programme start="%s" stop="%s" channel="Rai 1.it">'
         '<title>Film della sera</title></programme>\n'
         '<programme start="%s" stop="%s" channel="Rai 2.it">'
         '<title>Sport Live</title></programme>\n'
         '</tv>\n') % (_stamp(-1800), _stamp(1800), _stamp(1800), _stamp(5400),
                       _stamp(-900), _stamp(2700))
guide_data = tv.parse_guide(xmltv)

check(tv.channel_key('Rai1.it@SD') == tv.channel_key('Rai 1.it') == 'rai1',
      'id del canale normalizzato per la guida')
check(tv.parse_time('20261121180000 +0100') ==
      tv.parse_time('20261121170000 +0000'), 'fuso orario XMLTV rispettato')
current, following = tv.now_and_next(guide_data, 'Rai1.it@SD', 'Rai 1', at=now)
check(current and current[2] == 'Telegiornale' and
      following[2] == 'Film della sera', 'programma in onda e successivo')

original_guide = tv.guide
tv.guide = lambda url='', force=False: guide_data
run('?mode=tv')
labels = [item['label'] for item in ITEMS]
print('   canali: %s' % labels)
check(len(ITEMS) == 5, 'tre canali, filtro e Aggiorna')
check([label.split('  ')[0] for label in labels[:3]] ==
      ['Rai 1', 'Rai 2', 'Canale Senza Guida'],
      'canali in ordine di numero, chi non ha numero in fondo')
check(not any(label.startswith('Ordine dei canali') for label in labels),
      'in TV non serve la scelta dell\'ordine')
check(any(label.startswith('Rai 1') and 'Telegiornale' in label
          for label in labels), 'programma in onda accanto al canale')
rai1 = [item for item in ITEMS if item['label'].startswith('Rai 1')][0]
check(rai1['art']['thumb'] == 'http://example.com/rai1.png', 'logo del canale')
check('Dopo: Film della sera' in rai1['info']['plot'],
      'prossimo programma nel dettaglio')
check(rai1['label2'].startswith('Dopo:') and 'Film della sera' in rai1['label2'],
      'prossimo programma sulla seconda riga')
check(u'\u2192' in rai1['label'] and 'Film della sera' in rai1['label'],
      'il dopo sta anche nella label: la vista lista non disegna Label2')
check('Telegiornale' in rai1['label'],
      'il programma in onda resta per intero nella label')
guide_label = sys.modules['default'].guide_label
lungo = guide_label('Rai 1', {'epg': '21:00 ' + 'T' * 40,
                              'epg_next': '22:00 ' + 'F' * 40})
check('21:00 ' + 'T' * 40 in lungo,
      'quando lo spazio finisce il titolo in onda non si taglia')
check(u'\u2192 22:00' in lungo and u'\u2026' in lungo,
      'si accorcia solo il dopo, tenendone l orario: %s' % lungo)
senza = [item for item in ITEMS if item['label'].startswith('Canale Senza Guida')][0]
check('Telegiornale' not in senza['label'] and not senza['label2'],
      'canale senza guida resta pulito')
filtro = [item for item in ITEMS
          if item['label'].startswith('Solo canali con guida TV')]
check(filtro and '(2)' in filtro[0]['label'],
      'riga del filtro: solo i canali presenti nella guida')

run('?mode=tv&only=epg')
labels = [item['label'] for item in ITEMS]
check(len(ITEMS) == 4 and not any(label.startswith('Canale Senza Guida')
                                  for label in labels),
      'filtro attivo: solo canali con guida')
check(any(label == 'Tutti i canali' for label in labels),
      'dal filtro si torna a tutti i canali')

run('')
check('TV in chiaro' in [item['label'] for item in ITEMS],
      'voce TV nel menu principale')


def offline_guide(url='', force=False):
    raise tv.TvError('rete spenta')


tv.guide = offline_guide
run('?mode=tv')
check(len(ITEMS) == 4 and all('Telegiornale' not in item['label']
                              for item in ITEMS),
      'senza guida i canali restano elencati')
tv.guide = original_guide

print('16) guida TV unita da piu fonti')
check(tv.parse_guide(b'\xef\xbb\xbf' + xmltv.encode('utf-8'))
      ['programmes'], 'guida con BOM UTF-8 letta lo stesso')

sky_xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
           '<channel id="Sky Uno.it"><display-name>Sky Uno</display-name>'
           '</channel>\n'
           '<programme start="%s" stop="%s" channel="Sky Uno.it">'
           '<title>Serie</title></programme>\n'
           '<programme start="%s" stop="%s" channel="Rai 1.it">'
           '<title>Doppione</title></programme>\n</tv>\n'
           % (_stamp(-600), _stamp(1200), _stamp(-300), _stamp(900)))
CALLS = []


def fake_download(source):
    CALLS.append(source)
    if len(CALLS) == 1:
        return b'\xef\xbb\xbf' + xmltv.encode('utf-8')
    if len(CALLS) == 2:
        raise OSError('fonte spenta')
    return sky_xml.encode('utf-8')


original_download = tv._download
tv._download = fake_download
merged = tv.guide('', force=True)
tv._download = original_download
check(len(CALLS) == len(tv.GUIDE_URLS),
      'tutte le guide pubbliche vengono provate')
check('rai1' in merged['programmes'] and 'skyuno' in merged['programmes'],
      'canali di guide diverse nella stessa guida')
check(merged['programmes']['rai1'][0][2] == 'Telegiornale',
      'per un canale vince la prima fonte che lo conosce')
check(tv.guide_sources('http://example.com/mia.xml') ==
      ('http://example.com/mia.xml',),
      'una guida scelta dall utente resta l unica usata')

print('17) sorgenti multiple e canali singoli (sources.json)')
extra_list = os.path.join(workdir, 'extra.m3u')
with open(extra_list, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n')
    handle.write('#EXTINF:-1 group-title="Altri",Canale Extra\n')
    handle.write('http://example.com/extra.m3u8\n')
    handle.write('#EXTINF:-1 group-title="Altri",Rai 1 doppione\n')
    handle.write('http://example.com/rai1.m3u8\n')
sources_path = os.path.join(PROFILE_ROOT, 'sources.json')
with open(sources_path, 'w', encoding='utf-8') as handle:
    json.dump({'tv_url': tv_list,
               'tv_urls': [extra_list],
               'epg_urls': ['http://example.com/extra.xml'],
               'channels': [{'name': 'Mio Canale',
                             'url': 'http://example.com/mio.m3u8'}]},
              handle)
check(tv.channel_sources('') == [tv_list, extra_list],
      'liste M3U aggiuntive accanto a quella scelta')
check(tv.guide_sources('') == tv.GUIDE_URLS + ('http://example.com/extra.xml',),
      'guide aggiuntive accanto a quelle pubbliche')
sorgenti = tv.channels('', force=True)
nomi = [entry['name'] for entry in sorgenti]
check('Canale Extra' in nomi, 'i canali della seconda lista ci sono')
check('Rai 1' in nomi, 'i canali della lista principale restano')
check(nomi.count('Rai 1 doppione') == 0,
      'lo stesso link non entra due volte')
check('Mio Canale' in nomi, 'il canale singolo aggiunto a mano compare')
check('Mio Canale' in [entry['name'] for entry in tv.channels('')],
      'il canale singolo compare anche con la cache fresca')
os.remove(sources_path)
check('Mio Canale' not in [entry['name'] for entry in tv.channels('', force=True)],
      'senza sources.json il canale singolo sparisce')

print('18) vista delle cartelle ricordata')
dbfolder = os.path.join(workdir, 'database')
if not os.path.isdir(dbfolder):
    os.makedirs(dbfolder)
dbpath = os.path.join(dbfolder, 'ViewModes6.db')
connection = sqlite3.connect(dbpath)
connection.execute('create table view (idView integer primary key, window integer, '
                   'path text, viewMode integer, sortMethod integer, '
                   'sortOrder integer, sortAttributes integer, skin text)')
radice = 'plugin://plugin.video.ghoststream/'
connection.execute('insert into view values (1, 10025, ?, 66036, 0, 1, 0, ?)',
                   (radice, 'skin.test'))
connection.commit()
connection.close()
check(views.database().endswith('ViewModes6.db'), 'database delle viste trovato')
check(views.stored_view(radice) == 66036, 'vista scelta letta dal database di Kodi')
BUILTINS[:] = []
check(views.apply(radice) == 66036 and
      'Container.SetViewMode(66036)' in BUILTINS,
      'vista riapplicata alla cartella')
check(playlist_store.read_data('views.json').get(radice) == 66036,
      'vista copiata nella cartella dati dell addon')
os.remove(dbpath)
BUILTINS[:] = []
check(views.apply(radice) == 66036 and
      'Container.SetViewMode(66036)' in BUILTINS,
      'senza il database di Kodi vale la copia locale')
check(views.stored_view(radice) == 0, 'database assente: nessuna vista da leggere')
run('')
check('Container.SetViewMode(66036)' in BUILTINS,
      'aprendo il menu la vista scelta viene applicata davvero')

print('19) canali TV in ordine di numero (Rai 1, Rai 2, Rai 3...)')
disordinati = [{'name': 'Zeta TV'}, {'name': 'Canale 5 HD'},
               {'name': 'Rai 2'}, {'name': 'Rete 4'}, {'name': 'Rai 1'},
               {'name': 'Nove'}, {'name': 'Rai 1 HD'},
               {'name': 'QVC (Italy)'}, {'name': 'Boing (Italy) HD'}]
check([entry['name'] for entry in tv.sort_channels(disordinati)] ==
      ['Rai 1', 'Rai 1 HD', 'Rai 2', 'Rete 4', 'Canale 5 HD', 'Nove',
       'QVC (Italy)', 'Boing (Italy) HD', 'Zeta TV'],
      'nazionali in ordine di canale, gli altri in fondo per nome')
check(tv.channel_number('Canale 5 HD (1080p)') == 5 and
      tv.channel_number('LA7 HD') == 7,
      'qualita e parentesi non cambiano il numero')
check([entry['name'] for entry in tv.sort_channels(
          [{'name': 'B Canale', 'number': 2},
           {'name': 'A Canale', 'number': 1}])] == ['A Canale', 'B Canale'],
      'il numero scritto nella lista (tvg-chno) vince')

print('20) sorgenti predefinite dentro l addon (repo)')
builtin_path = os.path.join(workdir, 'builtin-sources.json')
saved_builtin = tv.BUILTIN_FILE
tv.BUILTIN_FILE = builtin_path
check(tv.sources() == {}, 'senza file predefinito non cambia niente')
with open(builtin_path, 'w', encoding='utf-8') as handle:
    json.dump({'tv_url': tv_list, 'tv_urls': [extra_list],
               'epg_urls': ['http://example.com/predefinita.xml'],
               'channels': [{'name': 'Canale Predefinito',
                             'url': 'http://example.com/pre.m3u8'}]}, handle)
check(tv.channel_sources('') == [tv_list, extra_list],
      'liste predefinite valide per tutti')
check('http://example.com/predefinita.xml' in tv.guide_sources(''),
      'guida predefinita usata')
nomi = [entry['name'] for entry in tv.channels('', force=True)]
check('Canale Predefinito' in nomi, 'canale predefinito in elenco')
with open(sources_path, 'w', encoding='utf-8') as handle:
    json.dump({'tv_urls': ['http://example.com/mia.m3u'],
               'channels': [{'name': 'Canale Utente',
                             'url': 'http://example.com/utente.m3u8'}]},
              handle)
check(tv.channel_sources('') ==
      [tv_list, extra_list, 'http://example.com/mia.m3u'],
      'le sorgenti dell utente si sommano alle predefinite')
nomi = [entry['name'] for entry in tv.channels('', force=True)]
check('Canale Predefinito' in nomi and 'Canale Utente' in nomi,
      'predefinite e sorgenti dell utente convivono')
os.remove(sources_path)
tv.BUILTIN_FILE = saved_builtin
check(tv.sources() == tv.builtin_sources(),
      'tornando al file vero non resta niente appeso')
check(tv.channel_sources('') == [tv.LIST_URL],
      'senza sorgenti predefinite vale la lista iptv-org')

print('21) nomi e gruppi sporchi delle liste pubbliche')
check(playlist.clean_group('Undefined') == '' and
      playlist.clean_group('   ') == '' and
      playlist.clean_group('Sport') == 'Sport',
      'i gruppi finti diventano nessun gruppo')
check(playlist.clean_name('Canale 5 [Geo-blocked]') == 'Canale 5' and
      playlist.clean_name('Rai 1 HD (1080p)') == 'Rai 1 HD (1080p)',
      'i bollini di stato escono dal nome, la qualita resta')
sporca = playlist.parse('#EXTM3U\n'
                        '#EXTINF:-1 tvg-id="x" group-title="Undefined",'
                        'Canale 5 [Geo-blocked]\n'
                        'http://example.com/a.m3u8\n')
check(sporca[0]['group'] == '' and sporca[0]['name'] == 'Canale 5',
      'la lista letta arriva gia pulita')
check(not playlist.has_groups(sporca),
      'un gruppo finto non fa comparire l opzione per gruppi')
check(playlist.groups(sporca) == [('', 1)],
      'il canale finisce tra quelli senza gruppo')
check(playlist.in_group(sporca, '') == sporca,
      'il filtro per gruppo vuoto lo trova')

print('22) copie dello stesso canale sotto un nome solo (SD/HD)')
check(tv.variant_label('Rai 1 HD (1080p)') == 'HD 1080p',
      'etichetta della copia: parola e risoluzione')
check(tv.variant_label('Rai 1 (720p)') == '720p', 'solo risoluzione')
check(tv.variant_label('Rai 1') == '', 'canale senza qualita: nessuna etichetta')

parziale = tv.group_channels([
    {'name': 'Rai 1 (720p)', 'url': 'http://example.com/a.m3u8', 'logo': ''},
    {'name': 'Rai 1 HD', 'url': 'http://example.com/b.m3u8', 'logo': '',
     'epg': '21:00 Telegiornale', 'epg_ok': True, 'plot': 'In onda: Telegiornale'}])
check(len(parziale) == 1 and parziale[0].get('epg') == '21:00 Telegiornale'
      and parziale[0].get('epg_ok'),
      'la guida di una copia vale per tutto il canale')

doppia = os.path.join(workdir, 'doppia.m3u')
with open(doppia, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n')
    handle.write('#EXTINF:-1 tvg-id="Rai1.it@SD" group-title="Rai",Rai 1\n')
    handle.write('http://example.com/rai1-sd.m3u8\n')
    handle.write('#EXTINF:-1 tvg-id="Rai1.it@HD" group-title="Rai",'
                 'Rai 1 HD (1080p)\n')
    handle.write('http://example.com/rai1-hd.m3u8\n')
    handle.write('#EXTINF:-1 group-title="Rai",Rai 1 (720p)\n')
    handle.write('http://example.com/rai1-720.m3u8\n')
    handle.write('#EXTINF:-1 tvg-id="Rai2.it@SD" group-title="Rai",Rai 2\n')
    handle.write('http://example.com/rai2.m3u8\n')

saved_tv_url = SETTINGS.get('tv_url')
SETTINGS['tv_url'] = doppia
# La lista si passa esplicitamente: channels() non legge le impostazioni.
canali = tv.group_channels(tv.channels(doppia, force=True))
check(len(canali) == 2, 'quattro flussi ma due canali in elenco: %s' %
      [(entry['name'], len(entry.get('variants') or [])) for entry in canali])
rai1 = [entry for entry in canali if entry['name'].startswith('Rai 1')][0]
check(len(rai1['variants']) == 3, 'tre copie sotto Rai 1')
check([copia['variant'] for copia in rai1['variants']] ==
      ['', 'HD 1080p', '720p'],
      'il flusso senza sigla in cima, poi le copie migliori')

run('?mode=tv')
labels = [item['label'] for item in ITEMS]
check(sum(1 for label in labels if label.startswith('Rai 1')) == 1,
      'una sola voce Rai 1 in elenco: %s' % labels)
voce = [item for item in ITEMS if item['label'].startswith('Rai 1')][0]
check(voce['folder'] and 'mode=tv_var' in voce['url'] and '(3)' in voce['label'],
      'la voce apre il sottomenu con quante copie ci sono')

run('?mode=tv_var&k=rai1')
check(len(ITEMS) == 3, 'il sottomenu mostra le tre copie')
check(ITEMS[0]['label'].startswith('Principale'),
      'prima il flusso principale, con un nome chiaro: %s' % ITEMS[0]['label'])
check(not ITEMS[0]['folder'] and 'rai1-sd.m3u8' in ITEMS[0]['url'],
      'la voce principale riproduce il flusso senza qualita')
check(ITEMS[1]['label'].startswith('HD 1080p') and
      'rai1-hd.m3u8' in ITEMS[1]['url'] and
      ITEMS[2]['label'].startswith('720p'),
      'poi le copie migliori: %s' % [item['label'] for item in ITEMS])
check(all(item['label'].strip() for item in ITEMS),
      'nessuna copia resta senza etichetta')
check(all('Telegiornale' in item['label'] for item in ITEMS),
      'ogni copia porta il programma in onda')

run('?mode=tv_var&k=inesistente')
check(ITEMS == [], 'canale sconosciuto: nessun elenco rotto')

if saved_tv_url is None:
    SETTINGS.pop('tv_url', None)
else:
    SETTINGS['tv_url'] = saved_tv_url

tv.channels(tv_list, force=True)

print('23) cartelle in cache e rinnovo in sottofondo')
run('')
check(END and END[-1].get('cacheToDisc') is True,
      'la cartella resta in cache: tornando indietro non si rifa tutto')

default = sys.modules['default']
BUILTINS[:] = []
default.redirect('plugin://plugin.video.ghoststream/?mode=tv')
check(BUILTINS and 'mode=tv' in BUILTINS[0] and 'v=' in BUILTINS[0],
      'la pagina ricostruita e nuova, non presa dalla cache: %s' % BUILTINS)
check(END[-1].get('cacheToDisc') is False,
      'la pagina di passaggio non finisce in cache')

playlist_store.write_data('prova.json', {'a': 1})
prova = os.path.join(PROFILE_ROOT, 'prova.json')
check(playlist_store.read_data('prova.json') == {'a': 1} and
      os.path.isfile(prova) and not os.path.exists(prova + '.tmp'),
      'scrittura atomica: chi legge non trova mai un file a meta')
os.remove(prova)

calls = []
original_channels, original_guide = tv.channels, tv.guide
tv.channels = lambda url='', force=False: (calls.append('canali'), [])[1]
tv.guide = lambda url='', force=False: (calls.append('guida'), {})[1]
playlist_store.write_data('tv.json', {'urls': [], 'fetched': int(time.time()),
                                     'entries': []})
playlist_store.write_data('epg.json', {'sources': [], 'fetched': int(time.time()),
                                      'guide': {}})
check(tv.cache_age('tv.json') is not None and tv.cache_age('tv.json') < 60,
      'eta della copia salvata leggibile')
check(tv.cache_age('mai-scritto.json') is None, 'copia che non c e: eta sconosciuta')
check(tv.warm() == [] and calls == [],
      'con le copie fresche il servizio non scarica niente')
playlist_store.write_data('tv.json', {'urls': [], 'fetched': 0, 'entries': []})
playlist_store.write_data('epg.json', {'sources': [], 'fetched': 0, 'guide': {}})
check(tv.warm() == ['canali', 'guida'], 'copie vecchie: canali e guida rinnovati')
check(calls == ['canali', 'guida'], 'prima i canali, poi la guida')

LOGS[:] = []
import service  # noqa: E402  (il servizio importa la lib dell addon)
service.refresh()
check(any('servizio' in line and 'rinnovati' in line for line in LOGS),
      'il servizio rinnova quello che serve e lo scrive nel log: %s' % LOGS[-1:])
tv.channels, tv.guide = original_channels, original_guide

addon_dir = os.path.abspath('plugin.video.ghoststream')
with open(os.path.join(addon_dir, 'addon.xml'), encoding='utf-8') as handle:
    manifest = handle.read()
check('xbmc.service' in manifest and 'library="service.py"' in manifest,
      'il servizio e dichiarato nell addon.xml')
check(os.path.isfile(os.path.join(addon_dir, 'service.py')),
      'il file del servizio viaggia nello zip')

print('ESITO OK')
