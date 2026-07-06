"""
file_processor.py — Procesador universal de archivos
Soporta: imágenes, PDFs, Word, Excel, CSV, JSON, código, audio, video
"""

import os
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import PyPDF2
    from docx import Document
    import openpyxl
    import pandas as pd
    from PIL import Image
    import cv2
    import numpy as np
    import pytesseract
    import fitz  # PyMuPDF
except ImportError:
    PyPDF2 = None
    Document = None
    openpyxl = None
    pd = None
    Image = None
    cv2 = None
    np = None
    pytesseract = None
    fitz = None

# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
FILE_PROCESSOR_CONFIG = Path(__file__).resolve().parent.parent / "config" / "file_processor.json"

def _get_config() -> Dict:
    """Carga la configuración."""
    if FILE_PROCESSOR_CONFIG.exists():
        try:
            return json.loads(FILE_PROCESSOR_CONFIG.read_text(encoding="utf-8"))
        except:
            pass
    
    default = {
        "temp_dir": str(Path.home() / "Documents" / "NEXUS_Temp"),
        "max_file_size": 50 * 1024 * 1024,  # 50MB
        "ocr_lang": "spa"
    }
    FILE_PROCESSOR_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    FILE_PROCESSOR_CONFIG.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default

def _ensure_temp_dir():
    """Asegura que el directorio temporal existe."""
    config = _get_config()
    temp_dir = Path(config.get("temp_dir", ""))
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir

# ─── FUNCIONES DE PROCESAMIENTO ────────────────────────────────────────────

def _process_image(file_path: str, action: str, params: Dict) -> str:
    """Procesa archivos de imagen."""
    if Image is None:
        return "❌ PIL no está instalado."
    
    try:
        img = Image.open(file_path)
        
        if action == "describe":
            # Generar descripción de la imagen
            width, height = img.size
            mode = img.mode
            format_name = img.format
            return f"""
📷 DESCRIPCIÓN DE IMAGEN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 Dimensiones: {width} x {height} píxeles
🎨 Modo: {mode}
📁 Formato: {format_name}
💾 Tamaño: {os.path.getsize(file_path) / 1024:.1f} KB
            """
        
        elif action == "resize":
            width = int(params.get("width", img.width))
            height = int(params.get("height", img.height))
            img = img.resize((width, height))
            output = _ensure_temp_dir() / f"resized_{Path(file_path).name}"
            img.save(output)
            return f"✅ Imagen redimensionada: {output}"
        
        elif action == "compress":
            quality = int(params.get("quality", 80))
            output = _ensure_temp_dir() / f"compressed_{Path(file_path).name}"
            img.save(output, optimize=True, quality=quality)
            return f"✅ Imagen comprimida: {output} (calidad {quality}%)"
        
        elif action == "ocr":
            if pytesseract is None:
                return "❌ Tesseract no está instalado."
            
            # Convertir a escala de grises para OCR
            if img.mode != 'RGB':
                img = img.convert('RGB')
            gray = img.convert('L')
            
            # OCR
            text = pytesseract.image_to_string(gray, lang=params.get("lang", "spa"))
            if text.strip():
                return f"📖 TEXTO EXTRAÍDO:\n{'-' * 40}\n{text.strip()}"
            else:
                return "📖 No se detectó texto en la imagen."
        
        elif action == "convert":
            format_type = params.get("format", "png")
            output = _ensure_temp_dir() / f"converted_{Path(file_path).stem}.{format_type}"
            img.save(output, format_type.upper())
            return f"✅ Imagen convertida a {format_type.upper()}: {output}"
        
        elif action == "info":
            return f"""
📊 INFORMACIÓN DE IMAGEN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 Dimensiones: {img.width} x {img.height}
🎨 Modo: {img.mode}
📁 Formato: {img.format}
💾 Tamaño: {os.path.getsize(file_path) / 1024:.1f} KB
🔢 Píxeles: {img.width * img.height:,}
            """
        
        else:
            return f"❌ Acción '{action}' no soportada para imágenes."
            
    except Exception as e:
        return f"❌ Error procesando imagen: {e}"

def _process_pdf(file_path: str, action: str, params: Dict) -> str:
    """Procesa archivos PDF."""
    try:
        if action == "summarize":
            # Extraer texto del PDF
            text = ""
            if fitz:
                doc = fitz.open(file_path)
                for page in doc:
                    text += page.get_text()
                doc.close()
            elif PyPDF2:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text()
            
            if text.strip():
                # Limitar texto para resumen
                if len(text) > 5000:
                    text = text[:5000] + "... (truncado)"
                return f"📄 TEXTO DEL PDF:\n{'-' * 40}\n{text}"
            else:
                return "📄 No se pudo extraer texto del PDF."
        
        elif action == "extract_text":
            text = ""
            if fitz:
                doc = fitz.open(file_path)
                for page in doc:
                    text += page.get_text()
                doc.close()
            elif PyPDF2:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text()
            
            if text.strip():
                return f"📄 TEXTO COMPLETO:\n{'-' * 40}\n{text}"
            else:
                return "📄 No se pudo extraer texto del PDF."
        
        elif action == "info":
            if fitz:
                doc = fitz.open(file_path)
                info = f"""
📊 INFORMACIÓN DEL PDF:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 Páginas: {len(doc)}
📁 Tamaño: {os.path.getsize(file_path) / 1024:.1f} KB
"""
                doc.close()
                return info
            else:
                return "❌ PyMuPDF no está instalado."
        
        else:
            return f"❌ Acción '{action}' no soportada para PDFs."
            
    except Exception as e:
        return f"❌ Error procesando PDF: {e}"

def _process_docx(file_path: str, action: str, params: Dict) -> str:
    """Procesa archivos Word (.docx)."""
    if Document is None:
        return "❌ python-docx no está instalado."
    
    try:
        doc = Document(file_path)
        
        if action == "summarize":
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            if text.strip():
                if len(text) > 5000:
                    text = text[:5000] + "... (truncado)"
                return f"📄 TEXTO DEL DOCUMENTO:\n{'-' * 40}\n{text}"
            else:
                return "📄 No se encontró texto en el documento."
        
        elif action == "extract_text":
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            return f"📄 TEXTO COMPLETO:\n{'-' * 40}\n{text}"
        
        elif action == "info":
            return f"""
📊 INFORMACIÓN DEL DOCUMENTO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 Párrafos: {len(doc.paragraphs)}
📁 Tamaño: {os.path.getsize(file_path) / 1024:.1f} KB
"""
        
        else:
            return f"❌ Acción '{action}' no soportada para documentos Word."
            
    except Exception as e:
        return f"❌ Error procesando documento: {e}"

def _process_excel(file_path: str, action: str, params: Dict) -> str:
    """Procesa archivos Excel (.xlsx, .csv)."""
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path) if pd else None
        else:
            df = pd.read_excel(file_path) if pd else None
        
        if df is None:
            return "❌ Pandas no está instalado."
        
        if action == "analyze":
            # Generar análisis estadístico
            stats = df.describe()
            head = df.head(5).to_string()
            
            return f"""
📊 ANÁLISIS DE DATOS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 Dimensiones: {df.shape[0]} filas x {df.shape[1]} columnas
📋 Columnas: {', '.join(df.columns.tolist())}
📊 Estadísticas:
{stats}

📌 Primeras 5 filas:
{head}
"""
        
        elif action == "stats":
            return f"""
📊 ESTADÍSTICAS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 Filas: {df.shape[0]}
📋 Columnas: {df.shape[1]}
📌 Columnas: {', '.join(df.columns.tolist())}
"""
        
        elif action == "filter":
            column = params.get("column", "")
            value = params.get("value", "")
            if column and value:
                filtered = df[df[column].astype(str).str.contains(value, case=False)]
                return f"✅ Filas filtradas: {len(filtered)}\n{filtered.head(10).to_string()}"
            else:
                return "❌ Se requiere 'column' y 'value' para filtrar."
        
        elif action == "convert":
            format_type = params.get("format", "csv")
            output = _ensure_temp_dir() / f"converted_{Path(file_path).stem}.{format_type}"
            if format_type == "csv":
                df.to_csv(output, index=False)
            elif format_type == "xlsx":
                df.to_excel(output, index=False)
            else:
                return f"❌ Formato '{format_type}' no soportado."
            return f"✅ Archivo convertido: {output}"
        
        else:
            return f"❌ Acción '{action}' no soportada para Excel/CSV."
            
    except Exception as e:
        return f"❌ Error procesando Excel: {e}"

def _process_code(file_path: str, action: str, params: Dict) -> str:
    """Procesa archivos de código."""
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        
        if action == "explain":
            # Generar explicación del código
            return f"""
💻 EXPLICACIÓN DEL CÓDIGO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Archivo: {Path(file_path).name}
🔤 Lenguaje: {Path(file_path).suffix.lstrip('.')}
📊 Líneas: {len(content.splitlines())}
📌 Código:
{content[:1500]}{'... (truncado)' if len(content) > 1500 else ''}
"""
        
        elif action == "review":
            # Revisión básica del código
            lines = content.splitlines()
            comments = sum(1 for l in lines if l.strip().startswith(('#', '//', '/*')))
            blank = sum(1 for l in lines if not l.strip())
            
            return f"""
📋 REVISIÓN DE CÓDIGO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Archivo: {Path(file_path).name}
📊 Total líneas: {len(lines)}
💬 Comentarios: {comments}
⬜ Líneas vacías: {blank}
🔢 Código efectivo: {len(lines) - comments - blank}
"""
        
        elif action == "optimize":
            # Sugerencias básicas de optimización
            lines = content.splitlines()
            suggestions = []
            for i, line in enumerate(lines, 1):
                if len(line) > 100:
                    suggestions.append(f"Línea {i}: Demasiado larga ({len(line)} caracteres)")
                if 'import *' in line:
                    suggestions.append(f"Línea {i}: Evita 'import *' - importa solo lo necesario")
                if 'except:' in line and 'Exception' not in line:
                    suggestions.append(f"Línea {i}: Especifica el tipo de excepción")
            
            if suggestions:
                return f"💡 SUGERENCIAS DE OPTIMIZACIÓN:\n{'-' * 40}\n" + "\n".join(suggestions)
            else:
                return "✅ El código parece estar bien optimizado."
        
        else:
            return f"❌ Acción '{action}' no soportada para código."
            
    except Exception as e:
        return f"❌ Error procesando código: {e}"

# ─── FUNCIÓN PRINCIPAL ──────────────────────────────────────────────────────

def file_processor(parameters: dict, player=None, speak=None) -> str:
    """
    Procesador universal de archivos.
    
    Acciones por tipo:
    - Imagen: describe, ocr, resize, compress, convert, info
    - PDF: summarize, extract_text, info
    - Word: summarize, extract_text, info
    - Excel/CSV: analyze, stats, filter, convert
    - Código: explain, review, optimize
    """
    
    file_path = parameters.get("file_path", "")
    action = parameters.get("action", "info").lower().strip()
    
    if not file_path:
        return "❌ Se requiere 'file_path' (ruta del archivo)"
    
    file_path = Path(file_path)
    if not file_path.exists():
        return f"❌ Archivo no encontrado: {file_path}"
    
    # Obtener extensión
    ext = file_path.suffix.lower().lstrip('.')
    
    if player: player.write_log(f"📂 Procesando: {file_path.name} ({action})")
    
    # ─── MAPEO POR TIPO DE ARCHIVO ─────────────────────────────────────────
    
    # Imágenes
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff']:
        return _process_image(str(file_path), action, parameters)
    
    # PDF
    elif ext == 'pdf':
        return _process_pdf(str(file_path), action, parameters)
    
    # Word
    elif ext in ['docx', 'doc']:
        return _process_docx(str(file_path), action, parameters)
    
    # Excel / CSV
    elif ext in ['xlsx', 'xls', 'csv']:
        return _process_excel(str(file_path), action, parameters)
    
    # Código
    elif ext in ['py', 'js', 'ts', 'html', 'css', 'cpp', 'c', 'java', 'rs', 'go', 'rb']:
        return _process_code(str(file_path), action, parameters)
    
    # JSON / XML
    elif ext in ['json', 'xml']:
        try:
            content = file_path.read_text(encoding="utf-8")
            if action == "format":
                if ext == 'json':
                    data = json.loads(content)
                    return f"📄 JSON FORMATTEADO:\n{'-' * 40}\n{json.dumps(data, indent=2)}"
                else:
                    return f"📄 XML:\n{'-' * 40}\n{content[:2000]}"
            else:
                return f"📄 CONTENIDO:\n{'-' * 40}\n{content[:2000]}"
        except Exception as e:
            return f"❌ Error: {e}"
    
    # Audio
    elif ext in ['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a']:
        try:
            import wave
            with wave.open(str(file_path), 'rb') as w:
                info = f"""
🎵 INFORMACIÓN DE AUDIO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Archivo: {file_path.name}
📊 Canales: {w.getnchannels()}
🎚️ Frecuencia: {w.getframerate()} Hz
📏 Tamaño: {w.getnframes()} frames
💾 Duración: {w.getnframes() / w.getframerate():.1f}s
"""
                return info
        except:
            return f"🎵 Archivo de audio: {file_path.name}\n💾 Tamaño: {file_path.stat().st_size / 1024:.1f} KB"
    
    # Video
    elif ext in ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv']:
        if cv2 is None:
            return "❌ OpenCV no está instalado."
        
        try:
            cap = cv2.VideoCapture(str(file_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            
            return f"""
🎬 INFORMACIÓN DE VIDEO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Archivo: {file_path.name}
📐 Resolución: {width} x {height}
🎞️ FPS: {fps:.1f}
📏 Frames: {frames:,}
⏱️ Duración: {frames / fps:.1f}s
💾 Tamaño: {file_path.stat().st_size / 1024 / 1024:.1f} MB
"""
        except Exception as e:
            return f"❌ Error procesando video: {e}"
    
    # ZIP / Archivos comprimidos
    elif ext in ['zip', 'rar', '7z', 'tar', 'gz']:
        try:
            import zipfile
            if ext == 'zip':
                with zipfile.ZipFile(file_path, 'r') as z:
                    files = z.namelist()
                    return f"""
📦 CONTENIDO DEL ZIP:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Archivo: {file_path.name}
📂 Archivos dentro: {len(files)}
📋 Lista: {', '.join(files[:10])}{'...' if len(files) > 10 else ''}
"""
        except:
            return f"📦 Archivo comprimido: {file_path.name}\n💾 Tamaño: {file_path.stat().st_size / 1024:.1f} KB"
    
    # Texto plano
    elif ext in ['txt', 'log', 'md']:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            return f"📄 CONTENIDO:\n{'-' * 40}\n{content[:3000]}{'... (truncado)' if len(content) > 3000 else ''}"
        except:
            return "❌ Error leyendo archivo de texto."
    
    # Otros
    else:
        return f"""
📂 INFORMACIÓN DEL ARCHIVO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Archivo: {file_path.name}
📂 Ruta: {file_path.parent}
📏 Extensión: {ext}
💾 Tamaño: {file_path.stat().st_size / 1024:.1f} KB

❌ Tipo de archivo no soportado para procesamiento avanzado.
   Acciones disponibles: info (por defecto)
"""
