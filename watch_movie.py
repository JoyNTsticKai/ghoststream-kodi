# watch_movie.py - Lo script principale che orchestra tutto
import cloudscraper
from bs4 import BeautifulSoup
import requests
import myResolver  # <-- IMPORTA IL MOTORE CHE ABBIAMO CARICATO!
import vlc # <-- LA LIBRERIA PER IL PLAYBACK
import time

# =======================================================================
# 🎯 CONFIGURAZIONE
# =======================================================================
# !!! CAMBIA QUESTO URL CON QUEL SITO CHE VUOI GUARDARE !!!
VIDEO_PAGE_URL = "https://example-cloudflare-test.com/mio-cartone" 

# =======================================================================
# FUNZIONI DI PARSING (Cosa cerchiamo nell'HTML)
# =======================================================================
def find_video_link_from_page(response):
    """Cerca link in modo 'manuale' basandosi su classi/tag comuni."""
    soup = BeautifulSoup(response.text, 'html.parser')
    video_url = None

    # Pattern 1: Tag <video> con classe specifica
    video_tag = soup.find('video', class_='main-player')
    if video_tag and 'src' in video_tag.attrs:
        video_url = video_tag['src']
        print(f"\n✅ Trovato link video nel tag <video> (Classe: main-player)!")
    
    # Pattern 2: Tag <a> con un link specifico
    else:
        link_tag = soup.find('a', class_='stream-link')
        if link_tag and 'href' in link_tag.attrs:
            video_url = link_tag['href']
            print(f"\n✅ Trovato link video in un tag <a> (Classe: stream-link)!")
        else:
            print("\n⚠️ Nessun link video trovato con i pattern standard di parsing!")
    
    return video_url

# =======================================================================
# FUNZIONE DI RISOLUZIONE AVANZATA
# =======================================================================
def resolve_with_myResolver(page_url):
    """Utilizza myResolver.streamsb per trovare link nascosti."""
    print("\n🚀 Tentativo di risoluzione automatica tramite myResolver.py...")
    links = myResolver.streamsb(page_url) 
    
    if links:
        print("\n✅ Risoluzione tramite myResolver.py completata! Trovati link:")
        for i, (link, desc) in enumerate(links[:3]):
            print(f"   [{i+1}] {desc}: {link}")
        return links
    else:
        print("❌ myResolver.py non ha restituito link tramite streamsb.")
        return []

# =======================================================================
# ESECUZIONE PRINCIPALE
# =======================================================================
print("=============================================================")
print("              🚀 AVVIO STRATEGIA SCRAPING VIDEO")
print("=============================================================")

# --- FASE 1: BYPASS CLOUDFLARE ---
print("🔍 FASE 1: Bypass di Cloudflare... In attesa del sblocco...")
scraper = cloudscraper.create_scraper() 
try:
    response = scraper.get(VIDEO_PAGE_URL) 
    response.raise_for_status()
    print(f"✅ Fase 1: Pagina sbloccata con successo! Status: {response.status_code}")
except requests.exceptions.RequestException as e:
    print(f"❌ ERRORE FATALE nel caricamento della pagina: {e}")
    exit()

# --- FASE 2: PARSING MANUALE (La logica semplice) ---
print("\n-------------------------------------------------------------")
print("🔍 FASE 2: Analisi Manuale del contenuto sbloccato...")
manual_video_url = find_video_link_from_page(response)

if manual_video_url:
    print(f"⭐ Link trovato con Parsing Manuale: {manual_video_url}")
else:
    print("⭐ Nessun link trovato dal Parsing Manuale. Passando al motore avanzato...")


# --- FASE 3: RISOLUZIONE AVANZATA (Il Super-Motore) ---
print("\n=============================================================")
resolution_links = resolve_with_myResolver(VIDEO_PAGE_URL)

# Scegliamo il link migliore: Quello trovato manualmente, oppure il primo del resolver
FINAL_VIDEO_URL = None
if manual_video_url:
    FINAL_VIDEO_URL = manual_video_url
else:
    if resolution_links:
        # Prendiamo il primo link che il resolver considera più valido
        FINAL_VIDEO_URL = resolution_links[0][0]
        print(f"\n🥇 LINK SELEZIONATO: (Dal Resolver) {FINAL_VIDEO_URL}")


# =======================================================================
# FASE 4: STREAMING/PLAYBACK (LA VERA MAGIA!)
# =======================================================================
if FINAL_VIDEO_URL:
    print("\n=============================================================")
    print("🎬 FASE 4: AVVIO STREAMING DIRETTO CON VLC! (Premi ESC per fermare)")
    
    # Inizializza il lettore VLC
    instance = vlc.Instance()
    player = instance.media_player_new()

    # Carica il media dall'URL che abbiamo trovato
    media = vlc.Media(FINAL_VIDEO_URL)
    player.set_media(media)

    # Avvia la riproduzione
    player.play()

    # Metti lo script in "pausa attiva" finché il video è in riproduzione
    try:
        while player.is_playing():
            time.sleep(0.1) 
    except KeyboardInterrupt:
        # Permette di fermare premendo CTRL+C
        print("\n\n👋 Interruzione manuale da tastiera rilevata.")
    finally:
        # Pulizia finale: ferma e chiude il player
        player.stop()
        print("\n=============================================================")
        print("🎉 STREAMING COMPLETATO. Il video è terminato o è stato fermato.")
        print("=============================================================")

else:
    print("\n\n🚨 FALLIMENTO TOTALE: Non siamo riusciti a trovare nessun link da puntare! Rivedi l'URL di partenza.")