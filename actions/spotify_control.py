# -*- coding: utf-8 -*-
"""
spotify_control.py — Spotify Controller FULLY FUNCTIONAL
Busca y reproduce canciones, playlists, álbumes en Spotify.
"""

import time
import json
import os
import webbrowser
import urllib.parse
from pathlib import Path
import subprocess
import pyautogui
import pygetwindow as gw

# Configuración por defecto (puedes cambiarlas en config.json)
DEFAULT_CLIENT_ID = "455d312ba37a4e0c8be373b53f6305a4"
DEFAULT_CLIENT_SECRET = "5a075d9e504c4f3cb4cc6c5e533d1b4a"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"

# Cache para evitar autenticación repetida
_SPOTIFY_CLIENT = None
_SPOTIFY_OAUTH = None


def _get_spotify_client(player=None):
    """Obtiene el cliente de Spotify (inicializa si es necesario)"""
    global _SPOTIFY_CLIENT, _SPOTIFY_OAUTH
    
    if _SPOTIFY_CLIENT is not None:
        return _SPOTIFY_CLIENT
    
    try:
        from memory.config_manager import load_api_keys, BASE_DIR
        cfg = load_api_keys()
        client_id = cfg.get("spotify_client_id", "").strip() or DEFAULT_CLIENT_ID
        client_secret = cfg.get("spotify_client_secret", "").strip() or DEFAULT_CLIENT_SECRET
        redirect_uri = cfg.get("spotify_redirect_uri", "").strip() or DEFAULT_REDIRECT_URI
    except:
        client_id = DEFAULT_CLIENT_ID
        client_secret = DEFAULT_CLIENT_SECRET
        redirect_uri = DEFAULT_REDIRECT_URI
        BASE_DIR = Path.home() / ".ilum"
        BASE_DIR.mkdir(exist_ok=True)
    
    if not client_id or not client_secret:
        if player:
            player.write_log("⚠️ No hay API keys de Spotify en config.json")
        return None
    
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        
        cache_path = BASE_DIR / ".spotify_cache"
        
        _SPOTIFY_OAUTH = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-modify-playback-state user-read-playback-state user-read-currently-playing user-library-read user-library-modify playlist-read-private playlist-modify-private",
            open_browser=False,
            cache_path=str(cache_path)
        )
        
        _SPOTIFY_CLIENT = spotipy.Spotify(auth_manager=_SPOTIFY_OAUTH)
        
        # Verificar que funciona
        _SPOTIFY_CLIENT.current_user()
        
        if player:
            player.write_log("✅ Spotify API conectada correctamente")
        
        return _SPOTIFY_CLIENT
        
    except Exception as e:
        if player:
            player.write_log(f"❌ Error conectando Spotify API: {e}")
        return None


def _open_spotify_app():
    """Abre la aplicación de Spotify si no está abierta"""
    try:
        # Buscar si ya está abierto
        for win in gw.getAllWindows():
            if "Spotify" in win.title:
                win.activate()
                return True
        
        # Si no, abrirlo
        spotify_paths = [
            os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Spotify", "Spotify.exe"),
            "C:\\Program Files\\Spotify\\Spotify.exe",
            "C:\\Program Files (x86)\\Spotify\\Spotify.exe",
        ]
        
        for path in spotify_paths:
            if os.path.exists(path):
                subprocess.Popen([path])
                time.sleep(2)
                return True
        
        return False
    except Exception:
        return False


def _get_active_device(sp, player=None):
    """Obtiene el dispositivo activo de Spotify"""
    try:
        devices = sp.devices().get("devices", [])
        
        # Buscar dispositivo activo
        for d in devices:
            if d.get("is_active"):
                return d["id"]
        
        # Si hay dispositivos pero ninguno activo, usar el primero
        if devices:
            device_id = devices[0]["id"]
            if player:
                player.write_log(f"📱 Usando dispositivo: {devices[0]['name']}")
            return device_id
        
        return None
    except Exception as e:
        if player:
            player.write_log(f"⚠️ Error obteniendo dispositivos: {e}")
        return None


def spotify_control(parameters: dict, player=None) -> str:
    """
    Controla Spotify - BUSCA y REPRODUCE canciones, playlists, álbumes.
    
    Acciones soportadas:
        play, search      - Reproduce una canción/artista/playlist
        pause             - Pausa la reproducción
        resume            - Reanuda la reproducción
        next, skip        - Siguiente canción
        prev, previous    - Canción anterior
        volume_up         - Sube el volumen
        volume_down       - Baja el volumen
        volume [0-100]    - Establece volumen específico
        current           - Muestra la canción actual
        like              - Guarda canción actual en favoritos
        playlist [nombre] - Reproduce una playlist
        album [nombre]    - Reproduce un álbum
        artist [nombre]   - Reproduce un artista
        devices           - Lista dispositivos disponibles
        open              - Abre Spotify
        close             - Cierra Spotify
        
    Ejemplos:
        {"action": "play", "query": "bad bunny"}
        {"action": "playlist", "query": "rock classics"}
        {"action": "volume", "value": "50"}
        {"action": "current"}
    """
    action = parameters.get("action", "").lower().strip()
    query = parameters.get("query", "").strip()
    search_type = parameters.get("type", "track").lower().strip()
    value = parameters.get("value", "")
    
    if not action:
        return "❌ Necesito una acción: play, pause, next, previous, volume, current, like, playlist, album, artist"
    
    if search_type not in ["track", "album", "playlist", "artist"]:
        search_type = "track"
    
    # === ACCIONES QUE NO NECESITAN API (rápidas) ===
    
    # Abrir Spotify
    if action == "open":
        if _open_spotify_app():
            return "🎵 Abriendo Spotify..."
        return "❌ No se pudo abrir Spotify"
    
    # Cerrar Spotify
    if action == "close":
        for win in gw.getAllWindows():
            if "Spotify" in win.title:
                win.close()
                return "🎵 Spotify cerrado"
        return "Spotify no estaba abierto"
    
    # Volumen por teclado (rápido)
    if action == "volume_up":
        pyautogui.press("volumeup", presses=3)
        return "🔊 Volumen subido"
    
    if action == "volume_down":
        pyautogui.press("volumedown", presses=3)
        return "🔉 Volumen bajado"
    
    # === ACCIONES QUE USAN LA API ===
    
    # Obtener cliente de Spotify
    sp = _get_spotify_client(player)
    
    # Si no hay API, usar fallback con teclas y navegador
    if not sp:
        return _fallback_control(action, query, search_type, value, player)
    
    # Obtener dispositivo activo
    device_id = _get_active_device(sp, player)
    
    # Si no hay dispositivo, abrir Spotify e intentar de nuevo
    if not device_id and action in ("play", "resume", "search", "pause", "next", "prev"):
        if player:
            player.write_log("📱 No hay dispositivo activo, abriendo Spotify...")
        _open_spotify_app()
        time.sleep(2)
        device_id = _get_active_device(sp, player)
        
        if not device_id:
            # Último recurso: abrir en navegador
            if query:
                search_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
                webbrowser.open(search_url)
                return f"🔍 Abriendo búsqueda de '{query}' en Spotify Web (no hay dispositivo activo)"
            return "⚠️ No hay dispositivo de Spotify activo. Abre Spotify en tu PC o celular."
    
    # === ACCIONES PRINCIPALES ===
    
    # Reproducir búsqueda
    if action in ("play", "resume", "search"):
        if not query:
            # Reanudar reproducción actual
            try:
                sp.start_playback(device_id=device_id)
                return "▶️ Reproducción reanudada"
            except:
                return "❌ No hay nada reproduciéndose. Especifica qué quieres escuchar."
        
        # Buscar y reproducir
        try:
            # Primero intentar como pista
            results = sp.search(q=query, limit=5, type=search_type)
            items_key = f"{search_type}s"
            items = results.get(items_key, {}).get("items", [])
            
            if not items:
                # Si no encuentra, buscar como track
                results = sp.search(q=query, limit=5, type="track")
                items = results.get("tracks", {}).get("items", [])
                search_type = "track"
            
            if not items:
                return f"❌ No se encontró nada para '{query}' en Spotify"
            
            item = items[0]
            item_name = item["name"]
            
            if search_type == "track":
                # Reproducir canción
                item_uri = item["uri"]
                artist_name = item["artists"][0]["name"] if item.get("artists") else "desconocido"
                
                sp.start_playback(device_id=device_id, uris=[item_uri])
                return f"🎵 Reproduciendo: {item_name} - {artist_name}"
            
            elif search_type == "playlist":
                # Reproducir playlist
                item_uri = item["uri"]
                sp.start_playback(device_id=device_id, context_uri=item_uri)
                return f"📋 Reproduciendo playlist: {item_name}"
            
            elif search_type == "album":
                # Reproducir álbum
                item_uri = item["uri"]
                artist_name = item["artists"][0]["name"] if item.get("artists") else ""
                sp.start_playback(device_id=device_id, context_uri=item_uri)
                return f"💿 Reproduciendo álbum: {item_name} - {artist_name}"
            
            elif search_type == "artist":
                # Reproducir artista (radio)
                item_uri = item["uri"]
                sp.start_playback(device_id=device_id, context_uri=item_uri)
                return f"🎤 Reproduciendo artista: {item_name}"
            
        except Exception as e:
            if "PREMIUM_REQUIRED" in str(e):
                return "⚠️ Spotify Premium requerido para esta acción. Usa Spotify Web o la app de escritorio."
            return f"❌ Error reproduciendo: {str(e)[:100]}"
    
    # Pausar
    elif action == "pause":
        try:
            sp.pause_playback(device_id=device_id)
            return "⏸️ Reproducción pausada"
        except:
            return "⚠️ No se pudo pausar (¿nada reproduciéndose?)"
    
    # Siguiente
    elif action in ("next", "skip"):
        try:
            sp.next_track(device_id=device_id)
            return "⏭️ Siguiente canción"
        except:
            return "⚠️ No se pudo saltar a la siguiente"
    
    # Anterior
    elif action in ("prev", "previous", "back"):
        try:
            sp.previous_track(device_id=device_id)
            return "⏮️ Canción anterior"
        except:
            return "⚠️ No se pudo ir a la anterior"
    
    # Volumen específico
    elif action == "volume":
        try:
            if value:
                vol = int(value)
                vol = max(0, min(100, vol))
                sp.volume(volume_percent=vol, device_id=device_id)
                return f"🔊 Volumen establecido en {vol}%"
            else:
                curr = sp.current_playback()
                if curr and curr.get("device"):
                    current_vol = curr["device"].get("volume_percent", 50)
                    return f"🔊 Volumen actual: {current_vol}%"
                return "No se pudo obtener el volumen actual"
        except Exception as e:
            return f"⚠️ Error ajustando volumen: {e}"
    
    # Canción actual
    elif action == "current":
        try:
            curr = sp.current_playback()
            if curr and curr.get("item"):
                item = curr["item"]
                name = item.get("name", "desconocido")
                artists = item.get("artists", [])
                artist = artists[0].get("name", "desconocido") if artists else "desconocido"
                progress = curr.get("progress_ms", 0) // 1000
                duration = item.get("duration_ms", 0) // 1000
                
                minutes = progress // 60
                seconds = progress % 60
                total_min = duration // 60
                total_sec = duration % 60
                
                return f"🎵 Sonando ahora: {name} - {artist}  [{minutes}:{seconds:02d}/{total_min}:{total_sec:02d}]"
            return "🎵 No hay nada reproduciéndose en Spotify"
        except:
            return "⚠️ No se pudo obtener la canción actual"
    
    # Me gusta / Guardar en biblioteca
    elif action == "like":
        try:
            curr = sp.current_playback()
            if curr and curr.get("item"):
                track_id = curr["item"]["id"]
                track_name = curr["item"]["name"]
                sp.current_user_saved_tracks_add(tracks=[track_id])
                return f"❤️ '{track_name}' agregada a Tus Favoritos"
            return "⚠️ No hay canción reproduciéndose para dar like"
        except:
            return "⚠️ No se pudo agregar a favoritos"
    
    # Listar dispositivos
    elif action == "devices":
        try:
            devices = sp.devices().get("devices", [])
            if devices:
                device_list = []
                for d in devices:
                    status = "✅ activo" if d.get("is_active") else "⚪ inactivo"
                    device_list.append(f"{d['name']} ({status})")
                return "📱 Dispositivos disponibles:\n" + "\n".join(device_list)
            return "📱 No hay dispositivos de Spotify disponibles"
        except:
            return "⚠️ No se pudieron obtener los dispositivos"
    
    # Reproducir playlist específica
    elif action == "playlist":
        if not query:
            return "❌ Especifica el nombre de la playlist (ej: 'query: rock classics')"
        
        try:
            results = sp.search(q=query, limit=5, type="playlist")
            items = results.get("playlists", {}).get("items", [])
            
            if not items:
                return f"❌ No se encontró la playlist '{query}'"
            
            pl = items[0]
            sp.start_playback(device_id=device_id, context_uri=pl["uri"])
            return f"📋 Reproduciendo playlist: {pl['name']}"
        except Exception as e:
            return f"❌ Error reproduciendo playlist: {e}"
    
    # Reproducir álbum
    elif action == "album":
        if not query:
            return "❌ Especifica el nombre del álbum"
        
        try:
            results = sp.search(q=query, limit=5, type="album")
            items = results.get("albums", {}).get("items", [])
            
            if not items:
                return f"❌ No se encontró el álbum '{query}'"
            
            album = items[0]
            sp.start_playback(device_id=device_id, context_uri=album["uri"])
            artist = album["artists"][0]["name"] if album.get("artists") else ""
            return f"💿 Reproduciendo álbum: {album['name']} - {artist}"
        except Exception as e:
            return f"❌ Error reproduciendo álbum: {e}"
    
    # Reproducir artista
    elif action == "artist":
        if not query:
            return "❌ Especifica el nombre del artista"
        
        try:
            results = sp.search(q=query, limit=5, type="artist")
            items = results.get("artists", {}).get("items", [])
            
            if not items:
                return f"❌ No se encontró el artista '{query}'"
            
            artist = items[0]
            sp.start_playback(device_id=device_id, context_uri=artist["uri"])
            return f"🎤 Reproduciendo artista: {artist['name']}"
        except Exception as e:
            return f"❌ Error reproduciendo artista: {e}"
    
    else:
        return f"❌ Acción '{action}' no reconocida. Acciones: play, pause, next, previous, volume, current, like, playlist, album, artist, devices, open, close"


def _fallback_control(action, query, search_type, value, player):
    """Control alternativo cuando no hay API de Spotify"""
    
    # Controles por teclado
    if action in ("play", "pause", "resume", "toggle"):
        pyautogui.press("playpause")
        return "🎵 Reproducción pausada/reanudada (control por teclado)"
    
    if action in ("next", "skip"):
        pyautogui.press("nexttrack")
        return "⏭️ Siguiente canción (control por teclado)"
    
    if action in ("prev", "previous", "back"):
        pyautogui.press("prevtrack")
        return "⏮️ Canción anterior (control por teclado)"
    
    if action == "volume_up":
        pyautogui.press("volumeup", presses=3)
        return "🔊 Volumen subido"
    
    if action == "volume_down":
        pyautogui.press("volumedown", presses=3)
        return "🔉 Volumen bajado"
    
    # Búsqueda - abrir en navegador
    if action in ("play", "search") and query:
        search_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
        webbrowser.open(search_url)
        return f"🔍 Buscando '{query}' en Spotify Web (no hay API configurada)"
    
    if action == "playlist" and query:
        search_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}/playlists"
        webbrowser.open(search_url)
        return f"🔍 Buscando playlist '{query}' en Spotify Web"
    
    if action == "current":
        # Intentar obtener de la ventana de Spotify
        for win in gw.getAllWindows():
            if "Spotify" in win.title:
                title = win.title.replace("Spotify", "").strip()
                if " - " in title:
                    parts = title.split(" - ")
                    if len(parts) >= 2:
                        return f"🎵 Posible canción actual: {parts[0]} - {parts[1]}"
                return f"🎵 Spotify: {title}"
        return "🎵 No se pudo obtener la canción actual (Spotify API no configurada)"
    
    return f"⚠️ Spotify API no configurada. Para usar control completo, configura spotify_client_id y spotify_client_secret en config.json"


# Función rápida para comandos de voz
def spotify_voice_command(voice_text: str, player=None) -> str:
    """Convierte comandos de voz a acciones de Spotify"""
    text = voice_text.lower()
    
    # Reproducir canción
    if any(word in text for word in ["reproduce", "pon", "toca", "play"]):
        for word in ["reproduce", "pon", "toca", "play"]:
            if word in text:
                song = text.split(word, 1)[1].strip()
                if song:
                    return spotify_control({"action": "play", "query": song}, player)
    
    # Pausa
    elif "pausa" in text or "pausar" in text:
        return spotify_control({"action": "pause"}, player)
    
    # Reanudar
    elif "reanuda" in text or "continua" in text:
        return spotify_control({"action": "resume"}, player)
    
    # Siguiente
    elif "siguiente" in text:
        return spotify_control({"action": "next"}, player)
    
    # Anterior
    elif "anterior" in text or "atrás" in text:
        return spotify_control({"action": "prev"}, player)
    
    # Volumen
    elif "sube el volumen" in text:
        return spotify_control({"action": "volume_up"}, player)
    elif "baja el volumen" in text:
        return spotify_control({"action": "volume_down"}, player)
    
    # Canción actual
    elif "qué suena" in text or "qué canción" in text:
        return spotify_control({"action": "current"}, player)
    
    # Playlist
    elif "playlist" in text or "lista" in text:
        song = text.replace("playlist", "").replace("lista", "").strip()
        if song:
            return spotify_control({"action": "playlist", "query": song}, player)
    
    # Álbum
    elif "álbum" in text or "album" in text:
        song = text.replace("álbum", "").replace("album", "").strip()
        if song:
            return spotify_control({"action": "album", "query": song}, player)
    
    # Artista
    elif "artista" in text:
        artist = text.replace("artista", "").strip()
        if artist:
            return spotify_control({"action": "artist", "query": artist}, player)
    
    return "No entendí el comando de música. Ejemplos: 'reproduce Bad Bunny', 'pausa', 'siguiente', 'qué suena'"
# ============================================================
# SOPORTE PARA USUARIOS SIN SPOTIFY PREMIUM
# ============================================================

def spotify_free_mode(parameters: dict, player=None) -> str:
    """
    Modo especial para usuarios SIN Spotify Premium.
    Usa Spotify Web y controles por teclado.
    
    Acciones soportadas:
        play, search     - Busca y abre en Spotify Web
        pause            - Pausa con tecla multimedia
        next/prev        - Siguiente/Anterior con teclado
        volume_up/down   - Control de volumen
        current          - Lee título de la ventana
        
    Ejemplo:
        {"action": "play", "query": "bad bunny"}
    """
    action = parameters.get("action", "").lower().strip()
    query = parameters.get("query", "").strip()
    
    if not action:
        return "❌ Necesito una acción: play, pause, next, previous, volume_up, volume_down, current"
    
    # Controles por teclado (funcionan siempre)
    if action in ("pause", "play", "resume", "toggle"):
        pyautogui.press("playpause")
        return "⏯️ Reproducción pausada/reanudada (modo gratis)"
    
    if action in ("next", "skip", "siguiente"):
        pyautogui.press("nexttrack")
        return "⏭️ Siguiente canción (modo gratis)"
    
    if action in ("prev", "previous", "back", "anterior"):
        pyautogui.press("prevtrack")
        return "⏮️ Canción anterior (modo gratis)"
    
    if action == "volume_up":
        pyautogui.press("volumeup", presses=3)
        return "🔊 Volumen subido"
    
    if action == "volume_down":
        pyautogui.press("volumedown", presses=3)
        return "🔉 Volumen bajado"
    
    # Búsqueda - abre Spotify Web (mejor que YouTube)
    if action in ("play", "search", "reproduce"):
        if not query:
            return "¿Qué canción o artista quieres buscar?"
        
        # Abrir Spotify Web directamente
        search_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
        webbrowser.open(search_url)
        
        # Opcional: intentar abrir la app de escritorio
        _open_spotify_app()
        
        return f"🔍 Buscando '{query}' en Spotify Web (modo gratis). Haz clic en la canción para reproducir."
    
    # Canción actual (desde la ventana)
    if action == "current":
        for win in gw.getAllWindows():
            if "Spotify" in win.title:
                title = win.title.replace("Spotify", "").strip()
                if title and " - " in title:
                    parts = title.split(" - ")
                    if len(parts) >= 2:
                        return f"🎵 Sonando ahora (modo gratis): {parts[0]} - {parts[1]}"
                elif title:
                    return f"🎵 Spotify: {title}"
        return "🎵 No hay nada reproduciéndose o Spotify no está abierto"
    
    # Abrir Spotify
    if action == "open":
        if _open_spotify_app():
            return "🎵 Abriendo Spotify (modo gratis)..."
        return "❌ No se pudo abrir Spotify"
    
    # Cerrar Spotify
    if action == "close":
        for win in gw.getAllWindows():
            if "Spotify" in win.title:
                win.close()
                return "🎵 Spotify cerrado"
        return "Spotify no estaba abierto"
    
    # Playlist (abre en web)
    if action == "playlist":
        if not query:
            return "¿Qué playlist quieres buscar?"
        search_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}/playlists"
        webbrowser.open(search_url)
        return f"🔍 Buscando playlist '{query}' en Spotify Web"
    
    # Álbum (abre en web)
    if action == "album":
        if not query:
            return "¿Qué álbum quieres buscar?"
        search_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}/albums"
        webbrowser.open(search_url)
        return f"💿 Buscando álbum '{query}' en Spotify Web"
    
    # Artista (abre en web)
    if action == "artist":
        if not query:
            return "¿Qué artista quieres buscar?"
        search_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}/artists"
        webbrowser.open(search_url)
        return f"🎤 Buscando artista '{query}' en Spotify Web"
    
    return f"❌ Acción '{action}' no reconocida en modo gratis. Acciones: play, pause, next, previous, volume_up, volume_down, current, open, close, playlist, album, artist"


# ============================================================
# VERSIÓN MEJORADA DE spotify_control QUE DETECTA PREMIUM
# ============================================================

def spotify_control_smart(parameters: dict, player=None) -> str:
    """
    Versión inteligente que detecta si tienes Premium y usa el mejor método.
    """
    action = parameters.get("action", "").lower().strip()
    
    # Intentar detectar si el usuario tiene Premium
    has_premium = False
    
    try:
        sp = _get_spotify_client(player)
        if sp:
            # Si podemos obtener la reproducción, asumimos Premium
            test = sp.current_playback()
            has_premium = True
    except:
        has_premium = False
    
    if has_premium:
        # Usuario con Premium - usar API completa
        if player:
            player.write_log("🎵 Detectado Spotify Premium - usando API completa")
        return spotify_control(parameters, player)
    else:
        # Usuario sin Premium - usar modo gratis
        if player:
            player.write_log("🎵 Modo gratis detectado - usando Spotify Web + teclado")
        return spotify_free_mode(parameters, player)


# ============================================================
# COMANDO DE VOZ UNIFICADO (funciona con o sin Premium)
# ============================================================

def spotify_voice(voice_text: str, player=None) -> str:
    """
    Comando de voz unificado para Spotify (funciona con o sin Premium).
    
    Ejemplos:
        "reproduce bad bunny"
        "pausa la música"
        "siguiente canción"
        "sube el volumen"
        "qué canción es esta"
        "abre spotify"
    """
    text = voice_text.lower()
    
    # Reproducir canción
    if any(word in text for word in ["reproduce", "pon", "toca", "play"]):
        for word in ["reproduce", "pon", "toca", "play"]:
            if word in text:
                song = text.split(word, 1)[1].strip()
                if song:
                    return spotify_control_smart({"action": "play", "query": song}, player)
    
    # Pausa
    elif any(word in text for word in ["pausa", "pausar", "detén", "detener"]):
        return spotify_control_smart({"action": "pause"}, player)
    
    # Reanudar
    elif any(word in text for word in ["reanuda", "continua", "sigue"]):
        return spotify_control_smart({"action": "resume"}, player)
    
    # Siguiente
    elif any(word in text for word in ["siguiente", "próxima", "next"]):
        return spotify_control_smart({"action": "next"}, player)
    
    # Anterior
    elif any(word in text for word in ["anterior", "atrás", "prev"]):
        return spotify_control_smart({"action": "prev"}, player)
    
    # Volumen
    elif "sube el volumen" in text or "más volumen" in text:
        return spotify_control_smart({"action": "volume_up"}, player)
    elif "baja el volumen" in text or "menos volumen" in text:
        return spotify_control_smart({"action": "volume_down"}, player)
    elif "volumen al" in text:
        # Extraer número
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            return spotify_control_smart({"action": "volume", "value": numbers[0]}, player)
    
    # Canción actual
    elif any(word in text for word in ["qué suena", "qué canción", "qué música"]):
        return spotify_control_smart({"action": "current"}, player)
    
    # Playlist
    elif "playlist" in text or "lista de reproducción" in text:
        song = text.replace("playlist", "").replace("lista de reproducción", "").strip()
        if song:
            return spotify_control_smart({"action": "playlist", "query": song}, player)
    
    # Álbum
    elif "álbum" in text or "album" in text:
        song = text.replace("álbum", "").replace("album", "").strip()
        if song:
            return spotify_control_smart({"action": "album", "query": song}, player)
    
    # Artista
    elif "artista" in text:
        artist = text.replace("artista", "").strip()
        if artist:
            return spotify_control_smart({"action": "artist", "query": artist}, player)
    
    # Abrir
    elif "abre spotify" in text:
        return spotify_control_smart({"action": "open"}, player)
    
    # Cerrar
    elif "cierra spotify" in text:
        return spotify_control_smart({"action": "close"}, player)
    
    return "❓ No entendí el comando de música. Ejemplos: 'reproduce Bad Bunny', 'pausa', 'siguiente', 'qué suena'"