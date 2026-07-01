"""
voice/fish_tts.py — Motor de síntesis de voz con Fish Audio API (clonación en la nube).

Envía texto a Fish Audio y recibe audio PCM raw (24kHz, 16-bit, mono)
directamente compatible con el pipeline de reproducción de JARVIS.
"""

import threading
import httpx

# ── Constantes ──────────────────────────────────────────────────────────────────
FISH_TTS_URL = "https://api.fish.audio/v1/tts"
FISH_SAMPLE_RATE = 24000       # Hz — coincide con RECEIVE_SAMPLE_RATE de main.py
FISH_CHUNK_BYTES = 960         # 480 samples × 2 bytes (16-bit) = 20ms chunks
TIMEOUT_SECONDS  = 30          # Timeout para la petición HTTP completa


def synthesize_speech(
    text: str,
    voice_id: str,
    api_key: str,
    stop_event: threading.Event | None = None,
) -> bytes:
    """
    Sintetiza texto con la voz clonada de Fish Audio.

    Args:
        text:       Texto a sintetizar.
        voice_id:   ID del modelo de voz clonada en Fish Audio.
        api_key:    API Key de Fish Audio.
        stop_event: Si se activa, aborta la descarga inmediatamente.

    Returns:
        bytes: Audio PCM raw (24kHz, 16-bit signed LE, mono).
               Vacío si hay error o se interrumpió.
    """
    if not text or not text.strip():
        return b""
    if not api_key or not voice_id:
        print("[FishTTS] ⚠️ API Key o Voice ID no configurados.")
        return b""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "text": text.strip(),
        "reference_id": voice_id,
        "format": "pcm",
        "sample_rate": FISH_SAMPLE_RATE,
        "latency": "balanced",
    }

    audio_buf = bytearray()

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            with client.stream("POST", FISH_TTS_URL, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    error_body = resp.read().decode(errors="replace")[:200]
                    print(f"[FishTTS] ❌ HTTP {resp.status_code}: {error_body}")
                    if resp.status_code == 402:
                        raise ValueError("Insufficient Balance")
                    elif resp.status_code == 401:
                        raise ValueError("Unauthorized")
                    return b""

                for chunk in resp.iter_bytes(chunk_size=4096):
                    if stop_event and stop_event.is_set():
                        print("[FishTTS] ⛔ Síntesis interrumpida por el usuario.")
                        return b""
                    audio_buf.extend(chunk)

    except httpx.TimeoutException:
        print("[FishTTS] ❌ Timeout al conectar con Fish Audio API.")
        return b""
    except httpx.ConnectError as e:
        print(f"[FishTTS] ❌ Error de conexión: {e}")
        return b""
    except Exception as e:
        print(f"[FishTTS] ❌ Error inesperado: {e}")
        return b""

    return bytes(audio_buf)


def split_into_sentences(text: str) -> list[str]:
    """
    Divide texto en fragmentos naturales para síntesis progresiva.
    Corta en puntos, signos de interrogación/exclamación y saltos de línea.
    """
    import re
    # Dividir por delimitadores de frase, manteniendo el delimitador con la frase
    parts = re.split(r'(?<=[.!?。\n])\s*', text)
    sentences = [s.strip() for s in parts if s.strip()]
    return sentences
