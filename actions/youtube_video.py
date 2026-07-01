"""youtube_video.py — YouTube video launcher with AUTO-PLAY feature."""
import webbrowser
import urllib.parse
import urllib.request
import time
import re
import pyautogui
import pygetwindow as gw


def youtube_video(parameters: dict, response=None, player=None) -> str:
    """
    Busca y REPRODUCE automáticamente un video de YouTube.
    
    Parámetros:
    - query: Título o nombre del video/canción
    - auto_play: True/False (reproduce automáticamente el primer resultado)
    - fullscreen: True/False (pone en pantalla completa)
    """
    query = parameters.get("query", "").strip()
    auto_play = parameters.get("auto_play", True)
    fullscreen = parameters.get("fullscreen", False)
    
    if not query:
        return "Por favor, dime qué video quieres reproducir en YouTube."
    
    try:
        encoded_query = urllib.parse.quote(query)
        
        if auto_play:
            if player:
                player.write_log(f"🔎 Buscando '{query}' en YouTube...")
                
            # MÉTODO 1: Deep Linking Instantáneo
            video_url = None
            try:
                search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
                req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
                html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
                video_ids = re.findall(r"watch\?v=(\S{11})", html)
                if video_ids:
                    video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            except Exception as e:
                if player:
                    player.write_log(f"⚠️ Falló el Deep Link ({e}), usando método clásico...")
            
            if video_url:
                webbrowser.open(video_url)
                msg = f"▶️ Reproduciendo '{query}' en YouTube de forma instantánea."
                if fullscreen:
                    time.sleep(2)
                    pyautogui.press('f')
            else:
                # MÉTODO 2: Clásico con fallback
                url = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAQ%3D%3D"
                webbrowser.open(url)
                time.sleep(1.5)
                
                browser = _find_browser_window()
                if browser:
                    browser.activate()
                    time.sleep(0.5)
                    pyautogui.press('tab')
                    time.sleep(0.2)
                    pyautogui.press('enter')
                    time.sleep(1)
                    pyautogui.press('space')
                    
                    if fullscreen:
                        time.sleep(1)
                        pyautogui.press('f')
                        
                    msg = f"▶️ Reproduciendo '{query}' en YouTube (Modo clásico)."
                else:
                    msg = f"✅ Abriendo búsqueda de '{query}' en YouTube."
        else:
            url = f"https://www.youtube.com/results?search_query={encoded_query}"
            webbrowser.open(url)
            msg = f"🔎 Mostrando resultados de búsqueda para '{query}' en YouTube."
        
        if player:
            player.write_log(msg)
        
        return msg
        
    except Exception as e:
        return f"❌ Error al reproducir video en YouTube: {e}"


def _find_browser_window():
    """Encuentra la ventana del navegador activa"""
    browser_keywords = ["Chrome", "Edge", "Firefox", "Brave", "Opera", "comet", "Safari", "Vivaldi", "YouTube"]
    
    for win in gw.getAllWindows():
        if win.title.strip():
            for kw in browser_keywords:
                if kw.lower() in win.title.lower():
                    return win
    return None


def youtube_music(parameters: dict, player=None) -> str:
    """
    Reproduce música en YouTube Music o YouTube normal.
    Especial para canciones.
    """
    song = parameters.get("song", "").strip()
    artist = parameters.get("artist", "").strip()
    
    if not song:
        return "Por favor, dime qué canción quieres reproducir."
    
    query = f"{song} {artist}".strip()
    encoded_query = urllib.parse.quote(query)
    
    use_youtube_music = parameters.get("use_music", True)
    
    if use_youtube_music:
        url = f"https://music.youtube.com/search?q={encoded_query}"
    else:
        url = f"https://www.youtube.com/results?search_query={encoded_query}"
    
    webbrowser.open(url)
    time.sleep(1.5)
    
    browser = _find_browser_window()
    if browser:
        browser.activate()
        time.sleep(0.5)
        pyautogui.press('tab')
        time.sleep(0.2)
        pyautogui.press('enter')
        time.sleep(0.5)
        pyautogui.press('space')
        
        msg = f"🎵 Reproduciendo '{song}'"
        if artist:
            msg += f" de {artist}"
        
        if player:
            player.write_log(f"🎵 {msg}")
        
        return msg
    else:
        return f"✅ Abriendo '{song}' en YouTube Music."


def youtube_playlist(parameters: dict, player=None) -> str:
    """
    Reproduce una playlist de YouTube.
    """
    playlist_id = parameters.get("playlist_id", "")
    playlist_url = parameters.get("url", "")
    
    if playlist_id:
        url = f"https://www.youtube.com/playlist?list={playlist_id}"
    elif playlist_url:
        url = playlist_url
    else:
        return "Necesito el ID o URL de la playlist de YouTube."
    
    webbrowser.open(url)
    time.sleep(1.5)
    
    browser = _find_browser_window()
    if browser:
        browser.activate()
        time.sleep(0.5)
        pyautogui.press('space')
    
    return f"🎵 Reproduciendo playlist desde {url}"