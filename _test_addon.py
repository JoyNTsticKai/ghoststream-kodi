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
    ASKED = []

    def notification(self, *args, **kwargs):
        pass

    def yesno(self, *args, **kwargs):
        # La domanda sulla cache si ricorda: la prova guarda cosa e' stato chiesto.
        Dialog.ASKED.append(args[-1] if args else '')
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

# Impostazioni finte di Kodi: la cache si legge e si scrive via JSON-RPC.
CACHE = {'memorysize': 20, 'readfactor': 400, 'calls': [], 'fail': False}


def executeJSONRPC(payload):
    request = json.loads(payload)
    params = request.get('params') or {}
    CACHE['calls'].append(request.get('method'))
    if CACHE['fail']:
        raise ValueError('webserver spento')
    key = params['setting'].split('.')[-1]
    if request.get('method') == 'Settings.GetSettingValue':
        return json.dumps({'result': {'value': CACHE[key]}})
    if request.get('method') == 'Settings.SetSettingValue':
        CACHE[key] = params['value']
        CACHE['calls'].append('%s=%s' % (params['setting'], params['value']))
        return json.dumps({'result': True})
    return json.dumps({'result': None})


xbmc.executeJSONRPC = executeJSONRPC

# Riproduzione finta: il servizio la segue con track_step() e il player
# risponde quello che gli si dice.
PLAYER = {'playing': False, 'time': 0.0, 'total': 0.0, 'seek': [],
          'played': []}


class Player(object):
    def isPlaying(self):
        return PLAYER['playing']

    def getTime(self):
        return PLAYER['time']

    def getTotalTime(self):
        return PLAYER['total']

    def seekTime(self, seconds):
        PLAYER['seek'].append(seconds)
        PLAYER['time'] = float(seconds)

    def play(self, item=None, listitem=None):
        # Il ripiego automatico apre la copia successiva da qui.
        PLAYER['played'].append({'path': item.path if item else '',
                                 'props': dict(item.props) if item else {},
                                 'offset': item.getProperty('StartOffset')
                                 if item else ''})


class Monitor(object):
    def abortRequested(self):
        return False

    def waitForAbort(self, seconds=None):
        return False


xbmc.Player = Player
xbmc.Monitor = Monitor

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

from resources.lib import (archive_api, diagnostica, dirette,  # noqa: E402
                           favorites, hidden, playlist, playlist_store,
                           progress, search, status, tv, views, youtube)


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
check(labels == ['Cerca', 'Carica un link (M3U o video)', 'Stato',
                 'Diagnostica'],
      'voce Carica nel menu, sotto Cerca: %s' % labels)
check(ITEMS[0]['art']['thumb'].endswith('search.png'),
      'Cerca ha la sua icona')
check(ITEMS[1]['art']['thumb'].endswith('load.png'), 'icona dedicata load.png')

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
    chiavi = {archive_api.episode_key(group['files'][0]) for group in groups}
    check(len(chiavi) == len(groups), 'nessuna puntata doppia')
except archive_api.ArchiveError as exc:
    print('  --  rete non disponibile, prova saltata: %s' % exc)

print('6) elenco a una riga per puntata')
FAKE = [
    {'title': 'Il ritorno', 'label': 'ep01.mkv', 'season': None, 'episode': 1,
     'format': 'Matroska', 'size': '516.0 MB', 'bytes': 541065216,
     'duration': 1456, 'bitrate': 2973000, 'heavy': True, 'priority': 0,
     'url': 'http://example.com/01.mkv'},
    {'title': 'Il ritorno', 'label': 'ep01.mp4', 'season': None, 'episode': 1,
     'format': 'h.264', 'size': '136.0 MB', 'bytes': 142606336,
     'duration': 1456, 'bitrate': 783551, 'heavy': False, 'priority': 3,
     'url': 'http://example.com/01.mp4'},
    {'title': 'La sfida', 'label': 'ep02.mp4', 'season': None, 'episode': 2,
     'format': 'h.264', 'size': '140.0 MB', 'bytes': 146800640,
     'duration': 1440, 'bitrate': 815559, 'heavy': False, 'priority': 3,
     'url': 'http://example.com/02.mp4'},
    {'title': 'La fine', 'label': 'ep10.mp4', 'season': None, 'episode': 10,
     'format': 'h.264', 'size': '141.0 MB', 'bytes': 147849216,
     'duration': 1440, 'bitrate': 821384, 'heavy': False, 'priority': 3,
     'url': 'http://example.com/10.mp4'},
    {'title': 'L ultima sfida', 'label': 'ep11.mkv', 'season': None, 'episode': 11,
     'format': 'Matroska', 'size': '842.7 MB', 'bytes': 883592691,
     'duration': 1480, 'bitrate': 4776176, 'heavy': True, 'priority': 0,
     'url': 'http://example.com/11.mkv'},
]
META = {'title': 'Ken il Guerriero', 'plot': 'Trama.', 'creator': 'Autore', 'year': 1986}
archive_api.playable_files = lambda identifier: ([dict(entry) for entry in FAKE], dict(META))

SETTINGS['source_archive'] = 'true'
run('?mode=archive_item&id=Ken')
print('   voci: %s' % [item['label'] for item in ITEMS])
check(len(ITEMS) == 4, 'quattro puntate, non cinque file')
check('(h.264' in ITEMS[0]['label'] and '2 versioni' in ITEMS[0]['label'],
      'formato preferito e numero di versioni sulla riga')
check(ITEMS[0]['folder'] is True, 'la puntata con piu formati apre il sottomenu')
check('mode=archive_versions' in ITEMS[0]['url'] and 'ep=1' in ITEMS[0]['url'],
      'il sottomenu porta alla puntata giusta')
check(ITEMS[1]['folder'] is False and 'mode=play' in ITEMS[1]['url'],
      'la puntata con un solo formato si riproduce subito')
check([item['info'].get('episode') for item in ITEMS] == [1, 2, 10, 11],
      'puntate in ordine')
check('516' not in ITEMS[0]['label'], 'la copia pesante non compare in elenco')
check('versione pesante' in ITEMS[3]['label'],
      'la puntata che esiste solo pesante e segnalata')
check('pesante' not in ITEMS[1]['label'],
      'la puntata con copia leggera non ha avviso')
check('4.8 Mbps' in ITEMS[3]['info'].get('plot', ''),
      'la trama spiega il limite della sorgente')
check(archive_api._heavy(883592691, 1480) is True, 'copia da 883 MB pesante')
check(archive_api._heavy(143890832, 1483) is False, 'copia da 137 MB leggera')
check(archive_api._heavy(0, 0) is False, 'senza dimensione nessun avviso')

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
check('versione pesante' in ITEMS[1]['label'],
      'la versione grossa e segnalata pesante')
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
check(labels == ['Cerca', 'Carica un link (M3U o video)', 'La mia lista',
                 'Stato', 'Diagnostica'],
      'la lista salvata compare nel menu principale')
check(ITEMS[2]['folder'] is True, 'la lista salvata apre un elenco')
check(ITEMS[2]['art']['thumb'] == 'http://example.com/ken.png',
      'logo della prima voce come copertina')
check(ITEMS[2]['context'] and 'list_remove' in ITEMS[2]['context'][0][1],
      'voce Rimuovi nel menu contestuale')

list_id = urllib.parse.parse_qs(
    urllib.parse.urlparse(ITEMS[2]['url']).query)['id'][0]
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

print('24) posizioni salvate: Continua a guardare e segno di visto')
check(progress.key('Ken  il Guerriero - Ep 1') ==
      progress.key('ken il guerriero - ep 1'),
      'la chiave del titolo ignora maiuscole e spazi doppi')
check(progress.key('') == '', 'titolo vuoto: nessuna chiave')
check([progress.time_text(0), progress.time_text(65), progress.time_text(3725)]
      == ['0:00', '1:05', '1:02:05'], 'posizione leggibile (m:ss e h:mm:ss)')

check(progress.store('Diretta', 'http://example.com/live.m3u8', '', 300, 0) is None and
      progress.find('Diretta') is None,
      'una diretta (durata sconosciuta) non finisce in Continua')

voce = progress.store('Ken - Ep 1', 'http://example.com/01.mp4', '', 120, 1400)
check(voce['position'] == 120 and not voce['finished'],
      'posizione salvata a meta video')
check(progress.resume('Ken - Ep 1') == 120, 'si riprende dal secondo salvato')
check(progress.store('Ken - Ep 2', 'http://example.com/02.mp4', '', 10, 1400) and
      progress.resume('Ken - Ep 2') == 0,
      'pochi secondi non meritano una riga Riprendi')
check(progress.store('Ken - Ep 3', 'http://example.com/03.mp4', '', 1395, 1400)['finished'],
      'oltre il 90% il video e visto')
check(progress.store('Ken - Ep 9', 'http://example.com/09.mp4', '', 1350, 1400)['finished'],
      'la coda del video (meno di 90 secondi) conta come vista')
check(progress.watched('Ken - Ep 3') and progress.resume('Ken - Ep 3') == 0,
      'un video visto non si riprende')
check([riga['title'] for riga in progress.continued()] == ['Ken - Ep 1'],
      'in Continua solo quello lasciato a meta: %s' % progress.continued())

ripresa = os.path.join(workdir, 'ripresa.m3u')
with open(ripresa, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n#EXTINF:-1,Ken - Ep 1\nhttp://example.com/01.mp4\n')
    handle.write('#EXTINF:-1,Ken - Ep 3\nhttp://example.com/03.mp4\n')
SETTINGS['source_load'] = 'true'
SETTINGS['source_youtube'] = 'false'
SETTINGS['source_archive'] = 'false'
SETTINGS['source_local'] = 'false'
SETTINGS['source_tv'] = 'false'
playlist_store.save_order('az')
Dialog.ANSWER = False
Keyboard.QUEUE = [ripresa]
run('?mode=load')
run('?mode=loaded')
print('   voci: %s' % [item['label'] for item in ITEMS])
a_meta = [item for item in ITEMS if 'Ep 1' in item['label']][0]
visto = [item for item in ITEMS if 'Ep 3' in item['label']][0]
check('Riprendi da 2:00' in a_meta['label'],
      'la voce a meta dice da dove riparte: %s' % a_meta['label'])
check('(visto)' in visto['label'] and visto['info'].get('playcount') == 1,
      'la voce vista ha il segno: %s' % visto['label'])
check(any('a=watch' in riga[1] for riga in a_meta['context']),
      'menu contestuale: segna come visto')
check(any('a=unwatch' in riga[1] for riga in visto['context']),
      'menu contestuale: segna come non visto su una voce vista')
azioni = [riga for riga in a_meta['context'] if 'mode=progress' in riga[1]]
check(len(azioni) >= 2, 'le azioni sulle posizioni passano dal modo progress')

run('')
print('   menu: %s' % [item['label'] for item in ITEMS])
check(ITEMS[0]['label'].startswith('Continua a guardare') and
      'mode=continue' in ITEMS[0]['url'],
      'riga Continua in cima al menu principale: %s' % ITEMS[0]['label'])
check('(1)' in ITEMS[0]['label'], 'la riga dice quanti video aspettano')

run('?mode=continue')
check(len(ITEMS) == 1 and 'Riprendi da 2:00' in ITEMS[0]['label'] and
      ITEMS[0]['folder'] is False,
      'la pagina Continua mostra la posizione: %s' % [i['label'] for i in ITEMS])
query = urllib.parse.urlparse(ITEMS[0]['url']).query
PLAYER.update({'playing': True, 'time': 200.0, 'total': 1400.0, 'seek': []})
run('?' + query)
check(RESOLVED[-1]['props'].get('StartOffset') == '120',
      'Kodi riceve StartOffset dal secondo salvato')
check(progress.now().get('title') == 'Ken - Ep 1',
      'il servizio sa quale titolo sta seguendo')
check(progress.track_step(Player()) == 'play' and
      progress.find('Ken - Ep 1')['position'] == 200.0,
      'il servizio salva la posizione durante la riproduzione')
PLAYER.update({'playing': True, 'time': 200.0, 'total': 1400.0, 'seek': []})
progress.track_step(Player())
check(progress.find('Ken - Ep 1')['position'] == 200.0,
      'se la posizione non e avanzata non si riscrive il file')
PLAYER.update({'playing': True, 'time': 0.0, 'total': 1400.0, 'seek': []})
progress.reset()
progress.begin('Ken - Ep 1', 'http://example.com/01.mp4', '', 120)
progress.track_step(Player())
check(PLAYER['seek'] == [120],
      'se Kodi ignora StartOffset il servizio sposta al secondo giusto')
PLAYER.update({'playing': False, 'time': 0.0, 'total': 0.0})
check(progress.track_step(Player()) == 'stop' and progress.now() == {},
      'a riproduzione fermata il segno in corso viene tolto')
check(progress.resume('Ken - Ep 1') == 200, 'la posizione resta quella salvata')


def progress_call(nome, azione, titolo):
    return '?mode=progress&a=%s&k=%s&t=%s' % (
        azione, nome, urllib.parse.quote(titolo))


run(progress_call(progress.key('Ken - Ep 3'), 'unwatch', 'Ken - Ep 3'))
check(not progress.watched('Ken - Ep 3'),
      'segna come non visto rimette la voce tra quelle da riprendere')
check(any('Container.Refresh' in command for command in BUILTINS),
      'dopo il segno la pagina aperta si ridisegna')

run(progress_call(progress.key('Ken - Ep 3'), 'forget', 'Ken - Ep 3'))
check(progress.find('Ken - Ep 3') is None, 'togli da Continua cancella la voce')

run(progress_call(progress.key('Ken - Ep 5'), 'watch', 'Ken - Ep 5'))
check(progress.watched('Ken - Ep 5'),
      'segna come visto funziona anche senza aver mai riprodotto')

check(os.path.isfile(os.path.join(PROFILE_ROOT, 'progress.json')),
      'le posizioni stanno nella cartella dati, non nei setting')

playlist_store.write_data('progress.json', {'items': {
    'vecchia': {'title': 'Vecchia', 'url': 'http://example.com/x.mp4',
                'position': 100, 'total': 600, 'finished': False,
                'updated': 1}}})
progress.reset()
progress.store('Ken - Ep 7', 'http://example.com/07.mp4', '', 100, 1400)
progress.reset()
check(progress.get('vecchia') is None,
      'le posizioni di due mesi fa vengono scartate')

check(playlist.USER_AGENT.endswith('1.9.14 (Kodi addon)') and
      archive_api.USER_AGENT.endswith('1.9.14 (Kodi addon)'),
      'versione e User-Agent allineati')
check('version="1.9.14"' in manifest, 'addon.xml alla stessa versione')
with open(os.path.join(addon_dir, 'service.py'), encoding='utf-8') as handle:
    servizio = handle.read()
check('progress.track_step' in servizio and 'threading' in servizio,
      'il servizio segue la riproduzione in un filo suo')

print('25) posta e copertina in Continua, e La mia lista')
conlogo = os.path.join(workdir, 'con-logo.m3u')
with open(conlogo, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n')
    handle.write('#EXTINF:-1 tvg-logo="http://example.com/poster.png",'
                 'Episodio con logo\n')
    handle.write('http://example.com/logo.mp4\n')
Dialog.ANSWER = False
Keyboard.QUEUE = [conlogo]
run('?mode=load')
run('?mode=loaded')
voce = ITEMS[0]
print('   voci: %s' % [item['label'] for item in ITEMS])
check('at=' in voce['url'],
      'la copertina viaggia col link della voce: %s' % voce['url'][-60:])
check(any('mode=favorite' in riga[1] for riga in voce['context']),
      'menu contestuale: aggiungi a La mia lista')

query = urllib.parse.urlparse(voce['url']).query
PLAYER.update({'playing': True, 'time': 300.0, 'total': 1400.0, 'seek': []})
run('?' + query)
check(progress.now().get('art', {}).get('thumb') == 'http://example.com/poster.png',
      'la copertina sta con la posizione in corso')
progress.track_step(Player())
check(progress.find('Episodio con logo')['art'].get('thumb') ==
      'http://example.com/poster.png',
      'copertina salvata insieme alla posizione')
PLAYER.update({'playing': False, 'time': 0.0, 'total': 0.0})
progress.track_step(Player())
run('?mode=continue')
riga = [item for item in ITEMS if 'Episodio con logo' in item['label']][0]
check(riga['art']['thumb'] == 'http://example.com/poster.png',
      'la pagina Continua mostra il poster, non l icona generica')

check(favorites.has('Episodio con logo') is False, 'la lista parte vuota')
run('?mode=favorite&a=add&k=%s&t=%s&u=%s&i=%s' % (
    progress.key('Episodio con logo'),
    urllib.parse.quote('Episodio con logo'),
    urllib.parse.quote('http://example.com/logo.mp4', safe=''),
    urllib.parse.quote('http://example.com/poster.png', safe='')))
check(favorites.has('Episodio con logo'), 'la voce entra in La mia lista')
voce_scelta = favorites.find('Episodio con logo')
check(voce_scelta['url'] == 'http://example.com/logo.mp4' and
      voce_scelta['art']['thumb'] == 'http://example.com/poster.png',
      'la voce scelta porta con se link e copertina')
check(any('Container.Refresh' in command for command in BUILTINS),
      'aggiungendo la voce la pagina si ridisegna')

favorites.add('Doppione', 'http://example.com/dup.mp4')
favorites.add('Doppione', 'http://example.com/dup.mp4')
check(favorites.count() == 2, 'lo stesso titolo non si duplica')
check(favorites.remove('Doppione') and not favorites.has('Doppione'),
      'la voce si toglie per titolo')
favorites.add('Doppione', 'http://example.com/dup.mp4')

run('')
print('   menu: %s' % [item['label'] for item in ITEMS])
check(ITEMS[0]['label'].startswith('La mia lista') and
      'mode=favorites' in ITEMS[0]['url'],
      'La mia lista in cima al menu: %s' % ITEMS[0]['label'])
check(ITEMS[1]['label'].startswith('Continua a guardare'),
      'subito sotto, Continua a guardare')

run('?mode=favorites')
print('   mia lista: %s' % [item['label'] for item in ITEMS])
check(len(ITEMS) == 2 and
      [item['label'].split('  [')[0] for item in ITEMS] ==
      ['Doppione', 'Episodio con logo'],
      'la pagina elenca le voci scelte, dalla piu recente')
scelto = [item for item in ITEMS if item['label'].startswith('Episodio con logo')][0]
check(scelto['art']['thumb'] == 'http://example.com/poster.png',
      'nella pagina si vede la copertina salvata')
check(scelto['folder'] is False and 'mode=play' in scelto['url'],
      'la voce scelta si riapre subito')
check(any('a=remove' in riga[1] for riga in scelto['context']),
      'menu contestuale: togli da La mia lista')

run('?mode=favorite&a=remove&k=%s&t=%s' % (
    progress.key('Episodio con logo'), urllib.parse.quote('Episodio con logo')))
check(not favorites.has('Episodio con logo'),
      'togli dalla mia lista elimina la voce')
run('?mode=favorites')
check(len(ITEMS) == 1 and ITEMS[0]['label'].startswith('Doppione'),
      'la pagina resta coerente dopo il togli')

check(os.path.isfile(os.path.join(PROFILE_ROOT, 'favorites.json')),
      'La mia lista vive nella cartella dati, non nei setting')
with open(os.path.join(addon_dir, 'addon.xml'), encoding='utf-8') as handle:
    check('1.9.14' in handle.read(), 'addon.xml 1.9.14 anche nel file appena letto')

print('26) menu senza doppioni, e nascondi canale e gruppo')
favorites.add('Episodio con logo', 'http://example.com/logo.mp4',
              art={'thumb': 'http://example.com/poster.png'})
run('?mode=favorites')
scelto = [item for item in ITEMS if item['label'].startswith('Episodio con logo')][0]
print('   menu: %s' % [riga[0] for riga in scelto['context']])
check([riga[0] for riga in scelto['context']] ==
      ['Togli da La mia lista', 'Segna come visto', 'Togli da Continua'],
      'nella mia lista il menu ha tre righe, senza doppioni')
check(len([riga for riga in scelto['context']
           if riga[0] == 'Togli da La mia lista']) == 1,
      'Togli da La mia lista compare una volta sola')

Dialog.ANSWER = False
Keyboard.QUEUE = [conlogo]
run('?mode=load')
run('?mode=loaded')
voce = ITEMS[0]
check([riga[0] for riga in voce['context']] ==
      ['Togli da La mia lista', 'Segna come visto', 'Togli da Continua',
       'Nascondi questo canale'],
      'nella lista il menu della voce ha quattro righe: %s'
      % [riga[0] for riga in voce['context']])
voce_scelta = favorites.add('Altra voce', 'http://example.com/altra.mp4')
run('?mode=loaded')
nuova = [item for item in ITEMS if 'Altra voce' in item['label']]
check(voce_scelta is not None and not nuova,
      'una voce nuova entra in La mia lista senza comparire nella lista d origine')
favorites.remove('Altra voce')


def hide_call(azione, titolo):
    return '?mode=hide&a=%s&k=%s&t=%s' % (
        azione, progress.key(titolo), urllib.parse.quote(titolo))


check(hidden.count() == 0, 'niente nascosto all inizio')
run(hide_call('channel', 'Episodio con logo'))
check(hidden.has_channel('Episodio con logo'), 'il canale nascosto e ricordato')
check(any('Container.Refresh' in command for command in BUILTINS),
      'nascondendo la voce la pagina si ridisegna')
run('?mode=loaded')
labels = [item['label'] for item in ITEMS]
print('   lista: %s' % labels)
check(not any('Episodio con logo' in label for label in labels),
      'la voce nascosta non compare piu nel suo elenco')
check(any(label.startswith('Voci nascoste') for label in labels),
      'in fondo la riga per rivedere i nascosti')

run('?mode=hidden')
print('   nascosti: %s' % [item['label'] for item in ITEMS])
check(len(ITEMS) == 2 and 'canale' in ITEMS[0]['label'] and
      ITEMS[1]['label'].startswith('Mostra tutti'),
      'la pagina elenca i nascosti e il comando Mostra tutti')
run('?' + urllib.parse.urlparse(ITEMS[0]['url']).query)
check(not hidden.has_channel('Episodio con logo'),
      'premendo la voce torna visibile')
check(any('mode=hidden' in command for command in BUILTINS),
      'dopo il ripristino si riapre l elenco dei nascosti')
run('?mode=loaded')
check(any('Episodio con logo' in item['label'] for item in ITEMS),
      'la voce ricompare nel suo elenco')

gruppi = os.path.join(workdir, 'gruppi-nascondi.m3u')
with open(gruppi, 'w', encoding='utf-8') as handle:
    handle.write('#EXTM3U\n')
    handle.write('#EXTINF:-1 group-title="Rai",Uno della Rai\n'
                 'http://example.com/rai.mp4\n')
    handle.write('#EXTINF:-1 group-title="Sport",Sport Uno\n'
                 'http://example.com/sport.mp4\n')
Keyboard.QUEUE = [gruppi]
run('?mode=load')
playlist_store.save_order('group')
run('?mode=loaded')
labels = [item['label'] for item in ITEMS]
print('   gruppi: %s' % labels)
check(labels[0].startswith('Tutti i canali') and labels[1].startswith('Rai') and
      labels[2].startswith('Sport'), 'gruppi in elenco')
riga = [item for item in ITEMS if item['label'].startswith('Sport')][0]
check([row[0] for row in riga['context']] == ['Nascondi il gruppo "Sport"'],
      'menu del gruppo: una riga sola')

run(hide_call('group', 'Sport'))
check(hidden.has_group('Sport'), 'il gruppo nascosto e ricordato')
run('?mode=loaded')
labels = [item['label'] for item in ITEMS]
check(not any(label.startswith('Sport') for label in labels),
      'il gruppo nascosto sparisce dall elenco')
run('?mode=loaded&g=*')
labels = [item['label'] for item in ITEMS]
print('   tutti: %s' % labels)
check(not any('Sport Uno' in label for label in labels),
      'i canali del gruppo nascosto spariscono')
check(any('Uno della Rai' in label for label in labels),
      'gli altri canali restano al loro posto')
check(any(label.startswith('Voci nascoste') for label in labels),
      'la riga dei nascosti c e anche qui')

run('?mode=unhide&tipo=group&k=%s' % hidden.key('Sport'))
check(not hidden.has_group('Sport'), 'il gruppo torna visibile')
playlist_store.save_order('az')
run('?mode=loaded&g=*')
check(any('Sport Uno' in item['label'] for item in ITEMS),
      'tornato visibile, il canale riappare')

check(hidden.key('Sport') == progress.key('sport'),
      'gruppo e titolo usano la stessa chiave normalizzata')
check(os.path.isfile(os.path.join(PROFILE_ROOT, 'hidden.json')),
      'i nascosti vivono nella cartella dati')
check(os.path.isfile(os.path.join(addon_dir, 'resources', 'lib', 'hidden.py')),
      'il modulo dei nascosti viaggia con l addon')

print('27) canali con piu flussi anche in La mia lista')
SETTINGS['tv_url'] = doppia
run('?mode=tv')
voce = [item for item in ITEMS if item['label'].startswith('Rai 1')][0]
print('   menu: %s' % [riga[0] for riga in voce['context']])
check(voce['folder'] and voce['context'][0][0] == 'Aggiungi a La mia lista',
      'la riga che apre il sottomenu ha comunque Aggiungi a La mia lista')
check('mode=favorite' in voce['context'][0][1],
      'la riga del menu e l azione sui preferiti')
run('?' + urllib.parse.urlparse(voce['context'][0][1]).query)
check(favorites.has('Rai 1'), 'il canale con piu flussi entra in La mia lista')
scelto = favorites.find('Rai 1')
check(scelto['url'] == 'http://example.com/rai1-sd.m3u8',
      'si salva il flusso principale, non il sottomenu: %s' % scelto['url'])
run('?mode=favorites')
riga = [item for item in ITEMS if item['label'].startswith('Rai 1')][0]
check(riga['folder'] is False and 'mode=play' in riga['url'] and
      'rai1-sd.m3u8' in urllib.parse.unquote(riga['url']),
      'da La mia lista il canale parte subito dal flusso principale')
check(riga['context'][0][0] == 'Togli da La mia lista',
      'e da li si puo anche togliere')
favorites.remove('Rai 1')
if saved_tv_url is None:
    SETTINGS.pop('tv_url', None)
else:
    SETTINGS['tv_url'] = saved_tv_url

print('28) ricerca unificata')
check(search.words('Citta  Rai') == ['citta', 'rai'],
      'la ricerca ignora accenti e spazi doppi')
check(search.matches('Citta mia', ['citta']), 'accenti ignorati nel confronto')
check(not search.matches('Rai 1', ['rai', 'telegiornale']),
      'servono tutte le parole cercate')
molte = [{'name': 'Canale %d' % numero} for numero in range(50)]
check(len(search.filter_entries(molte, 'canale')) == search.MAX_RESULTS,
      'i risultati sono limitati per provenienza')
check(search.filter_entries(molte, '') == [], 'una ricerca vuota non trova niente')

raccolta = os.path.join(workdir, 'raccolta')
os.makedirs(os.path.join(raccolta, 'Ken il Guerriero', 'Stagione 1'),
            exist_ok=True)
with open(os.path.join(raccolta, 'Ken il Guerriero', 'Stagione 1',
                       'Episodio 01.mp4'), 'wb') as handle:
    handle.write(b'x')
with open(os.path.join(raccolta, 'Altro Film.mp4'), 'wb') as handle:
    handle.write(b'x')
check(len(search.find_local(raccolta, 'ken')) == 1,
      'la ricerca nella raccolta apre anche le cartelle')
check(len(search.find_local(raccolta, 'altro')) == 1, 'e trova i file in chiaro')
check(search.find_local('', 'ken') == [],
      'senza cartella impostata non si cerca nella raccolta')

archive_original = archive_api.search
archive_calls = []


def fake_archive(q, page=1, rows=30):
    archive_calls.append((q, page, rows))
    return ([{'identifier': 'Ken', 'title': 'Ken il Guerriero'}], 1)


archive_api.search = fake_archive
youtube_original = youtube.available
youtube.available = lambda: True

Dialog.ANSWER = True
Keyboard.QUEUE = [ripresa, 'Ken lista']
run('?mode=load')
SETTINGS['source_tv'] = 'true'
SETTINGS['source_local'] = 'true'
SETTINGS['source_archive'] = 'true'
SETTINGS['local_path'] = raccolta
SETTINGS['tv_url'] = doppia

Keyboard.QUEUE = ['ken']
run('?mode=search')
check(any('mode=search_results' in command and 'q=ken' in command
          for command in BUILTINS),
      'la tastiera porta alla pagina dei risultati: %s' % BUILTINS)
run('?mode=search_results&q=ken')
labels = [item['label'] for item in ITEMS]
print('   risultati: %s' % labels)
check(any(label.startswith('Le tue liste') for label in labels),
      'sezione delle liste salvate')
check(any(label.startswith('La mia raccolta') for label in labels),
      'sezione della raccolta locale')
archive_rows = [item for item in ITEMS if 'mode=archive_list' in item['url']]
check(len(archive_rows) == 1 and
      archive_rows[0]['label'].startswith('Internet Archive'),
      'Internet Archive ha la sua riga, senza bloccare il resto')
check(any(label.startswith('Cerca su YouTube') for label in labels),
      'riga che passa la ricerca a YouTube')
check(not any(label.startswith('Canali TV') for label in labels),
      'la sezione TV compare solo quando trova qualcosa')
check(archive_calls == [],
      'la pagina dei risultati non aspetta Internet Archive: %s' % archive_calls)
run('?' + urllib.parse.urlparse(archive_rows[0]['url']).query)
check(archive_calls and any('Ken il Guerriero' in item['label'] for item in ITEMS),
      'premendo la riga arrivano i risultati di Internet Archive')

run('?mode=search_results&q=rai')
labels = [item['label'] for item in ITEMS]
print('   risultati rai: %s' % labels)
check(any(label.startswith('Canali TV') for label in labels),
      'sezione dei canali TV')
rai1 = [item for item in ITEMS if item['label'].startswith('Rai 1')][0]
check('mode=tv_var' in rai1['url'],
      'nei risultati il canale con piu flussi apre il sottomenu')
check(any('mode=favorite' in riga[1] for riga in rai1['context']),
      'e si puo aggiungere a La mia lista anche da qui')

print('   canali e gruppi nascosti non tornano fuori con la ricerca')
run('?mode=search_results&q=rai')
prima = [item['label'].split('  [COLOR')[0] for item in ITEMS
         if item['label'].startswith('Rai')]
check(prima == ['Rai 1', 'Rai 2'], 'entrambi i canali nei risultati')
run(hide_call('channel', 'Rai 1'))
run('?mode=search_results&q=rai')
dopo = [item['label'].split('  [COLOR')[0] for item in ITEMS
        if item['label'].startswith('Rai')]
check(dopo == ['Rai 2'], 'il canale nascosto non compare nei risultati')
hidden.show(hidden.key('Rai 1'))
run(hide_call('group', 'Rai'))
run('?mode=search_results&q=rai')
labels = [item['label'] for item in ITEMS]
check(not any(label.startswith('Canali TV') for label in labels),
      'un gruppo nascosto porta via i suoi canali anche dalla ricerca')
check(not any(label.startswith('Rai') for label in labels),
      'nessun canale del gruppo nascosto nei risultati')
hidden.show(hidden.key('Rai'), 'groups')

run('?mode=search_results&q=ken')
prima = [item['label'] for item in ITEMS if item['label'].startswith('Ken - Ep')]
check(len(prima) == 2, 'due voci della lista nei risultati')
run(hide_call('channel', 'Ken - Ep 1'))
run('?mode=search_results&q=ken')
check([item['label'] for item in ITEMS if item['label'].startswith('Ken - Ep')]
      == ['Ken - Ep 3'], 'un canale nascosto sparisce anche dai risultati delle liste')
hidden.show(hidden.key('Ken - Ep 1'))

youtube.available = lambda: False
run('?mode=search_results&q=zzzznulla')
check([item['label'].split(':')[0] for item in ITEMS] == ['Internet Archive'],
      'senza risultati restano solo le ricerche esterne: %s'
      % [item['label'] for item in ITEMS])
archive_api.search = archive_original
youtube.available = youtube_original
run('?mode=search_results&q=')
check(ITEMS == [], 'ricerca senza parola: nessuna pagina rotta')

check(os.path.isfile(os.path.join(addon_dir, 'resources', 'lib', 'search.py')),
      'il modulo della ricerca viaggia con l addon')
check(youtube.search_url('ken') ==
      'plugin://plugin.video.youtube/kodion/search/query/?q=ken',
      'la ricerca YouTube usa il percorso kodion')
check('1.9.14' in manifest, 'addon.xml 1.9.14')

print('29) pagina Stato')
check(status.age_text(None) == 'mai', 'copia assente: mai')
check([status.age_text(30), status.age_text(300), status.age_text(7200),
       status.age_text(3 * 86400)] == ['adesso', '5 min', '2 h', '3 giorni'],
      'eta leggibile in minuti, ore e giorni')
check(status.when_text(0) == 'mai' and status.when_text(time.time()),
      'data del giro del servizio leggibile')

playlist_store.write_data(tv.CHANNEL_CACHE, {
    'urls': [], 'fetched': int(time.time()) - 7200,
    'entries': [{'name': 'Rai 1', 'url': 'http://example.com/1.m3u8', 'logo': ''},
                {'name': 'Rai 1 HD', 'url': 'http://example.com/1hd.m3u8',
                 'logo': ''},
                {'name': 'Rai 2', 'url': 'http://example.com/2.m3u8', 'logo': ''}]})
canali = status.channels_info()
check(canali['channels'] == 2 and canali['streams'] == 3,
      'canali e flussi contati dalla copia locale: %s' % canali)
check(7100 < canali['age'] < 7300, 'eta della copia dei canali')
playlist_store.write_data(tv.GUIDE_CACHE, {
    'sources': [], 'fetched': int(time.time()) - 300,
    'guide': {'aliases': {}, 'programmes': {'rai1': [], 'rai2': []}}})
guida = status.guide_info()
check(guida['channels'] == 2 and guida['age'] < 400,
      'canali con guida ed eta della copia')

playlist_store.write_data('service.json', {})
check(status.service_run() == {'when': 0, 'renewed': []},
      'servizio mai girato: nessun segno')
status.mark_service(['canali'])
giro = status.service_run()
check(giro['when'] > 0 and giro['renewed'] == ['canali'],
      'il giro del servizio resta scritto nella cartella dati')

run('?mode=status')
labels = [item['label'] for item in ITEMS]
print('   stato: %s' % labels)
check(len(ITEMS) == 4, 'quattro righe: canali, guida, servizio, rinnova')
check(labels[0].startswith('Canali TV: 2 canali (3 flussi)') and
      'copia di 2 h' in labels[0], 'riga dei canali con eta della copia')
check(labels[1].startswith('Guida TV: 2 canali con guida') and
      'copia di 5 min' in labels[1], 'riga della guida con eta della copia')
check(labels[2].startswith('Ultimo rinnovo del servizio') and
      'canali' in labels[2], 'riga dell ultimo rinnovo del servizio')
check(labels[3] == 'Rinnova ora' and 'mode=status_refresh' in ITEMS[3]['url'],
      'pulsante Rinnova ora')

chiamate = []
channels_originale, guide_originale = tv.channels, tv.guide
tv.channels = lambda url='', force=False: (chiamate.append(('canali', force)), [])[1]
tv.guide = lambda url='', force=False: (chiamate.append(('guida', force)), {})[1]
run('?mode=status_refresh')
check(chiamate == [('canali', True), ('guida', True)],
      'Rinnova ora forza canali e guida: %s' % chiamate)
check(len(ITEMS) == 4 and ITEMS[0]['label'].startswith('Canali TV'),
      'e ridisegna la pagina Stato, senza passare da una pagina vuota')
check(not any('Container.Update' in command for command in BUILTINS),
      'niente rimandi altrove: la pagina si costruisce qui: %s' % BUILTINS)

chiamate[:] = []
run('?mode=tv_refresh')
check(chiamate[:2] == [('canali', True), ('guida', True)] and len(chiamate) == 4,
      'Aggiorna la lista rinnova e poi ridisegna la TV: %s' % chiamate)
check(not any('Container.Update' in command for command in BUILTINS),
      'e anche qui niente pagina di servizio vuota: %s' % BUILTINS)
check('mode=tv_refresh' in ITEMS[-1]['url'] and 'v=' in ITEMS[-1]['url'],
      'la riga Aggiorna porta un numero nuovo, cosi non ripesca la cache')

playlist_store.write_data('service.json', {})
service.refresh()
check(status.service_run()['when'] > 0,
      'il servizio segna il suo giro per la pagina Stato')
tv.channels, tv.guide = channels_originale, guide_originale

playlist_store.write_data(tv.CHANNEL_CACHE, {'urls': [], 'fetched': 0,
                                             'entries': []})
playlist_store.write_data(tv.GUIDE_CACHE, {'sources': [], 'fetched': 0,
                                           'guide': {}})
run('?mode=status')
labels = [item['label'] for item in ITEMS]
check(labels[0].startswith('Canali TV: nessuna copia') and
      labels[1].startswith('Guida TV: nessuna copia'),
      'senza copie la pagina lo dice: %s' % labels[:2])

run('')
check(any(item['label'] == 'Stato' for item in ITEMS),
      'Stato raggiungibile dal menu principale')
check(os.path.isfile(os.path.join(addon_dir, 'resources', 'lib', 'status.py')),
      'il modulo Stato viaggia con l addon')

for riga in favorites.load():
    favorites.remove(riga['title'])
hidden.clear()
playlist_store.write_data('progress.json', {'items': {}, 'now': {}})
progress.reset()
run('?mode=favorites')
check(len(ITEMS) == 1 and 'vuota' in ITEMS[0]['label'] and
      'mode=favorites' in ITEMS[0]['url'],
      'La mia lista vuota lo dice, invece di restare bianca: %s'
      % [item['label'] for item in ITEMS])
run('?mode=continue')
check(len(ITEMS) == 1 and ITEMS[0]['label'].startswith('Niente da riprendere'),
      'Continua vuoto lo dice')
run('?mode=hidden')
check(len(ITEMS) == 1 and ITEMS[0]['label'].startswith('Niente di nascosto'),
      'Voci nascoste vuota lo dice')
check(all('v=' in item['url'] or 'mode=' in item['url'] for item in ITEMS),
      'la riga riapre la stessa pagina')

print('30) ripiego sulla copia successiva')

playlist_store.save_session('http://example.com/vuota.m3u', [],
                            autoplay=False)
run('?mode=loaded')
check(len(ITEMS) == 1 and ITEMS[0]['label'].startswith('Link non valido') and
      'mode=load' in ITEMS[0]['url'],
      'sessione senza voci: lo dice e riapre il caricamento: %s'
      % [item['label'] for item in ITEMS])

spenta = playlist_store.add('Spenta', 'http://example.com/spenta.m3u',
                            entries=[])
carica_originale = playlist.load


def carica_spenta(*args, **kwargs):
    raise playlist.PlaylistError('spenta')


playlist.load = carica_spenta
run('?mode=list&id=%s' % spenta['id'])
playlist.load = carica_originale
check(len(ITEMS) == 1 and ITEMS[0]['label'].startswith('Link non valido') and
      'mode=list' in ITEMS[0]['url'],
      'lista salvata senza voci: lo dice invece di restare bianca: %s'
      % [item['label'] for item in ITEMS])

SETTINGS['source_tv'] = 'true'
SETTINGS['tv_url'] = doppia
run('?mode=tv_var&k=rai1')
check(len(ITEMS) == 3, 'le tre copie di Rai 1: %d' % len(ITEMS))
voce = '?' + ITEMS[0]['url'].split('?', 1)[1]
copie = json.loads(urllib.parse.parse_qs(
    urllib.parse.urlparse(voce).query)['alt'][0])
check([row['url'] for row in copie] == ['http://example.com/rai1-hd.m3u8',
                                        'http://example.com/rai1-720.m3u8'],
      'la copia principale si porta dietro le altre: %s' % copie)

PLAYER.update({'playing': False, 'time': 0.0, 'total': 0.0, 'seek': []})
PLAYER['played'] = []
run(voce)
check([row['path'] for row in PLAYER['played']] ==
      ['http://example.com/rai1-hd.m3u8', 'http://example.com/rai1-720.m3u8'],
      'flusso che non parte: prova da solo HD e poi 720p: %s'
      % [row['path'] for row in PLAYER['played']])

PLAYER.update({'playing': True, 'time': 5.0, 'total': 600.0})
PLAYER['played'] = []
run(voce)
check(PLAYER['played'] == [], 'se il flusso parte non si prova altro')

PLAYER.update({'playing': True, 'time': 5.0, 'total': 600.0})
run('?mode=play&u=http://example.com/uno.m3u8&title=Uno')
check(RESOLVED and RESOLVED[-1]['path'] == 'http://example.com/uno.m3u8' and
      PLAYER['played'] == [],
      'una voce senza copie si riproduce e basta')

import default as pagina  # noqa: E402  (ricaricato da run())
check(pagina.read_alternates('') == [] and
      len(pagina.read_alternates(json.dumps(
          [{'url': 'a'}, {'url': 'b'}, {'url': 'c'}]))) == 2 and
      pagina.read_alternates('non json') == [],
      'le copie si fermano a due e i valori rotti si ignorano')

print('31) cache bassa e puntata pesante')
CACHE.update({'memorysize': 20, 'readfactor': 400, 'calls': [], 'fail': False})
Dialog.ASKED = []
Dialog.ANSWER = True
RESOLVED[:] = []
PLAYER.update({'playing': True, 'time': 5.0, 'total': 1480.0})
run('?mode=play&u=http://example.com/01.mkv&title=Uno&heavy=1')
print('   chiesto: %s' % Dialog.ASKED)
check(len(Dialog.ASKED) == 1 and '20 MB' in Dialog.ASKED[0],
      'chiede prima di toccare la cache')
check(CACHE['memorysize'] == 256 and CACHE['readfactor'] == 0,
      'cache a 256 MB e fattore Adattivo: %s' % CACHE)
check('Settings.SetSettingValue' in CACHE['calls'] and
      'filecache.readfactor=0' in CACHE['calls'],
      'si impostano memoria e fattore di lettura')
check(RESOLVED and RESOLVED[-1]['path'] == 'http://example.com/01.mkv',
      'la puntata parte lo stesso')

CACHE.update({'memorysize': 256, 'readfactor': 400, 'calls': []})
Dialog.ASKED = []
Dialog.ANSWER = True
run('?mode=play&u=http://example.com/01.mkv&title=Due&heavy=1')
check(Dialog.ASKED == [] and 'Settings.SetSettingValue' not in CACHE['calls'],
      'con 256 MB non chiede e non cambia niente')

CACHE.update({'memorysize': 20, 'readfactor': 400, 'calls': []})
Dialog.ASKED = []
Dialog.ANSWER = False
run('?mode=play&u=http://example.com/01.mkv&title=Tre&heavy=1')
check(len(Dialog.ASKED) == 1 and CACHE['memorysize'] == 20 and
      'Settings.SetSettingValue' not in CACHE['calls'],
      'se dice no la cache resta com e')

CACHE.update({'memorysize': 20, 'readfactor': 400, 'calls': [], 'fail': True})
Dialog.ASKED = []
Dialog.ANSWER = True
RESOLVED[:] = []
run('?mode=play&u=http://example.com/01.mkv&title=Quattro&heavy=1')
check(Dialog.ASKED == [] and RESOLVED and
      RESOLVED[-1]['path'] == 'http://example.com/01.mkv',
      'cache illeggibile: nessuna domanda, la puntata parte')
CACHE['fail'] = False

CACHE.update({'memorysize': 20, 'readfactor': 400, 'calls': []})
Dialog.ASKED = []
Dialog.ANSWER = True
run('?mode=play&u=http://example.com/02.mp4&title=Leggera')
check(Dialog.ASKED == [], 'una puntata leggera non chiede niente')

# Il segno pesante viaggia con la posizione salvata e con i preferiti.
CACHE.update({'memorysize': 20, 'readfactor': 400, 'calls': [], 'fail': False})
Dialog.ASKED = []
Dialog.ANSWER = False          # qui interessa il segno, non il cambio di cache
PLAYER.update({'playing': True, 'time': 60.0, 'total': 1480.0, 'seek': []})
run('?mode=play&u=http://example.com/11.mkv&title=Pesante&heavy=1')
progress.reset()
progress.track_step(Player())
salvata = progress.find('Pesante') or {}
check(salvata.get('heavy') is True, 'il segno pesante si salva con la posizione')

run('?mode=continue')
riga = [item for item in ITEMS if item['label'].startswith('Pesante')][0]
print('   continua: %s' % riga['url'])
check('heavy=1' in riga['url'], 'Continua riporta il segno pesante')
Dialog.ASKED = []
CACHE['calls'] = []
run('?' + urllib.parse.urlparse(riga['url']).query)
check(len(Dialog.ASKED) == 1 and '20 MB' in Dialog.ASKED[0],
      'riaprendo da Continua si chiede la cache')

run('?mode=favorite&a=add&k=%s&t=%s&u=%s&heavy=1' % (
    progress.key('Pesante'), urllib.parse.quote('Pesante'),
    urllib.parse.quote('http://example.com/11.mkv', safe='')))
check((favorites.find('Pesante') or {}).get('heavy') is True,
      'la voce scelta ricorda il segno pesante')
run('?mode=favorites')
riga = [item for item in ITEMS if item['label'].startswith('Pesante')][0]
print('   mia lista: %s' % riga['url'])
check('heavy=1' in riga['url'], 'La mia lista riporta il segno pesante')
Dialog.ASKED = []
CACHE['calls'] = []
run('?' + urllib.parse.urlparse(riga['url']).query)
check(len(Dialog.ASKED) == 1 and '20 MB' in Dialog.ASKED[0],
      'riaprendo da La mia lista si chiede la cache')

# Una voce leggera resta leggera anche passando da Continua.
run('?mode=play&u=http://example.com/02.mp4&title=Leggera')
progress.reset()
progress.track_step(Player())
run('?mode=continue')
leggera = [item for item in ITEMS if item['label'].startswith('Leggera')][0]
check('heavy=1' not in leggera['url'],
      'una puntata leggera non porta il segno pesante')
Dialog.ANSWER = False

print('32) dirette ufficiali Rai')
check(len(dirette.CHANNELS) == 10,
      'dieci canali ufficiali: %d' % len(dirette.CHANNELS))
voci = dirette.entries()
check(all('relinkerServlet.htm?cont=' in entry['url'] for entry in voci),
      'ogni diretta punta al relinker Rai, non a un indirizzo che scade')
check(all(entry['headers'].get('User-Agent') for entry in voci),
      'il link porta il suo User-Agent: senza, il relinker risponde 403')
numeri = [entry['number'] for entry in voci]
check(numeri == sorted(numeri), 'numeri del telecomando in ordine: %s' % numeri)
check(len(set(numeri)) == len(numeri), 'nessun numero doppio')

adesso = int(time.time())
tv.guide = lambda url='', force=False: {
    'aliases': {},
    'programmes': {'rai1': [[adesso - 600, adesso + 600, 'Uno Mattina']]},
}
SETTINGS['source_tv'] = 'true'
run('')
check('Dirette ufficiali' in [item['label'] for item in ITEMS],
      'voce Dirette ufficiali nel menu principale')
run('?mode=dirette')
labels = [item['label'] for item in ITEMS]
print('   dirette: %s' % labels)
check(len(ITEMS) == 10, 'dieci dirette in elenco: %d' % len(ITEMS))
check(labels[0].startswith('Rai 1') and labels[-1].startswith('Rai Sport'),
      'ordine del telecomando, dalla prima all ultima: %s' % labels[-1])
check('In onda:' in labels[0] and 'Uno Mattina' in labels[0],
      'la guida si vede anche sulle dirette')
check('relinkerServlet' in urllib.parse.unquote(ITEMS[0]['url']) and
      'manifest_type' in urllib.parse.unquote(ITEMS[0]['url']),
      'la voce porta il link ufficiale e il tipo di manifest')
check(ITEMS[0]['folder'] is False, 'una diretta si apre subito')
run('?' + urllib.parse.urlparse(ITEMS[0]['url']).query)
check(RESOLVED[-1]['props'].get('inputstream') == 'inputstream.adaptive' and
      RESOLVED[-1]['props'].get('inputstream.adaptive.manifest_type') == 'hls',
      'la diretta va a inputstream.adaptive, non al demuxer: %s'
      % RESOLVED[-1]['props'])

print('33) diagnostica')
reach_orig = diagnostica.reach
archive_orig = archive_api.search
chiamate = []


def fake_reach(url, headers=None):
    chiamate.append(url)
    return True, 'HTTP 302'


diagnostica.reach = fake_reach
archive_api.search = lambda q, page=1, rows=30: ([{'identifier': 'x'}], 42)
CACHE.update({'memorysize': 256, 'readfactor': 0, 'calls': [], 'fail': False})
run('')
check('Diagnostica' in [item['label'] for item in ITEMS],
      'voce Diagnostica nel menu principale')
run('?mode=diag')
labels = [item['label'] for item in ITEMS]
print('   controlli: %s' % labels)
check(len(ITEMS) == 10, 'nove controlli piu la riga Riprova: %d' % len(ITEMS))
check(any(label.startswith('Internet Archive: [COLOR=green]ok')
          for label in labels), 'Internet Archive risponde')
check(any(label.startswith('Dirette ufficiali Rai: [COLOR=green]ok')
          for label in labels), 'le dirette ufficiali rispondono')
check(any(label.startswith('Cache di Kodi: [COLOR=green]ok') and 'Adattivo' in label
          for label in labels), 'cache e fattore Adattivo letti da Kodi')
check(any('relinkerServlet' in url for url in chiamate),
      'la prova delle dirette chiede davvero il flusso')
check(labels[-1].startswith('Riprova'), 'in fondo la riga per riprovare')

CACHE['memorysize'] = 20
run('?mode=diag')
check(any(label.startswith('Cache di Kodi: [COLOR=red]ko') and '20 MB' in label
          for label in [item['label'] for item in ITEMS]),
      'una cache da 20 MB si vede subito')


def broken_search(*args, **kwargs):
    raise archive_api.ArchiveError('rete assente')


archive_api.search = broken_search
run('?mode=diag')
check(any('Internet Archive: [COLOR=red]ko' in item['label'] for item in ITEMS),
      'se una fonte non risponde la riga diventa rossa')

run('?mode=diag_refresh')
check(any('mode=diag' in command for command in BUILTINS),
      'Riprova ricostruisce la pagina da zero')
diagnostica.reach = reach_orig
archive_api.search = archive_orig
CACHE.update({'memorysize': 20, 'readfactor': 400, 'calls': [], 'fail': False})

print('34) due file con lo stesso numero di puntata')
stesso = [
    dict(FAKE[2], title='La sfida', label='013 - La sfida.mp4', episode=13,
         url='http://example.com/13a.mp4'),
    dict(FAKE[2], title='Il ritorno', label='013 - Il ritorno.mp4', episode=13,
         url='http://example.com/13b.mp4'),
]
archive_api.playable_files = lambda identifier: (
    [dict(entry) for entry in stesso], dict(META))
run('?mode=archive_item&id=Ken')
check(len(ITEMS) == 2, 'due puntate con lo stesso numero restano due: %s'
      % [item['label'] for item in ITEMS])
check(len({item['url'] for item in ITEMS}) == 2,
      'due link diversi: una non e piu copia dell altra')

doppie = [
    dict(FAKE[2], title='La sfida', label='a.mp4', episode=13,
         url='http://example.com/a.mp4'),
    dict(FAKE[0], title='La sfida', label='a.mkv', episode=13,
         url='http://example.com/a.mkv'),
    dict(FAKE[2], title='Il ritorno', label='b.mp4', episode=13,
         url='http://example.com/b.mp4'),
    dict(FAKE[0], title='Il ritorno', label='b.mkv', episode=13,
         url='http://example.com/b.mkv'),
]
archive_api.playable_files = lambda identifier: (
    [dict(entry) for entry in doppie], dict(META))
run('?mode=archive_item&id=Ken')
check(len(ITEMS) == 2, 'due puntate, ognuna con le sue copie: %s'
      % [item['label'] for item in ITEMS])
check(all('2 versioni' in item['label'] for item in ITEMS),
      'ognuna dichiara le sue copie')
seconda = [item for item in ITEMS if 'Il ritorno' in item['label']][0]
run('?' + urllib.parse.urlparse(seconda['url']).query)
labels = [item['label'] for item in ITEMS]
check(len(ITEMS) == 2 and all('Il ritorno' in label for label in labels),
      'il sottomenu apre la puntata giusta, non la prima: %s' % labels)

print('ESITO OK')
