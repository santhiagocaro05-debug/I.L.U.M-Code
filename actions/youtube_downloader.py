import os
import shutil
import threading
from yt_dlp import YoutubeDL

# Conjunto global para rastrear URLs en proceso de descarga
_ACTIVE_DOWNLOADS = set()
_DOWNLOAD_LOCK = threading.Lock()

class MyLogger:
    def __init__(self, player=None):
        self.player = player
        
    def debug(self, msg):
        pass
        
    def warning(self, msg):
        msg_lower = msg.lower()
        if "dpapi" not in msg_lower and "cookie" not in msg_lower and "javascript runtime" not in msg_lower:
            if self.player:
                self.player.write_log(f"⚠️ {msg}")
                
    def error(self, msg):
        msg_lower = msg.lower()
        if "dpapi" not in msg_lower and "cookie" not in msg_lower:
            if self.player:
                self.player.write_log(f"❌ {msg}")

def download_youtube(parameters: dict, player=None, speak=None) -> str:
    """Descarga videos de YouTube en ALTA CALIDAD (720p, 1080p, 4K, 8K)"""
    
    # Obtener parámetros
    url = parameters.get("url", "").strip()
    opcion = str(parameters.get("opcion", "1"))
    calidad = str(parameters.get("calidad", "5"))  # 5 = 1080p por defecto
    
    # Validar calidad
    try:
        calidad_int = int(calidad)
        if calidad_int < 1:
            calidad_int = 5
        if calidad_int > 8:
            calidad_int = 8
    except:
        calidad_int = 5
        calidad = "5"
    
    # Obtener URL del navegador si es necesario
    if not url or url.lower() == "auto":
        try:
            import pygetwindow as gw
            import pyautogui
            import pyperclip
            import time
            browsers = [w for w in gw.getWindowsWithTitle('') if 'Chrome' in w.title or 'Edge' in w.title or 'Firefox' in w.title]
            if browsers:
                browser = browsers[0]
                try:
                    browser.activate()
                except:
                    pass
                time.sleep(0.1)
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(0.1)
                pyautogui.hotkey('ctrl', 'c')
                time.sleep(0.1)
                url = pyperclip.paste().strip()
        except Exception as e:
            if player: player.write_log(f"⚠️ Error obteniendo URL: {e}")
            
    if not url or not url.startswith('http'):
        return "No se pudo obtener el enlace. Por favor, proporciona una URL válida."

    # Ruta de descargas
    base_descargas = os.path.join(os.path.expanduser("~"), "Downloads", "Nexus_Downloads")
    if opcion == '1':
        ruta_descargas = os.path.join(base_descargas, "Videos")
    else:
        ruta_descargas = os.path.join(base_descargas, "Musica")
    os.makedirs(ruta_descargas, exist_ok=True)

    # Verificar FFmpeg (OBLIGATORIO para HD)
    ffmpeg_location = shutil.which("ffmpeg")
    has_ffmpeg = ffmpeg_location is not None

    if not has_ffmpeg:
        try:
            import sys
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            local_ffmpeg = os.path.join(base_dir, "ffmpeg.exe")
            if os.path.exists(local_ffmpeg):
                ffmpeg_location = local_ffmpeg
                has_ffmpeg = True
        except:
            pass

    # Si no hay FFmpeg, solo se puede hasta 720p (formatos pre-fusionados)
    if not has_ffmpeg:
        if player:
            player.write_log("⚠️ FFmpeg no detectado. La calidad máxima será 720p.")
            player.write_log("💡 Para 1080p/4K/8K instala FFmpeg: winget install ffmpeg")
    
    # ========== FORMATOS CORRECTOS PARA ALTA CALIDAD ==========
    # Con FFmpeg: video+audio separados (CALIDAD REAL)
    # Sin FFmpeg: formatos pre-fusionados (máximo 720p)
    
    calidades_dict = {
        '1': {'name': '144p', 'format': 'worst[height<=144]'},
        '2': {'name': '360p', 'format': 'worst[height<=360]'},
        '3': {'name': '480p', 'format': 'best[height<=480]'},
        '4': {'name': '720p', 'format': 'best[height<=720]'},
        '5': {'name': '1080p', 'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]'},
        '6': {'name': '2K', 'format': 'bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440]'},
        '7': {'name': '4K', 'format': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]'},
        '8': {'name': '8K', 'format': 'bestvideo[height<=4320]+bestaudio/best[height<=4320]'},
    }
    
    # Si no hay FFmpeg, limitar a 720p máximo
    if not has_ffmpeg and calidad_int >= 5:
        if player:
            player.write_log("⚠️ Sin FFmpeg, limitando a 720p máximo")
        calidad_int = 4
        calidad = "4"
    
    calidad_info = calidades_dict.get(str(calidad_int), calidades_dict['4'])
    
    # Mostrar información al usuario
    if player:
        player.write_log(f"🎬 Solicitando: {calidad_info['name']}")
        if has_ffmpeg:
            player.write_log(f"✅ FFmpeg disponible - Calidad REAL disponible")
        else:
            player.write_log(f"⚠️ FFmpeg NO disponible - Calidad limitada a 720p")

    def _download():
        with _DOWNLOAD_LOCK:
            if url in _ACTIVE_DOWNLOADS:
                if speak: speak("Esta descarga ya está en progreso")
                return
            _ACTIVE_DOWNLOADS.add(url)
        
        try:
            logger = MyLogger(player)
            
            # Configurar opciones de descarga MEJORADAS
            ydl_opts = {
                'outtmpl': os.path.join(ruta_descargas, '%(title)s.%(ext)s'),
                'format': calidad_info['format'],
                'no_warnings': True,
                'quiet': True,
                'logger': logger,
                'noplaylist': True,
                'ignoreerrors': True,
                'continuedl': True,
                'retries': 10,
                'fragment_retries': 10,
                'socket_timeout': 30,
            }
            
            # Añadir FFmpeg si está disponible
            if ffmpeg_location:
                ydl_opts['ffmpeg_location'] = ffmpeg_location
            
            # Para HD, especificar formato de salida
            if has_ffmpeg and opcion == '1' and calidad_int >= 4:
                ydl_opts['merge_output_format'] = 'mp4'
                # Priorizar códecs de alta calidad
                ydl_opts['format_sort'] = ['res', 'codec:av1', 'codec:vp9', 'codec:h264']
            
            if player:
                player.write_log(f"📥 Descargando {calidad_info['name']}...")
            
            # Buscar cookies para videos restringidos
            cookies_paths = [
                os.path.join(os.path.expanduser("~"), "Desktop", "cookies.txt"),
                os.path.join(os.path.expanduser("~"), "Downloads", "cookies.txt"),
            ]
            for cookie_path in cookies_paths:
                if os.path.exists(cookie_path):
                    ydl_opts['cookiefile'] = cookie_path
                    if player:
                        player.write_log(f"🍪 Usando cookies: {cookie_path}")
                    break
            
            # Intentar descarga con el formato seleccionado
            success = False
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    # Primero obtener info del video
                    info = ydl.extract_info(url, download=False)
                    available_formats = [f.get('height', 0) for f in info.get('formats', []) if f.get('height')]
                    if player:
                        player.write_log(f"📊 Calidades disponibles: {sorted(set(available_formats))}p")
                    
                    # Descargar
                    code = ydl.download([url])
                    if code == 0:
                        success = True
                        if player:
                            player.write_log(f"✅ Descarga completada en {calidad_info['name']}")
                        if speak:
                            speak(f"Video descargado en {calidad_info['name']}")
                            
            except Exception as e:
                error_msg = str(e)
                if player:
                    player.write_log(f"⚠️ Error: {error_msg[:150]}")
                
                # Fallback 1: Intentar sin video+audio separado
                if "requested format" in error_msg.lower() or "no video formats" in error_msg.lower():
                    fallback_format = 'best[height<=720]' if calidad_int >= 5 else calidad_info['format']
                    if player:
                        player.write_log(f"🔄 Reintentando con formato: {fallback_format}")
                    
                    ydl_opts['format'] = fallback_format
                    try:
                        with YoutubeDL(ydl_opts) as ydl:
                            code = ydl.download([url])
                            if code == 0:
                                success = True
                                if player:
                                    player.write_log(f"✅ Video descargado (calidad alternativa)")
                                if speak:
                                    speak("Video descargado exitosamente")
                    except Exception as e2:
                        if player:
                            player.write_log(f"❌ Falló también: {e2[:100]}")
                
                # Fallback 2: Intentar con cookies del navegador
                if not success:
                    if player:
                        player.write_log("🔄 Intentando con cookies del navegador...")
                    browsers = ['chrome', 'edge', 'firefox', 'brave', 'opera']
                    for browser in browsers:
                        try:
                            ydl_opts['cookiesfrombrowser'] = (browser,)
                            with YoutubeDL(ydl_opts) as ydl:
                                code = ydl.download([url])
                                if code == 0:
                                    success = True
                                    if player:
                                        player.write_log(f"✅ Éxito usando {browser}")
                                    break
                        except:
                            continue
            
            if not success:
                if player:
                    player.write_log("❌ No se pudo completar la descarga")
                if speak:
                    speak("No se pudo descargar el video")
                    
        except Exception as e:
            if player:
                player.write_log(f"❌ Error general: {e}")
        finally:
            with _DOWNLOAD_LOCK:
                _ACTIVE_DOWNLOADS.discard(url)
    
    # Iniciar descarga
    threading.Thread(target=_download, daemon=True).start()
    
    # Mensaje de inicio
    return f"🎬 Iniciando descarga en {calidad_info['name']}. Se guardará en: {ruta_descargas}"