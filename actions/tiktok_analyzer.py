"""
TikTok Analyzer Module v3.0
===========================
Analiza perfiles públicos de TikTok usando la API interna y Selenium.
Soporta extracción desde __UNIVERSAL_DATA_FOR_REHYDRATION__ y API real.
"""

import json
import re
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, quote
import threading
import importlib

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    webdriver = importlib.import_module("selenium.webdriver")
    By = importlib.import_module("selenium.webdriver.common.by").By
    WebDriverWait = importlib.import_module("selenium.webdriver.support.ui").WebDriverWait
    EC = importlib.import_module("selenium.webdriver.support.expected_conditions")
    Options = importlib.import_module("selenium.webdriver.chrome.options").Options
    exceptions_mod = importlib.import_module("selenium.common.exceptions")
    TimeoutException = exceptions_mod.TimeoutException
    NoSuchElementException = exceptions_mod.NoSuchElementException
except ImportError:
    webdriver = None
    By = None
    WebDriverWait = None
    EC = None
    Options = None
    TimeoutException = None
    NoSuchElementException = None


# ─── CONSTANTES ─────────────────────────────────────────────────────────────
TIKTOK_API_BASE = "https://www.tiktok.com"
TIKTOK_API = "https://www.tiktok.com/api"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

CACHE_DIR = Path("config/tiktok_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_EXPIRY = 900  # 15 minutos (TikTok cambia rápido)


# ─── FUNCIONES DE CACHÉ ──────────────────────────────────────────────────
def get_cache_key(username: str) -> str:
    return f"tiktok_{username.lower()}.json"


def get_cached_profile(username: str) -> Optional[Dict]:
    cache_file = CACHE_DIR / get_cache_key(username)
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - data.get("cached_at", 0) < CACHE_EXPIRY:
                return data.get("profile")
        except:
            pass
    return None


def cache_profile(username: str, profile_data: Dict):
    try:
        cache_file = CACHE_DIR / get_cache_key(username)
        cache_file.write_text(
            json.dumps({
                "cached_at": time.time(),
                "profile": profile_data
            }, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except:
        pass


# ─── EXTRACTOR DE JSON UNIVERSAL (MEJORADO) ──────────────────────────────
def _extract_json_from_script(html: str, script_id: str = "__UNIVERSAL_DATA_FOR_REHYDRATION__") -> Optional[Dict]:
    """
    Extrae y parsea el JSON de un script específico.
    Este es el método principal que usa TikTok actualmente.
    """
    if not html:
        return None

    # Buscar el script con el ID específico
    pattern = rf'<script[^>]*id=["\']?{script_id}["\']?[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    
    if match:
        script_content = match.group(1).strip()
        # Limpiar caracteres problemáticos
        script_content = script_content.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')
        
        try:
            return json.loads(script_content)
        except json.JSONDecodeError:
            # Intentar extraer solo el objeto JSON completo
            try:
                start = script_content.find('{')
                end = script_content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(script_content[start:end])
            except:
                pass
    
    # Buscar cualquier script que contenga datos de usuario
    script_pattern = r'<script[^>]*>(.*?)</script>'
    for script_match in re.finditer(script_pattern, html, re.DOTALL):
        script_text = script_match.group(1)
        if 'UserModule' in script_text or 'ItemModule' in script_text or 'PostModule' in script_text:
            try:
                # Intentar extraer JSON del script
                json_match = re.search(r'({[^{]*"UserModule"[^}]*})', script_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                # Buscar ItemModule
                json_match = re.search(r'({[^{]*"ItemModule"[^}]*})', script_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
            except:
                continue
    
    return None


def _extract_user_from_json(json_data: Dict, username: str) -> Dict:
    """
    Extrae datos del usuario desde cualquier estructura JSON que encuentre.
    """
    result = {
        "username": username,
        "display_name": username,
        "bio": "",
        "followers": 0,
        "following": 0,
        "likes": 0,
        "verified": False,
        "private": False,
        "profile_pic": "",
    }

    if not json_data:
        return result

    # Método 1: __DEFAULT_SCOPE__ -> UserModule -> users
    try:
        default_scope = json_data.get("__DEFAULT_SCOPE__", {})
        user_module = default_scope.get("UserModule", {})
        users = user_module.get("users", {})
        
        for user_id, user_data in users.items():
            if isinstance(user_data, dict):
                if user_data.get("uniqueId", "").lower() == username.lower():
                    result["username"] = user_data.get("uniqueId", username)
                    result["display_name"] = user_data.get("nickname", result["username"])
                    result["bio"] = user_data.get("bioDescription", "")
                    result["followers"] = user_data.get("followerCount", 0)
                    result["following"] = user_data.get("followingCount", 0)
                    result["likes"] = user_data.get("heartCount", 0)
                    result["verified"] = user_data.get("verified", False)
                    result["private"] = user_data.get("privateAccount", False)
                    result["profile_pic"] = user_data.get("avatarMedium", "")
                    break
    except:
        pass

    # Método 2: __DEFAULT_SCOPE__ -> UserInfo
    if not result["display_name"] or result["display_name"] == username:
        try:
            user_info = default_scope.get("UserInfo", {})
            if user_info:
                result["username"] = user_info.get("uniqueId", username)
                result["display_name"] = user_info.get("nickname", result["username"])
                result["bio"] = user_info.get("bioDescription", "")
                result["followers"] = user_info.get("followerCount", 0)
                result["following"] = user_info.get("followingCount", 0)
                result["likes"] = user_info.get("heartCount", 0)
                result["verified"] = user_info.get("verified", False)
                result["private"] = user_info.get("privateAccount", False)
                result["profile_pic"] = user_info.get("avatarMedium", "")
        except:
            pass

    return result


def _extract_videos_from_json(json_data: Dict, username: str, max_videos: int = 10) -> List[Dict]:
    """
    Extrae videos de cualquier estructura JSON de TikTok.
    Soporta ItemModule, PostModule y otras variantes.
    """
    videos = []
    
    if not json_data:
        return videos

    default_scope = json_data.get("__DEFAULT_SCOPE__", {})
    
    # Método 1: ItemModule (más común actualmente)
    try:
        item_module = default_scope.get("ItemModule", {})
        if item_module:
            for item_id, item_data in item_module.items():
                if isinstance(item_data, dict):
                    stats = item_data.get("stats", {})
                    video = {
                        "id": item_id,
                        "url": f"{TIKTOK_API_BASE}/@{username}/video/{item_id}",
                        "description": item_data.get("desc", ""),
                        "plays": stats.get("playCount", 0),
                        "likes": stats.get("diggCount", 0),
                        "comments": stats.get("commentCount", 0),
                        "shares": stats.get("shareCount", 0),
                        "created_at": item_data.get("createTime", 0),
                    }
                    if video["id"]:
                        videos.append(video)
            if videos:
                # Ordenar por fecha
                videos.sort(key=lambda x: x.get("created_at", 0), reverse=True)
                return videos[:max_videos]
    except:
        pass

    # Método 2: PostModule (alternativa)
    try:
        post_module = default_scope.get("PostModule", {})
        if post_module:
            posts = post_module.get("posts", {})
            for post_id, post_data in posts.items():
                if isinstance(post_data, dict):
                    stats = post_data.get("stats", {})
                    video = {
                        "id": post_id,
                        "url": f"{TIKTOK_API_BASE}/@{username}/video/{post_id}",
                        "description": post_data.get("desc", ""),
                        "plays": stats.get("playCount", 0),
                        "likes": stats.get("diggCount", 0),
                        "comments": stats.get("commentCount", 0),
                        "shares": stats.get("shareCount", 0),
                        "created_at": post_data.get("createTime", 0),
                    }
                    if video["id"]:
                        videos.append(video)
            if videos:
                videos.sort(key=lambda x: x.get("created_at", 0), reverse=True)
                return videos[:max_videos]
    except:
        pass

    # Método 3: Buscar directamente en el JSON
    try:
        # Buscar cualquier objeto con "stats" y "id" o "itemId"
        def find_videos(obj, path=""):
            if isinstance(obj, dict):
                # Si tiene stats y un ID, probablemente es un video
                if "stats" in obj and ("id" in obj or "itemId" in obj or "videoId" in obj):
                    stats = obj.get("stats", {})
                    video_id = obj.get("id") or obj.get("itemId") or obj.get("videoId")
                    if video_id and isinstance(video_id, str):
                        video = {
                            "id": video_id,
                            "url": f"{TIKTOK_API_BASE}/@{username}/video/{video_id}",
                            "description": obj.get("desc", ""),
                            "plays": stats.get("playCount", 0),
                            "likes": stats.get("diggCount", 0),
                            "comments": stats.get("commentCount", 0),
                            "shares": stats.get("shareCount", 0),
                            "created_at": obj.get("createTime", 0),
                        }
                        if video["id"] and video["id"] not in [v["id"] for v in videos]:
                            videos.append(video)
                # Recursivo
                for key, value in obj.items():
                    find_videos(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for item in obj:
                    find_videos(item, f"{path}[]")
        
        find_videos(json_data)
        if videos:
            videos.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return videos[:max_videos]
    except:
        pass

    return videos[:max_videos]


# ─── SCRAPER PRINCIPAL ────────────────────────────────────────────────────

class TikTokScraperV3:
    """Scraper de TikTok v3 - Usa JSON de la página principal + Selenium."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.session = requests.Session() if requests else None
        self.driver = None
        self._setup_session()
    
    def _setup_session(self):
        if self.session:
            self.session.headers.update({
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            })
    
    def _get_driver(self):
        """Obtiene o crea el driver de Selenium."""
        if self.driver is None and webdriver:
            options = Options()
            if self.headless:
                options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            
            try:
                self.driver = webdriver.Chrome(options=options)
                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        })
                    """
                })
            except Exception as e:
                print(f"[TikTok] Error creando driver: {e}")
                self.driver = None
        
        return self.driver
    
    def _extract_username(self, url_or_username: str) -> str:
        """Extrae el nombre de usuario de una URL o texto."""
        if not url_or_username:
            return ""
        
        text = url_or_username.strip()
        
        # Si es @username, quitar @
        if text.startswith("@"):
            return text[1:].strip()
        
        # Si es URL, extraer
        try:
            parsed = urlparse(text)
            if parsed.netloc and "tiktok.com" in parsed.netloc:
                path_parts = parsed.path.strip("/").split("/")
                if path_parts and path_parts[0].startswith("@"):
                    return path_parts[0][1:]
        except:
            pass
        
        return text.strip()
    
    def analyze_profile(self, username: str, max_videos: int = 10, force_refresh: bool = False) -> Dict:
        """
        Analiza un perfil de TikTok usando JSON incrustado + Selenium.
        """
        username = self._extract_username(username)
        if not username:
            return {"error": "Nombre de usuario inválido"}

        # Verificar caché
        if not force_refresh:
            cached = get_cached_profile(username)
            if cached:
                return cached

        if not self.session:
            return {"error": "Requests no instalado"}

        try:
            # Obtener la página del perfil
            url = f"{TIKTOK_API_BASE}/@{username}"
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return {"error": f"Error al acceder al perfil: {response.status_code}"}

            html = response.text
            
            # === MÉTODO 1: Extraer JSON de __UNIVERSAL_DATA_FOR_REHYDRATION__ ===
            json_data = _extract_json_from_script(html)
            if json_data:
                profile_data = {}
                user_data = _extract_user_from_json(json_data, username)
                videos = _extract_videos_from_json(json_data, username, max_videos)
                
                if user_data["display_name"] or videos:
                    profile_data.update(user_data)
                    profile_data["videos"] = videos
                    profile_data["video_count"] = len(videos)
                    profile_data["engagement"] = self._calculate_engagement(profile_data)
                    profile_data["platform"] = "tiktok"
                    profile_data["method"] = "json_script"
                    
                    cache_profile(username, profile_data)
                    return profile_data

            # === MÉTODO 2: Selenium (si falla el JSON) ===
            if webdriver and self._get_driver():
                profile_data = self._analyze_with_selenium(username, max_videos)
                if profile_data and profile_data.get("display_name"):
                    cache_profile(username, profile_data)
                    return profile_data

            return {"error": "No se pudieron extraer datos del perfil"}

        except Exception as e:
            print(f"[TikTok] Error: {e}")
            return {"error": f"Error al analizar: {str(e)}"}

    def _analyze_with_selenium(self, username: str, max_videos: int = 10) -> Dict:
        """Analiza usando Selenium para obtener datos de JavaScript."""
        driver = self._get_driver()
        if not driver:
            return {"error": "Selenium no disponible"}

        try:
            url = f"{TIKTOK_API_BASE}/@{username}"
            driver.get(url)
            
            # Esperar a que cargue
            time.sleep(4)
            
            # Intentar obtener __UNIVERSAL_DATA_FOR_REHYDRATION__ desde JavaScript
            try:
                json_data = driver.execute_script("""
                    return window.__UNIVERSAL_DATA_FOR_REHYDRATION__ || null;
                """)
                
                if json_data:
                    profile_data = _extract_user_from_json(json_data, username)
                    videos = _extract_videos_from_json(json_data, username, max_videos)
                    
                    if profile_data["display_name"] or videos:
                        profile_data["videos"] = videos
                        profile_data["video_count"] = len(videos)
                        profile_data["engagement"] = self._calculate_engagement(profile_data)
                        profile_data["platform"] = "tiktok"
                        profile_data["method"] = "selenium_js"
                        return profile_data
            except:
                pass
            
            # Extraer del HTML de Selenium (que incluye JavaScript renderizado)
            html = driver.page_source
            
            # Buscar JSON en el HTML renderizado
            json_data = _extract_json_from_script(html)
            if json_data:
                profile_data = _extract_user_from_json(json_data, username)
                videos = _extract_videos_from_json(json_data, username, max_videos)
                
                if profile_data["display_name"] or videos:
                    profile_data["videos"] = videos
                    profile_data["video_count"] = len(videos)
                    profile_data["engagement"] = self._calculate_engagement(profile_data)
                    profile_data["platform"] = "tiktok"
                    profile_data["method"] = "selenium_html"
                    return profile_data

            return {"error": "No se encontraron datos con Selenium"}

        except Exception as e:
            print(f"[TikTok] Error Selenium: {e}")
            return {"error": f"Error Selenium: {str(e)}"}
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None

    def _calculate_engagement(self, profile: Dict) -> Dict:
        """Calcula métricas de engagement."""
        videos = profile.get("videos", [])
        followers = profile.get("followers", 1)
        
        if not videos or followers == 0:
            return {
                "avg_likes": 0,
                "avg_comments": 0,
                "avg_shares": 0,
                "avg_plays": 0,
                "engagement_rate": 0,
                "total_plays": 0,
                "total_likes": 0,
                "total_comments": 0,
                "total_shares": 0,
            }
        
        video_count = len(videos)
        total_plays = sum(v.get("plays", 0) for v in videos)
        total_likes = sum(v.get("likes", 0) for v in videos)
        total_comments = sum(v.get("comments", 0) for v in videos)
        total_shares = sum(v.get("shares", 0) for v in videos)
        
        total_engagement = total_likes + total_comments + total_shares
        engagement_rate = (total_engagement / followers * 100) if followers > 0 else 0
        
        return {
            "total_plays": total_plays,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "avg_plays": total_plays // video_count if video_count > 0 else 0,
            "avg_likes": total_likes // video_count if video_count > 0 else 0,
            "avg_comments": total_comments // video_count if video_count > 0 else 0,
            "avg_shares": total_shares // video_count if video_count > 0 else 0,
            "engagement_rate": round(engagement_rate, 2),
        }


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────

def tiktok_analyzer(parameters: dict, player=None) -> str:
    """
    Analiza perfiles públicos de TikTok.

    Args:
        parameters:
            - profile_url: URL o nombre de usuario de TikTok
            - max_videos: Número máximo de videos a analizar (default: 10)
            - force_refresh: Forzar actualización (ignorar caché)
            - use_selenium: Usar Selenium para extracción (default: True)
    """
    p = parameters or {}
    profile_url = p.get("profile_url", "").strip()
    max_videos = int(p.get("max_videos", 10))
    force_refresh = p.get("force_refresh", False)
    use_selenium = p.get("use_selenium", True)

    if not profile_url:
        return "❌ Error: Especifica la URL o nombre de usuario del perfil."

    try:
        scraper = TikTokScraperV3(headless=True)
        
        # Extraer nombre de usuario
        username = scraper._extract_username(profile_url)
        if not username:
            return "❌ Error: No se pudo extraer el nombre de usuario."

        # Verificar caché
        if not force_refresh:
            cached = get_cached_profile(username)
            if cached:
                return generate_tiktok_report(cached)

        # Analizar
        profile_data = scraper.analyze_profile(username, max_videos, force_refresh)
        
        if "error" in profile_data:
            return f"❌ {profile_data['error']}"

        return generate_tiktok_report(profile_data)

    except Exception as e:
        return f"❌ Error al analizar el perfil: {str(e)}"


def generate_tiktok_report(profile_data: Dict) -> str:
    """Genera un reporte formateado del perfil analizado."""
    if not profile_data or "error" in profile_data:
        return f"❌ Error: {profile_data.get('error', 'Datos no disponibles')}"

    method = profile_data.get("method", "unknown")
    method_label = {
        "json_script": "📄 JSON incrustado",
        "selenium_js": "🌐 Selenium JS",
        "selenium_html": "🌐 Selenium HTML",
    }.get(method, "❓ Método desconocido")

    lines = [
        "📊 ANÁLISIS DE TIKTOK",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🔍 Extraído con: {method_label}",
        "",
        f"👤 Usuario: @{profile_data.get('username', 'N/A')}",
        f"📛 Nombre: {profile_data.get('display_name', 'N/A')}",
        f"📝 Bio: {profile_data.get('bio', 'Sin bio')[:100]}...",
        f"🔵 Verificado: {'✅ Sí' if profile_data.get('verified') else '❌ No'}",
        "",
        "📈 ESTADÍSTICAS",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"👥 Seguidores: {profile_data.get('followers', 0):,}",
        f"👤 Siguiendo: {profile_data.get('following', 0):,}",
        f"❤️ Likes totales: {profile_data.get('likes', 0):,}",
        f"📹 Videos: {profile_data.get('video_count', 0)}",
        "",
        "🎬 VIDEOS RECIENTES",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    
    videos = profile_data.get("videos", [])
    if videos:
        for i, video in enumerate(videos[:5], 1):
            plays = f"{video.get('plays', 0):,}"
            likes = f"{video.get('likes', 0):,}"
            desc = video.get('description', '')[:40]
            lines.append(f"  {i}. 🎥 {plays} vistas | ❤️ {likes} likes")
            if desc:
                lines.append(f"     📝 {desc}...")
        
        if len(videos) > 5:
            lines.append(f"  ... y {len(videos) - 5} videos más")
    else:
        lines.append("  ⚠️ No se pudieron obtener videos.")
        lines.append("  💡 TikTok puede estar bloqueando el acceso.")
    
    # Engagement
    engagement = profile_data.get("engagement", {})
    if engagement.get("total_plays", 0) > 0:
        lines.extend([
            "",
            "📊 ENGAGEMENT",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📈 Tasa de engagement: {engagement.get('engagement_rate', 0):.2f}%",
            f"❤️ Promedio likes/video: {engagement.get('avg_likes', 0):,}",
            f"💬 Promedio comments/video: {engagement.get('avg_comments', 0):,}",
            f"🔄 Promedio shares/video: {engagement.get('avg_shares', 0):,}",
            f"👁️ Promedio plays/video: {engagement.get('avg_plays', 0):,}",
        ])
    
    return "\n".join(lines)


# ─── INICIALIZACIÓN ──────────────────────────────────────────────────────
print("[TikTok] Inicializando v3.0...")
print(f"[TikTok] Caché en: {CACHE_DIR}")

if __name__ == "__main__":
    # Prueba
    result = tiktok_analyzer({
        "profile_url": "@tiktok",
        "max_videos": 5,
        "use_selenium": True
    })
    print(result)