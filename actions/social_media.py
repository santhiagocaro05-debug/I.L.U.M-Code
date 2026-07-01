"""
Social Media Hub for ILUM
=========================
Búsqueda de perfiles y videos en redes (IG, TikTok, FB) 
y descarga de videos en máxima calidad sin marca de agua usando yt-dlp.
"""

import webbrowser
import urllib.parse
import os
from pathlib import Path
import threading

def social_media(parameters: dict, player=None) -> str:
    action = parameters.get("action", "search_profile").lower()
    platform = parameters.get("platform", "instagram").lower()
    query = parameters.get("query", "")
    url = parameters.get("url", "")
    
    # Búsqueda de perfiles
    if action == "search_profile":
        if not query:
            return "❌ Por favor especifica el usuario o nombre a buscar."
            
        if "tiktok" in platform:
            # TikTok perfiles empiezan con @
            username = query if query.startswith("@") else f"@{query}"
            search_url = f"https://www.tiktok.com/{username}"
            webbrowser.open(search_url)
            return f"📱 Buscando el perfil de '{username}' en TikTok."
            
        elif "instagram" in platform or "ig" in platform:
            # Instagram es directo al username
            username = query.replace("@", "")
            search_url = f"https://www.instagram.com/{username}/"
            webbrowser.open(search_url)
            return f"📸 Buscando el perfil de '{username}' en Instagram."
            
        elif "facebook" in platform or "fb" in platform:
            search_url = f"https://www.facebook.com/search/people/?q={urllib.parse.quote(query)}"
            webbrowser.open(search_url)
            return f"👥 Buscando a '{query}' en Facebook."
            
        else:
            return f"❌ Plataforma {platform} no soportada para búsqueda directa."
            
    # Búsqueda de videos
    elif action == "search_video":
        if not query:
            return "❌ Específica qué video buscar."
            
        if "tiktok" in platform:
            search_url = f"https://www.tiktok.com/search?q={urllib.parse.quote(query)}"
        elif "instagram" in platform or "ig" in platform:
            search_url = f"https://www.instagram.com/explore/tags/{urllib.parse.quote(query.replace(' ',''))}/"
        else:
            search_url = f"https://www.google.com/search?q=site:{platform}.com+{urllib.parse.quote(query)}"
            
        webbrowser.open(search_url)
        return f"🔍 Buscando videos sobre '{query}' en {platform}."

    # Descarga de videos sin marca de agua
    elif action == "download_video":
        if not url:
            return "❌ Específica la URL del video a descargar."
            
        download_dir = Path(os.path.expanduser("~")) / "Downloads"
        
        def run_download():
            try:
                import yt_dlp
                ydl_opts = {
                    'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
                    'format': 'bestvideo+bestaudio/best',
                    'merge_output_format': 'mp4',
                    'quiet': True,
                    'no_warnings': True,
                    # yt-dlp by default downloads TikTok without watermarks if it selects the right format.
                }
                if player:
                    player.write_log(f"⬇️ Iniciando descarga de video: {url}")
                    
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    
                if player:
                    player.write_log(f"✅ Descarga completada. Revisa tu carpeta de Descargas.")
            except Exception as e:
                if player:
                    player.write_log(f"❌ Error al descargar video: {e}")

        # Ejecutar en hilo separado para no bloquear la interfaz
        t = threading.Thread(target=run_download, daemon=True)
        t.start()
        
        return "⬇️ Descarga iniciada en segundo plano. Te avisaré cuando termine."
        
    return "❌ Acción de redes sociales no reconocida."
