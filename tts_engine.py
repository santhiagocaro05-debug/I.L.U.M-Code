"""
tts_engine.py — Motor de voz ILUM con clonación XTTS-v2 (español latino).
Incluye preprocesamiento profesional de clips de voz a -16 LUFS, Mono, 22050 Hz.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ILUM.TTS")

# ─────────────────────────────────────────────────────────────────────────────
# Rutas
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parent
SAMPLES_DIR    = BASE_DIR / "assets" / "voice_samples" / "ilum"
PROCESSED_DIR  = BASE_DIR / "assets" / "voice_samples" / "ilum_processed"
CACHE_DIR      = BASE_DIR / "config" / "tts_cache"
EMBEDDING_PATH = CACHE_DIR / "ilum_es_embedding.pt"
MODEL_NAME     = "tts_models/multilingual/multi-dataset/xtts_v2"
LANGUAGE       = "es"                  # español
EDGE_VOICE     = "es-MX-JorgeNeural"   # fallback: voz masculina mexicana

CACHE_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Normalización y Preprocesamiento de Audio
# ─────────────────────────────────────────────────────────────────────────────
def calculate_lufs_48k(data_48k, sr=48000) -> float:
    """
    Calcula la sonoridad en LUFS utilizando filtros K estándar (BS.1770-4) a 48000 Hz.
    """
    import numpy as np
    from scipy.signal import lfilter

    # Coeficientes del filtro K a 48000 Hz
    # Etapa 1: Ponderación de alta frecuencia (High Shelf)
    b1 = [1.53090959, -2.65877453, 1.12786494]
    a1 = [1.0, -1.66360011, 0.66360011]
    # Etapa 2: Filtro RLB (Paso Alto)
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, -1.99004745, 0.99007218]

    # Aplicar filtros
    y = lfilter(b1, a1, data_48k, axis=0)
    y = lfilter(b2, a2, y, axis=0)

    # Calcular valor cuadrático medio (MS) por canal
    if len(y.shape) > 1:
        ms = np.mean(y**2, axis=0)
        weighted_ms = np.sum(ms) / len(ms)  # Promedio de canales estéreo
    else:
        weighted_ms = np.mean(y**2)

    if weighted_ms < 1e-12:
        return -70.0  # Silencio

    return -0.691 + 10.0 * np.log10(weighted_ms)


def preprocess_audio_clips() -> bool:
    """
    Normaliza todos los clips en SAMPLES_DIR a -16 LUFS, mono, 22050 Hz y los guarda en PROCESSED_DIR.
    Retorna True si hubo cambios y se requiere regenerar el embedding de XTTS.
    """
    import numpy as np
    import soundfile as sf
    import librosa

    if not SAMPLES_DIR.exists():
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        return False

    exts = {".wav", ".mp3", ".flac", ".ogg"}
    source_clips = sorted(p for p in SAMPLES_DIR.iterdir() if p.suffix.lower() in exts)

    if not source_clips:
        logger.warning("[TTS] No se encontraron clips de audio de origen en %s", SAMPLES_DIR)
        return False

    # Medir huella de archivos originales para evitar reprocesamiento innecesario
    hasher = hashlib.md5()
    for p in source_clips:
        hasher.update(p.name.encode())
        hasher.update(str(p.stat().st_mtime).encode())
    fingerprint = hasher.hexdigest()

    fingerprint_file = PROCESSED_DIR / "processing_fingerprint.txt"
    if fingerprint_file.exists() and fingerprint_file.read_text().strip() == fingerprint:
        # Los clips originales no han cambiado, no hay nada que procesar
        return False

    logger.info("[TTS] [CONFIG] Iniciando preprocesamiento de clips a -16 LUFS, mono, 22050 Hz...")
    
    # Limpiar directorio de procesados
    for f in PROCESSED_DIR.glob("*.wav"):
        try:
            f.unlink()
        except:
            pass

    for clip_path in source_clips:
        try:
            # 1. Cargar el audio original (con su sample rate original)
            data, sr = librosa.load(str(clip_path), sr=None, mono=False)
            
            # 2. Resamplear a 48000 Hz temporalmente para calcular LUFS con filtros calibrados
            data_48k = librosa.resample(data, orig_sr=sr, target_sr=48000)
            
            # 3. Calcular sonoridad en LUFS
            current_lufs = calculate_lufs_48k(data_48k, 48000)
            
            # 4. Calcular ganancia para llegar a -16 LUFS
            gain = 10.0 ** ((-16.0 - current_lufs) / 20.0)
            data_normalized = data * gain
            
            # 5. Prevenir distorsión digital (clipping) limitando el pico a -1 dB True Peak (0.89)
            peak = np.max(np.abs(data_normalized))
            if peak > 0.89:
                data_normalized = data_normalized * (0.89 / peak)
            
            # 6. Convertir a Mono y resamplear al formato final de XTTS (22050 Hz)
            data_mono = librosa.to_mono(data_normalized)
            data_22050 = librosa.resample(data_mono, orig_sr=sr, target_sr=22050)
            
            # 7. Guardar en carpeta de procesados como WAV de 22050 Hz
            out_path = PROCESSED_DIR / f"{clip_path.stem}_normalized.wav"
            sf.write(str(out_path), data_22050, 22050, subtype="PCM_16")
            logger.info(f"   [OK] Procesado: {clip_path.name} -> {out_path.name} (Sonoridad: {current_lufs:.1f} LUFS)")
            
        except Exception as e:
            logger.error(f"   [ERROR] Error procesando {clip_path.name}: {e}")

    # Guardar huella de procesamiento exitoso
    fingerprint_file.write_text(fingerprint)
    
    # Forzar eliminación del caché viejo de XTTS para regenerar el embedding con los nuevos clips
    fp_embedding = CACHE_DIR / "embedding_fingerprint.txt"
    if EMBEDDING_PATH.exists():
        try:
            EMBEDDING_PATH.unlink()
            logger.info("[TTS] Caché de embedding viejo eliminado para regeneración.")
        except Exception as e:
            logger.warning(f"[TTS] No se pudo borrar ilum_es_embedding.pt: {e}")
            
    if fp_embedding.exists():
        try:
            fp_embedding.unlink()
        except:
            pass

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Motor principal
# ─────────────────────────────────────────────────────────────────────────────
class IlumTTS:
    """
    Sintetizador de voz con clonación XTTS-v2 en español.
    Carga el modelo una sola vez en background y reutiliza el embedding cacheado.
    """

    def __init__(self):
        self._tts       = None
        self._gpt_cond  = None
        self._speaker   = None
        self._lock      = threading.Lock()
        self._ready     = False
        self._use_xtts  = True
        self._queue: list[str] = []

        threading.Thread(
            target=self._load_model, daemon=True, name="TTS-Loader"
        ).start()

    # ── Carga del modelo ──────────────────────────────────────────────────────
    def _load_model(self) -> None:
        try:
            # 1. Preprocesar audios antes de recolectar clips
            changed = preprocess_audio_clips()
            
            try:
                from TTS.api import TTS  # type: ignore
            except ImportError:
                raise ImportError(
                    "No se encontró TTS. Instala 'coqui-tts' ejecutando:\n"
                    "  pip install coqui-tts>=0.25.0"
                )

            # Recolectar clips procesados de la carpeta ilum_processed
            samples = self._collect_samples()
            if not samples:
                logger.warning(
                    "[TTS] No se encontraron audios en %s — usando Edge TTS.", PROCESSED_DIR
                )
                self._use_xtts = False
                self._ready = True
                return

            logger.info("[TTS] Cargando modelo XTTS-v2 (primera vez ~2 min)...")
            tts = TTS(MODEL_NAME, gpu=self._has_gpu())
            self._tts = tts

            self._gpt_cond, self._speaker = self._load_or_build_embedding(tts, samples)
            self._ready = True
            logger.info("[TTS] [READY] Motor XTTS-v2 listo — voz ILUM español.")

        except ImportError as exc:
            logger.warning("[TTS] %s — usando Edge TTS.", exc)
            self._use_xtts = False
            self._ready = True
        except Exception as exc:
            logger.error("[TTS] Error cargando modelo: %s — usando Edge TTS.", exc)
            self._use_xtts = False
            self._ready = True

    def _collect_samples(self) -> list[str]:
        if not PROCESSED_DIR.exists():
            PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
            return []
        exts = {".wav", ".mp3", ".flac", ".ogg"}
        return sorted(
            str(p) for p in PROCESSED_DIR.iterdir() if p.suffix.lower() in exts
        )

    def _load_or_build_embedding(self, tts, samples: list[str]):
        import torch  # type: ignore

        fingerprint = self._fingerprint(samples)
        fp_file     = CACHE_DIR / "embedding_fingerprint.txt"

        if (
            EMBEDDING_PATH.exists()
            and fp_file.exists()
            and fp_file.read_text().strip() == fingerprint
        ):
            logger.info("[TTS] Cargando embedding cacheado...")
            data = torch.load(EMBEDDING_PATH, map_location="cpu")
            return data["gpt_cond"], data["speaker"]

        logger.info("[TTS] Construyendo embedding desde %d clip(s)...", len(samples))
        gpt_cond, speaker = tts.synthesizer.tts_model.get_conditioning_latents(
            audio_path=samples
        )
        torch.save({"gpt_cond": gpt_cond, "speaker": speaker}, EMBEDDING_PATH)
        fp_file.write_text(fingerprint)
        logger.info("[TTS] Embedding guardado en caché.")
        return gpt_cond, speaker

    @staticmethod
    def _fingerprint(paths: list[str]) -> str:
        h = hashlib.md5()
        for p in sorted(paths):
            h.update(p.encode())
            h.update(str(os.path.getmtime(p)).encode())
        return h.hexdigest()

    @staticmethod
    def _has_gpu() -> bool:
        try:
            import torch  # type: ignore
            return torch.cuda.is_available()
        except ImportError:
            return False

    # ── API pública ───────────────────────────────────────────────────────────
    def speak(self, text: str, blocking: bool = False) -> None:
        """
        Sintetiza y reproduce `text` con la voz de ILUM.
        blocking=False  → no bloquea la UI (recomendado).
        blocking=True   → espera a que termine antes de retornar.
        """
        if not text or not text.strip():
            return

        if blocking:
            self._speak_sync(text)
        else:
            threading.Thread(
                target=self._speak_sync,
                args=(text,),
                daemon=True,
                name="TTS-Speak",
            ).start()

    def _speak_sync(self, text: str) -> None:
        deadline = time.time() + 120
        while not self._ready and time.time() < deadline:
            time.sleep(0.2)

        if self._use_xtts and self._tts is not None:
            self._speak_xtts(text)
        else:
            asyncio.run(self._speak_edge(text))

    def _speak_xtts(self, text: str) -> None:
        """Síntesis en tiempo real con XTTS-v2 y streaming de chunks."""
        try:
            import numpy as np          # type: ignore
            import sounddevice as sd    # type: ignore

            with self._lock:
                chunks = self._tts.synthesizer.tts_model.inference_stream(
                    text,
                    language=LANGUAGE,
                    gpt_cond_latent=self._gpt_cond,
                    speaker_embedding=self._speaker,
                    temperature=0.7,         # voz natural y estable
                    repetition_penalty=2.0,   # penalización estándar para voz clara, evita tono ahogado
                    top_k=50,
                    top_p=0.85,
                    speed=1.05,              # 5% más rápida para respuesta ágil y nítida
                    enable_text_splitting=True,
                )

            # Abrir un stream en tiempo real para reproducir chunks a medida que se generan
            with sd.OutputStream(samplerate=24000, channels=1, dtype='float32') as stream:
                for chunk in chunks:
                    if isinstance(chunk, list):
                        chunk = np.array(chunk, dtype=np.float32)
                    elif hasattr(chunk, "cpu"):
                        chunk = chunk.cpu().numpy()
                    
                    # Asegurar formato mono 1D
                    if len(chunk.shape) > 1:
                        chunk = np.mean(chunk, axis=1)
                        
                    stream.write(chunk)

        except Exception as exc:
            logger.error("[TTS] Error XTTS-v2: %s — usando Edge TTS.", exc)
            asyncio.run(self._speak_edge(text))

    async def _speak_edge(self, text: str) -> None:
        """Fallback con Edge TTS — voz masculina en español de México."""
        try:
            import edge_tts   # type: ignore
            import soundfile as sf  # type: ignore
            import sounddevice as sd  # type: ignore

            tmp = CACHE_DIR / "_edge_tmp.mp3"
            communicate = edge_tts.Communicate(
                text,
                voice=EDGE_VOICE,
                rate="-8%",
                pitch="-10Hz",
            )
            await communicate.save(str(tmp))
            data, samplerate = sf.read(str(tmp))
            sd.play(data, samplerate=samplerate)
            sd.wait()
            tmp.unlink(missing_ok=True)

        except Exception as exc:
            logger.error("[TTS] Error Edge TTS: %s", exc)

    def generate_tts_chunks(self, text: str):
        """
        Genera fragmentos de audio para `text` en formato PCM int16, 24000Hz, Mono.
        Soporta tanto XTTS-v2 (local) como Edge TTS (fallback).
        """
        import numpy as np
        
        # Esperar a que el motor esté listo
        deadline = time.time() + 120
        while not self._ready and time.time() < deadline:
            time.sleep(0.1)
            
        if self._use_xtts and self._tts is not None:
            try:
                with self._lock:
                    chunks = self._tts.synthesizer.tts_model.inference_stream(
                        text,
                        language=LANGUAGE,
                        gpt_cond_latent=self._gpt_cond,
                        speaker_embedding=self._speaker,
                        temperature=0.7,
                        repetition_penalty=2.0,
                        top_k=50,
                        top_p=0.85,
                        speed=1.05,
                        enable_text_splitting=True,
                    )
                
                for chunk in chunks:
                    if isinstance(chunk, list):
                        chunk = np.array(chunk, dtype=np.float32)
                    elif hasattr(chunk, "cpu"):
                        chunk = chunk.cpu().numpy()
                    
                    if len(chunk.shape) > 1:
                        chunk = np.mean(chunk, axis=1)
                    
                    # Convertir float32 a int16 PCM
                    chunk_int16 = (chunk * 32767.0).clip(-32768.0, 32767.0).astype(np.int16)
                    yield chunk_int16.tobytes()
            except Exception as e:
                logger.error(f"[TTS] Error en generación de chunks XTTS: {e}. Cayendo a Edge TTS.")
                yield from self._generate_edge_chunks(text)
        else:
            yield from self._generate_edge_chunks(text)

    def _generate_edge_chunks(self, text: str):
        """Genera chunks de Edge TTS convertidos a PCM int16 24000Hz mono."""
        import numpy as np
        import soundfile as sf
        import librosa
        try:
            import edge_tts
            tmp = CACHE_DIR / f"_edge_tmp_{threading.get_ident()}.mp3"
            communicate = edge_tts.Communicate(
                text,
                voice=EDGE_VOICE,
                rate="-8%",
                pitch="-10Hz",
            )
            asyncio.run(communicate.save(str(tmp)))
            
            data, sr = sf.read(str(tmp))
            if tmp.exists():
                try:
                    tmp.unlink()
                except:
                    pass
            
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
                
            if sr != 24000:
                data = librosa.resample(data, orig_sr=sr, target_sr=24000)
                
            data_int16 = (data * 32767.0).clip(-32768.0, 32767.0).astype(np.int16)
            
            # Enviar en fragmentos de 960 muestras (40ms a 24kHz)
            chunk_size = 960
            for i in range(0, len(data_int16), chunk_size):
                yield data_int16[i:i+chunk_size].tobytes()
                
        except Exception as e:
            logger.error(f"[TTS] Error generando chunks de Edge TTS: {e}")

    def wait_ready(self, timeout: float = 120.0) -> bool:
        deadline = time.time() + timeout
        while not self._ready and time.time() < deadline:
            time.sleep(0.2)
        return self._ready

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def engine_name(self) -> str:
        return "XTTS-v2" if self._use_xtts else "Edge TTS"


# ─────────────────────────────────────────────────────────────────────────────
# Singleton global
# ─────────────────────────────────────────────────────────────────────────────
_engine: Optional[IlumTTS] = None
_engine_lock = threading.Lock()


def get_engine() -> IlumTTS:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = IlumTTS()
    return _engine


def speak(text: str, blocking: bool = False) -> None:
    get_engine().speak(text, blocking=blocking)


def wait_ready(timeout: float = 120.0) -> bool:
    return get_engine().wait_ready(timeout)


# ─────────────────────────────────────────────────────────────────────────────
# Prueba rápida
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print("Iniciando motor de voz ILUM en español...")
    engine = IlumTTS()
    ready = engine.wait_ready(timeout=180)
    if ready:
        print(f"Motor listo: {engine.engine_name}")
        engine.speak(
            "Todos los sistemas operativos y en línea, señor. "
            "¿En qué puedo asistirle hoy?",
            blocking=True,
        )
    else:
        print("El motor no pudo inicializarse a tiempo.")
