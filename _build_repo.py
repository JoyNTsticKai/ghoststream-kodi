# -*- coding: utf-8 -*-
"""Costruisce il repository Kodi da pubblicare su GitHub.

    python _build_repo.py --base https://raw.githubusercontent.com/UTENTE/REPO/main/repo

Crea in repo/:
  addons.xml, addons.xml.md5
  plugin.video.ghoststream/plugin.video.ghoststream-<versione>.zip
  repository.ghoststream/repository.ghoststream-<versione>.zip

e nella cartella del progetto il repository.ghoststream-<versione>.zip da
installare a mano la prima volta (Kodi: Add-on -> Installa da file zip).
Dopo di che Kodi si aggiorna da solo dal repository.

Senza --base (o senza repo_base.txt) lo script si ferma: un repository con
l'indirizzo sbagliato dentro non e' installabile e non si aggiorna.
"""

import argparse
import hashlib
import os
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'repo')
PLUGIN = 'plugin.video.ghoststream'
REPOSITORY = 'repository.ghoststream'
ADDONS = (REPOSITORY, PLUGIN)
SKIP_DIRS = {'__pycache__', '.git'}
SKIP_EXT = {'.pyc', '.pyo', '.pdb'}
BASE_FILE = os.path.join(ROOT, 'repo_base.txt')


def addon_xml(addon_id):
    return os.path.join(ROOT, addon_id, 'addon.xml')


def version(addon_id):
    return ET.parse(addon_xml(addon_id)).getroot().get('version')


def repository_xml(base):
    """addon.xml del repository con l'indirizzo vero al posto del segnaposto."""
    with open(addon_xml(REPOSITORY), encoding='utf-8') as handle:
        return handle.read().replace('__REPO_BASE__', base.rstrip('/'))


def zip_addon(addon_id, base, destination):
    """Zip con dentro <addon_id>/... come vuole Kodi."""
    target = os.path.join(destination, '%s-%s.zip' % (addon_id, version(addon_id)))
    folder = os.path.join(ROOT, addon_id)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for current, dirs, files in os.walk(folder):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
            for name in files:
                if os.path.splitext(name)[1].lower() in SKIP_EXT:
                    continue
                path = os.path.join(current, name)
                inside = os.path.join(addon_id,
                                      os.path.relpath(path, folder)).replace('\\', '/')
                data = None
                if addon_id == REPOSITORY and name == 'addon.xml':
                    data = repository_xml(base).encode('utf-8')
                if data is None:
                    bundle.write(path, inside)
                else:
                    bundle.writestr(inside, data)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='',
                        help='indirizzo pubblico della cartella repo/ su GitHub')
    args = parser.parse_args()

    base = args.base.strip()
    if not base and os.path.isfile(BASE_FILE):
        with open(BASE_FILE, encoding='utf-8') as handle:
            base = handle.read().strip()
    if not base.startswith('http') or 'UTENTE' in base:
        print('Fermato: indirizzo del repository mancante o finto (%r).' % base)
        print('Serve l indirizzo vero della cartella repo/ sul branch pubblicato:')
        print('  python _build_repo.py --base '
              'https://raw.githubusercontent.com/<utente>/<repo>/main/repo')
        raise SystemExit(2)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    for addon_id in ADDONS:
        folder = os.path.join(OUT, addon_id)
        os.makedirs(folder)
        target = zip_addon(addon_id, base, folder)
        print('zip: %s (%d byte)' % (os.path.relpath(target, ROOT),
                                     os.path.getsize(target)))
        # Anche in radice: il repository per la prima installazione, il
        # plugin per chi preferisce installare lo zip a mano.
        shutil.copyfile(target, os.path.join(ROOT, os.path.basename(target)))

    # Una release non lascia in giro gli zip delle versioni precedenti.
    for name in os.listdir(ROOT):
        if not name.endswith('.zip'):
            continue
        for addon_id in ADDONS:
            if name.startswith(addon_id + '-') and name != '%s-%s.zip' % (
                    addon_id, version(addon_id)):
                os.remove(os.path.join(ROOT, name))
                print('rimosso: %s' % name)
                break

    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<addons>']
    for addon_id in ADDONS:
        with open(addon_xml(addon_id), encoding='utf-8') as handle:
            text = handle.read()
        if addon_id == REPOSITORY:
            text = repository_xml(base)
        body = text.split('?>', 1)[-1].strip()
        parts.append(body)
    parts.append('</addons>')
    addons = '\n'.join(parts) + '\n'
    # newline='\n': su Windows il testo non deve diventare \r\n, altrimenti
    # l'md5 calcolato qui non corrisponde ai byte del file scaricato da Kodi.
    with open(os.path.join(OUT, 'addons.xml'), 'w', encoding='utf-8',
              newline='\n') as handle:
        handle.write(addons)
    with open(os.path.join(OUT, 'addons.xml.md5'), 'w', encoding='utf-8',
              newline='\n') as handle:
        handle.write(hashlib.md5(addons.encode('utf-8')).hexdigest())

    # L'indirizzo resta scritto qui: le release successive sono un comando solo.
    with open(BASE_FILE, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(base.rstrip('/') + '\n')

    print('repo: %s (addons.xml + %s)' % (os.path.relpath(OUT, ROOT),
                                          ', '.join(ADDONS)))
    print('zip in radice: %s-%s.zip (plugin), %s-%s.zip (repository)' % (
        PLUGIN, version(PLUGIN), REPOSITORY, version(REPOSITORY)))
    print('prima installazione: %s-%s.zip' % (REPOSITORY, version(REPOSITORY)))


if __name__ == '__main__':
    main()
