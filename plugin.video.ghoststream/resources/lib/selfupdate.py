# -*- coding: utf-8 -*-
"""Aggiornamento dell'addon da una cartella del disco.

Kodi sa installare solo gli zip scelti a mano o quelli del repository: per non
dover ogni volta passare da Impostazioni > Add-on, l'addon si prende la
versione piu' nuova che trova in una cartella (lo zip
plugin.video.ghoststream-x.y.z.zip oppure la cartella dell'addon) e la copia
sopra se stesso. Poi serve un riavvio di Kodi: i moduli caricati all'avvio
resterebbero quelli vecchi.
"""

import os
import re
import zipfile

import xbmc

from resources.lib import update

ADDON_ID = 'plugin.video.ghoststream'
ZIP_NAME = re.compile(r'^%s-([0-9][0-9.]*)\.zip$' % re.escape(ADDON_ID), re.I)
ADDON_XML = 'addon.xml'
SKIP_DIRS = ('__pycache__',)
# Cosa si copia: niente eseguibili o roba che non c'entra con l'addon.
ALLOWED = ('.py', '.xml', '.po', '.pot', '.png', '.jpg', '.jpeg', '.gif',
           '.txt', '.md', '.json', '.ttf')


class UpdateError(Exception):
    """Cartella, zip o file non leggibili."""


def folder_version(path):
    """Versione dichiarata dall'addon.xml di una cartella ('' se non c'e')."""
    try:
        with open(os.path.join(path, ADDON_XML), 'r', encoding='utf-8',
                  errors='replace') as handle:
            text = handle.read()
    except OSError:
        return ''
    if ('id="%s"' % ADDON_ID) not in text:
        return ''
    return update.version_in(text, ADDON_ID)


def zip_version(path):
    """Versione dichiarata dall'addon.xml dentro lo zip ('' se non c'e')."""
    try:
        with zipfile.ZipFile(path) as archive:
            text = archive.read('%s/%s' % (ADDON_ID, ADDON_XML)).decode(
                'utf-8', 'replace')
    except (OSError, KeyError, zipfile.BadZipFile):
        return ''
    if ('id="%s"' % ADDON_ID) not in text:
        return ''
    return update.version_in(text, ADDON_ID)


def newest(folder):
    """La versione piu' nuova in una cartella: (versione, percorso, tipo).

    tipo e' 'zip' o 'cartella'. Restituisce None se non c'e' niente da
    installare.
    """
    try:
        names = os.listdir(folder)
    except OSError as exc:
        raise UpdateError('cartella non leggibile: %s' % exc)

    found = []
    for name in names:
        path = os.path.join(folder, name)
        if os.path.isdir(path):
            if name == ADDON_ID:
                version = folder_version(path)
                if version:
                    found.append((version, path, 'cartella'))
            continue
        if not ZIP_NAME.match(name or ''):
            continue
        version = zip_version(path)
        if version:
            found.append((version, path, 'zip'))
    if not found:
        return None
    return max(found, key=lambda row: update.parse(row[0]))


def install(source, kind, destination):
    """Copia l'addon nuovo sopra quello installato; torna i file scritti."""
    if kind == 'zip':
        return _from_zip(source, destination)
    return _from_folder(source, destination)


def _from_zip(archive, destination):
    written = 0
    try:
        with zipfile.ZipFile(archive) as zipped:
            for name in zipped.namelist():
                if name.endswith('/'):
                    continue
                parts = name.split('/')
                # Lo zip puo' avere una cartella di contorno: si scarta.
                if len(parts) < 2 or parts[0] != ADDON_ID:
                    continue
                if any(part in SKIP_DIRS for part in parts):
                    continue
                if not name.lower().endswith(ALLOWED):
                    continue
                _write(os.path.join(destination, *parts[1:]),
                       zipped.read(name))
                written += 1
    except (OSError, zipfile.BadZipFile) as exc:
        raise UpdateError('zip non leggibile: %s' % exc)
    return written


def _from_folder(source, destination):
    written = 0
    for root, folders, files in os.walk(source):
        folders[:] = [name for name in folders if name not in SKIP_DIRS]
        relative = os.path.relpath(root, source)
        for name in files:
            if name.endswith('.pyc'):
                continue
            target = os.path.join(destination,
                                  *([] if relative == '.' else [relative]),
                                  name)
            try:
                with open(os.path.join(root, name), 'rb') as handle:
                    _write(target, handle.read())
            except OSError as exc:
                raise UpdateError('file non copiato (%s): %s' % (name, exc))
            written += 1
    return written


def _write(path, data):
    try:
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with open(path, 'wb') as handle:
            handle.write(data)
    except OSError as exc:
        raise UpdateError('scrittura fallita (%s): %s' % (path, exc))


def restart():
    """Riavvia Kodi, cosi' i moduli nuovi vengono caricati davvero."""
    try:
        xbmc.executebuiltin('RestartApp')
        return True
    except Exception:
        return False
