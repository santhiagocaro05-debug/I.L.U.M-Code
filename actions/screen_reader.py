"""
screen_reader.py — Lector de pantalla con OCR para accesibilidad
Soporta: lectura de pantalla, selección, elementos específicos
"""

import time
import os
from pathlib import Path

try:
    import pyautogui
    import cv2
    import numpy as np
    from PIL import ImageGrab, Image
    import pytesseract
except ImportError:
    pyautogui = None
    cv2 = None
    np = None
    ImageGrab = None
    Image = None
    pytesseract = None

# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
# Configurar ruta de Tesseract si está instalado en una ubicación personalizada
TESSERACT_PATHS = [
    "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    "C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
]

def _setup_tesseract():
    """Configura la ruta de Tesseract."""
    if pytesseract is None:
        return False
    
    for path in TESSERACT_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True
    
    # Intentar encontrar en PATH
    try:
        import subprocess
        result = subprocess.run(["where", "tesseract"], capture_output=True, text=True)
        if result.returncode == 0:
            path = result.stdout.strip().split("\n")[0]
            pytesseract.pytesseract.tesseract_cmd = path
            return True
    except:
        pass
    
    return False

# ─── FUNCIONES PRINCIPALES ─────────────────────────────────────────────────

def _capture_screen(region: tuple = None) -> Image.Image:
    """Captura la pantalla o una región específica."""
    if ImageGrab is None:
        return None
    
    if region:
        return ImageGrab.grab(bbox=region)
    return ImageGrab.grab()

def _ocr_image(image: Image.Image, lang: str = "spa") -> str:
    """Extrae texto de una imagen usando OCR."""
    if pytesseract is None or image is None:
        return ""
    
    try:
        # Convertir a escala de grises para mejor OCR
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Aplicar preprocesamiento
        img = np.array(image)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Aumentar contraste
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
        
        # Aplicar threshold adaptativo
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY, 11, 2)
        
        # OCR
        text = pytesseract.image_to_string(gray, lang=lang)
        return text.strip()
        
    except Exception as e:
        print(f"[ScreenReader] Error: {e}")
        return ""

def _find_text_on_screen(text: str, confidence: float = 0.7) -> tuple:
    """
    Busca texto en la pantalla y devuelve su posición.
    """
    try:
        # Capturar pantalla
        screenshot = _capture_screen()
        if screenshot is None:
            return None
        
        # Buscar texto con OCR
        screen_text = _ocr_image(screenshot)
        
        # Buscar coincidencia
        if text.lower() in screen_text.lower():
            # Estimar posición (aproximada)
            lines = screen_text.lower().split('\n')
            for i, line in enumerate(lines):
                if text.lower() in line:
                    # Calcular posición aproximada
                    y_pos = int(i * 20 + 100)
                    x_pos = len(line[:line.find(text.lower())]) * 10
                    return (x_pos, y_pos)
        
        return None
        
    except Exception as e:
        print(f"[ScreenReader] Error buscando texto: {e}")
        return None

# ─── FUNCIÓN PRINCIPAL ──────────────────────────────────────────────────────

def screen_reader(parameters: dict, player=None) -> str:
    """
    Lector de pantalla con OCR.
    
    Acciones:
    - read: Lee TODO el texto visible en la pantalla
    - read_selection: Lee el texto seleccionado
    - read_element: Lee un elemento específico (por descripción)
    - find_text: Busca y resalta texto en la pantalla
    - status: Estado del lector de pantalla
    """
    
    # Verificar dependencias
    if pyautogui is None:
        return "❌ Error: PyAutoGUI no está instalado."
    if cv2 is None:
        return "❌ Error: OpenCV no está instalado."
    if pytesseract is None:
        return "❌ Error: Tesseract no está instalado."
    
    action = parameters.get("action", "").lower().strip()
    text = parameters.get("text", "")
    lang = parameters.get("language", "spa")  # spa, eng, etc.
    element_desc = parameters.get("element", "")
    
    # Configurar Tesseract
    if not _setup_tesseract():
        return "❌ Error: No se encontró Tesseract OCR. Instala Tesseract-OCR desde https://github.com/tesseract-ocr/tesseract"
    
    # ─── MAPEO DE ACCIONES ──────────────────────────────────────────────────
    
    # 1. LEER PANTALLA COMPLETA
    if action == "read" or action == "read_screen":
        if player: player.write_log("📖 Leyendo pantalla...")
        
        screenshot = _capture_screen()
        if screenshot is None:
            return "❌ Error capturando pantalla."
        
        text = _ocr_image(screenshot, lang)
        
        if text:
            # Limitar a 2000 caracteres para no sobrecargar
            if len(text) > 2000:
                text = text[:2000] + "... (texto truncado)"
            
            # Dividir en líneas para mejor presentación
            lines = text.split('\n')
            formatted = "\n".join([f"  {line}" for line in lines if line.strip()])
            
            return f"📖 Texto detectado en pantalla:\n{'-' * 40}\n{formatted}\n{'-' * 40}"
        else:
            return "📖 No se detectó texto en la pantalla."
    
    # 2. LEER TEXTO SELECCIONADO
    elif action == "read_selection":
        if player: player.write_log("📖 Leyendo selección...")
        
        try:
            # Usar pyautogui para obtener texto seleccionado
            # (esto es aproximado, depende del sistema operativo)
            import subprocess
            if os.name == 'nt':  # Windows
                result = subprocess.run(
                    ["powershell", "-Command", "Get-Clipboard"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    return f"📖 Texto seleccionado:\n{'-' * 40}\n{result.stdout.strip()}"
        except:
            pass
        
        return "⚠️ No se pudo leer la selección. Asegúrate de tener texto seleccionado."
    
    # 3. LEER ELEMENTO ESPECÍFICO
    elif action == "read_element":
        if not element_desc:
            return "❌ Se requiere 'element' para leer un elemento específico."
        
        if player: player.write_log(f"🔍 Buscando elemento: {element_desc}...")
        
        # Buscar texto en la pantalla
        position = _find_text_on_screen(element_desc)
        
        if position:
            return f"📖 Elemento '{element_desc}' encontrado en posición {position}."
        else:
            return f"⚠️ No se encontró el elemento '{element_desc}' en la pantalla."
    
    # 4. ENCONTRAR TEXTO
    elif action == "find_text":
        if not text:
            return "❌ Se requiere 'text' para buscar."
        
        if player: player.write_log(f"🔍 Buscando '{text}' en la pantalla...")
        
        position = _find_text_on_screen(text)
        
        if position:
            return f"✅ Texto '{text}' encontrado en posición {position}."
        else:
            return f"⚠️ Texto '{text}' no encontrado en la pantalla."
    
    # 5. STATUS
    elif action == "status":
        tesseract_ok = _setup_tesseract()
        
        return f"""
📊 ESTADO DEL LECTOR DE PANTALLA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Tesseract: {'✅ OK' if tesseract_ok else '❌ No instalado'}
📷 PyAutoGUI: {'✅ OK' if pyautogui else '❌ No instalado'}
🖼️ OpenCV: {'✅ OK' if cv2 else '❌ No instalado'}
🌐 Idioma OCR: {lang}

📋 Acciones disponibles:
  • read → Leer toda la pantalla
  • read_selection → Leer texto seleccionado
  • read_element → Leer elemento específico
  • find_text → Buscar texto en pantalla
  • status → Estado actual

📝 Ejemplos:
  {"action": "read"}
  {"action": "read_selection"}
  {"action": "read_element", "element": "botón de enviar"}
  {"action": "find_text", "text": "Bienvenido"}
"""
    
    # 6. HELP
    else:
        return """
🎯 SCREEN READER - Comandos:

📖 Lectura:
  • read → Lee toda la pantalla
  • read_selection → Lee texto seleccionado
  • read_element → Lee elemento específico

🔍 Búsqueda:
  • find_text → Busca texto en pantalla

📋 Gestión:
  • status → Estado del sistema

📝 Ejemplos:
  {"action": "read"}
  {"action": "read_element", "element": "botón de enviar"}
  {"action": "find_text", "text": "archivo.pdf"}

🔧 REQUISITOS:
  • Tesseract-OCR instalado
  • OpenCV (pip install opencv-python)
  • PIL (pip install pillow)
"""
