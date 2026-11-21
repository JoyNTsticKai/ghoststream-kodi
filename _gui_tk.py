# -*- coding: utf-8 -*-
"""Interfaccia Tkinter per Ghost-Stream: repository Kodi e sorgenti TV.

    python _gui_tk.py

Scheda "Repository"
    indirizzo base della cartella repo/ su GitHub, "Aggiorna repository"
    (lancia _build_repo.py: zip + addons.xml), "Commit e push", "Verifica
    online" (scarica addons.xml e confronta l'md5) e "Nuova versione" (alza
    la patch in addon.xml e nei due User-Agent).

Scheda "Sorgenti TV"
    lista canali principale (tv_url), liste M3U aggiuntive, guida TV
    principale (epg_url), guide XMLTV aggiuntive e canali singoli. Tutto
    finisce in sources.json nella cartella dati dell'addon, dove tv.py lo
    legge accanto alle impostazioni di Kodi.

Solo libreria standard: nessuna dipendenza da installare.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import urllib.request
import xml.etree.ElementTree as ET

import tkinter as tk
from tkinter import messagebox, ttk

ROOT = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = 'plugin.video.ghoststream'
REPOSITORY_DIR = 'repository.ghoststream'
BASE_FILE = os.path.join(ROOT, 'repo_base.txt')
PROFILE_FILE = os.path.join(ROOT, 'gui_profile.txt')
SOURCES_FILE = 'sources.json'
USER_AGENT = 'Ghost-Stream gestione/1.0'
DEFAULT_PROFILE = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                               'Kodi', 'userdata', 'addon_data', ADDON_DIR)


# --------------------------------------------------------------------------
# Utilita'
# --------------------------------------------------------------------------
def read_text(path, default=''):
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()
    except OSError:
        return default


def write_text(path, text):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def addon_version():
    try:
        tree = ET.parse(os.path.join(ROOT, ADDON_DIR, 'addon.xml'))
    except (OSError, ET.ParseError):
        return '?'
    return tree.getroot().get('version') or '?'


def repository_version():
    try:
        tree = ET.parse(os.path.join(ROOT, REPOSITORY_DIR, 'addon.xml'))
    except (OSError, ET.ParseError):
        return '?'
    return tree.getroot().get('version') or '?'


def fetch(url, timeout=25):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


# --------------------------------------------------------------------------
# Finestra
# --------------------------------------------------------------------------
class App(object):
    def __init__(self, root):
        self.root = root
        self.busy = False
        self._last_output = ''
        root.title('Ghost-Stream - repository e sorgenti')
        root.minsize(760, 620)

        self.base = tk.StringVar(value=read_text(BASE_FILE).strip())
        self.message = tk.StringVar(
            value='Aggiornamento repository Kodi (%s).' % addon_version())
        self.profile = tk.StringVar(value=self._profile_path())
        self.tv_url = tk.StringVar()
        self.tv_extra = tk.StringVar()
        self.epg_url = tk.StringVar()
        self.epg_extra = tk.StringVar()
        self.channel_name = tk.StringVar()
        self.channel_url = tk.StringVar()

        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=8, pady=(8, 4))
        self._repo_tab(notebook)
        self._sources_tab(notebook)
        self._output_box(root)

        self.load_sources()
        self._append('Ghost-Stream: addon %s, repository %s.'
                     % (addon_version(), repository_version()))
        if not self.base.get():
            self._append('Manca l indirizzo base: scrivilo e premi '
                         '"Salva indirizzo" prima di aggiornare il repository.')

    # ---------------------------------------------------------------- layout
    def _repo_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text='Repository')

        ttk.Label(tab, text='Indirizzo base (cartella repo/ pubblicata):'
                  ).grid(row=0, column=0, sticky='w')
        entry = ttk.Entry(tab, textvariable=self.base)
        entry.grid(row=1, column=0, sticky='we', pady=(2, 6))
        ttk.Button(tab, text='Salva indirizzo',
                   command=self.save_base).grid(row=2, column=0, sticky='w')

        ttk.Separator(tab, orient='horizontal').grid(
            row=3, column=0, sticky='we', pady=10)

        ttk.Label(tab, text='Messaggio del commit:').grid(row=4, column=0,
                                                          sticky='w')
        ttk.Entry(tab, textvariable=self.message).grid(
            row=5, column=0, sticky='we', pady=(2, 8))

        buttons = ttk.Frame(tab)
        buttons.grid(row=6, column=0, sticky='w')
        for label, command in (('Aggiorna repository', self.build_repo),
                               ('Commit e push', self.commit_push),
                               ('Verifica online', self.verify_online),
                               ('Nuova versione', self.bump_version)):
            ttk.Button(buttons, text=label, command=command).pack(
                side='left', padx=(0, 6))

        ttk.Label(tab, text=('"Aggiorna repository" rigenera repo/ e gli zip, '
                             '"Commit e push" pubblica le modifiche su GitHub: '
                             'dopo di che Kodi aggiorna da solo.'),
                  wraplength=700, foreground='#555').grid(
            row=7, column=0, sticky='w', pady=(10, 0))
        tab.columnconfigure(0, weight=1)

    def _sources_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text='Sorgenti TV')
        tab.columnconfigure(1, weight=1)

        ttk.Label(tab, text='Cartella dati dell addon:').grid(
            row=0, column=0, sticky='w')
        ttk.Entry(tab, textvariable=self.profile).grid(
            row=0, column=1, sticky='we', pady=2)
        ttk.Button(tab, text='Carica', command=self.load_sources).grid(
            row=0, column=2, padx=(6, 0))

        ttk.Label(tab, text='Lista canali principale (tv_url), vuoto = '
                            'lista italiana iptv-org:').grid(
            row=1, column=0, columnspan=3, sticky='w', pady=(8, 0))
        ttk.Entry(tab, textvariable=self.tv_url).grid(
            row=2, column=0, columnspan=3, sticky='we')

        ttk.Label(tab, text='Liste M3U aggiuntive (una per riga):').grid(
            row=3, column=0, columnspan=3, sticky='w', pady=(8, 0))
        self.tv_list = self._listbox(tab, 4, 4)
        ttk.Entry(tab, textvariable=self.tv_extra).grid(
            row=5, column=0, sticky='we', pady=(4, 0))
        self._add_remove(tab, 5, self.tv_extra, self.tv_list)

        ttk.Label(tab, text='Guida TV principale (epg_url), vuoto = guide '
                            'italiane pubbliche:').grid(
            row=6, column=0, columnspan=3, sticky='w', pady=(10, 0))
        ttk.Entry(tab, textvariable=self.epg_url).grid(
            row=7, column=0, columnspan=3, sticky='we')

        ttk.Label(tab, text='Guide XMLTV aggiuntive (una per riga):').grid(
            row=8, column=0, columnspan=3, sticky='w', pady=(8, 0))
        self.epg_list = self._listbox(tab, 9, 3)
        ttk.Entry(tab, textvariable=self.epg_extra).grid(
            row=10, column=0, sticky='we', pady=(4, 0))
        self._add_remove(tab, 10, self.epg_extra, self.epg_list)

        ttk.Label(tab, text='Canali singoli:').grid(
            row=11, column=0, columnspan=3, sticky='w', pady=(10, 0))
        riga = ttk.Frame(tab)
        riga.grid(row=12, column=0, columnspan=3, sticky='we')
        ttk.Label(riga, text='Nome').pack(side='left')
        ttk.Entry(riga, textvariable=self.channel_name, width=22).pack(
            side='left', padx=(4, 8))
        ttk.Label(riga, text='URL').pack(side='left')
        ttk.Entry(riga, textvariable=self.channel_url).pack(
            side='left', fill='x', expand=True, padx=(4, 8))
        ttk.Button(riga, text='Aggiungi canale',
                   command=self.add_channel).pack(side='left')

        self.channel_list = tk.Listbox(tab, height=4, exportselection=False)
        self.channel_list.grid(row=13, column=0, columnspan=3, sticky='we',
                               pady=(4, 0))
        ttk.Button(tab, text='Rimuovi canale selezionato',
                   command=self.remove_channel).grid(
            row=14, column=0, sticky='w', pady=(4, 0))

        ttk.Button(tab, text='Salva sorgenti', command=self.save_sources).grid(
            row=15, column=0, sticky='w', pady=(12, 0))
        ttk.Label(tab, text=('Le sorgenti si salvano in sources.json: l addon '
                             'le usa al posto dei valori vuoti, senza toccare '
                             'le impostazioni di Kodi.'),
                  wraplength=700, foreground='#555').grid(
            row=16, column=0, columnspan=3, sticky='w', pady=(8, 0))

    def _listbox(self, parent, row, height):
        box = tk.Listbox(parent, height=height, exportselection=False)
        box.grid(row=row, column=0, columnspan=3, sticky='we')
        return box

    def _add_remove(self, parent, row, variable, box):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, columnspan=2, sticky='e', pady=(4, 0))

        def add():
            value = variable.get().strip()
            if value and value not in box.get(0, 'end'):
                box.insert('end', value)
            variable.set('')

        def remove():
            for index in reversed(box.curselection()):
                box.delete(index)

        ttk.Button(frame, text='Aggiungi', command=add).pack(side='left')
        ttk.Button(frame, text='Rimuovi', command=remove).pack(side='left',
                                                              padx=(4, 0))

    def _output_box(self, root):
        frame = ttk.Frame(root, padding=(8, 0, 8, 8))
        frame.pack(fill='both', expand=True)
        self.out = tk.Text(frame, height=12, wrap='word', state='disabled',
                           background='#111', foreground='#ddd')
        bar = ttk.Scrollbar(frame, command=self.out.yview)
        self.out.configure(yscrollcommand=bar.set)
        self.out.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')

    # ---------------------------------------------------------------- output
    def _append(self, text):
        def inner():
            self.out.configure(state='normal')
            self.out.insert('end', text.rstrip() + '\n')
            self.out.see('end')
            self.out.configure(state='disabled')
        self.root.after(0, inner)

    def _work(self, func):
        """Comandi lunghi fuori dal thread dell'interfaccia."""
        if self.busy:
            messagebox.showinfo('Un momento', 'C e gia un comando in corso.')
            return
        self.busy = True
        self.root.configure(cursor='watch')

        def runner():
            try:
                func()
            except Exception as exc:
                self._append('errore: %s' % exc)
            finally:
                def done():
                    self.busy = False
                    self.root.configure(cursor='')
                self.root.after(0, done)

        threading.Thread(target=runner, daemon=True).start()

    def _run(self, args):
        """Esegue un comando, ne mostra l'uscita e restituisce il codice."""
        self._append('> ' + ' '.join(args))
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                              encoding='utf-8', errors='replace',
                              creationflags=flags)
        output = ((proc.stdout or '') + (proc.stderr or '')).strip()
        self._last_output = output
        if output:
            self._append(output)
        self._append('uscita: %d' % proc.returncode)
        return proc.returncode

    # ------------------------------------------------------------ repository
    def save_base(self):
        base = self.base.get().strip().rstrip('/')
        if not base.startswith('http'):
            messagebox.showerror('Indirizzo non valido',
                                 'Serve un indirizzo che comincia con http.')
            return
        write_text(BASE_FILE, base + '\n')
        self.base.set(base)
        self._append('indirizzo base salvato: %s' % base)

    def build_repo(self):
        base = self.base.get().strip().rstrip('/')
        if not base.startswith('http'):
            messagebox.showerror('Indirizzo non valido',
                                 'Prima scrivi e salva l indirizzo base.')
            return
        write_text(BASE_FILE, base + '\n')

        def job():
            self._run([sys.executable, '_build_repo.py', '--base', base])
        self._work(job)

    def commit_push(self):
        message = self.message.get().strip() or 'Aggiornamento repository Kodi'
        if not self.base.get().strip():
            messagebox.showerror('Indirizzo non valido',
                                 'Prima scrivi e salva l indirizzo base.')
            return
        write_text(BASE_FILE, self.base.get().strip().rstrip('/') + '\n')

        def job():
            self._run(['git', 'add', '-A'])
            self._run(['git', 'status', '--porcelain'])
            if not (self._last_output or '').strip():
                self._append('niente da committare.')
                return
            self._run(['git', 'commit', '-m', message])
            if self._run(['git', 'push', 'origin', 'main']) != 0:
                self._append('push non riuscito: controlla il remote '
                             '(git remote -v) e l accesso a GitHub.')
        self._work(job)

    def verify_online(self):
        base = self.base.get().strip().rstrip('/')
        if not base.startswith('http'):
            messagebox.showerror('Indirizzo non valido',
                                 'Prima scrivi e salva l indirizzo base.')
            return

        def job():
            self._append('verifico %s/addons.xml' % base)
            try:
                data = fetch(base + '/addons.xml')
                remote = fetch(base + '/addons.xml.md5').decode(
                    'utf-8', 'replace').strip()
            except Exception as exc:
                self._append('online non raggiungibile: %s' % exc)
                return
            local = hashlib.md5(data).hexdigest()
            self._append('md5 nel file .md5 : %s' % remote)
            self._append('md5 del download   : %s' % local)
            self._append('ESITO: %s' % ('coerente' if remote == local
                                        else 'DIVERSO, ricarica il repository'))
            try:
                root = ET.fromstring(data)
            except ET.ParseError as exc:
                self._append('addons.xml illeggibile: %s' % exc)
                return
            for node in root.findall('addon'):
                self._append('pubblicato: %s %s' % (node.get('id'),
                                                    node.get('version')))
        self._work(job)

    def bump_version(self):
        if not messagebox.askyesno(
                'Nuova versione',
                'Alzo la patch di %s e dei due User-Agent?'
                % addon_version()):
            return

        def job():
            path = os.path.join(ROOT, ADDON_DIR, 'addon.xml')
            text = read_text(path)
            match = re.search(r'version="(\d+)\.(\d+)\.(\d+)"', text)
            if not match:
                self._append('versione non trovata in addon.xml')
                return
            major, minor, patch = (int(part) for part in match.groups())
            old = match.group(0)
            new = 'version="%d.%d.%d"' % (major, minor, patch + 1)
            write_text(path, text.replace(old, new, 1))
            for name in ('playlist.py', 'archive_api.py'):
                lib = os.path.join(ROOT, ADDON_DIR, 'resources', 'lib', name)
                body = read_text(lib)
                if not body:
                    continue
                write_text(lib, body.replace('%d.%d.%d' % (major, minor, patch),
                                             '%d.%d.%d' % (major, minor, patch + 1)))
            self.message.set('Ghost-Stream %d.%d.%d.' % (major, minor, patch + 1))
            self._append('nuova versione: %s (prima %s)'
                         % (new, old))
        self._work(job)

    # --------------------------------------------------------------- sorgenti
    def _profile_path(self):
        stored = read_text(PROFILE_FILE).strip()
        return stored or DEFAULT_PROFILE

    def _sources_path(self):
        return os.path.join(self.profile.get().strip() or DEFAULT_PROFILE,
                            SOURCES_FILE)

    def load_sources(self):
        path = self._sources_path()
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
            except (OSError, ValueError) as exc:
                self._append('sources.json illeggibile: %s' % exc)
                return
        if not isinstance(data, dict):
            data = {}
        self.tv_url.set(str(data.get('tv_url') or ''))
        self.epg_url.set(str(data.get('epg_url') or ''))
        for box, key in ((self.tv_list, 'tv_urls'), (self.epg_list, 'epg_urls')):
            box.delete(0, 'end')
            for url in data.get(key) or []:
                if str(url).strip():
                    box.insert('end', str(url).strip())
        self.channel_list.delete(0, 'end')
        for item in data.get('channels') or []:
            if isinstance(item, dict) and item.get('url'):
                self.channel_list.insert('end', '%s | %s'
                                         % (item.get('name') or item['url'],
                                            item['url']))
        self._append('sorgenti lette da %s (%d liste, %d guide, %d canali)'
                     % (path, self.tv_list.size(), self.epg_list.size(),
                        self.channel_list.size()))

    def add_channel(self):
        name = self.channel_name.get().strip()
        url = self.channel_url.get().strip()
        if not url:
            messagebox.showerror('Canale senza URL', 'Incolla l URL del canale.')
            return
        self.channel_list.insert('end', '%s | %s' % (name or url, url))
        self.channel_name.set('')
        self.channel_url.set('')

    def remove_channel(self):
        for index in reversed(self.channel_list.curselection()):
            self.channel_list.delete(index)

    def save_sources(self):
        try:
            write_text(PROFILE_FILE, self.profile.get().strip() + '\n')
        except OSError:
            pass
        path = self._sources_path()
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                data = {}
        if not isinstance(data, dict):
            data = {}
        data['tv_url'] = self.tv_url.get().strip()
        data['tv_urls'] = [str(url).strip() for url in self.tv_list.get(0, 'end')
                          if str(url).strip()]
        data['epg_url'] = self.epg_url.get().strip()
        data['epg_urls'] = [str(url).strip() for url in self.epg_list.get(0, 'end')
                            if str(url).strip()]
        channels = []
        for line in self.channel_list.get(0, 'end'):
            name, _, url = line.rpartition(' | ')
            if url.strip():
                channels.append({'name': name.strip() or url.strip(),
                                 'url': url.strip()})
        data['channels'] = channels
        try:
            write_text(path, json.dumps(data, ensure_ascii=False, indent=1) + '\n')
        except OSError as exc:
            messagebox.showerror('Salvataggio non riuscito', str(exc))
            return
        self._append('sorgenti salvate in %s (%d liste, %d guide, %d canali)'
                     % (path, len(data['tv_urls']), len(data['epg_urls']),
                        len(channels)))
        self._append('in Kodi: sezione TV in chiaro -> aggiorna (tasto destro '
                     'o voce Aggiorna) per rileggere liste e guida.')


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use('vista' if os.name == 'nt' else 'clam')
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
