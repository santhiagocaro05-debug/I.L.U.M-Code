import os
import re
import sys
import time
import random
import subprocess
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

# ============================================================
#  CONFIGURACIÓN
# ============================================================

MAX_PROMPT_LENGTH = 800          # Pollinations soporta prompts largos, pero
                                  # limitamos para evitar URLs gigantes/errores.
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2        # se multiplica por el número de intento
REQUEST_TIMEOUT = 30

# Sólo bloqueamos si la palabra "video"/"vídeo" aparece como palabra
# completa, para no atrapar falsos positivos como "videojuego",
# "videoclip", "videollamada", etc.
VIDEO_BLOCK_PATTERN = re.compile(r"\b(video|vídeo)\b", re.IGNORECASE)

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'image',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'cross-site',
}


# ============================================================
#  HELPERS
# ============================================================

def _log(player, msg: str):
    if player and hasattr(player, "write_log"):
        player.write_log(msg)


def _sanitize_prompt(prompt: str) -> str:
    prompt = prompt.strip()
    if len(prompt) > MAX_PROMPT_LENGTH:
        prompt = prompt[:MAX_PROMPT_LENGTH]
    return prompt


def _build_url(prompt: str, width: int, height: int, model: str,
               seed: int, negative: str, nologo: bool) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    params = {
        "width": str(width),
        "height": str(height),
        "seed": str(seed),
        "nologo": "true" if nologo else "false",
    }
    if model:
        params["model"] = model
    if negative:
        params["negative_prompt"] = negative

    query = urllib.parse.urlencode(params)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?{query}"


def _download_image(url: str, save_path: Path) -> None:
    """
    Descarga la imagen validando que el content-type realmente sea de
    imagen (Pollinations, como cualquier servicio, a veces responde con
    una página HTML de error que sin esta validación se guardaría como
    si fuera un .jpg válido).
    """
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read()

        if "image" not in content_type.lower():
            raise ValueError(
                f"El servidor no devolvió una imagen (Content-Type: {content_type or 'desconocido'})."
            )
        if len(data) < 512:
            # Una imagen real de 1024x1024 nunca pesa unos pocos bytes;
            # esto casi siempre es un error disfrazado.
            raise ValueError("La respuesta del servidor es demasiado pequeña para ser una imagen válida.")

        with open(save_path, "wb") as f:
            f.write(data)


def _open_file(path: Path):
    """
    Abre el archivo con la aplicación predeterminada del sistema.
    os.startfile solo existe en Windows; agregamos fallback para que
    el módulo no reviente si algún día corre en otro sistema.
    """
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        # No es crítico si falla abrir el visor; la imagen ya quedó guardada.
        pass


# ============================================================
#  FUNCIÓN PRINCIPAL
# ============================================================

def image_generation(parameters: dict, player=None) -> str:
    """
    Genera una imagen con IA (Pollinations) a partir de un prompt y la
    guarda localmente.

    Parámetros soportados en 'parameters':
    - prompt (str, requerido): descripción de la imagen.
    - width (int, opcional): ancho en px. Default 1024.
    - height (int, opcional): alto en px. Default 1024.
    - model (str, opcional): modelo específico de Pollinations (ej. 'flux').
    - negative (str, opcional): qué evitar en la imagen.
    - seed (int, opcional): semilla fija para reproducir el mismo resultado.
      Si no se da, se usa una semilla aleatoria para que cada generación
      sea distinta aunque el prompt se repita.
    - output_dir (str, opcional): carpeta donde guardar la imagen.
    """
    prompt = parameters.get("prompt", "")

    if not prompt or not prompt.strip():
        return "No proporcionaste una descripción para generar."

    prompt = _sanitize_prompt(prompt)
    prompt_lower = prompt.lower()

    if VIDEO_BLOCK_PATTERN.search(prompt_lower):
        _log(player, "SYS: Intento de generación de video bloqueado por falta de membresía.")
        return ("Para usar la generación de video debes pagar una membresía VIP para "
                "desbloquear la función o comprarla directamente en la tienda de NEXUS.")

    width = int(parameters.get("width", 1024))
    height = int(parameters.get("height", 1024))
    model = parameters.get("model", "")
    negative = parameters.get("negative", "")
    seed = parameters.get("seed")
    seed = int(seed) if seed is not None else random.randint(1, 999_999_999)

    # Carpeta de salida configurable, con default igual al original.
    output_dir_param = parameters.get("output_dir")
    if output_dir_param:
        downloads_dir = Path(output_dir_param)
    else:
        downloads_dir = Path.home() / "Downloads" / "Nexus_Downloads" / "fotos generadas"

    try:
        downloads_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return f"❌ No se pudo crear la carpeta de destino ({downloads_dir}): {e}"

    filename = f"nexus_gen_{int(time.time())}_{seed}.jpg"
    save_path = downloads_dir / filename

    url = _build_url(prompt, width, height, model, seed, negative, nologo=True)

    _log(player, f"SYS: Generando imagen con IA: '{prompt}' ({width}x{height}, seed={seed})...")
    _log(player, f"SYS: Guardando en: {save_path}")

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _download_image(url, save_path)
            _open_file(save_path)
            _log(player, f"SYS: Imagen guardada y abierta desde: {save_path}")
            return f"✅ Imagen generada y guardada en: {save_path}"

        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 403:
                last_error_msg = "Error 403: el servidor está bloqueando la solicitud."
            elif e.code == 429:
                last_error_msg = "Error 429: demasiadas solicitudes, hay que esperar un poco."
            elif 500 <= e.code < 600:
                last_error_msg = f"Error {e.code}: problema temporal del servidor."
            else:
                last_error_msg = f"Error HTTP {e.code}: {e.reason}"

            # 403/429/5xx pueden ser transitorios: reintentamos con backoff.
            if e.code in (403, 429) or 500 <= e.code < 600:
                _log(player, f"SYS: Intento {attempt}/{MAX_RETRIES} falló ({last_error_msg}). Reintentando...")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
            else:
                # Errores no recuperables (400, 404, etc.) no vale la pena reintentar.
                return f"❌ {last_error_msg}"

        except urllib.error.URLError as e:
            last_error = e
            _log(player, f"SYS: Intento {attempt}/{MAX_RETRIES} falló (problema de conexión: {e.reason}).")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue

        except ValueError as e:
            # Respuesta que no es una imagen válida.
            last_error = e
            _log(player, f"SYS: Intento {attempt}/{MAX_RETRIES} falló ({e}).")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue

        except Exception as e:
            last_error = e
            _log(player, f"SYS: Intento {attempt}/{MAX_RETRIES} falló con error inesperado: {e}.")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue

    # Si llegamos aquí, se agotaron los reintentos.
    if isinstance(last_error, urllib.error.HTTPError):
        if last_error.code == 403:
            return ("❌ Error 403: el servidor está bloqueando la solicitud tras varios intentos. "
                     "Prueba: 1) Desactivar VPN 2) Esperar unos minutos 3) Usar un prompt más corto.")
        return f"❌ Error HTTP {last_error.code} tras {MAX_RETRIES} intentos: {last_error.reason}"
    elif isinstance(last_error, urllib.error.URLError):
        return f"❌ No se pudo conectar con el servidor tras {MAX_RETRIES} intentos: {last_error.reason}"
    else:
        return f"❌ Ocurrió un error al intentar generar la imagen tras {MAX_RETRIES} intentos: {last_error}"