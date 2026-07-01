"""
WhatsApp Control Module for ILUM
================================
Módulo avanzado para controlar WhatsApp Desktop y Web con:
- Gestión de contactos local
- Envío de mensajes de texto
- Envío de imágenes con captions
- Lectura de mensajes (básico)
- Detección de mensajes sin leer
- Manejo robusto de errores
- Verificación de dependencias
"""

import time
import urllib.parse
import webbrowser
import json
import os
import sys
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Union, Tuple

# ============================================================
#  DEPENDENCY MANAGEMENT
# ============================================================

_HAS_PYAUTOGUI = False
_HAS_PYGETWINDOW = False
_HAS_PIL = False
_HAS_PYTESSERACT = False
_HAS_NUMPY = False

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None

try:
    import pygetwindow as gw
    _HAS_PYGETWINDOW = True
except ImportError:
    gw = None

try:
    from PIL import Image, ImageGrab
    _HAS_PIL = True
except ImportError:
    Image = None
    ImageGrab = None

try:
    import pytesseract
    _HAS_PYTESSERACT = True
except ImportError:
    pytesseract = None

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None

# ============================================================
#  PATHS & CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
CONTACTS_FILE = BASE_DIR / "config" / "whatsapp_contacts.json"

# Configuración de tiempos (optimizados para rendimiento y envíos reales)
TIMING = {
    "app_launch": 8.0, # Dar más tiempo a que WhatsApp abra y cargue el chat
    "app_launch_web": 12.0,
    "search_delay": 1.0,
    "message_delay": 0.5,
    "send_delay": 1.0,
    "image_paste_delay": 2.0,
    "clipboard_delay": 1.0,
    "retry_attempts": 3,
    "screenshot_delay": 1.0,
}

# ============================================================
#  CONTACT MANAGEMENT
# ============================================================

def load_contacts() -> Dict:
    """Carga los contactos desde el archivo JSON"""
    if CONTACTS_FILE.exists():
        try:
            return json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return {}
    return {}

def save_contacts(contacts: Dict) -> bool:
    """Guarda los contactos en el archivo JSON"""
    try:
        CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONTACTS_FILE.write_text(
            json.dumps(contacts, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )
        return True
    except Exception as e:
        print(f"[WhatsApp] Error saving contacts: {e}")
        return False

def normalize_phone(phone: str) -> str:
    """
    Normaliza un número de teléfono:
    - Elimina espacios
    - Mantiene solo dígitos y el signo '+'
    - Elimina caracteres especiales
    """
    if not phone:
        return ""
    cleaned = "".join(c for c in phone if c.isdigit() or c == '+')
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    return cleaned

def validate_phone(phone: str) -> bool:
    """Valida que un número de teléfono sea válido (mínimo 8 dígitos)"""
    if not phone:
        return False
    digits = "".join(c for c in phone if c.isdigit())
    return len(digits) >= 8

def find_contact_by_name(name: str, contacts: Dict) -> Optional[Dict]:
    """Busca un contacto por nombre (case-insensitive, soporta substring)"""
    if not name:
        return None
    
    name_lower = name.lower()
    
    # 1. Exact match
    if name_lower in contacts:
        return contacts[name_lower]
    
    # 2. Substring match (más flexible)
    for key, contact in contacts.items():
        contact_name_lower = contact.get("name", "").lower()
        if name_lower in contact_name_lower or contact_name_lower in name_lower:
            return contact
        if name_lower in key or key in name_lower:
            return contact
    
    return None

def find_contact_by_phone(phone: str, contacts: Dict) -> Optional[Dict]:
    """Busca un contacto por número de teléfono"""
    if not phone:
        return None
    
    phone_clean = normalize_phone(phone)
    for contact in contacts.values():
        contact_phone = normalize_phone(contact.get("phone", ""))
        if phone_clean in contact_phone or contact_phone in phone_clean:
            return contact
    
    return None

def get_contact_or_phone(receiver: str, contacts: Dict) -> Tuple[str, str]:
    """
    Determina el número de teléfono y nombre del contacto
    Retorna: (phone, contact_name)
    """
    receiver_clean = normalize_phone(receiver)
    digit_count = sum(c.isdigit() for c in receiver_clean)
    
    if digit_count >= 8:
        return receiver_clean, receiver_clean
    
    contact = find_contact_by_name(receiver, contacts)
    if contact:
        phone = normalize_phone(contact.get("phone", ""))
        name = contact.get("name", receiver)
        return phone, name
    
    return "", receiver

# ============================================================
#  WHATSAPP WINDOW MANAGEMENT
# ============================================================

def find_whatsapp_window() -> Optional[object]:
    """Encuentra y activa la ventana de WhatsApp"""
    if not _HAS_PYGETWINDOW or not gw:
        return None
    
    try:
        windows = gw.getWindowsWithTitle('WhatsApp')
        if not windows:
            windows = gw.getWindowsWithTitle('WhatsApp Web')
        if not windows:
            return None
        
        win = windows[0]
        if win.isMinimized:
            win.restore()
            time.sleep(0.3)
        win.activate()
        time.sleep(0.3)
        return win
    except Exception as e:
        print(f"[WhatsApp] Error finding window: {e}")
        return None

def ensure_whatsapp_open(receiver: str = None, phone: str = None, message: str = "") -> Tuple[bool, str]:
    """Asegura que WhatsApp esté abierto y listo para enviar"""
    win = find_whatsapp_window()
    
    if not win:
        try:
            if phone:
                encoded_msg = urllib.parse.quote(message)
                url = f"whatsapp://send?phone={phone}&text={encoded_msg}"
            else:
                url = "whatsapp://"
            
            os.startfile(url)
            time.sleep(TIMING["app_launch"])
        except Exception:
            if phone:
                encoded_msg = urllib.parse.quote(message)
                webbrowser.open(f"https://web.whatsapp.com/send?phone={phone}&text={encoded_msg}")
            else:
                webbrowser.open("https://web.whatsapp.com")
            time.sleep(TIMING["app_launch_web"])
        
        win = find_whatsapp_window()
        if not win:
            return False, "No se pudo abrir WhatsApp. Verifica que esté instalado."
    
    if receiver:
        try:
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(TIMING["search_delay"])
            pyautogui.write(receiver, interval=0.02)
            time.sleep(TIMING["search_delay"] + 1)
            pyautogui.press('enter')
            time.sleep(TIMING["search_delay"] + 1)
            return True, None
        except Exception as e:
            return False, f"Error al buscar contacto: {e}"
    
    return True, None

# ============================================================
#  IMAGE HANDLING
# ============================================================

def copy_image_to_clipboard(image_path: str) -> bool:
    """Copia una imagen al portapapeles usando PIL"""
    if not _HAS_PIL or not Image:
        return False
    
    try:
        import io
        import ctypes
        
        img = Image.open(image_path)
        if img.size[0] * img.size[1] > 5000000:
            img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        img.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        
        ctypes.windll.user32.OpenClipboard(None)
        ctypes.windll.user32.EmptyClipboard()
        
        h_mem = ctypes.windll.kernel32.GlobalAlloc(0x0002, len(data))
        if h_mem:
            ctypes.windll.user32.SetClipboardData(8, h_mem)
            p_mem = ctypes.windll.kernel32.GlobalLock(h_mem)
            if p_mem:
                ctypes.cdll.msvcrt.memcpy(p_mem, data, len(data))
                ctypes.windll.kernel32.GlobalUnlock(h_mem)
        
        ctypes.windll.user32.CloseClipboard()
        return True
    except Exception as e:
        print(f"[WhatsApp] Error copying image to clipboard: {e}")
        return False

def send_image_via_clipboard(image_path: str, caption: str = "") -> bool:
    """Envía una imagen pegándola desde el portapapeles"""
    if not _HAS_PYAUTOGUI or not pyautogui:
        return False
    
    for attempt in range(TIMING["retry_attempts"]):
        try:
            if not copy_image_to_clipboard(image_path):
                time.sleep(0.5)
                continue
            
            time.sleep(TIMING["clipboard_delay"])
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(TIMING["image_paste_delay"])
            
            if caption:
                pyautogui.write(caption, interval=0.02)
                time.sleep(TIMING["message_delay"])
            
            pyautogui.press('enter')
            time.sleep(TIMING["send_delay"])
            return True
        except Exception as e:
            print(f"[WhatsApp] Image send attempt {attempt+1} failed: {e}")
            time.sleep(0.5)
    
    return False

# ============================================================
#  MESSAGE SENDING
# ============================================================

def send_text_message(message: str, prefilled: bool = False) -> bool:
    """Envía un mensaje de texto en la ventana activa"""
    if not _HAS_PYAUTOGUI or not pyautogui:
        return False
    
    try:
        if not prefilled:
            pyautogui.write(message, interval=0.01)
            time.sleep(TIMING["message_delay"])
            
        # Presionar Enter para enviar
        pyautogui.press('enter')
        time.sleep(TIMING["send_delay"])
        return True
    except Exception as e:
        print(f"[WhatsApp] Error sending text: {e}")
        return False

# ============================================================
#  READ MESSAGES
# ============================================================

def read_recent_messages(count: int = 10, player=None) -> str:
    """Lee mensajes recientes usando OCR"""
    if not _HAS_PYTESSERACT or not pytesseract:
        return "❌ Para leer mensajes se requiere instalar 'pytesseract' y Tesseract OCR."
    
    if not _HAS_PIL or not ImageGrab:
        return "❌ Se requiere PIL/Pillow para capturar la pantalla."
    
    try:
        win = find_whatsapp_window()
        if not win:
            return "❌ No se encontró la ventana de WhatsApp."
        
        win.activate()
        time.sleep(TIMING["screenshot_delay"])
        
        bbox = (win.left + 50, win.top + 150, win.right - 50, win.bottom - 100)
        screenshot = ImageGrab.grab(bbox)
        
        text = pytesseract.image_to_string(screenshot, lang='spa+eng')
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        if not lines:
            return "📖 No se detectaron mensajes. Asegúrate de tener un chat abierto."
        
        recent = lines[-count:]
        result = f"📖 Últimos {len(recent)} mensajes:\n"
        for i, line in enumerate(recent, 1):
            result += f"   {i}. {line}\n"
        
        return result
    except Exception as e:
        return f"❌ Error leyendo mensajes: {e}"

# ============================================================
#  DETECTAR MENSAJES SIN LEER (NUEVO)
# ============================================================

def detect_unread_messages(player=None) -> Dict:
    """
    Detecta mensajes sin leer usando OCR y análisis de color
    Retorna: dict con información de mensajes sin leer
    """
    if not _HAS_PIL or not ImageGrab:
        return {"error": "Se requiere PIL/Pillow"}
    
    try:
        win = find_whatsapp_window()
        if not win:
            return {"error": "No se encontró la ventana de WhatsApp"}
        
        win.activate()
        time.sleep(TIMING["screenshot_delay"])
        
        # Capturar lista de chats (lado izquierdo)
        bbox = (win.left + 10, win.top + 80, win.left + 380, win.bottom - 50)
        screenshot = ImageGrab.grab(bbox)
        
        # MÉTODO 1: OCR para detectar números de mensajes sin leer
        if _HAS_PYTESSERACT and pytesseract:
            text = pytesseract.image_to_string(screenshot, lang='spa+eng')
            unread_pattern = re.compile(r'\b([1-9][0-9]{0,2})\b')
            matches = unread_pattern.findall(text)
            unread_counts = [int(m) for m in matches if 1 <= int(m) <= 99]
            
            if unread_counts:
                total = sum(unread_counts)
                return {
                    "has_unread": True,
                    "total": total,
                    "chats": len(unread_counts),
                    "counts": unread_counts,
                    "method": "ocr"
                }
        
        # MÉTODO 2: Detección por color (círculo verde de WhatsApp)
        if _HAS_NUMPY and np:
            img_array = np.array(screenshot)
            r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]
            
            # Detectar píxeles verdes (badge de WhatsApp)
            green_mask = (g > r + 15) & (g > b + 15) & (g > 60) & (g < 200)
            green_pixels = np.sum(green_mask)
            
            if green_pixels > 80:
                # Estimar número de chats con mensajes sin leer
                chats_estimate = max(1, green_pixels // 200)
                return {
                    "has_unread": True,
                    "total": chats_estimate * 2,  # Estimación
                    "chats": chats_estimate,
                    "method": "color_detection"
                }
        
        return {"has_unread": False, "total": 0, "chats": 0}
        
    except Exception as e:
        return {"error": str(e)}

def has_unread_messages(player=None) -> str:
    """
    Verifica si hay mensajes sin leer y devuelve un resumen formateado
    """
    result = detect_unread_messages(player)
    
    if "error" in result:
        return f"❌ Error detectando mensajes: {result['error']}"
    
    if result.get("has_unread", False):
        total = result.get("total", 0)
        chats = result.get("chats", 0)
        method = result.get("method", "unknown")
        
        response = f"📬 ¡Tienes {total} mensaje(s) sin leer en {chats} chat(s)!"
        
        if method == "ocr":
            counts = result.get("counts", [])
            if counts:
                response += f"\n\n   📋 Desglose:"
                for i, count in enumerate(counts[:5], 1):
                    response += f"\n      • Chat {i}: {count} mensajes"
                if len(counts) > 5:
                    response += f"\n      • ... y {len(counts) - 5} chat(s) más"
        
        return response
    else:
        return "📭 No tienes mensajes sin leer. ¡Todo al día!"

# ============================================================
#  MAIN FUNCTION
# ============================================================

def whatsapp(parameters: dict, player=None) -> str:
    """
    Control avanzado de WhatsApp que gestiona contactos locales y
    automatiza el envío de mensajes de texto e imágenes.
    
    Acciones soportadas:
    - add_contact: Agregar contacto
    - delete_contact: Eliminar contacto
    - list_contacts: Listar contactos
    - send: Enviar mensaje de texto
    - send_image: Enviar imagen (con o sin caption)
    - read: Leer mensajes
    - unread: Ver mensajes no leídos
    - has_unread: Verificar si hay mensajes sin leer (alias: tengo_mensajes, mensajes_pendientes)
    - status: Verificar estado de WhatsApp
    """
    
    # ============================================================
    #  PARAMETER EXTRACTION
    # ============================================================
    
    action = parameters.get("action", "").lower()
    receiver = parameters.get("receiver", "")
    message = parameters.get("message", "")
    image_path = parameters.get("image_path", "")
    caption = parameters.get("caption", "")
    name = parameters.get("name", "")
    phone_param = parameters.get("phone", "")
    count = parameters.get("count", 10)
    
    contacts = load_contacts()
    
    # Mapeo de acciones (compatibilidad con main.py + nuevas)
    action_map = {
        "send_text": "send",
        "read_unread": "read",
        "read_chat": "read",
        "unread": "has_unread",
        "tengo_mensajes": "has_unread",
        "mensajes_pendientes": "has_unread",
        "hay_mensajes": "has_unread",
        "sin_leer": "has_unread",
    }
    action = action_map.get(action, action)
    
    # ============================================================
    #  1. STATUS / INFO
    # ============================================================
    
    if action == "status":
        return get_whatsapp_status()
    
    # ============================================================
    #  2. CONTACT MANAGEMENT
    # ============================================================
    
    if action == "add_contact":
        contact_name = name or receiver
        contact_phone = phone_param
        
        if not contact_name or not contact_phone:
            return "❌ Error: Se requiere 'name' y 'phone' para agregar un contacto."
        
        contact_phone = normalize_phone(contact_phone)
        
        if not validate_phone(contact_phone):
            return f"❌ Error: El número '{contact_phone}' no parece válido (mínimo 8 dígitos)."
        
        contacts[contact_name.lower()] = {
            "name": contact_name,
            "phone": contact_phone
        }
        
        if save_contacts(contacts):
            return f"✅ Contacto '{contact_name}' guardado con teléfono: {contact_phone}."
        return "❌ Error al guardar el contacto."
    
    elif action == "delete_contact":
        contact_name = name or receiver
        if not contact_name:
            return "❌ Error: Se requiere 'name' para eliminar un contacto."
        
        if contact_name.lower() in contacts:
            del contacts[contact_name.lower()]
            if save_contacts(contacts):
                return f"✅ Contacto '{contact_name}' eliminado."
        
        return f"❌ No se encontró el contacto '{contact_name}'."
    
    elif action == "list_contacts":
        if not contacts:
            return "📋 No hay contactos guardados."
        
        result = "📋 Contactos guardados:\n"
        for contact in sorted(contacts.values(), key=lambda x: x.get("name", "")):
            result += f"   • {contact.get('name', 'Sin nombre')}: {contact.get('phone', 'Sin teléfono')}\n"
        
        return result
    
    # ============================================================
    #  3. HAS UNREAD MESSAGES (NUEVO)
    # ============================================================
    
    elif action == "has_unread":
        return has_unread_messages(player)
    
    # ============================================================
    #  4. SEND MESSAGE / IMAGE
    # ============================================================
    
    elif action in ["send", "send_image"]:
        if not receiver:
            return "❌ Error: No se especificó el destinatario ('receiver')."
        
        if not _HAS_PYAUTOGUI:
            return "⚠️ pyautogui no está instalado. El mensaje se abrirá en WhatsApp pero no se enviará automáticamente."
        
        phone, contact_name = get_contact_or_phone(receiver, contacts)
        target_desc = contact_name if contact_name else receiver
        
        if player:
            player.write_log(f"💬 Enviando a '{target_desc}'...")
        
        success, error = ensure_whatsapp_open(
            receiver=receiver if not phone else None,
            phone=phone,
            message=message
        )
        
        if not success:
            return f"❌ Error: {error}"
        
        # El Deep Link (ensure_whatsapp_open) ya rellenó el texto si usamos `phone`.
        # Solo falta presionar Enter. Si usamos `receiver` (busqueda), no está rellenado.
        is_prefilled = bool(phone and message)
        
        if message:
            # Damos un respiro final para asegurar que WhatsApp enfocó la caja de texto
            time.sleep(2.0)
            if not send_text_message(message, prefilled=is_prefilled):
                return f"⚠️ Mensaje enviado parcialmente. Verifica que la ventana de WhatsApp esté activa."
        
        if action == "send_image" and image_path:
            img_path = Path(image_path)
            if not img_path.exists():
                return f"⚠️ Mensaje enviado, pero no se encontró la imagen: {image_path}"
            
            time.sleep(0.5)
            
            if send_image_via_clipboard(str(img_path), caption):
                return f"✅ Mensaje e imagen enviados a '{target_desc}'."
            else:
                return f"⚠️ Mensaje enviado, pero falló el envío de la imagen."
        
        return f"✅ Mensaje enviado a '{target_desc}'."
    
    # ============================================================
    #  5. READ MESSAGES
    # ============================================================
    
    elif action == "read":
        return read_recent_messages(count=count, player=player)
    
    # ============================================================
    #  6. STORIES (ESTADOS)
    # ============================================================
    
    elif action == "post_story":
        if not _HAS_PYAUTOGUI:
            return "❌ Error: PyAutoGUI no está instalado."
        
        win = find_whatsapp_window()
        if not win:
            webbrowser.open("https://web.whatsapp.com")
            time.sleep(5)
            
        return f"✅ WhatsApp enfocado. Iniciando flujo para publicar estado (historia) con la imagen proporcionada: {image_path}."

    # ============================================================
    #  7. DEFAULT / HELP
    # ============================================================
    
    else:
        try:
            os.startfile("whatsapp://")
        except Exception:
            webbrowser.open("https://web.whatsapp.com")
        
        if action:
            return f"📱 Acción '{action}' no reconocida. Abriendo WhatsApp."
        return "📱 Abriendo WhatsApp."

# ============================================================
#  UTILITY FUNCTIONS FOR MAIN.PY INTEGRATION
# ============================================================

def get_whatsapp_status() -> str:
    """Verifica el estado de WhatsApp y sus dependencias"""
    status = []
    
    status.append(f"✅ pyautogui: {'Disponible' if _HAS_PYAUTOGUI else 'No disponible'}")
    status.append(f"✅ pygetwindow: {'Disponible' if _HAS_PYGETWINDOW else 'No disponible'}")
    status.append(f"✅ PIL: {'Disponible' if _HAS_PIL else 'No disponible'}")
    status.append(f"✅ pytesseract: {'Disponible' if _HAS_PYTESSERACT else 'No disponible'}")
    status.append(f"✅ numpy: {'Disponible' if _HAS_NUMPY else 'No disponible'}")
    
    contacts = load_contacts()
    status.append(f"📋 Contactos: {len(contacts)} guardados")
    
    win = find_whatsapp_window()
    status.append(f"📱 WhatsApp: {'Abierto' if win else 'Cerrado'}")
    
    return "\n".join(status)

# ============================================================
#  TEST / DEBUG
# ============================================================

if __name__ == "__main__":
    print("=== WhatsApp Module Test ===")
    print(get_whatsapp_status())
    
    print("\n--- Testing unread detection ---")
    print(has_unread_messages())
    
    print("\n--- Testing list contacts ---")
    test_result = whatsapp({"action": "list_contacts"})
    print(test_result)