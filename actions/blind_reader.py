"""
Blind Reader Module for ILUM
============================
Toma una captura de pantalla completa, usa OCR para extraer todo el texto visible 
y se lo devuelve a ILUM para que pueda leérselo en voz alta al usuario invidente.
"""

import time
try:
    from PIL import ImageGrab
    _HAS_PIL = True
except ImportError:
    ImageGrab = None

try:
    import pytesseract
    _HAS_PYTESSERACT = True
except ImportError:
    pytesseract = None

def blind_reader(parameters: dict, player=None) -> str:
    """
    Toma una captura de pantalla y lee el texto usando OCR.
    """
    if not _HAS_PIL or not ImageGrab:
        return "❌ Error: Se requiere PIL (Pillow) para capturar la pantalla."
        
    if not _HAS_PYTESSERACT or not pytesseract:
        return "❌ Error: Se requiere PyTesseract instalado en el sistema."

    if player: player.write_log("👁️‍🗨️ Lector OCR iniciado. Escaneando pantalla...")
    
    try:
        # Tomar captura de pantalla completa
        screenshot = ImageGrab.grab()
        
        # Extraer texto usando Tesseract
        text = pytesseract.image_to_string(screenshot, lang='spa+eng')
        
        clean_text = " ".join([line.strip() for line in text.split('\n') if line.strip()])
        
        if not clean_text:
            return "No hay ningún texto legible visible en la pantalla en este momento."
            
        # Limitar la longitud a unos 1500 caracteres para no saturar la voz
        if len(clean_text) > 1500:
            clean_text = clean_text[:1500] + "... [Fin del extracto]"
            
        return f"El texto que aparece en la pantalla es: {clean_text}"
        
    except Exception as e:
        return f"❌ Error al intentar leer la pantalla: {str(e)}"
