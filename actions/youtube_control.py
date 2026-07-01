"""
YouTube Control Module for ILUM
===============================
Permite controlar YouTube a través de atajos de teclado web.
"""

import time
import webbrowser
import urllib.parse
import urllib.request
import re
try:
    import pyautogui
except ImportError:
    pyautogui = None
try:
    import pygetwindow as gw
except ImportError:
    gw = None

def focus_browser():
    """Intenta enfocar un navegador abierto para enviar comandos de teclado."""
    if not gw:
        return
    browsers = ["Chrome", "Edge", "Firefox", "Brave", "Opera"]
    for window in gw.getWindowsWithTitle(""):
        title = window.title.lower()
        if "youtube" in title or any(b.lower() in title for b in browsers):
            try:
                if window.isMinimized:
                    window.restore()
                window.activate()
                time.sleep(0.5)
                return True
            except Exception:
                continue
    return False

def youtube_control(parameters: dict, player=None) -> str:
    """
    Control de YouTube vía atajos nativos de navegador.
    Acciones: open, search, play_pause, next, mute, fullscreen
    """
    action = parameters.get("action", "open").lower()
    query = parameters.get("query", "")

    if not pyautogui:
        return "❌ Error: PyAutoGUI no está instalado."

    # Mapeo de sinónimos de acciones
    if action in ["play", "pause", "pausar", "reproducir"]:
        action = "play_pause"
    elif action in ["siguiente", "next", "pasar"]:
        action = "next"
    elif action in ["buscar", "search"]:
        action = "search"
    elif action in ["silenciar", "mutear", "mute"]:
        action = "mute"
    elif action in ["fullscreen", "pantalla_completa", "ampliar"]:
        action = "fullscreen"
    elif action in ["reproducir_video", "play_video"]:
        action = "play_video"

    if action == "open":
        if player: player.write_log("🎵 Abriendo YouTube...")
        webbrowser.open("https://www.youtube.com")
        return "✅ YouTube abierto en tu navegador."
        
    elif action == "search":
        if not query:
            return "❌ Error: Se necesita especificar qué buscar ('query')."
        if player: player.write_log(f"🔍 Buscando '{query}' en YouTube...")
        # Direct search via URL is safer than typing
        encoded_query = urllib.parse.quote(query)
        webbrowser.open(f"https://www.youtube.com/results?search_query={encoded_query}")
        return f"✅ Buscando '{query}' en YouTube."

    elif action == "play_video":
        if not query:
            return "❌ Error: Se necesita especificar qué video reproducir ('query')."
        if player: player.write_log(f"🎵 Buscando y reproduciendo '{query}'...")
        
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded_query}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req).read().decode('utf-8')
            video_ids = re.findall(r"watch\?v=(\S{11})", html)
            if video_ids:
                webbrowser.open(f"https://www.youtube.com/watch?v={video_ids[0]}")
                return f"✅ Reproduciendo '{query}' en YouTube."
            else:
                webbrowser.open(url)
                return f"⚠️ No se encontró video exacto. Mostrando resultados para '{query}'."
        except Exception as e:
            webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
            return f"⚠️ Error al obtener video directo, abriendo búsqueda."

    else:
        # Acciones que requieren enfocar el navegador e inyectar teclas
        if not focus_browser():
            if player: player.write_log("⚠️ No se pudo enfocar el navegador. Asegúrate de tener YouTube abierto.")
            
        if action == "play_pause":
            if player: player.write_log("⏯️ Play / Pausa en YouTube...")
            pyautogui.press('k')
            return "✅ Comando Play/Pausa enviado a YouTube."
            
        elif action == "next":
            if player: player.write_log("⏭️ Siguiente video...")
            pyautogui.hotkey('shift', 'n')
            return "✅ Comando de Siguiente video enviado."
            
        elif action == "mute":
            if player: player.write_log("🔇 Silenciando YouTube...")
            pyautogui.press('m')
            return "✅ Comando de Mute enviado a YouTube."
            
        elif action == "fullscreen":
            if player: player.write_log("🖥️ Cambiando Pantalla Completa...")
            pyautogui.press('f')
            return "✅ Comando de Pantalla Completa enviado."

    return f"❌ Acción '{action}' no reconocida para YouTube."
