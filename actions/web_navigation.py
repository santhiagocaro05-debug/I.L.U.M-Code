# -*- coding: utf-8 -*-
"""
web_navigation.py — Navegación web mejorada con múltiples funciones.
Soporta YouTube, Google, Bing, Wikipedia, y más.
"""

import urllib.request
import urllib.parse
import re
import webbrowser
import traceback
import time
import subprocess
import sys
import importlib

# Cache para evitar búsquedas repetidas
_SEARCH_CACHE = {}
_LAST_SEARCH_TIME = 0

def web_navigation(parameters: dict, player=None) -> str:
    """
    Navegación web mejorada con múltiples acciones.
    
    Acciones soportadas:
        - play_youtube, youtube: Reproduce música en YouTube
        - search: Búsqueda en Google
        - wikipedia: Busca en Wikipedia
        - bing: Búsqueda en Bing
        - open_url: Abre cualquier URL
        - go_to: Navega a una página específica
        - translate: Traduce texto (abre Google Translate)
        - maps: Abre Google Maps
        - images: Búsqueda de imágenes
        - news: Búsqueda de noticias
        - define: Definición de palabra
        - weather: Clima de una ciudad
        - calculator: Calculadora online
        - youtube_music: Busca música específica en YouTube
        - what_is: Responde preguntas básicas (abre web)
    
    Ejemplos:
        {"action": "youtube", "query": "bad bunny titi me pregunto"}
        {"action": "search", "query": "inteligencia artificial"}
        {"action": "wikipedia", "query": "messi"}
        {"action": "weather", "query": "madrid"}
        {"action": "translate", "query": "hola mundo to english"}
        {"action": "define", "query": "amor"}
        {"action": "open_url", "url": "https://github.com"}
    """
    action = parameters.get("action", "").lower().strip()
    query = parameters.get("query", "").strip()
    url = parameters.get("url", "").strip()
    
    # Validación básica
    if action not in ["play_youtube", "youtube", "search", "wikipedia", "bing", 
                      "open_url", "go_to", "translate", "maps", "images", 
                      "news", "define", "weather", "calculator", 
                      "youtube_music", "what_is"]:
        return f"❌ Acción '{action}' no reconocida. Acciones: youtube, search, wikipedia, bing, open_url, translate, maps, images, news, define, weather, calculator, what_is"
    
    # === ACCIONES QUE NO NECESITAN QUERY ===
    
    # Abrir URL directa
    if action in ("open_url", "go_to"):
        if not url:
            return "❌ Necesito una URL para abrir (parámetro 'url')"
        
        # Asegurar que tenga http:// o https://
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        try:
            webbrowser.open(url)
            return f"🌐 Abriendo {url}"
        except Exception as e:
            return f"❌ Error abriendo URL: {e}"
    
    # Si las demás acciones requieren query
    if not query:
        return f"❌ Necesito un 'query' para la acción '{action}'"
    
    try:
        # ============================================================
        # 1. YOUTUBE (reproducir música/videos)
        # ============================================================
        if action in ("play_youtube", "youtube", "youtube_music"):
            return _play_youtube(query, player)
        
        # ============================================================
        # 2. GOOGLE SEARCH (búsqueda general)
        # ============================================================
        elif action == "search":
            encoded = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded}"
            webbrowser.open(search_url)
            
            if player:
                player.write_log(f"🔍 Buscando '{query}' en Google")
            
            return f"🔍 Buscando '{query}' en Google"
        
        # ============================================================
        # 3. WIKIPEDIA
        # ============================================================
        elif action == "wikipedia":
            encoded = urllib.parse.quote(query)
            wiki_url = f"https://es.wikipedia.org/wiki/{encoded}"
            webbrowser.open(wiki_url)
            return f"📚 Buscando '{query}' en Wikipedia"
        
        # ============================================================
        # 4. BING
        # ============================================================
        elif action == "bing":
            encoded = urllib.parse.quote(query)
            bing_url = f"https://www.bing.com/search?q={encoded}"
            webbrowser.open(bing_url)
            return f"🔍 Buscando '{query}' en Bing"
        
        # ============================================================
        # 5. GOOGLE TRANSLATE
        # ============================================================
        elif action == "translate":
            # Detectar idioma de destino
            text_to_translate = query
            target_lang = "es"  # por defecto a español
            
            # Comandos como "hello world to english" o "hola mundo al inglés"
            if " to " in query.lower():
                parts = query.lower().split(" to ")
                text_to_translate = parts[0].strip()
                lang_dest = parts[1].strip()
                
                # Mapeo de idiomas
                lang_map = {
                    "english": "en", "inglés": "en", "ingles": "en",
                    "spanish": "es", "español": "es", "espanol": "es",
                    "french": "fr", "francés": "fr", "frances": "fr",
                    "german": "de", "alemán": "de", "aleman": "de",
                    "italian": "it", "italiano": "it",
                    "portuguese": "pt", "portugués": "pt", "portugues": "pt",
                    "chinese": "zh", "chino": "zh",
                    "japanese": "ja", "japonés": "ja", "japones": "ja",
                    "russian": "ru", "ruso": "ru",
                    "arabic": "ar", "árabe": "ar", "arabe": "ar"
                }
                target_lang = lang_map.get(lang_dest, "en")
                query = text_to_translate
            
            encoded = urllib.parse.quote(query)
            translate_url = f"https://translate.google.com/?sl=auto&tl={target_lang}&text={encoded}"
            webbrowser.open(translate_url)
            return f"🌐 Traduciendo '{query[:50]}' al {target_lang} en Google Translate"
        
        # ============================================================
        # 6. GOOGLE MAPS
        # ============================================================
        elif action == "maps":
            encoded = urllib.parse.quote(query)
            maps_url = f"https://www.google.com/maps/search/{encoded}"
            webbrowser.open(maps_url)
            return f"🗺️ Buscando '{query}' en Google Maps"
        
        # ============================================================
        # 7. GOOGLE IMAGES
        # ============================================================
        elif action == "images":
            encoded = urllib.parse.quote(query)
            images_url = f"https://www.google.com/search?q={encoded}&tbm=isch"
            webbrowser.open(images_url)
            return f"🖼️ Buscando imágenes de '{query}'"
        
        # ============================================================
        # 8. GOOGLE NEWS
        # ============================================================
        elif action == "news":
            encoded = urllib.parse.quote(query)
            news_url = f"https://news.google.com/search?q={encoded}"
            webbrowser.open(news_url)
            return f"📰 Buscando noticias sobre '{query}'"
        
        # ============================================================
        # 9. DEFINICIÓN (diccionario)
        # ============================================================
        elif action == "define":
            encoded = urllib.parse.quote(query)
            define_url = f"https://www.google.com/search?q=define%3A+{encoded}"
            webbrowser.open(define_url)
            return f"📖 Buscando definición de '{query}'"
        
        # ============================================================
        # 10. CLIMA
        # ============================================================
        elif action == "weather":
            encoded = urllib.parse.quote(query)
            weather_url = f"https://www.google.com/search?q=clima+{encoded}"
            webbrowser.open(weather_url)
            return f"🌤️ Buscando el clima de '{query}'"
        
        # ============================================================
        # 11. CALCULADORA
        # ============================================================
        elif action == "calculator":
            encoded = urllib.parse.quote(query)
            calc_url = f"https://www.google.com/search?q={encoded}"
            webbrowser.open(calc_url)
            return f"🧮 Calculando '{query}' en Google"
        
        # ============================================================
        # 12. WHAT IS (preguntas rápidas)
        # ============================================================
        elif action == "what_is":
            encoded = urllib.parse.quote(query)
            what_url = f"https://www.google.com/search?q=what+is+{encoded}"
            webbrowser.open(what_url)
            return f"❓ Buscando información sobre '{query}'"
        
        else:
            return f"❌ Acción '{action}' no implementada"
    
    except Exception as e:
        error_msg = f"❌ Error en web_navigation: {str(e)}\n{traceback.format_exc()}"
        if player:
            player.write_log(error_msg)
        return f"Error al navegar: {str(e)}"


def _play_youtube(query: str, player=None) -> str:
    """
    Reproduce música/videos en YouTube.
    Intenta múltiples métodos para asegurar reproducción.
    """
    try:
        # MÉTODO 1: pywhatkit (reproduce directamente)
        try:
            import pywhatkit
            if player:
                player.write_log(f"▶️ Reproduciendo '{query}' en YouTube...")
            
            # pywhatkit.playonyt() abre y reproduce
            pywhatkit.playonyt(query)
            
            if player and hasattr(player, "set_state"):
                player.set_state("SUCCESS")
            
            return f"🎵 Reproduciendo '{query}' en YouTube"
        
        except ImportError:
            if player:
                player.write_log("⚠️ pywhatkit no instalado, usando método alternativo")
        
        except Exception as e:
            if player:
                player.write_log(f"⚠️ pywhatkit falló: {e}, usando fallback")
        
        # MÉTODO 2: Abrir YouTube con la búsqueda
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        webbrowser.open(search_url)
        
        # MÉTODO 3: Intentar abrir directamente el primer video
        time.sleep(1.5)  # Esperar a que cargue
        try:
            # Intentar obtener el ID del primer video (opcional)
            import requests
            from bs4 import BeautifulSoup
            
            response = requests.get(search_url, timeout=5)
            if response.status_code == 200:
                # Buscar el primer link de video
                video_ids = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', response.text)
                if video_ids:
                    direct_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
                    webbrowser.open(direct_url)
                    return f"🎵 Reproduciendo '{query}' en YouTube (primer resultado)"
        except:
            pass  # Si falla, al menos abrió la búsqueda
        
        return f"🔍 Abriendo YouTube con búsqueda: '{query}'. Haz clic en el video para reproducir."
    
    except Exception as e:
        # ÚLTIMO RECURSO: Solo abrir YouTube
        webbrowser.open("https://www.youtube.com")
        return f"⚠️ No se pudo reproducir '{query}'. Abrí YouTube para que busques manualmente. Error: {str(e)}"


# ============================================================
# FUNCIONES ADICIONALES ÚTILES
# ============================================================

def web_search_advanced(parameters: dict, player=None) -> str:
    """
    Búsqueda avanzada con filtros.
    
    Parámetros:
        query: texto a buscar
        site: buscar solo en un sitio (ej: "wikipedia.org")
        filetype: tipo de archivo (ej: "pdf")
        time: tiempo (ej: "day", "week", "month", "year")
        region: región (ej: "es", "us")
    """
    query = parameters.get("query", "").strip()
    site = parameters.get("site", "")
    filetype = parameters.get("filetype", "")
    time_range = parameters.get("time", "")
    region = parameters.get("region", "")
    
    if not query:
        return "❌ Necesito un query para buscar"
    
    # Construir URL de Google con filtros
    url = "https://www.google.com/search?q="
    
    # Query principal
    full_query = query
    
    # Filtro por sitio
    if site:
        full_query += f" site:{site}"
    
    # Filtro por tipo de archivo
    if filetype:
        full_query += f" filetype:{filetype}"
    
    # Filtro de tiempo
    if time_range:
        time_params = {
            "day": "&tbs=qdr:d",
            "week": "&tbs=qdr:w",
            "month": "&tbs=qdr:m",
            "year": "&tbs=qdr:y"
        }
        time_param = time_params.get(time_range.lower(), "")
    else:
        time_param = ""
    
    # Región
    if region:
        url += f"&cr=country{region.upper()}"
    
    encoded = urllib.parse.quote(full_query)
    full_url = f"{url}{encoded}{time_param}"
    
    webbrowser.open(full_url)
    return f"🔍 Búsqueda avanzada: {full_query}"


def open_website(parameters: dict, player=None) -> str:
    """
    Abre sitios web comunes rápidamente.
    
    Sitios predefinidos:
        google, youtube, gmail, drive, github, twitter, facebook, instagram,
        whatsapp, telegram, reddit, linkedin, twitch, spotify, netflix, amazon
    """
    site = parameters.get("site", "").lower().strip()
    custom_url = parameters.get("url", "").strip()
    
    # Sitios predefinidos
    sites = {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "drive": "https://drive.google.com",
        "github": "https://github.com",
        "twitter": "https://twitter.com",
        "facebook": "https://facebook.com",
        "instagram": "https://instagram.com",
        "whatsapp": "https://web.whatsapp.com",
        "telegram": "https://web.telegram.org",
        "reddit": "https://reddit.com",
        "linkedin": "https://linkedin.com",
        "twitch": "https://twitch.tv",
        "spotify": "https://open.spotify.com",
        "netflix": "https://netflix.com",
        "amazon": "https://amazon.com",
        "wikipedia": "https://wikipedia.org",
        "bing": "https://bing.com",
        "yahoo": "https://yahoo.com",
    }
    
    if custom_url:
        if not custom_url.startswith(("http://", "https://")):
            custom_url = "https://" + custom_url
        webbrowser.open(custom_url)
        return f"🌐 Abriendo {custom_url}"
    
    if site in sites:
        webbrowser.open(sites[site])
        return f"🌐 Abriendo {site.title()}"
    
    return f"❌ Sitio '{site}' no reconocido. Disponibles: {', '.join(sites.keys())}"


# ============================================================
# COMANDO DE VOZ UNIFICADO
# ============================================================

def web_voice(voice_text: str, player=None) -> str:
    """
    Convierte comandos de voz a acciones web.
    
    Ejemplos:
        "reproduce bad bunny en youtube"
        "busca inteligencia artificial"
        "abre wikipedia"
        "qué es el amor"
        "clima en madrid"
        "traduce hola mundo al inglés"
        "define felicidad"
        "abre gmail"
    """
    text = voice_text.lower()
    
    # YouTube
    if any(word in text for word in ["reproduce", "pon", "toca", "play en youtube"]):
        for word in ["reproduce", "pon", "toca"]:
            if word in text:
                song = text.split(word, 1)[1].replace("en youtube", "").replace("youtube", "").strip()
                if song:
                    return web_navigation({"action": "youtube", "query": song}, player)
        return web_navigation({"action": "youtube", "query": text.replace("youtube", "").strip()}, player)
    
    # Wikipedia
    elif "wikipedia" in text or "busca en wikipedia" in text:
        topic = text.replace("wikipedia", "").replace("busca en", "").strip()
        return web_navigation({"action": "wikipedia", "query": topic}, player)
    
    # Búsqueda general
    elif "busca" in text or "buscar" in text or "google" in text:
        query = text.replace("busca", "").replace("buscar", "").replace("google", "").strip()
        return web_navigation({"action": "search", "query": query}, player)
    
    # Clima
    elif "clima" in text or "tiempo" in text:
        city = text.replace("clima", "").replace("tiempo", "").replace("en", "").strip()
        return web_navigation({"action": "weather", "query": city}, player)
    
    # Traducción
    elif "traduce" in text:
        rest = text.replace("traduce", "").strip()
        return web_navigation({"action": "translate", "query": rest}, player)
    
    # Definición
    elif "define" in text or "qué significa" in text:
        word = text.replace("define", "").replace("qué significa", "").strip()
        return web_navigation({"action": "define", "query": word}, player)
    
    # Pregunta "qué es"
    elif "qué es" in text:
        topic = text.replace("qué es", "").strip()
        return web_navigation({"action": "what_is", "query": topic}, player)
    
    # Mapas
    elif "mapa" in text or "dónde está" in text:
        location = text.replace("mapa", "").replace("dónde está", "").strip()
        return web_navigation({"action": "maps", "query": location}, player)
    
    # Noticias
    elif "noticias" in text:
        news = text.replace("noticias", "").replace("de", "").strip()
        if news:
            return web_navigation({"action": "news", "query": news}, player)
        return web_navigation({"action": "search", "query": "últimas noticias"}, player)
    
    # Imágenes
    elif "imagen" in text or "foto" in text or "imágenes" in text:
        img = text.replace("imagen", "").replace("foto", "").replace("imágenes", "").strip()
        return web_navigation({"action": "images", "query": img}, player)
    
    # Abrir sitio
    elif "abre" in text:
        site = text.replace("abre", "").strip()
        return open_website({"site": site}, player)
    
    return "❓ No entendí el comando web. Ejemplos: 'reproduce bad bunny', 'busca inteligencia artificial', 'abre youtube', 'clima en madrid'"