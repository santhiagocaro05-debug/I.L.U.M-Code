# -*- coding: utf-8 -*-
"""
browser_control.py — Control Universal de Navegadores para ILUM
=============================================================
Soporta:
- Brave, Chrome, Edge, Firefox, Opera, Vivaldi, Safari
- Búsqueda en apps (Rappi, Uber, TikTok, etc.)
- Navegación, pestañas, scroll, zoom, historial
- Búsqueda en múltiples motores de búsqueda
- Control de YouTube, Spotify, Netflix

CHANGELOG (mejoras 157 Team):
- FIX: maximize/fullscreen ahora manejan correctamente el estado minimizado
  y la transición ventana <-> pantalla completa.
- NUEVO: acción 'clear_history' para borrar historial/datos de navegación.
- NUEVO: 'close_tab' ahora acepta 'tab_name' para cerrar una pestaña
  específica (por título) sin afectar la pestaña activa actual.
- NUEVO: acción 'restore' y alias 'windowed'/'exit_fullscreen'.
- FIX: bug real en youtube_next/youtube_prev, usaban pyautogui.press()
  con múltiples argumentos (no funciona), ahora usan hotkey().
"""

import time
import ctypes
import pyautogui
import pygetwindow as gw
import urllib.parse
import webbrowser
from pathlib import Path
import json
import re

# ============================================================
#  CONFIGURACIÓN
# ============================================================

# Palabras clave para detectar navegadores
BROWSER_KEYWORDS = [
    "Brave", "Chrome", "Edge", "Firefox", "Opera",
    "Vivaldi", "Safari", "Internet Explorer", "Microsoft Edge",
    "Opera Mini", "comet", "Arc", "SigmaOS", "Orion"
]

# Motores de búsqueda
SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "yahoo": "https://search.yahoo.com/search?p={query}",
    "ecosia": "https://www.ecosia.org/search?q={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "wikipedia": "https://es.wikipedia.org/wiki/{query}",
}

# ============================================================
#  BASE DE DATOS DE APLICACIONES WEB
# ============================================================

APP_URLS = {
    # ============================================================
    #  REDES SOCIALES Y COMUNICACIÓN
    # ============================================================
    "tiktok": "https://www.tiktok.com/search?q={query}",
    "instagram": "https://www.instagram.com/explore/search/keyword/?q={query}",
    "facebook": "https://www.facebook.com/search/top?q={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "twitch": "https://www.twitch.tv/search?term={query}",
    "pinterest": "https://www.pinterest.com/search/pins/?q={query}",
    "twitter": "https://twitter.com/search?q={query}",
    "x": "https://x.com/search?q={query}",
    "linkedin": "https://www.linkedin.com/search/results/all/?keywords={query}",
    "reddit": "https://www.reddit.com/search/?q={query}",
    "discord": "https://discord.com/search?query={query}",
    "telegram": "https://t.me/s/{query}",
    "whatsapp": "whatsapp://send?text={query}",
    "signal": "https://signal.org/search?q={query}",
    "slack": "https://slack.com/search?q={query}",
    "teams": "https://teams.microsoft.com/search?q={query}",
    "zoom": "https://zoom.us/search?q={query}",
    "meet": "https://meet.google.com/search?q={query}",

    # ============================================================
    #  COMPRAS Y MARKETPLACES
    # ============================================================
    "mercadolibre": "https://listado.mercadolibre.com.co/{query}",
    "amazon": "https://www.amazon.com/s?k={query}",
    "rappi": "https://www.rappi.com.co/search?query={query}",
    "uber": "https://www.ubereats.com/search?q={query}",
    "didi": "https://www.didi.com/search?q={query}",
    "pedidosya": "https://www.pedidosya.com.co/search?q={query}",
    "ifood": "https://www.ifood.com.ar/search?q={query}",
    "cornershop": "https://cornershopapp.com/search?q={query}",
    "exito": "https://www.exito.com/search?q={query}",
    "jumbo": "https://www.jumbo.com.co/search?q={query}",
    "falabella": "https://www.falabella.com.co/falabella-co/search?Ntt={query}",
    "alkosto": "https://www.alkosto.com/search?q={query}",
    "kabum": "https://www.kabum.com.br/busca/{query}",
    "aliexpress": "https://www.aliexpress.com/wholesale?SearchText={query}",
    "shopee": "https://shopee.com.br/search?keyword={query}",
    "linio": "https://www.linio.com.mx/search?q={query}",
    "wish": "https://www.wish.com/search/{query}",
    "temu": "https://www.temu.com/search?q={query}",
    "shein": "https://es.shein.com/search?q={query}",
    "etsy": "https://www.etsy.com/search?q={query}",
    "olx": "https://www.olx.com.co/search?q={query}",
    "facebook_marketplace": "https://www.facebook.com/marketplace/search?q={query}",

    # ============================================================
    #  MÚSICA Y ENTRETENIMIENTO
    # ============================================================
    "spotify": "https://open.spotify.com/search/{query}",
    "deezer": "https://www.deezer.com/search/{query}",
    "apple_music": "https://music.apple.com/search?term={query}",
    "soundcloud": "https://soundcloud.com/search?q={query}",
    "shazam": "https://www.shazam.com/search?term={query}",
    "bandcamp": "https://bandcamp.com/search?q={query}",
    "tidal": "https://tidal.com/search/{query}",
    "netflix": "https://www.netflix.com/search?q={query}",
    "prime_video": "https://www.primevideo.com/search?query={query}",
    "max": "https://www.max.com/search?q={query}",
    "disney_plus": "https://www.disneyplus.com/search/{query}",
    "hbo": "https://www.hbo.com/search?q={query}",
    "star_plus": "https://www.starplus.com/search?q={query}",
    "paramount": "https://www.paramountplus.com/search/?q={query}",
    "crunchyroll": "https://www.crunchyroll.com/search?q={query}",
    "pluto_tv": "https://pluto.tv/search?q={query}",
    "vix": "https://vix.com/search?q={query}",

    # ============================================================
    #  NOTICIAS
    # ============================================================
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "yahoo": "https://search.yahoo.com/search?p={query}",
    "ecosia": "https://www.ecosia.org/search?q={query}",
    "wikipedia": "https://es.wikipedia.org/wiki/{query}",
    "bbc": "https://www.bbc.com/search?q={query}",
    "cnn": "https://cnn.com/search?q={query}",
    "eltiempo": "https://www.eltiempo.com/buscar?q={query}",
    "semana": "https://www.semana.com/buscar?q={query}",
    "infobae": "https://www.infobae.com/search?q={query}",
    "clarin": "https://www.clarin.com/buscar?q={query}",
    "lanacion": "https://www.lanacion.com.ar/buscar/?q={query}",

    # ============================================================
    #  DEPORTES
    # ============================================================
    "espn": "https://www.espn.com/search?q={query}",
    "marca": "https://www.marca.com/search?q={query}",
    "as": "https://as.com/buscar?q={query}",
    "sport": "https://www.sport.es/buscar?q={query}",
    "goal": "https://www.goal.com/search?q={query}",
    "transfermarkt": "https://www.transfermarkt.es/suche/ergebnis?query={query}",

    # ============================================================
    #  TECNOLOGÍA Y PROGRAMACIÓN
    # ============================================================
    "github": "https://github.com/search?q={query}",
    "gitlab": "https://gitlab.com/search?search={query}",
    "stackoverflow": "https://stackoverflow.com/search?q={query}",
    "dev_to": "https://dev.to/search?q={query}",
    "medium": "https://medium.com/search?q={query}",
    "hackernews": "https://news.ycombinator.com/search?q={query}",
    "producthunt": "https://www.producthunt.com/search?q={query}",
    "figma": "https://www.figma.com/search?q={query}",
    "dribbble": "https://dribbble.com/search?q={query}",
    "behance": "https://www.behance.net/search/projects?search={query}",
    "codepen": "https://codepen.io/search/pens?q={query}",
    "replit": "https://replit.com/search?q={query}",
    "kaggle": "https://www.kaggle.com/search?q={query}",
    "pypi": "https://pypi.org/search/?q={query}",
    "npm": "https://www.npmjs.com/search?q={query}",
    "docker": "https://hub.docker.com/search?q={query}",
    "crates": "https://crates.io/search?q={query}",

    # ============================================================
    #  EDUCACIÓN
    # ============================================================
    "coursera": "https://www.coursera.org/search?query={query}",
    "udemy": "https://www.udemy.com/courses/search/?q={query}",
    "edx": "https://www.edx.org/search?q={query}",
    "platzi": "https://platzi.com/search/?search={query}",
    "codecademy": "https://www.codecademy.com/search?query={query}",
    "freecodecamp": "https://www.freecodecamp.org/news/search/?query={query}",
    "khanacademy": "https://www.khanacademy.org/search?page_search_query={query}",
    "brilliant": "https://brilliant.org/search/?q={query}",
    "datacamp": "https://www.datacamp.com/search?q={query}",
    "duolingo": "https://www.duolingo.com/search?q={query}",

    # ============================================================
    #  VIAJES Y MAPAS
    # ============================================================
    "google_maps": "https://www.google.com/maps/search/{query}",
    "waze": "https://www.waze.com/live-map/directions?q={query}",
    "google_flights": "https://www.google.com/travel/flights/search?q={query}",
    "despegar": "https://www.despegar.com/search?q={query}",
    "booking": "https://www.booking.com/searchresults.html?ss={query}",
    "airbnb": "https://www.airbnb.com/s/{query}/homes",
    "tripadvisor": "https://www.tripadvisor.com/Search?q={query}",
    "skyscanner": "https://www.skyscanner.com/transport/flights/{query}",
    "kayak": "https://www.kayak.com/search?q={query}",
    "viva_air": "https://www.vivaair.com/search?q={query}",
    "avianca": "https://www.avianca.com/search?q={query}",
    "latam": "https://www.latam.com/search?q={query}",
    "satena": "https://www.satena.com/search?q={query}",

    # ============================================================
    #  FINANZAS Y TRABAJO
    # ============================================================
    "linkedin_jobs": "https://www.linkedin.com/jobs/search/?keywords={query}",
    "indeed": "https://www.indeed.com/jobs?q={query}",
    "computrabajo": "https://www.computrabajo.com/ofertas-de-trabajo/?q={query}",
    "getonbrd": "https://www.getonbrd.com/search?q={query}",
    "upwork": "https://www.upwork.com/nx/search?q={query}",
    "fiverr": "https://www.fiverr.com/search/gigs?query={query}",
    "freelancer": "https://www.freelancer.com/search/projects?q={query}",
    "dolar_hoy": "https://dolarhoy.com/search?q={query}",
    "binance": "https://www.binance.com/en/search?q={query}",
    "coinmarketcap": "https://coinmarketcap.com/search/?q={query}",

    # ============================================================
    #  JUEGOS
    # ============================================================
    "steam": "https://store.steampowered.com/search/?term={query}",
    "epic_games": "https://store.epicgames.com/es-ES/search?q={query}",
    "xbox": "https://www.xbox.com/search?q={query}",
    "playstation": "https://store.playstation.com/search/{query}",
    "nintendo": "https://www.nintendo.com/search?q={query}",
    "gog": "https://www.gog.com/en/games?search={query}",
    "itchio": "https://itch.io/search?q={query}",
    "gamejolt": "https://gamejolt.com/search?q={query}",

    # ============================================================
    #  SALUD Y BIENESTAR
    # ============================================================
    "webmd": "https://www.webmd.com/search?q={query}",
    "mayoclinic": "https://www.mayoclinic.org/search/search-results?q={query}",
    "medline": "https://medlineplus.gov/search/?query={query}",
    "pubmed": "https://pubmed.ncbi.nlm.nih.gov/?term={query}",
    "calm": "https://www.calm.com/search?q={query}",
    "headspace": "https://www.headspace.com/search?q={query}",
    "myfitnesspal": "https://www.myfitnesspal.com/search?q={query}",

    # ============================================================
    #  LEGALES Y GOBIERNO
    # ============================================================
    "dian": "https://www.dian.gov.co/search?q={query}",
    "mintrabajo": "https://www.mintrabajo.gov.co/search?q={query}",
    "migracion": "https://www.migracioncolombia.gov.co/search?q={query}",
    "registraduria": "https://www.registraduria.gov.co/search?q={query}",
    "icfes": "https://www.icfes.gov.co/search?q={query}",

    # ============================================================
    #  HERRAMIENTAS
    # ============================================================
    "translate": "https://translate.google.com/?text={query}",
    "deepl": "https://www.deepl.com/translator#es/en/{query}",
    "wordreference": "https://www.wordreference.com/es/en/translation.asp?spen={query}",
    "rae": "https://dle.rae.es/{query}",
    "imdb": "https://www.imdb.com/find?q={query}",
    "rottentomatoes": "https://www.rottentomatoes.com/search?search={query}",
    "metacritic": "https://www.metacritic.com/search/{query}/",
    "canva": "https://www.canva.com/search?q={query}",
    "removebg": "https://www.remove.bg/es/search?q={query}",
    "tinyurl": "https://tinyurl.com/app/create?url={query}",
    "pastebin": "https://pastebin.com/search?q={query}",
    "notion": "https://www.notion.so/search?q={query}",
    "obsidian": "https://obsidian.md/search?q={query}",
    "evernote": "https://www.evernote.com/search?q={query}",
    "dropbox": "https://www.dropbox.com/search?q={query}",
    "onedrive": "https://onedrive.live.com/search?q={query}",
    "drive": "https://drive.google.com/drive/search?q={query}",
    "wetransfer": "https://wetransfer.com/search?q={query}",

    # ============================================================
    #  BANCOS (COLOMBIA)
    # ============================================================
    "bancolombia": "https://www.bancolombia.com/search?q={query}",
    "davivienda": "https://www.davivienda.com/search?q={query}",
    "bogota": "https://www.bancodebogota.com/search?q={query}",
    "nequi": "https://www.nequi.com.co/search?q={query}",
    "daviplata": "https://www.daviplata.com/search?q={query}",
    "bancamia": "https://www.bancamia.com/search?q={query}",
    "banco_occidente": "https://www.bancodeoccidente.com/search?q={query}",
    "bbva": "https://www.bbva.com.co/search?q={query}",
    "colpatria": "https://www.colpatria.com/search?q={query}",
    "falabella_bank": "https://www.falabellabank.com/search?q={query}",
    "itau": "https://www.itau.com.co/search?q={query}",
    "scotiabank": "https://www.scotiabank.com/search?q={query}",
}

# ============================================================
#  HELPERS DE BAJO NIVEL (WINDOWS API)
# ============================================================

def _get_window_title_by_hwnd(hwnd) -> str:
    """
    Lee el título REAL y actual de una ventana por su handle.
    Importante: el título de la ventana del navegador cambia según
    la pestaña activa, así que esto nos sirve para detectar en qué
    pestaña estamos parados en cada momento.
    """
    try:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    except Exception:
        return ""


def close_tab_by_name(target_window, tab_name: str, player=None, max_tabs: int = 30) -> str:
    """
    Busca, entre las pestañas abiertas de la ventana activa, una cuyo
    título contenga 'tab_name' y la cierra — SIN afectar la pestaña que
    el usuario tenía activa, salvo que sea justamente esa la que coincide.

    Funciona cambiando de pestaña con Ctrl+Tab y leyendo el título real
    de la ventana en cada paso (el título de la ventana refleja siempre
    la pestaña activa en Chrome/Brave/Edge/Opera/Vivaldi/Firefox).
    """
    hwnd = target_window._hWnd
    tab_name_lower = tab_name.lower().strip()

    original_title = _get_window_title_by_hwnd(hwnd)

    # Caso 1: la pestaña activa ya es la que buscamos
    if tab_name_lower in original_title.lower():
        pyautogui.hotkey('ctrl', 'w')
        if player:
            player.write_log(f"🗑️ Pestaña activa '{original_title[:40]}' cerrada.")
        return f"✅ Pestaña '{tab_name}' (activa) cerrada."

    seen_titles = {original_title}
    found = False

    for _ in range(max_tabs):
        pyautogui.hotkey('ctrl', 'tab')
        time.sleep(0.18)
        current_title = _get_window_title_by_hwnd(hwnd)

        # Dimos toda la vuelta y no encontramos nada nuevo
        if current_title in seen_titles:
            break
        seen_titles.add(current_title)

        if tab_name_lower in current_title.lower():
            pyautogui.hotkey('ctrl', 'w')
            found = True
            if player:
                player.write_log(f"🗑️ Pestaña '{current_title[:40]}' cerrada.")
            return f"✅ Pestaña que coincide con '{tab_name}' cerrada ({current_title[:40]})."

    if not found:
        # Regresar a la pestaña original sin dejar rastro, límite acotado
        attempts = 0
        while attempts < max_tabs and _get_window_title_by_hwnd(hwnd) != original_title:
            pyautogui.hotkey('ctrl', 'tab')
            time.sleep(0.15)
            attempts += 1
        return f"❌ No se encontró ninguna pestaña que coincida con '{tab_name}'."

    return f"❌ No se encontró ninguna pestaña que coincida con '{tab_name}'."


# ============================================================
#  FUNCIÓN DE BÚSQUEDA EN APPS
# ============================================================

def search_in_apps(app_name: str, query: str, player=None) -> str:
    """
    Busca en una aplicación web específica
    """
    app_name_lower = app_name.lower()
    encoded_query = urllib.parse.quote(query)
    target_url = None

    # Buscar coincidencia exacta o parcial
    for key, url_template in APP_URLS.items():
        if app_name_lower == key or app_name_lower in key or key in app_name_lower:
            target_url = url_template.format(query=encoded_query)
            break

    if not target_url:
        # Fallback: búsqueda en Google con site específico
        target_url = f"https://www.google.com/search?q=site:{app_name}.com+{encoded_query}"

    if player:
        player.write_log(f"🌐 Abriendo {app_name.capitalize()} para '{query}'...")

    webbrowser.open(target_url)
    return f"Abriendo {app_name.capitalize()} con la búsqueda '{query}'."

# ============================================================
#  FUNCIÓN DE BÚSQUEDA EN MOTORES
# ============================================================

def search_with_engine(engine: str, query: str, player=None) -> str:
    """
    Busca usando un motor de búsqueda específico
    """
    engine_lower = engine.lower()
    encoded_query = urllib.parse.quote(query)

    if engine_lower in SEARCH_ENGINES:
        url = SEARCH_ENGINES[engine_lower].format(query=encoded_query)
    else:
        # Fallback a Google
        url = SEARCH_ENGINES["google"].format(query=encoded_query)

    if player:
        player.write_log(f"🔍 Buscando en {engine.capitalize()}: '{query}'...")

    webbrowser.open(url)
    return f"Buscando '{query}' en {engine.capitalize()}."

# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================

def browser_control(parameters: dict, player=None) -> str:
    """
    Controla el navegador activo del usuario mediante simulación de teclado.

    Acciones soportadas:
    - go_to: Navegar a una URL
    - search: Buscar en Google
    - search_app: Buscar en una app específica (Rappi, Uber, TikTok, etc.)
    - search_engine: Buscar en un motor específico (google, bing, duckduckgo)
    - new_tab: Abrir nueva pestaña
    - close_tab: Cerrar pestaña actual, o una específica si se pasa 'tab_name'
    - scroll: Scroll (up/down)
    - zoom: Zoom (in/out/reset)
    - back: Retroceder
    - forward: Avanzar
    - refresh: Recargar
    - reload: Recargar (alias)
    - print: Imprimir
    - save: Guardar
    - find: Buscar en página
    - fullscreen: Pantalla completa (toggle)
    - windowed / exit_fullscreen: Salir de pantalla completa (alias de fullscreen)
    - restore: Restaurar ventana a modo ventana normal
    - history: Abrir historial
    - clear_history: Borrar historial / datos de navegación
    - bookmarks: Marcadores
    - devtools: Herramientas de desarrollador
    - downloads: Descargas
    - settings: Configuración
    - mute: Silenciar pestaña
    - pin: Fijar pestaña
    - duplicate: Duplicar pestaña
    - switch_tab: Cambiar de pestaña (next/prev)
    - close_window: Cerrar ventana
    - minimize: Minimizar ventana
    - maximize: Maximizar ventana (restaura primero si estaba minimizada)
    """
    action = parameters.get("action", "").lower()

    # 1. Encontrar el navegador activo
    target_window = None

    for win in gw.getAllWindows():
        if win.title.strip():
            for kw in BROWSER_KEYWORDS:
                if kw.lower() in win.title.lower():
                    target_window = win
                    break
        if target_window:
            break

    # Si no se encuentra, buscar por clase de ventana
    if not target_window:
        for win in gw.getAllWindows():
            if win._hWnd:
                try:
                    user32 = ctypes.windll.user32
                    class_name = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(win._hWnd, class_name, 256)
                    class_name_str = class_name.value.lower()
                    if any(kw.lower() in class_name_str for kw in ["chrome", "brave", "edge", "firefox", "opera"]):
                        target_window = win
                        break
                except Exception:
                    pass

    if not target_window:
        return "❌ No se encontró ningún navegador (Brave, Chrome, Edge, Firefox, etc.) abierto."

    try:
        # 2. Restaurar y Enfocar la ventana
        if target_window.isMinimized:
            target_window.restore()
            time.sleep(0.1)
        target_window.activate()
        time.sleep(0.15)

        win_title = target_window.title[:50]

        # ============================================================
        #  ACCIONES DE NAVEGACIÓN
        # ============================================================

        if action == "go_to":
            url = parameters.get("url", "")
            if not url:
                return "❌ Error: Falta la URL."
            if not url.startswith("http"):
                url = "https://" + url
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.05)
            pyautogui.write(url, interval=0.005)
            pyautogui.press('enter')
            return f"✅ Navegando a {url} en '{win_title}'."

        elif action == "search":
            query = parameters.get("query", "")
            engine = parameters.get("engine", "google").lower()
            if not query:
                return "❌ Error: Falta la búsqueda (query)."

            if engine in SEARCH_ENGINES:
                url = SEARCH_ENGINES[engine].format(query=urllib.parse.quote(query))
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(0.05)
                pyautogui.write(url, interval=0.005)
                pyautogui.press('enter')
                return f"✅ Buscando '{query}' en {engine.capitalize()} en '{win_title}'."
            else:
                return f"❌ Motor '{engine}' no soportado."

        elif action == "search_app":
            app_name = parameters.get("app_name", "")
            query = parameters.get("query", "")
            if not app_name:
                return "❌ Error: Falta el nombre de la app (app_name)."
            if not query:
                return "❌ Error: Falta la búsqueda (query)."

            return search_in_apps(app_name, query, player)

        elif action == "search_engine":
            engine = parameters.get("engine", "google")
            query = parameters.get("query", "")
            if not query:
                return "❌ Error: Falta la búsqueda (query)."
            return search_with_engine(engine, query, player)

        # ============================================================
        #  ACCIONES DE PESTAÑAS
        # ============================================================

        elif action == "new_tab":
            url = parameters.get("url", "")
            pyautogui.hotkey('ctrl', 't')
            time.sleep(0.3)
            if url:
                if not url.startswith("http"):
                    url = "https://" + url
                pyautogui.write(url, interval=0.01)
                pyautogui.press('enter')
                return f"✅ Nueva pestaña abierta navegando a {url}."
            return "✅ Nueva pestaña abierta."

        elif action == "close_tab":
            # Si nos dicen el nombre/título de la pestaña, cerramos ESA
            # específicamente, sin tocar la pestaña en la que estábamos.
            tab_name = parameters.get("tab_name", "") or parameters.get("name", "")
            if tab_name:
                return close_tab_by_name(target_window, tab_name, player)
            pyautogui.hotkey('ctrl', 'w')
            return "✅ Pestaña actual cerrada."

        elif action == "duplicate":
            pyautogui.hotkey('ctrl', 'shift', 'd')
            return "✅ Pestaña duplicada."

        elif action == "switch_tab":
            direction = parameters.get("direction", "next").lower()
            if direction == "next":
                pyautogui.hotkey('ctrl', 'tab')
            else:
                pyautogui.hotkey('ctrl', 'shift', 'tab')
            return f"✅ Cambiando a la {'siguiente' if direction=='next' else 'anterior'} pestaña."

        elif action == "pin":
            pyautogui.hotkey('ctrl', 'shift', 'p')
            return "✅ Pestaña fijada/desfijada."

        # ============================================================
        #  ACCIONES DE SCROLL Y ZOOM
        # ============================================================

        elif action == "scroll":
            direction = parameters.get("direction", "down").lower()
            amount = int(parameters.get("amount", 1))

            if direction == "down":
                for _ in range(amount):
                    pyautogui.press('pgdn')
                    time.sleep(0.01)
            elif direction == "up":
                for _ in range(amount):
                    pyautogui.press('pgup')
                    time.sleep(0.01)
            elif direction == "top":
                pyautogui.press('home')
            elif direction == "bottom":
                pyautogui.press('end')
            return f"✅ Scroll {'hacia abajo' if direction=='down' else 'hacia arriba'} completado."

        elif action == "zoom":
            direction = parameters.get("direction", "in").lower()
            if direction == "in":
                pyautogui.hotkey('ctrl', '+')
            elif direction == "out":
                pyautogui.hotkey('ctrl', '-')
            elif direction == "reset":
                pyautogui.hotkey('ctrl', '0')
            return f"✅ Zoom {direction} completado."

        # ============================================================
        #  ACCIONES DE NAVEGACIÓN (HISTORIAL)
        # ============================================================

        elif action == "back":
            pyautogui.hotkey('alt', 'left')
            return "✅ Retrocediendo en el historial."

        elif action == "forward":
            pyautogui.hotkey('alt', 'right')
            return "✅ Avanzando en el historial."

        elif action in ["refresh", "reload"]:
            pyautogui.hotkey('ctrl', 'r')
            return "✅ Página recargada."

        elif action == "refresh_hard":
            pyautogui.hotkey('ctrl', 'shift', 'r')
            return "✅ Página recargada (sin caché)."

        # ============================================================
        #  ACCIONES DE VENTANA (mejoradas)
        # ============================================================

        elif action == "close_window":
            pyautogui.hotkey('alt', 'f4')
            return "✅ Ventana cerrada."

        elif action == "minimize":
            target_window.minimize()
            return "✅ Ventana minimizada."

        elif action == "maximize":
            # FIX: si venía minimizada o en fullscreen, primero la
            # restauramos para asegurar que el maximize() realmente
            # "la agrande de nuevo" en modo ventana normal.
            if target_window.isMinimized:
                target_window.restore()
                time.sleep(0.15)
                target_window.activate()
                time.sleep(0.1)
            try:
                target_window.maximize()
            except Exception:
                # Fallback por si el backend de pygetwindow falla:
                # restauramos y reintentamos una vez.
                target_window.restore()
                time.sleep(0.1)
                target_window.maximize()
            return "✅ Ventana maximizada."

        elif action == "restore":
            # Vuelve a modo ventana normal (ni minimizada, ni maximizada,
            # ni fullscreen).
            if target_window.isMinimized:
                target_window.restore()
            else:
                target_window.restore()
            time.sleep(0.1)
            return "✅ Ventana restaurada a modo ventana."

        # ============================================================
        #  ACCIONES DE HERRAMIENTAS
        # ============================================================

        elif action in ("fullscreen", "windowed", "exit_fullscreen", "unfullscreen"):
            # F11 hace toggle en todos los navegadores. Nos aseguramos
            # de que la ventana esté activa y no minimizada antes de
            # enviar la tecla, si no, el toggle no aplica a nada.
            if target_window.isMinimized:
                target_window.restore()
                time.sleep(0.1)
                target_window.activate()
                time.sleep(0.1)
            pyautogui.press('f11')
            return "✅ Pantalla completa activada/desactivada."

        elif action == "history":
            pyautogui.hotkey('ctrl', 'h')
            return "✅ Abriendo historial."

        elif action in ("clear_history", "delete_history", "borrar_historial"):
            # Ctrl+Shift+Supr abre el diálogo nativo de "Borrar datos de
            # navegación" en Chrome, Brave, Edge, Opera, Vivaldi y Firefox.
            # A propósito NO confirmamos el borrado automáticamente:
            # el usuario elige el rango de tiempo y confirma, para
            # evitar borrar datos sin que se den cuenta.
            pyautogui.hotkey('ctrl', 'shift', 'delete')
            return "✅ Abriendo el diálogo para borrar historial/datos de navegación. Confirma el rango y presiona 'Borrar datos'."

        elif action == "bookmarks":
            pyautogui.hotkey('ctrl', 'shift', 'b')
            return "✅ Mostrando/ocultando marcadores."

        elif action == "devtools":
            pyautogui.hotkey('ctrl', 'shift', 'i')
            return "✅ Abriendo herramientas de desarrollador."

        elif action == "console":
            pyautogui.hotkey('ctrl', 'shift', 'j')
            return "✅ Abriendo consola de desarrollador."

        elif action == "downloads":
            pyautogui.hotkey('ctrl', 'j')
            return "✅ Abriendo descargas."

        elif action == "settings":
            # En Chrome/Edge/Brave/Opera: Alt+E abre el menú, desde ahí
            # se puede navegar a Configuración. En Firefox no aplica igual.
            pyautogui.hotkey('alt', 'e')
            return "✅ Abriendo menú de configuración."

        elif action == "print":
            pyautogui.hotkey('ctrl', 'p')
            return "✅ Abriendo diálogo de impresión."

        elif action == "save":
            pyautogui.hotkey('ctrl', 's')
            return "✅ Guardando página actual."

        elif action == "find":
            pyautogui.hotkey('ctrl', 'f')
            return "✅ Abriendo buscador en página."

        elif action == "mute":
            pyautogui.hotkey('ctrl', 'm')
            return "✅ Silenciando/activando pestaña."

        # ============================================================
        #  ACCIONES DE YOUTUBE
        # ============================================================

        elif action == "play_song":
            song_title = parameters.get("song_title", "")
            if not song_title:
                return "❌ Error: Falta el título de la canción."
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.05)
            pyautogui.write(f"ytsearch {song_title}", interval=0.005)
            pyautogui.press('enter')
            time.sleep(2)
            pyautogui.press('enter')  # Reproducir el primer resultado
            return f"✅ Reproduciendo '{song_title}' en YouTube."

        elif action == "youtube_play":
            # Control de reproducción YouTube (si está abierto)
            pyautogui.press('space')
            return "✅ Play/Pausa en YouTube."

        elif action == "youtube_next":
            # FIX: pyautogui.press() no acepta combinaciones de teclas,
            # el atajo Shift+N debe enviarse con hotkey().
            pyautogui.hotkey('shift', 'n')
            return "✅ Siguiente video en YouTube."

        elif action == "youtube_prev":
            # FIX: mismo bug que arriba, corregido con hotkey().
            pyautogui.hotkey('shift', 'p')
            return "✅ Video anterior en YouTube."

        # ============================================================
        #  ACCIÓN POR DEFECTO
        # ============================================================

        else:
            return """❌ Acción no soportada.

📋 Acciones disponibles:

🌐 NAVEGACIÓN:
  • go_to <url>           - Navegar a URL
  • search <query>        - Buscar en Google
  • search_engine <engine> <query> - Buscar en google/bing/duckduckgo
  • search_app <app> <query> - Buscar en app específica

📑 PESTAÑAS:
  • new_tab [url]         - Nueva pestaña
  • close_tab [tab_name]  - Cerrar pestaña actual, o la que coincida con tab_name
  • duplicate             - Duplicar pestaña
  • switch_tab [next/prev] - Cambiar pestaña
  • pin                   - Fijar pestaña

⬆️ SCROLL & ZOOM:
  • scroll [up/down/top/bottom] - Scroll
  • zoom [in/out/reset]  - Zoom

↩️ NAVEGACIÓN:
  • back                  - Retroceder
  • forward               - Avanzar
  • refresh               - Recargar

🪟 VENTANA:
  • close_window          - Cerrar ventana
  • minimize              - Minimizar
  • maximize              - Maximizar / agrandar de nuevo (restaura primero si hace falta)
  • restore               - Volver a modo ventana normal
  • fullscreen / windowed - Alternar pantalla completa

🛠️ HERRAMIENTAS:
  • history               - Historial
  • clear_history         - Borrar historial / datos de navegación
  • bookmarks             - Marcadores
  • devtools              - DevTools
  • downloads             - Descargas
  • settings              - Configuración
  • print                 - Imprimir
  • find                  - Buscar en página

🎵 YOUTUBE:
  • play_song <title>     - Buscar y reproducir canción
  • youtube_play          - Play/Pausa
  • youtube_next          - Siguiente video
  • youtube_prev          - Video anterior
"""

    except Exception as e:
        return f"❌ Error al controlar el navegador: {str(e)}"