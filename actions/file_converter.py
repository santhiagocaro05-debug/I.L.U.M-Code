"""
file_converter.py - Universal File Converter for ILUM using FFmpeg
Professional media converter with GPU support, batch processing, profiles, HDR, subtitles, and more
"""

import os
import subprocess
import json
import shutil
import tempfile
import time
import copy
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable, Set
from dataclasses import dataclass, field, asdict
import logging

# Configuración de logging
LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "converter.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── CONSTANTES ──────────────────────────────────────────────────────

VIDEO_EXTENSIONS: Set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", 
    ".mpeg", ".ts", ".m4v", ".3gp", ".ogv", ".vob"
}

AUDIO_EXTENSIONS: Set[str] = {
    ".mp3", ".wav", ".aac", ".ogg", ".m4a", ".flac", 
    ".opus", ".alac", ".aiff", ".amr", ".wma"
}

IMAGE_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"
}

SUBTITLE_EXTENSIONS: Set[str] = {
    ".srt", ".ass", ".vtt", ".ssa", ".sub"
}

ALL_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS | SUBTITLE_EXTENSIONS

SUPPORTED_OUTPUTS: Set[str] = {
    "mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", 
    "mpeg", "ts", "m4v", "3gp", "ogv", "vob",
    "mp3", "wav", "aac", "ogg", "m4a", "flac", 
    "opus", "alac", "aiff", "amr", "wma",
    "png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif",
    "srt", "ass", "vtt", "ssa", "sub"
}

# ─── PERFILES DE CONVERSIÓN ──────────────────────────────────────

@dataclass
class ConversionProfile:
    """Perfil de conversión con parámetros optimizados"""
    name: str
    description: str
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    video_bitrate: Optional[str] = "2000k"
    audio_bitrate: str = "192k"
    crf: Optional[int] = 23
    preset: str = "medium"
    resolution: Optional[str] = None
    fps: Optional[int] = None
    extra_args: List[str] = field(default_factory=list)
    container: str = "mp4"
    gpu_codec: Optional[str] = None
    pixel_format: Optional[str] = None
    color_primaries: Optional[str] = None
    color_trc: Optional[str] = None
    color_space: Optional[str] = None
    hwaccel: Optional[str] = None
    
    def get_ffmpeg_args(self, use_gpu: bool = False, input_info: Optional[Dict] = None, 
                        output_type: str = "video") -> List[str]:
        """Obtiene los argumentos de FFmpeg para este perfil"""
        args = []
        
        # Codec de video (solo si hay video y no es un audio-only)
        if self.video_codec and self.video_codec != "none" and output_type != "audio":
            if use_gpu and self.gpu_codec:
                args.extend(["-c:v", self.gpu_codec])
            elif self.video_codec == "copy":
                args.extend(["-c:v", "copy"])
            else:
                args.extend(["-c:v", self.video_codec])
            
            if self.video_bitrate and self.video_codec != "copy":
                args.extend(["-b:v", self.video_bitrate])
            
            if self.crf is not None and self.video_codec in ["libx264", "libx265", "libxvid"]:
                args.extend(["-crf", str(self.crf)])
            
            if self.preset and self.video_codec != "copy":
                args.extend(["-preset", self.preset])
            
            if self.fps and self.video_codec != "copy":
                args.extend(["-r", str(self.fps)])
            
            if self.pixel_format:
                args.extend(["-pix_fmt", self.pixel_format])
            if self.color_primaries:
                args.extend(["-color_primaries", self.color_primaries])
            if self.color_trc:
                args.extend(["-color_trc", self.color_trc])
            if self.color_space:
                args.extend(["-colorspace", self.color_space])
        
        # Audio
        if self.audio_codec:
            if self.audio_codec == "copy":
                args.extend(["-c:a", "copy"])
            else:
                args.extend(["-c:a", self.audio_codec])
                if self.audio_bitrate:
                    args.extend(["-b:a", self.audio_bitrate])
        
        args.extend(["-map_metadata", "0"])
        args.extend(self.extra_args)
        
        return args

# ─── PERFILES PREDEFINIDOS ────────────────────────────────────────

PROFILES = {
    "ultra": ConversionProfile(
        name="Ultra",
        description="Máxima calidad para archivos maestros",
        video_codec="libx265",
        audio_codec="flac",
        video_bitrate="8000k",
        audio_bitrate="320k",
        crf=18,
        preset="slow",
        container="mkv",
        gpu_codec="hevc_nvenc",
        pixel_format="yuv420p10le",
        hwaccel="cuda"
    ),
    "alta": ConversionProfile(
        name="Alta",
        description="Alta calidad para archivos profesionales",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="4000k",
        audio_bitrate="256k",
        crf=20,
        preset="slower",
        container="mp4",
        gpu_codec="h264_nvenc",
        hwaccel="cuda"
    ),
    "media": ConversionProfile(
        name="Media",
        description="Calidad estándar para uso general",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="2000k",
        audio_bitrate="192k",
        crf=23,
        preset="medium",
        container="mp4",
        gpu_codec="h264_nvenc",
        hwaccel="cuda"
    ),
    "ligero": ConversionProfile(
        name="Ligero",
        description="Tamaño reducido para sharing",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="1000k",
        audio_bitrate="128k",
        crf=28,
        preset="fast",
        container="mp4",
        gpu_codec="h264_nvenc",
        hwaccel="cuda"
    ),
    "streaming": ConversionProfile(
        name="Streaming",
        description="Optimizado para streaming en vivo",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="6000k",
        audio_bitrate="192k",
        crf=23,
        preset="veryfast",
        extra_args=["-tune", "zerolatency"],
        container="mp4",
        gpu_codec="h264_nvenc",
        hwaccel="cuda"
    ),
    "youtube": ConversionProfile(
        name="YouTube",
        description="Optimizado para YouTube",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="8000k",
        audio_bitrate="192k",
        crf=22,
        preset="slow",
        container="mp4",
        gpu_codec="h264_nvenc",
        hwaccel="cuda"
    ),
    "tiktok": ConversionProfile(
        name="TikTok",
        description="Optimizado para TikTok",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="3000k",
        audio_bitrate="160k",
        crf=25,
        preset="fast",
        resolution="1080x1920",
        container="mp4",
        gpu_codec="h264_nvenc",
        hwaccel="cuda"
    ),
    "instagram": ConversionProfile(
        name="Instagram",
        description="Optimizado para Instagram",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="2500k",
        audio_bitrate="160k",
        crf=25,
        preset="fast",
        resolution="1080x1080",
        container="mp4",
        gpu_codec="h264_nvenc",
        hwaccel="cuda"
    ),
    "whatsapp": ConversionProfile(
        name="WhatsApp",
        description="Optimizado para WhatsApp",
        video_codec="libx264",
        audio_codec="aac",
        video_bitrate="1000k",
        audio_bitrate="128k",
        crf=28,
        preset="fast",
        resolution="854x480",
        container="mp4",
        gpu_codec="h264_nvenc",
        hwaccel="cuda"
    ),
    "audio_hq": ConversionProfile(
        name="Audio HQ",
        description="Audio de alta calidad",
        video_codec="none",
        audio_codec="flac",
        audio_bitrate="320k",
        container="flac"
    ),
    "audio_mp3": ConversionProfile(
        name="Audio MP3",
        description="Audio en MP3 estéreo",
        video_codec="none",
        audio_codec="libmp3lame",
        audio_bitrate="192k",
        container="mp3"
    ),
    "hdr": ConversionProfile(
        name="HDR",
        description="Preservar HDR (HDR10/Dolby Vision)",
        video_codec="libx265",
        audio_codec="aac",
        video_bitrate="6000k",
        audio_bitrate="192k",
        crf=18,
        preset="slow",
        container="mkv",
        gpu_codec="hevc_nvenc",
        pixel_format="yuv420p10le",
        color_primaries="bt2020",
        color_trc="smpte2084",
        color_space="bt2020nc",
        hwaccel="cuda",
        extra_args=["-copy_unknown"]
    ),
    }

AUDIO_CODEC_MAP = {
    "mp3": "libmp3lame",
    "aac": "aac",
    "m4a": "aac",
    "wav": "pcm_s16le",
    "flac": "flac",
    "ogg": "libvorbis",
    "opus": "libopus",
    "wma": "wmav2",
    "alac": "alac",
    "aiff": "pcm_s16be",
    "amr": "libopencore_amrnb",
}


# ─── DETECCIÓN DE GPU ──────────────────────────────────────────────

class GPUDetector:
    """Detecta GPUs y codecs disponibles"""
    
    def __init__(self, ffmpeg_path: str):
        self.ffmpeg_path = ffmpeg_path
        self._codecs_cache = None
        
    def get_available_codecs(self) -> List[str]:
        if self._codecs_cache is not None:
            return self._codecs_cache
        
        codecs = []
        try:
            cmd = [self.ffmpeg_path, "-encoders"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if any(gpu in line.lower() for gpu in ['nvenc', 'qsv', 'amf', 'cuda', 'vaapi']):
                        parts = line.split()
                        if len(parts) >= 2:
                            codec = parts[1].strip()
                            if codec.endswith(('_nvenc', '_qsv', '_amf', '_cuda', '_vaapi')):
                                codecs.append(codec)
        except Exception as e:
            logger.warning(f"Error detectando codecs GPU: {e}")
        
        self._codecs_cache = codecs
        return codecs
    
    def detect_gpu(self) -> Dict[str, Any]:
        available_codecs = self.get_available_codecs()
        
        result = {
            "nvidia": False,
            "amd": False,
            "intel": False,
            "codecs": available_codecs
        }
        
        for codec in available_codecs:
            if "nvenc" in codec:
                result["nvidia"] = True
            elif "amf" in codec:
                result["amd"] = True
            elif "qsv" in codec:
                result["intel"] = True
        
        return result

# ─── GESTOR DE FFMPEG ──────────────────────────────────────────────

class FFMpegManager:
    """Gestor de FFmpeg con detección automática"""
    
    def __init__(self):
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self._find_ffmpeg()
        self.gpu_detector = GPUDetector(self.ffmpeg_path)
        self.gpu_info = self.gpu_detector.detect_gpu()
        
    def _find_ffmpeg(self):
        paths_to_try = [
            Path(__file__).parent.parent / "ffmpeg.exe",
            Path(__file__).parent.parent / "bin" / "ffmpeg.exe",
            Path(__file__).parent.parent / "ffmpeg" / "ffmpeg.exe",
            "ffmpeg",
            "ffmpeg.exe",
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/opt/ffmpeg/bin/ffmpeg",
        ]
        
        for path in paths_to_try:
            try:
                if shutil.which(path) or (isinstance(path, Path) and path.exists()):
                    self.ffmpeg_path = str(Path(path) if isinstance(path, Path) else Path(path))
                    ffprobe_path = Path(self.ffmpeg_path).parent / "ffprobe.exe"
                    if ffprobe_path.exists():
                        self.ffprobe_path = str(ffprobe_path)
                    elif shutil.which("ffprobe"):
                        self.ffprobe_path = shutil.which("ffprobe")
                    else:
                        self.ffprobe_path = "ffprobe"
                    
                    logger.info(f"FFmpeg encontrado en: {self.ffmpeg_path}")
                    return
            except:
                continue
        
        logger.error("FFmpeg no encontrado")
        raise FileNotFoundError("FFmpeg no encontrado en el sistema")
    
    def get_ffmpeg(self) -> str:
        return self.ffmpeg_path
    
    def get_ffprobe(self) -> str:
        return self.ffprobe_path

# ─── PROGRESS HANDLER ──────────────────────────────────────────────

class ProgressHandler:
    """Maneja el progreso de la conversión"""
    
    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback
        self.duration = None
        self.current_time = 0
        self.last_percent = 0
        self.last_update = time.time()
        self.progress_data = {}
    
    def parse_progress(self, line: str) -> Optional[int]:
        """Parsea la salida de progreso de FFmpeg"""
        # Buscar duración en el formato -progress
        if "duration=" in line:
            try:
                self.duration = float(line.split("=")[1])
            except:
                pass
        
        # También buscar en formato tradicional
        if "Duration:" in line:
            match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
            if match:
                h, m, s, cs = map(int, match.groups())
                self.duration = h * 3600 + m * 60 + s + cs / 100
        
        # Progreso con -progress
        if "out_time_ms=" in line:
            try:
                time_ms = int(line.split("=")[1])
                self.current_time = time_ms / 1000000
                
                if self.duration and self.duration > 0:
                    percent = min(100, int((self.current_time / self.duration) * 100))
                    if percent != self.last_percent and time.time() - self.last_update > 0.5:
                        self.last_percent = percent
                        self.last_update = time.time()
                        if self.callback:
                            self.callback(percent)
                        return percent
            except:
                pass
        
        # Cuando el progreso llega a 100% con -progress
        if "progress=end" in line:
            if self.callback:
                self.callback(100)
            return 100
        
        return None
    
    def get_progress_bar(self, percent: int, width: int = 40) -> str:
        filled = int(width * percent / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"│{bar}│ {percent}%"

# ─── CONVERSOR PRINCIPAL ──────────────────────────────────────────

class FileConverter:
    """Conversor de archivos universal con todas las funcionalidades"""
    
    def __init__(self):
        self.ffmpeg = FFMpegManager()
        self.gpu_info = self.ffmpeg.gpu_info
        self.current_process = None
        self.cancel_requested = False
        
        self.config_dir = Path(__file__).resolve().parent.parent / "config"
        self.profiles_file = self.config_dir / "converter_profiles.json"
        
        self.profiles = PROFILES.copy()
        self._load_custom_profiles()
    
    def _load_custom_profiles(self):
        if self.profiles_file.exists():
            try:
                data = json.loads(self.profiles_file.read_text(encoding="utf-8"))
                for name, profile_data in data.items():
                    self.profiles[name] = ConversionProfile(**profile_data)
                logger.info(f"Perfiles personalizados cargados: {len(data)}")
            except Exception as e:
                logger.error(f"Error cargando perfiles personalizados: {e}")
    
    def _save_custom_profiles(self):
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        custom = {k: asdict(v) for k, v in self.profiles.items() if k not in PROFILES}
        self.profiles_file.write_text(json.dumps(custom, indent=4, ensure_ascii=False), encoding="utf-8")
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        input_path = Path(file_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        info = {
            "name": input_path.name,
            "size": input_path.stat().st_size,
            "size_mb": round(input_path.stat().st_size / (1024 * 1024), 2),
            "extension": input_path.suffix.lower(),
            "type": "unknown",
            "streams": []
        }
        
        if info["extension"] in VIDEO_EXTENSIONS:
            info["type"] = "video"
        elif info["extension"] in AUDIO_EXTENSIONS:
            info["type"] = "audio"
        elif info["extension"] in IMAGE_EXTENSIONS:
            info["type"] = "image"
        elif info["extension"] in SUBTITLE_EXTENSIONS:
            info["type"] = "subtitle"
        
        try:
            ffprobe = self.ffmpeg.get_ffprobe()
            cmd = [
                ffprobe,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                "-show_chapters",
                str(input_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                if "format" in data:
                    fmt = data["format"]
                    info["duration"] = float(fmt.get("duration", 0))
                    info["bitrate"] = int(fmt.get("bit_rate", 0))
                    info["format_name"] = fmt.get("format_name", "")
                
                info["streams"] = []
                for stream in data.get("streams", []):
                    stream_info = {
                        "type": stream.get("codec_type"),
                        "codec": stream.get("codec_name"),
                        "index": stream.get("index"),
                        "language": stream.get("tags", {}).get("language", "und")
                    }
                    
                    if stream.get("codec_type") == "video":
                        stream_info["width"] = stream.get("width", 0)
                        stream_info["height"] = stream.get("height", 0)
                        stream_info["fps"] = self._parse_fps(stream)
                        stream_info["pixel_format"] = stream.get("pix_fmt", "")
                        stream_info["color_primaries"] = stream.get("color_primaries", "")
                        stream_info["color_trc"] = stream.get("color_transfer", "")
                        stream_info["color_space"] = stream.get("color_space", "")
                        stream_info["bit_depth"] = self._get_bit_depth(stream)
                        stream_info["hdr"] = self._is_hdr(stream)
                        stream_info["master_display"] = stream.get("tags", {}).get("master_display", "")
                        stream_info["content_light"] = stream.get("tags", {}).get("content_light", "")
                    
                    if stream.get("codec_type") == "audio":
                        stream_info["channels"] = stream.get("channels", 0)
                        stream_info["sample_rate"] = stream.get("sample_rate", 0)
                        stream_info["bit_depth"] = stream.get("bits_per_raw_sample", 0)
                    
                    if stream.get("codec_type") == "subtitle":
                        stream_info["codec"] = stream.get("codec_name", "")
                    
                    info["streams"].append(stream_info)
                
                info["chapters"] = []
                for chapter in data.get("chapters", []):
                    info["chapters"].append({
                        "start": float(chapter.get("start", 0)),
                        "end": float(chapter.get("end", 0)),
                        "title": chapter.get("tags", {}).get("title", "")
                    })
                
                video_streams = [s for s in info["streams"] if s["type"] == "video"]
                if video_streams:
                    v = video_streams[0]
                    info["resolution"] = f"{v.get('width', 0)}x{v.get('height', 0)}"
                    info["fps"] = v.get("fps", 0)
                    info["video_codec"] = v.get("codec", "")
                    info["pixel_format"] = v.get("pixel_format", "")
                    info["hdr"] = v.get("hdr", False)
                
                audio_streams = [s for s in info["streams"] if s["type"] == "audio"]
                if audio_streams:
                    a = audio_streams[0]
                    info["audio_codec"] = a.get("codec", "")
                    info["channels"] = a.get("channels", 0)
                    info["sample_rate"] = a.get("sample_rate", 0)
                    info["audio_streams"] = len(audio_streams)
                
                subtitle_streams = [s for s in info["streams"] if s["type"] == "subtitle"]
                if subtitle_streams:
                    info["subtitle_streams"] = len(subtitle_streams)
                
        except Exception as e:
            logger.error(f"Error obteniendo información: {e}")
        
        return info
    
    def _parse_fps(self, stream: Dict) -> float:
        try:
            if "r_frame_rate" in stream:
                num, den = stream["r_frame_rate"].split("/")
                return float(num) / float(den) if float(den) > 0 else 0
            if "avg_frame_rate" in stream:
                num, den = stream["avg_frame_rate"].split("/")
                return float(num) / float(den) if float(den) > 0 else 0
        except:
            pass
        return 0
    
    def _get_bit_depth(self, stream: Dict) -> int:
        try:
            if "bits_per_raw_sample" in stream:
                return int(stream["bits_per_raw_sample"])
            if "pix_fmt" in stream:
                if "10le" in stream["pix_fmt"] or "10be" in stream["pix_fmt"]:
                    return 10
                if "12le" in stream["pix_fmt"] or "12be" in stream["pix_fmt"]:
                    return 12
            return 8
        except:
            return 8
    
    def _is_hdr(self, stream: Dict) -> bool:
        try:
            color_primaries = stream.get("color_primaries", "")
            color_trc = stream.get("color_transfer", "")
            color_space = stream.get("color_space", "")
            
            if "bt2020" in color_primaries and "smpte2084" in color_trc:
                return True
            if "bt2020" in color_space and "smpte2084" in color_trc:
                return True
            if "arib-std-b67" in color_trc:
                return True
            if "dovi" in stream.get("codec_name", ""):
                return True
            if self._get_bit_depth(stream) > 8:
                if "bt2020" in color_primaries:
                    return True
        except:
            pass
        return False
    
    def _detect_input_type(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            return "video"
        elif ext in AUDIO_EXTENSIONS:
            return "audio"
        elif ext in IMAGE_EXTENSIONS:
            return "image"
        elif ext in SUBTITLE_EXTENSIONS:
            return "subtitle"
        return "unknown"
    
    def _is_valid_output_format(self, output_format: str) -> bool:
        return output_format in SUPPORTED_OUTPUTS
    
    def _get_output_path(self, input_path: str, output_format: str, suffix: str = "") -> Path:
        input_p = Path(input_path)
        output_p = input_p.with_suffix(f".{output_format}")
        
        if input_p == output_p:
            name = f"{input_p.stem}{suffix}_convertido"
            output_p = input_p.with_name(f"{name}.{output_format}")
        
        counter = 1
        while output_p.exists():
            name = f"{input_p.stem}{suffix}_convertido_{counter}"
            output_p = input_p.with_name(f"{name}.{output_format}")
            counter += 1
        
        return output_p
    
    def _escape_text(self, text: str) -> str:
        """Escapa texto para usar en filtros FFmpeg"""
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "\\'")
        text = text.replace(":", "\\:")
        text = text.replace("%", "%%")
        text = text.replace('"', '\\"')
        return text
    
    def _build_filter_complex(self, video_filters: List[str], 
                             watermark_input: Optional[str] = None,
                             watermark_pos: str = "bottom-right",
                             subtitle_input: Optional[str] = None,
                             subtitle_burn: bool = False,
                             input_count: int = 1) -> Tuple[Optional[str], Optional[List[str]], int]:
        """Construye un filter_complex completo"""
        filters = []
        map_outputs = []
        next_input = input_count
        
        # Si no hay filtros, retornar None
        if not video_filters and not watermark_input and not (subtitle_input and subtitle_burn):
            return None, [], next_input
        
        # Filtros de video
        if video_filters:
            valid_filters = [f for f in video_filters if f and f.strip()]
            if valid_filters:
                filters.append(f"[0:v]{','.join(valid_filters)}[v0]")
            else:
                filters.append(f"[0:v]null[v0]")
        else:
            filters.append(f"[0:v]null[v0]")
        
        current = "v0"
        
        # Watermark
        if watermark_input:
            positions = {
                "top-left": "10:10",
                "top-right": "W-w-10:10",
                "bottom-left": "10:H-h-10",
                "bottom-right": "W-w-10:H-h-10",
                "center": "(W-w)/2:(H-h)/2"
            }
            pos = positions.get(watermark_pos, "W-w-10:H-h-10")
            filters.append(f"[{current}][{next_input}:v]overlay={pos}[v1]")
            current = "v1"
            next_input += 1
        
        # Subtítulos (burn)
        if subtitle_input and subtitle_burn:
            escaped = self._escape_text(subtitle_input)
            filters.append(f"[{current}]subtitles='{escaped}'[vout]")
            current = "vout"
        else:
            filters.append(f"[{current}]null[vout]")
        
        filter_complex = "; ".join(filters)
        map_outputs = ["[vout]"]
        
        return filter_complex, map_outputs, next_input
    
    def _run_ffmpeg(self, args: List[str], progress_callback: Optional[Callable] = None) -> Tuple[bool, str]:
        """Ejecuta FFmpeg con manejo de progreso"""
        self.cancel_requested = False
        progress = ProgressHandler(progress_callback)
        
        cmd = [self.ffmpeg.get_ffmpeg()]
        cmd.extend(["-progress", "pipe:2"])
        cmd.extend(["-nostats"])
        cmd.extend(args)
        
        # Debug - mostrar comando
        print("\n" + "="*70)
        print("FFMPEG COMMAND:")
        cmd_str = " ".join(f'"{x}"' if " " in x else x for x in cmd)
        print(cmd_str)
        print("="*70 + "\n")
        logger.info(f"FFmpeg CMD: {cmd_str}")
        
        try:
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
            
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags,
                universal_newlines=True
            )
            
            output_lines = []
            while True:
                if self.cancel_requested:
                    self.current_process.terminate()
                    return False, "Conversión cancelada por el usuario"
                
                line = self.current_process.stdout.readline()
                if not line:
                    break
                
                output_lines.append(line)
                progress.parse_progress(line)
            
            self.current_process.wait()
            
            if self.current_process.returncode == 0:
                return True, "Conversión completada exitosamente"
            else:
                error_msg = "".join(output_lines)
                return False, error_msg
                
        except Exception as e:
            return False, f"Error en la conversión: {str(e)}"
        finally:
            self.current_process = None
    
    def _parse_error(self, stderr: str) -> str:
        error_messages = {
            "No such file or directory": "❌ Archivo no encontrado",
            "Invalid data found": "❌ Datos inválidos o archivo corrupto",
            "Codec not found": "❌ Codec no soportado",
            "Permission denied": "❌ Sin permisos para escribir el archivo",
            "No space left on device": "❌ Espacio insuficiente en disco",
            "Encoder not found": "❌ Codec no encontrado en el sistema",
            "Invalid argument": "❌ Argumento inválido para FFmpeg",
            "Unsupported codec": "❌ Codec no soportado",
            "Container not supported": "❌ Contenedor no soportado",
            "Subtitle encoding": "❌ Error en codificación de subtítulos"
        }
        
        for key, msg in error_messages.items():
            if key in stderr:
                return f"{msg}\n\nDetalles técnicos:\n{stderr}"
        
        return f"❌ Error en FFmpeg:\n{stderr}"
    
    def cancel_conversion(self) -> bool:
        if self.current_process:
            self.cancel_requested = True
            try:
                self.current_process.terminate()
                return True
            except:
                pass
        return False
    
    # ─── MÉTODOS DE CONVERSIÓN ──────────────────────────────────────
    
    def convert_file(
        self,
        input_path: str,
        output_format: str,
        profile: str = "media",
        quality: str = "medium",
        use_gpu: bool = True,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """Convierte un archivo al formato deseado"""
        input_p = Path(input_path)
        
        if not input_p.exists():
            return f"❌ Archivo no encontrado: {input_path}"
        
        input_type = self._detect_input_type(str(input_p))
        output_format = output_format.lower().replace(".", "")
        
        if not self._is_valid_output_format(output_format):
            return f"❌ Formato no soportado: {output_format}"
        
        if input_type == "unknown":
            return f"❌ Tipo de archivo no soportado: {input_p.suffix}"
        
        profile_obj = copy.deepcopy(
            self.profiles.get(profile, self.profiles["media"])
        )
        
        # Determinar tipo de salida CORRECTAMENTE
        output_type = "video"
        if f".{output_format}" in AUDIO_EXTENSIONS:
            output_type = "audio"
            profile_obj.video_codec = "none"
            correct_codec = AUDIO_CODEC_MAP.get(output_format)
            if correct_codec:
                profile_obj.audio_codec = correct_codec
        elif f".{output_format}" in IMAGE_EXTENSIONS:
            output_type = "image"
        
        # Ajustar calidad
        if quality == "low":
            profile_obj.crf = 28
            profile_obj.video_bitrate = "1000k"
            profile_obj.preset = "fast"
        elif quality == "high":
            profile_obj.crf = 20
            profile_obj.video_bitrate = "4000k"
            profile_obj.preset = "slow"
        elif quality == "lossless":
            profile_obj.crf = 0
            profile_obj.video_bitrate = None
            profile_obj.preset = "veryslow"
        
        if kwargs.get("resolution"):
            profile_obj.resolution = kwargs["resolution"]
        if kwargs.get("fps"):
            profile_obj.fps = kwargs["fps"]
        
        input_info = self.get_file_info(str(input_p))
        
        # HDR - preservar metadata
        if input_info.get("hdr", False):
            if "-copy_unknown" not in profile_obj.extra_args:
                profile_obj.extra_args.append("-copy_unknown")
            
            if profile_obj.pixel_format is None:
                profile_obj.pixel_format = "yuv420p10le"
            if not profile_obj.color_primaries:
                profile_obj.color_primaries = "bt2020"
            if not profile_obj.color_trc:
                profile_obj.color_trc = "smpte2084"
            if not profile_obj.color_space:
                profile_obj.color_space = "bt2020nc"
        
        # GPU
        use_gpu = use_gpu and profile_obj.gpu_codec is not None
        if use_gpu and profile_obj.gpu_codec not in self.gpu_info.get("codecs", []):
            use_gpu = False
            logger.warning(f"GPU codec {profile_obj.gpu_codec} no disponible, usando CPU")
        
        output_p = self._get_output_path(str(input_p), output_format)
        
        # ─── CONSTRUIR COMANDO ─────────────────────────────────────
        cmd = []
        
        # 1. GPU ACCELERATION (SOLO PARA VIDEO) - DEBE IR ANTES DE -i
        if use_gpu and profile_obj.hwaccel and output_type != "audio":
            cmd.extend(["-hwaccel", profile_obj.hwaccel])
        
        # 2. Tiempo (antes de -i)
        if kwargs.get("start_time"):
            cmd.extend(["-ss", kwargs["start_time"]])
        if kwargs.get("end_time"):
            cmd.extend(["-to", kwargs["end_time"]])
        
        # 3. Input principal
        cmd.extend(["-i", str(input_p)])
        next_input_index = 1
        
        # Watermark (solo para video)
        watermark_input = None
        if output_type != "audio" and kwargs.get("watermark"):
            watermark_input = kwargs["watermark"]
            cmd.extend(["-i", watermark_input])
            next_input_index += 1
        
        # Subtítulos (solo para video)
        subtitle_input = None
        if output_type != "audio" and kwargs.get("subtitle_file"):
            subtitle_input = kwargs["subtitle_file"]
            cmd.extend(["-i", subtitle_input])
            next_input_index += 1
        
        # 4. PARA AUDIO: solo audio, sin filtros de video
        if output_type == "audio":
            # Solo mapear audio
            cmd.extend(["-map", "0:a"])
            cmd.extend(["-vn"])
            # No usar filter_complex para audio
            filter_complex = None
            map_outputs = []
        else:
            # Mapeo de streams para video
            map_streams = kwargs.get("map_streams", [])
            if map_streams:
                for stream in map_streams:
                    cmd.extend(["-map", stream])
            else:
                cmd.extend(["-map", "0"])
            
            if kwargs.get("audio_stream"):
                cmd.extend(["-map", f"0:a:{kwargs['audio_stream']}"])
            if kwargs.get("subtitle_stream"):
                cmd.extend(["-map", f"0:s:{kwargs['subtitle_stream']}"])
            
            # 5. Filtros de video (solo para video)
            video_filters = []
            
            # Rotación
            if kwargs.get("rotate"):
                rotations = {
                    "90": "transpose=1",
                    "180": "transpose=2,transpose=2",
                    "270": "transpose=2",
                    "horizontal": "hflip",
                    "vertical": "vflip"
                }
                if kwargs["rotate"] in rotations:
                    video_filters.append(rotations[kwargs["rotate"]])
            
            # Resolución
            resolution = kwargs.get("resolution") or profile_obj.resolution
            if resolution:
                video_filters.append(f"scale={resolution}:flags=lanczos")
            
            # FPS
            fps = kwargs.get("fps") or profile_obj.fps
            if fps:
                video_filters.append(f"fps={fps}")
            
            # Text overlay (escapado)
            text_watermark = kwargs.get("text")
            if text_watermark:
                escaped_text = self._escape_text(text_watermark)
                font_size = kwargs.get("font_size", 24)
                text_color = kwargs.get("text_color", "white")
                position = kwargs.get("text_position", "center")
                positions = {
                    "top-left": "10:10",
                    "top-center": "(W-text_w)/2:10",
                    "top-right": "W-w-10:10",
                    "center": "(W-text_w)/2:(H-text_h)/2",
                    "bottom-left": "10:H-h-10",
                    "bottom-center": "(W-text_w)/2:H-h-10",
                    "bottom-right": "W-w-10:H-h-10"
                }
                pos = positions.get(position, "(W-text_w)/2:(H-text_h)/2")
                video_filters.append(f"drawtext=text='{escaped_text}':fontsize={font_size}:fontcolor={text_color}:x={pos.split(':')[0]}:y={pos.split(':')[1]}")
            
            # 6. Filter Complex (solo si hay filtros complejos)
            subtitle_burn = kwargs.get("subtitle_burn", False)
            watermark_pos = kwargs.get("watermark_position", "bottom-right")
            
            filter_complex, map_outputs, _ = self._build_filter_complex(
                video_filters=video_filters,
                watermark_input=watermark_input,
                watermark_pos=watermark_pos,
                subtitle_input=subtitle_input,
                subtitle_burn=subtitle_burn,
                input_count=next_input_index
            )
            
            if filter_complex:
                cmd.extend(["-filter_complex", filter_complex])
                # Limpiar mapas de video antiguos
                new_cmd = []
                skip_next = False
                for i, arg in enumerate(cmd):
                    if skip_next:
                        skip_next = False
                        continue
                    if arg == "-map" and i + 1 < len(cmd):
                        next_arg = cmd[i + 1]
                        if next_arg in ["0:v", "0"] or next_arg.startswith("0:v"):
                            skip_next = True
                            continue
                    new_cmd.append(arg)
                cmd = new_cmd
                
                for map_out in map_outputs:
                    cmd.extend(["-map", map_out])
            
            # 7. Subtítulos no quemados (solo video)
            if subtitle_input and not subtitle_burn:
                subtitle_index = 1
                if watermark_input:
                    subtitle_index += 1
                cmd.extend(["-map", str(subtitle_index)])
                cmd.extend(["-c:s", "mov_text" if output_format == "mp4" else "ass"])
        
        # 8. Perfil de conversión
        cmd.extend(profile_obj.get_ffmpeg_args(use_gpu, input_info, output_type))
        
        if kwargs.get("copy_chapters", True):
            cmd.extend(["-map_chapters", "0"])
        
        # 9. Extraer fotogramas (solo video)
        if output_type != "audio" and kwargs.get("extract_frames"):
            output_pattern = str(output_p.parent / f"{output_p.stem}_frame_%04d.png")
            if kwargs.get("frame_interval"):
                cmd = []
                if use_gpu and profile_obj.hwaccel:
                    cmd.extend(["-hwaccel", profile_obj.hwaccel])
                if kwargs.get("start_time"):
                    cmd.extend(["-ss", kwargs["start_time"]])
                cmd.extend(["-i", str(input_p)])
                cmd.extend(["-vf", f"fps=1/{kwargs['frame_interval']}"])
                cmd.append(output_pattern)
            else:
                frames = kwargs.get("frames", [])
                if frames:
                    filters = []
                    for frame in frames:
                        filters.append(f"select='eq(n\\,{frame})'")
                    cmd = []
                    if use_gpu and profile_obj.hwaccel:
                        cmd.extend(["-hwaccel", profile_obj.hwaccel])
                    if kwargs.get("start_time"):
                        cmd.extend(["-ss", kwargs["start_time"]])
                    cmd.extend(["-i", str(input_p)])
                    cmd.extend(["-vf", "+".join(filters)])
                    cmd.extend(["-vsync", "vfr"])
                    cmd.append(output_pattern)
        else:
            cmd.append(str(output_p))
        
        # Ejecutar
        success, message = self._run_ffmpeg(cmd, progress_callback)
        
        if success:
            return f"✅ {message}\n📁 Guardado en: {output_p}"
        else:
            return self._parse_error(message)
    
    def convert_batch(self, input_paths: List[str], output_format: str, 
                      profile: str = "media", **kwargs) -> str:
        """Convierte múltiples archivos en lote"""
        results = []
        total = len(input_paths)
        
        for i, path in enumerate(input_paths, 1):
            result = self.convert_file(
                path,
                output_format,
                profile=profile,
                **kwargs
            )
            results.append(f"[{i}/{total}] {result}")
        
        return "\n\n".join(results)
    
    def extract_audio(self, input_path: str, audio_format: str = "mp3", 
                      bitrate: str = "192k", **kwargs) -> str:
        """Extrae audio de un archivo de video"""
        return self.convert_file(
            input_path,
            audio_format,
            profile="audio_mp3",
            quality="high",
            **kwargs
        )
    
    def create_gif(self, input_path: str, output_path: Optional[str] = None,
                   fps: int = 10, duration: Optional[int] = None, **kwargs) -> str:
        """Crea un GIF animado desde un video con paleta optimizada"""
        input_p = Path(input_path)
        
        if not output_path:
            output_p = input_p.with_suffix(".gif")
        else:
            output_p = Path(output_path)
        
        info = self.get_file_info(str(input_p))
        
        palette_p = output_p.parent / f"{output_p.stem}_palette.png"
        
        try:
            # Generar paleta
            palette_cmd = [self.ffmpeg.get_ffmpeg(), "-y", "-i", str(input_p)]
            
            filters = [f"fps={fps}"]
            if kwargs.get("resolution"):
                filters.append(f"scale={kwargs['resolution']}:flags=lanczos")
            elif info.get("width", 640) > 640:
                filters.append("scale=640:-1:flags=lanczos")
            
            if duration:
                palette_cmd.extend(["-t", str(duration)])
            
            palette_cmd.extend(["-vf", ",".join(filters) + ",palettegen"])
            palette_cmd.append(str(palette_p))
            
            self._run_ffmpeg(palette_cmd)
            
            # Crear GIF con la paleta
            gif_cmd = [self.ffmpeg.get_ffmpeg(), "-y", "-i", str(input_p), "-i", str(palette_p)]
            
            if duration:
                gif_cmd.extend(["-t", str(duration)])
            
            gif_cmd.extend([
                "-lavfi",
                f"fps={fps},scale={kwargs.get('resolution', '640:-1')}:flags=lanczos [x]; [x][1:v] paletteuse"
            ])
            gif_cmd.append(str(output_p))
            
            success, message = self._run_ffmpeg(gif_cmd)
            
            if success:
                return f"✅ GIF creado exitosamente\n📁 Guardado en: {output_p}"
            return message
            
        finally:
            if palette_p.exists():
                palette_p.unlink()
    
    def merge_videos(self, video_paths: List[str], output_path: Optional[str] = None,
                     **kwargs) -> str:
        """Une múltiples videos en uno solo"""
        if len(video_paths) < 2:
            return "❌ Necesitas al menos 2 videos para unir"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for path in video_paths:
                f.write(f"file '{Path(path).absolute()}'\n")
            list_file = f.name
        
        try:
            if not output_path:
                output_p = Path(video_paths[0]).with_suffix(".mp4")
            else:
                output_p = Path(output_path)
            
            cmd = [
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy"
            ]
            
            if kwargs.get("reencode", False):
                cmd = [
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file,
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-preset", "medium",
                    "-crf", "23"
                ]
            
            cmd.append(str(output_p))
            
            success, message = self._run_ffmpeg(cmd)
            
            if success:
                return f"✅ Videos unidos exitosamente\n📁 Guardado en: {output_p}"
            return message
            
        finally:
            os.unlink(list_file)
    
    def merge_audio(self, audio_paths: List[str], output_path: Optional[str] = None,
                    **kwargs) -> str:
        """Une múltiples audios en uno solo"""
        if len(audio_paths) < 2:
            return "❌ Necesitas al menos 2 audios para unir"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for path in audio_paths:
                f.write(f"file '{Path(path).absolute()}'\n")
            list_file = f.name
        
        try:
            if not output_path:
                output_p = Path(audio_paths[0]).with_suffix(".mp3")
            else:
                output_p = Path(output_path)
            
            cmd = [
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy"
            ]
            cmd.append(str(output_p))
            
            success, message = self._run_ffmpeg(cmd)
            
            if success:
                return f"✅ Audios unidos exitosamente\n📁 Guardado en: {output_p}"
            return message
            
        finally:
            os.unlink(list_file)
    
    def compress_video(self, input_path: str, output_path: Optional[str] = None,
                       target_size_mb: Optional[int] = None, quality: str = "medium",
                       **kwargs) -> str:
        """Comprime un video reduciendo su tamaño"""
        if target_size_mb:
            info = self.get_file_info(input_path)
            duration = info.get("duration", 0)
            if duration > 0:
                target_bits = target_size_mb * 8 * 1024 * 1024
                bitrate = int(target_bits / duration)
                kwargs["video_bitrate"] = f"{bitrate}k"
        
        return self.convert_file(
            input_path,
            "mp4",
            profile="ligero" if quality == "low" else "media",
            quality=quality,
            **kwargs
        )
    
    def change_resolution(self, input_path: str, resolution: str, **kwargs) -> str:
        """Cambia la resolución de un video"""
        return self.convert_file(
            input_path,
            "mp4",
            profile="media",
            resolution=resolution,
            **kwargs
        )
    
    def create_thumbnail(self, input_path: str, output_path: Optional[str] = None,
                         time_position: str = "00:00:10", **kwargs) -> str:
        """Crea una miniatura del video"""
        input_p = Path(input_path)
        
        if not output_path:
            output_p = input_p.with_suffix(".jpg")
        else:
            output_p = Path(output_path)
        
        cmd = ["-y"]
        
        if time_position:
            cmd.extend(["-ss", time_position])
        
        cmd.extend(["-i", str(input_p)])
        cmd.extend(["-vframes", "1"])
        cmd.extend(["-q:v", "2"])
        
        if kwargs.get("resolution"):
            cmd.extend(["-vf", f"scale={kwargs['resolution']}:flags=lanczos"])
        elif kwargs.get("width"):
            cmd.extend(["-vf", f"scale={kwargs['width']}:-1:flags=lanczos"])
        
        cmd.append(str(output_p))
        
        success, message = self._run_ffmpeg(cmd)
        
        if success:
            return f"✅ Miniatura creada exitosamente\n📁 Guardado en: {output_p}"
        return message
    
    def create_profile(self, name: str, profile_data: Dict) -> str:
        """Crea un nuevo perfil de conversión"""
        if name in self.profiles:
            return f"⚠️ El perfil '{name}' ya existe"
        
        try:
            new_profile = ConversionProfile(**profile_data)
            self.profiles[name] = new_profile
            self._save_custom_profiles()
            return f"✅ Perfil '{name}' creado exitosamente"
        except Exception as e:
            return f"❌ Error creando perfil: {e}"
    
    def list_profiles(self) -> str:
        """Lista todos los perfiles disponibles"""
        result = "📋 **Perfiles de conversión disponibles:**\n\n"
        
        for name, profile in self.profiles.items():
            result += f"**{name}**: {profile.description}\n"
            result += f"  Codec: {profile.video_codec}\n"
            result += f"  Preset: {profile.preset}\n"
            result += f"  Contenedor: {profile.container}\n"
            if profile.gpu_codec:
                result += f"  GPU: {profile.gpu_codec}\n"
            if profile.hwaccel:
                result += f"  HW Accel: {profile.hwaccel}\n"
            result += "\n"
        
        return result

# ─── INSTANCIA GLOBAL ──────────────────────────────────────────────

_CONVERTER = FileConverter()

# ─── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────

def convert_file(input_path: str, output_format: str, player=None, **kwargs) -> str:
    """Punto de entrada principal para el conversor de archivos"""
    converter = _CONVERTER
    
    def progress_callback(percent: int):
        if player:
            bar = ProgressHandler().get_progress_bar(percent)
            player.write_log(f"🔄 Progreso: {bar}")
    
    if player:
        player.write_log(f"🎬 Iniciando conversión...")
        player.write_log(f"📁 Origen: {input_path}")
        player.write_log(f"📁 Destino: {output_format}")
    
    try:
        action = kwargs.get("action", "convert")
        
        if action == "extract_audio":
            result = converter.extract_audio(input_path, output_format, **kwargs)
        elif action == "create_gif":
            result = converter.create_gif(input_path, **kwargs)
        elif action == "merge_videos":
            videos = kwargs.get("videos", [])
            result = converter.merge_videos(videos, **kwargs)
        elif action == "merge_audio":
            audios = kwargs.get("audios", [])
            result = converter.merge_audio(audios, **kwargs)
        elif action == "compress":
            result = converter.compress_video(input_path, **kwargs)
        elif action == "change_resolution":
            resolution = kwargs.get("resolution", "1920x1080")
            result = converter.change_resolution(input_path, resolution, **kwargs)
        elif action == "info":
            info = converter.get_file_info(input_path)
            result = "📊 **Información del archivo:**\n"
            result += json.dumps(info, indent=2, ensure_ascii=False)
        elif action == "batch":
            files = kwargs.get("files", [])
            result = converter.convert_batch(files, output_format, **kwargs)
        elif action == "list_profiles":
            result = converter.list_profiles()
        elif action == "create_profile":
            name = kwargs.get("name", "")
            profile_data = kwargs.get("profile_data", {})
            result = converter.create_profile(name, profile_data)
        elif action == "cancel":
            result = "✅ Conversión cancelada" if converter.cancel_conversion() else "⚠️ No hay conversión activa"
        elif action == "thumbnail":
            result = converter.create_thumbnail(input_path, **kwargs)
        else:
            result = converter.convert_file(
                input_path,
                output_format,
                progress_callback=progress_callback,
                **kwargs
            )
        
        if player:
            player.write_log(result)
        
        return result
        
    except Exception as e:
        error_msg = f"❌ Error en la conversión: {str(e)}"
        if player:
            player.write_log(error_msg)
        return error_msg

# ─── FUNCIONES DE AYUDA ────────────────────────────────────────────

def get_profile_names() -> List[str]:
    return list(_CONVERTER.profiles.keys())

def get_supported_formats() -> Dict[str, List[str]]:
    return {
        "video": sorted(list(VIDEO_EXTENSIONS)),
        "audio": sorted(list(AUDIO_EXTENSIONS)),
        "image": sorted(list(IMAGE_EXTENSIONS)),
        "subtitle": sorted(list(SUBTITLE_EXTENSIONS))
    }

def get_gpu_info() -> Dict[str, Any]:
    return _CONVERTER.gpu_info