"""
youtube_controller.py — Control de YouTube (HÍBRIDO: simple + Selenium bajo demanda)
=====================================================================================

MODO SIMPLE (por defecto, sin Selenium):
  open, go_to, search, play_video, play_pause, next, previous, mute, unmute,
  volume_up, volume_down, fullscreen, mini_player, captions, speed_up, speed_down,
  scroll, status.
  Usa webbrowser.open() (navegador predeterminado) + atajos de teclado nativos.

MODO AVANZADO (activa Selenium automáticamente la primera vez que se necesita):
  like, subscribe, set_speed (valor exacto), loop (encender/apagar real),
  create_playlist, play_playlist, close.
  Estas acciones requieren tu SESIÓN DE GOOGLE iniciada (para dar like, etc.).
  Para lograrlo SIN chocar con tu navegador normal, Selenium usa un perfil
  DEDICADO Y SEPARADO (una carpeta propia, distinta a tu perfil de Chrome/
  Edge/Brave de uso diario). La primera vez que se use, esa ventana se abrirá
  SIN sesión iniciada — debes loguearte en Google manualmente ahí UNA sola
  vez. A partir de entonces la sesión queda guardada para siempre en esa
  carpeta, y nunca vuelve a chocar con tu navegador normal (puedes tener
  ambos abiertos al mismo tiempo sin problema).

⚠️ AUTODETECCIÓN: prueba Chrome → Edge → Brave, usando el primero instalado.

⚠️ CONTINUIDAD DE SESIÓN:
  Una vez que se activa el modo avanzado (Selenium), TODAS las acciones de
  navegación posteriores (open, search, play_video, go_to) empiezan a usar
  esa misma ventana controlada por Selenium, para que "reproduce X" seguido
  de "dale like" actúen sobre el mismo video. Si "dale like" se pide sin
  haber reproducido nada antes en modo avanzado, no habrá video cargado.

REQUISITOS:
    pip install pyautogui pygetwindow selenium webdriver-manager

USO:
    from youtube_controller import youtube_control

    youtube_control({"action": "play_video", "query": "Plan B Candy"})
    youtube_control({"action": "like"})
    youtube_control({"action": "set_speed", "speed": 1.5})
    youtube_control({"action": "create_playlist", "name": "Favoritas"})
    youtube_control({"action": "close"})
"""

import os
import re
import time
import shutil
import platform
import threading
import webbrowser
import urllib.parse
import urllib.request

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.common.exceptions import (
        NoSuchElementException,
        ElementClickInterceptedException,
        SessionNotCreatedException,
        WebDriverException,
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    WDM_AVAILABLE = True
except ImportError:
    WDM_AVAILABLE = False


YOUTUBE_URL = "https://www.youtube.com"

SECTION_MAP = {
    "home": "/",
    "subscriptions": "/feed/subscriptions",
    "library": "/feed/library",
    "history": "/feed/history",
    "trending": "/feed/trending",
    "shorts": "/shorts",
    "watch_later": "/playlist?list=WL",
    "liked": "/playlist?list=LL",
}

VALID_SPEEDS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)

ACTION_ALIASES = {
    "play": "play_pause", "pause": "play_pause", "pausar": "play_pause", "reproducir": "play_pause",
    "siguiente": "next", "pasar": "next",
    "anterior": "previous",
    "buscar": "search",
    "silenciar": "mute", "mutear": "mute",
    "desmutear": "unmute", "activar_sonido": "unmute",
    "fullscreen": "fullscreen", "pantalla_completa": "fullscreen", "ampliar": "fullscreen",
    "reproducir_video": "play_video", "play_video": "play_video",
    "subir_volumen": "volume_up", "bajar_volumen": "volume_down",
    "mas_rapido": "speed_up", "mas_lento": "speed_down",
    "subtitulos": "captions",
    "me_gusta": "like", "dale_like": "like", "like_video": "like",
    "suscribir": "subscribe", "suscribete": "subscribe", "suscribirse": "subscribe",
    "repetir": "loop",
    "cerrar": "close", "cerrar_youtube": "close", "cerrar_navegador": "close",
    "crear_playlist": "create_playlist", "nueva_playlist": "create_playlist",
    "reproducir_playlist": "play_playlist", "play_playlist": "play_playlist",
    "velocidad": "set_speed", "speed": "set_speed",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODO SIMPLE — utilidades sin Selenium
# ═══════════════════════════════════════════════════════════════════════════

def focus_browser() -> bool:
    """Intenta enfocar la ventana del navegador donde está YouTube abierto."""
    if not gw:
        return False
    browser_names = ["chrome", "edge", "firefox", "brave", "opera", "youtube"]
    try:
        windows = gw.getAllWindows()
    except Exception:
        return False
    for window in windows:
        title = (window.title or "").lower()
        if any(name in title for name in browser_names):
            try:
                if window.isMinimized:
                    window.restore()
                window.activate()
                time.sleep(0.5)
                return True
            except Exception:
                continue
    return False


def _extract_first_video_id(query: str):
    encoded = urllib.parse.quote(query)
    url = f"{YOUTUBE_URL}/results?search_query={encoded}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
        ids = re.findall(r"watch\?v=(\S{11})", html)
        return ids[0] if ids else None
    except Exception:
        return None


def _extract_first_playlist_id(query: str):
    """Busca playlists (filtro sp=EgIQAw) y devuelve el ID de la primera."""
    encoded = urllib.parse.quote(query)
    url = f"{YOUTUBE_URL}/results?search_query={encoded}&sp=EgIQAw%253D%253D"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="ignore")
        ids = re.findall(r"list=([a-zA-Z0-9_-]+)", html)
        return ids[0] if ids else None
    except Exception:
        return None


def _send_key(key=None, hotkey=None) -> bool:
    if not pyautogui:
        return False
    focused = focus_browser()
    if hotkey:
        pyautogui.hotkey(*hotkey)
    elif key:
        pyautogui.press(key)
    return focused


# ═══════════════════════════════════════════════════════════════════════════
# MODO AVANZADO — Selenium con perfil de automatización dedicado (lazy)
# ═══════════════════════════════════════════════════════════════════════════

_driver = None
_browser_used = None
_driver_lock = threading.Lock()


def _find_binary(candidates):
    for path in candidates:
        expanded = os.path.expandvars(path)
        if os.path.isfile(expanded):
            return expanded
    return None


def _find_chrome():
    if platform.system() == "Windows":
        return _find_binary([
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
        ])
    return shutil.which("google-chrome") or shutil.which("chromium")


def _find_edge():
    if platform.system() == "Windows":
        return _find_binary([
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
        ])
    return shutil.which("microsoft-edge")


def _find_brave():
    if platform.system() == "Windows":
        return _find_binary([
            r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ])
    return shutil.which("brave-browser") or shutil.which("brave")


def _automation_profile_dir(name: str):
    """
    Carpeta de perfil DEDICADA para la automatización (NO tu perfil normal).
    Se crea la primera vez; queda vacía (sin sesión) hasta que inicies sesión
    manualmente ahí una vez. A partir de entonces la sesión queda guardada
    permanentemente en esta carpeta separada — nunca choca con tu navegador
    normal porque nunca la usa nadie más.
    """
    base = os.path.join(os.path.expanduser("~"), ".ilum_automation_profile", name)
    os.makedirs(base, exist_ok=True)
    return base


BROWSER_DETECTORS = {"chrome": _find_chrome, "edge": _find_edge, "brave": _find_brave}


def _build_driver(name: str, binary_path: str):
    """Arranca el navegador usando un perfil dedicado a la automatización."""
    profile_dir = _automation_profile_dir(name)

    if name in ("chrome", "brave"):
        options = webdriver.ChromeOptions()

        options.binary_location = binary_path
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument("--profile-directory=Default")
        options.add_argument("--start-maximized")
        options.add_argument("--mute-audio")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        if WDM_AVAILABLE:
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        return webdriver.Chrome(options=options)

    elif name == "edge":
        options = webdriver.EdgeOptions()
        options.binary_location = binary_path
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument("--profile-directory=Default")
        options.add_argument("--start-maximized")
        options.add_argument("--mute-audio")
        if WDM_AVAILABLE:
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        return webdriver.Edge(options=options)

    raise RuntimeError(f"Navegador '{name}' no soportado en modo avanzado.")


def _get_driver():
    """Lanza (o reutiliza) el navegador controlado por Selenium, con un perfil dedicado."""
    global _driver, _browser_used
    if _driver is not None:
        return _driver

    if not SELENIUM_AVAILABLE:
        raise RuntimeError(
            "Esta acción necesita Selenium. Instala con: pip install selenium webdriver-manager"
        )

    with _driver_lock:
        if _driver is not None:
            return _driver

        errors = []
        for name in ("chrome", "edge", "brave"):
            binary = BROWSER_DETECTORS[name]()
            if not binary:
                errors.append(f"{name}: no instalado")
                continue
            try:
                driver = _build_driver(name, binary)
                driver.get(YOUTUBE_URL)
                time.sleep(1.5)
                _driver = driver
                _browser_used = name
                is_logged_in = len(driver.find_elements(By.CSS_SELECTOR, "ytd-topbar-menu-button-renderer button img")) > 0
                if not is_logged_in:
                    print(
                        f"[YouTubeController] Perfil de automatización nuevo/sin sesión en {name}. "
                        "Inicia sesión en Google manualmente en esa ventana; quedará guardado para siempre."
                    )
                return _driver
            except SessionNotCreatedException as e:
                errors.append(f"{name}: {e.msg if hasattr(e, 'msg') else e}")
            except Exception as e:
                errors.append(f"{name}: {e}")

        detail = "\n".join(f"  - {e}" for e in errors)
        raise RuntimeError(
            "❌ No se pudo abrir ningún navegador en modo avanzado.\n"
            f"{detail}\n\n"
            "Instala Google Chrome, Microsoft Edge o Brave. "
            "Si el error persiste, revisa el mensaje detallado de arriba."
        )


def _safe_wait_clickable(driver, by, locator, timeout=4):
    """Polling manual — nunca lanza AttributeError como EC.element_to_be_clickable."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            for el in driver.find_elements(by, locator):
                try:
                    if el.is_displayed() and el.is_enabled():
                        return el
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.2)
    return None


def _click_safely(driver, element) -> bool:
    try:
        element.click()
        return True
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception:
        return False


def _click_by_aria(driver, labels, timeout=4) -> bool:
    for label in labels:
        xpath = f"//button[contains(@aria-label,'{label}')] | //ytd-button-renderer[contains(@aria-label,'{label}')]//button"
        el = _safe_wait_clickable(driver, By.XPATH, xpath, timeout=timeout)
        if el is not None:
            return _click_safely(driver, el)
    return False


def _get_video_element(driver):
    els = driver.find_elements(By.TAG_NAME, "video")
    return els[0] if els else None


def _dismiss_consent(driver):
    for xpath in [
        "//button[.//span[contains(text(),'Accept all')]]",
        "//button[.//span[contains(text(),'Aceptar todo')]]",
        "//button[contains(@aria-label,'Accept')]",
    ]:
        btn = _safe_wait_clickable(driver, By.XPATH, xpath, timeout=2)
        if btn:
            _click_safely(driver, btn)
            time.sleep(0.5)
            return


# ─── Acciones avanzadas ────────────────────────────────────────────────────

def adv_open():
    d = _get_driver()
    d.get(YOUTUBE_URL)
    time.sleep(1.5)
    _dismiss_consent(d)
    return "✅ YouTube abierto (modo avanzado)."


def adv_go_to(section: str):
    if section not in SECTION_MAP:
        return f"❌ Sección '{section}' no reconocida."
    d = _get_driver()
    d.get(f"{YOUTUBE_URL}{SECTION_MAP[section]}")
    time.sleep(1.5)
    return f"✅ Navegando a {section}."


def adv_search(query: str):
    d = _get_driver()
    d.get(f"{YOUTUBE_URL}/results?search_query={urllib.parse.quote(query)}")
    time.sleep(1.5)
    return f"✅ Resultados de '{query}' cargados."


def adv_play_video(query: str, index: int = 1):
    d = _get_driver()
    d.get(f"{YOUTUBE_URL}/results?search_query={urllib.parse.quote(query)}")
    time.sleep(2)
    links = d.find_elements(By.CSS_SELECTOR, "ytd-video-renderer a#video-title")
    if not links or index > len(links):
        return f"❌ No se encontraron resultados para '{query}'."
    target = links[index - 1]
    d.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
    time.sleep(0.3)
    _click_safely(d, target)
    time.sleep(2)
    return f"✅ Reproduciendo '{query}'."


def like_video():
    d = _get_driver()
    if _click_by_aria(d, ["Me gusta", "like this video", "I like this"]):
        return "✅ Like enviado."
    return "❌ No se encontró el botón de like (¿hay un video reproduciéndose?)."


def subscribe_channel():
    d = _get_driver()
    el = _safe_wait_clickable(d, By.CSS_SELECTOR, "ytd-subscribe-button-renderer button", timeout=5)
    if el:
        _click_safely(d, el)
        return "✅ Suscripción enviada."
    return "❌ No se encontró el botón de suscripción (¿hay un video reproduciéndose?)."


def set_speed_exact(speed: float):
    d = _get_driver()
    if speed not in VALID_SPEEDS:
        speed = min(VALID_SPEEDS, key=lambda s: abs(s - speed))
    video = _get_video_element(d)
    if video is None:
        return "❌ No hay video activo en la ventana controlada."
    d.execute_script(f"arguments[0].playbackRate = {speed};", video)
    return f"✅ Velocidad cambiada a {speed}x."


def set_loop_exact(enable: bool = True):
    d = _get_driver()
    video = _get_video_element(d)
    if video is None:
        return "❌ No hay video activo en la ventana controlada."
    d.execute_script(f"arguments[0].loop = {str(enable).lower()};", video)
    return "✅ Repetición activada." if enable else "✅ Repetición desactivada."


def create_playlist(name: str):
    if not name:
        return "❌ Se requiere 'name' para la playlist."
    d = _get_driver()
    d.get(f"{YOUTUBE_URL}/feed/library")
    time.sleep(2)

    # Botón "Nueva playlist" / "New playlist" (en la barra lateral o en Library)
    btn = None
    for label in ["Nueva lista de reproducción", "New playlist", "Create playlist", "Crear"]:
        btn = _safe_wait_clickable(d, By.XPATH, f"//*[contains(text(),'{label}')]", timeout=3)
        if btn:
            break
    if btn is None:
        return "❌ No se encontró el botón para crear playlist. Verifica que hayas iniciado sesión."

    _click_safely(d, btn)
    time.sleep(1.5)

    # Campo de texto para el nombre
    input_el = _safe_wait_clickable(d, By.CSS_SELECTOR, "input#textbox, textarea#textbox", timeout=4)
    if input_el is None:
        return "⚠️ Se abrió el diálogo pero no se encontró el campo de nombre. Complétalo manualmente."
    input_el.clear()
    input_el.send_keys(name)
    time.sleep(0.5)

    # Botón de confirmar creación
    create_btn = None
    for label in ["Crear", "Create"]:
        create_btn = _safe_wait_clickable(d, By.XPATH, f"//*[self::button or self::yt-button-shape][.//*[contains(text(),'{label}')]]", timeout=3)
        if create_btn:
            break
    if create_btn:
        _click_safely(d, create_btn)
        return f"✅ Playlist '{name}' creada."
    return f"⚠️ Nombre '{name}' escrito, pero no se encontró el botón de confirmar. Confírmalo manualmente."


def play_playlist(query: str):
    """No requiere login: busca una playlist pública y la reproduce completa."""
    playlist_id = _extract_first_playlist_id(query)
    if not playlist_id:
        return f"❌ No se encontró ninguna playlist para '{query}'."
    url = f"{YOUTUBE_URL}/watch?list={playlist_id}&index=1&autoplay=1"
    if _driver is not None:
        _driver.get(url)
        time.sleep(1.5)
    else:
        webbrowser.open(url)
    return f"✅ Reproduciendo playlist '{query}' completa."


def close_browser():
    global _driver, _browser_used
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
        _browser_used = None
        return "✅ Navegador (modo avanzado) cerrado."
    return "ℹ️ No había ninguna ventana en modo avanzado abierta."


# ═══════════════════════════════════════════════════════════════════════════
# DESPACHADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def youtube_control(parameters: dict, player=None) -> str:
    action = parameters.get("action", "open").lower().strip()
    action = ACTION_ALIASES.get(action, action)
    query = parameters.get("query", "")
    section = parameters.get("section", "home")
    log = player.write_log if player else (lambda msg: None)

    advanced_active = _driver is not None

    try:
        # ── Navegación: usa Selenium si ya está activo, si no, modo simple ──
        if action == "open":
            log("🎵 Abriendo YouTube...")
            if advanced_active:
                return adv_open()
            webbrowser.open(YOUTUBE_URL)
            time.sleep(1.5)
            return "✅ YouTube abierto."

        elif action == "go_to":
            log(f"📺 Navegando a {section}...")
            if advanced_active:
                return adv_go_to(section)
            if section not in SECTION_MAP:
                return f"❌ Sección '{section}' no reconocida."
            webbrowser.open(f"{YOUTUBE_URL}{SECTION_MAP[section]}")
            time.sleep(1.5)
            return f"✅ Navegando a {section}."

        elif action == "search":
            if not query:
                return "❌ Se requiere 'query'."
            log(f"🔍 Buscando '{query}'...")
            if advanced_active:
                return adv_search(query)
            webbrowser.open(f"{YOUTUBE_URL}/results?search_query={urllib.parse.quote(query)}")
            return f"✅ Buscando '{query}' en YouTube."

        elif action == "play_video":
            if not query:
                return "❌ Se requiere 'query'."
            log(f"🎵 Reproduciendo '{query}'...")
            if advanced_active:
                return adv_play_video(query, int(parameters.get("video_index", 1)))
            video_id = _extract_first_video_id(query)
            if video_id:
                webbrowser.open(f"{YOUTUBE_URL}/watch?v={video_id}")
                return f"✅ Reproduciendo '{query}' directamente."
            webbrowser.open(f"{YOUTUBE_URL}/results?search_query={urllib.parse.quote(query)}")
            return f"⚠️ No se pudo obtener el video exacto de '{query}'."

        # ── Acciones avanzadas (activan Selenium si hace falta) ──
        elif action == "like":
            log("👍 Dando like...")
            return like_video()

        elif action == "subscribe":
            log("🔔 Suscribiéndose...")
            return subscribe_channel()

        elif action == "set_speed":
            speed = float(parameters.get("speed", 1.0))
            log(f"⚡ Velocidad exacta: {speed}x")
            return set_speed_exact(speed)

        elif action == "loop":
            enable = bool(parameters.get("enable", True))
            log("🔄 Repetición")
            return set_loop_exact(enable)

        elif action == "create_playlist":
            name = parameters.get("name", parameters.get("query", ""))
            log(f"📁 Creando playlist '{name}'...")
            return create_playlist(name)

        elif action == "play_playlist":
            if not query:
                return "❌ Se requiere 'query' (nombre de la playlist)."
            log(f"📃 Reproduciendo playlist '{query}'...")
            return play_playlist(query)

        elif action == "close":
            log("🚪 Cerrando navegador...")
            return close_browser()

        # ── Controles de reproducción por teclado (modo simple) ──
        elif action == "play_pause":
            log("⏯️ Play/Pausa")
            if advanced_active:
                v = _get_video_element(_driver)
                if v is None:
                    return "❌ No hay video activo."
                _driver.execute_script("arguments[0].paused ? arguments[0].play() : arguments[0].pause();", v)
                return "✅ Play/Pausa."
            ok = _send_key(key="k")
            return "✅ Play/Pausa enviado." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "next":
            log("⏭️ Siguiente")
            ok = _send_key(hotkey=("shift", "n"))
            return "✅ Siguiente video." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "previous":
            log("⏮️ Anterior")
            ok = _send_key(hotkey=("shift", "p"))
            return "✅ Video anterior." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "mute":
            log("🔇 Silenciando")
            ok = _send_key(key="m")
            return "✅ Silenciado." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "unmute":
            log("🔊 Reactivando sonido")
            ok = _send_key(key="m")
            return "✅ Sonido alternado." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "volume_up":
            ok = _send_key(key="up")
            return "✅ Volumen subido." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "volume_down":
            ok = _send_key(key="down")
            return "✅ Volumen bajado." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "fullscreen":
            log("🖥️ Pantalla completa")
            ok = _send_key(key="f")
            return "✅ Pantalla completa alternada." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "mini_player":
            ok = _send_key(hotkey=("shift", "i"))
            return "✅ Mini reproductor alternado." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "captions":
            ok = _send_key(hotkey=("shift", "c"))
            return "✅ Subtítulos alternados." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "speed_up":
            ok = _send_key(hotkey=("shift", "."))
            return "✅ Velocidad aumentada." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "speed_down":
            ok = _send_key(hotkey=("shift", ","))
            return "✅ Velocidad reducida." if ok else "⚠️ No se pudo confirmar el foco del navegador."

        elif action == "scroll":
            if not pyautogui:
                return "❌ PyAutoGUI no está instalado."
            direction = parameters.get("direction", "down")
            amount = int(parameters.get("scroll_amount", 3))
            focus_browser()
            for _ in range(amount):
                pyautogui.scroll(-100 if direction == "down" else 100)
                time.sleep(0.2)
            return f"✅ Desplazado {direction} x{amount}."

        elif action == "status":
            is_focused = focus_browser()
            modo = f"avanzado ({_browser_used})" if advanced_active else "simple"
            return f"📊 Modo actual: {modo} | Navegador enfocado: {'✅' if is_focused else '❌'}"

        else:
            return _help_text()

    except RuntimeError as e:
        return f"❌ {e}"
    except Exception as e:
        return f"❌ Error ejecutando '{action}': {e}"


def _help_text() -> str:
    return """
🎯 YouTube Control (híbrido) - Comandos disponibles:

📺 Navegación (modo simple):
  open, go_to {section}, search {query}, play_video {query}

🎮 Reproducción (teclado):
  play_pause, next, previous, mute, unmute, volume_up, volume_down,
  fullscreen, mini_player, captions, speed_up, speed_down, scroll

⭐ Avanzado (perfil de automatización separado; la 1ra vez inicia sesión manualmente):
  like, subscribe, set_speed {speed}, loop {enable},
  create_playlist {name}, play_playlist {query}, close

📊 Otros:
  status
"""