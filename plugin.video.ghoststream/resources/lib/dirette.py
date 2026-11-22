# -*- coding: utf-8 -*-
"""Dirette ufficiali: i canali Rai in diretta dal relinker pubblico di RaiPlay.

Il link del relinker e' stabile, il flusso no: ogni apertura restituisce un
indirizzo firmato che scade dopo pochi minuti. Per questo si tiene solo il
link del relinker e il flusso vero si chiede al momento della riproduzione,
invece di salvare un indirizzo che domani non vale piu'.

Il relinker risponde 403 a chi non manda un User-Agent da applicazione (anche
a curl): le voci portano quindi l'header esplicito, che viaggia col link fino
al player. Il link non finisce con .m3u8, percio' la voce dichiara anche il
tipo di manifest: senza quella direttiva Kodi aprirebbe la diretta col
demuxer predefinito, che sul live va a scatti.
"""

from resources.lib import playlist

RELINKER = ('https://mediapolis.rai.it/relinker/relinkerServlet.htm'
            '?cont=%s&output=16')

# (nome, numero del telecomando, id del canale RaiPlay)
CHANNELS = (
    ('Rai 1', 1, '2606803'),
    ('Rai 2', 2, '308718'),
    ('Rai 3', 3, '308709'),
    ('Rai 4', 21, '746966'),
    ('Rai 5', 23, '395276'),
    ('Rai Movie', 24, '747002'),
    ('Rai Premium', 25, '746992'),
    ('Rai News 24', 48, '1'),
    ('Rai Storia', 54, '746990'),
    ('Rai Sport', 58, '358025'),
)

HEADERS = {'User-Agent': playlist.USER_AGENT}
PROPS = {'inputstream.adaptive.manifest_type': 'hls'}


def entries():
    """Le dirette nella stessa forma delle voci di una lista M3U."""
    return [{'name': name, 'url': RELINKER % content, 'logo': '',
             'group': '', 'tvg_id': name, 'number': number, 'live': True,
             'props': dict(PROPS), 'headers': dict(HEADERS)}
            for name, number, content in CHANNELS]


def probe_url():
    """Link della prima diretta: la Diagnostica lo usa per provare la fonte."""
    return RELINKER % CHANNELS[0][2]
