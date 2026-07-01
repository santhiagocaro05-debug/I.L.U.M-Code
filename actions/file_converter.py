"""
file_converter.py - Universal File Converter for ILUM using FFmpeg
Converts Audio and Video files seamlessly.
"""

import os
import subprocess
from pathlib import Path

def convert_file(input_path: str, output_format: str, player=None) -> str:
    """
    Converts a media file to the desired format using the bundled FFmpeg.
    """
    try:
        input_p = Path(input_path)
        if not input_p.exists():
            return f"Error: No se encontró el archivo origen en {input_path}."
            
        output_format = output_format.lower().replace(".", "")
        if not output_format:
            return "Error: Formato de salida no especificado."
            
        output_p = input_p.with_suffix(f".{output_format}")
        
        # Avoid overwriting directly if same path
        if input_p == output_p:
            output_p = input_p.with_name(f"{input_p.stem}_convertido.{output_format}")
            
        # Locate bundled ffmpeg
        base_dir = Path(__file__).parent.parent
        ffmpeg_path = base_dir / "ffmpeg.exe"
        
        if not ffmpeg_path.exists():
            return "Error: No se encontró el motor ffmpeg.exe en el sistema base."
            
        if player:
            player.write_log(f"🔄 Convirtiendo '{input_p.name}' a '{output_format}'...")
            
        command = [
            str(ffmpeg_path),
            "-y", # Overwrite output if exists
            "-i", str(input_p),
        ]
        
        # Audio extraction/conversion fast parameters
        if output_format in ["mp3", "wav", "flac", "ogg", "aac", "m4a"]:
            if output_format == "mp3":
                command.extend(["-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k"])
            elif output_format == "wav":
                command.extend(["-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2"])
        elif output_format in ["mp4", "mkv", "avi", "mov"]:
            command.extend(["-c:v", "libx264", "-preset", "fast", "-c:a", "aac"])
            
        command.append(str(output_p))
        
        # Run conversion
        # Use CREATE_NO_WINDOW on Windows to avoid console flash
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
            
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
            text=True
        )
        
        if process.returncode == 0 and output_p.exists():
            return f"Archivo convertido exitosamente. Guardado en: {output_p}"
        else:
            return f"Error en la conversión. FFmpeg devolvió código {process.returncode}:\n{process.stderr[-200:]}"
            
    except Exception as e:
        return f"Error interno al intentar convertir el archivo: {str(e)}"
