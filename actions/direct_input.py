# -*- coding: utf-8 -*-
"""
direct_input.py — Low-level DirectInput keyboard scan-code sender for DirectX/OpenGL video games (e.g. Minecraft).
"""
import ctypes
import time

SendInput = ctypes.windll.user32.SendInput

# Structure definitions for User32 SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Mouse Event Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

# Hex DirectInput scan codes mapping
SCAN_CODES = {
    # Basic keyboard letters (DirectInput Scan Codes)
    "w": 0x11, "a": 0x1E, "s": 0x1F, "d": 0x20,
    "q": 0x10, "e": 0x12, "r": 0x13, "t": 0x14, "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "f": 0x21, "g": 0x22, "h": 0x23, "j": 0x24, "k": 0x25, "l": 0x26,
    "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30, "n": 0x31, "m": 0x32,
    
    # Numbers
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    
    # Common UI/Control Keys
    "space": 0x39, "espacio": 0x39, "enter": 0x1C, "intro": 0x1C, "escape": 0x01, "esc": 0x01, "backspace": 0x0E, "borrar": 0x0E, "tab": 0x0F,
    "shift": 0x2A, "mayus": 0x2A, "lshift": 0x2A, "rshift": 0x36,
    "ctrl": 0x1D, "control": 0x1D, "lctrl": 0x1D, "rctrl": 0x9D,
    "alt": 0x38, "lalt": 0x38, "ralt": 0xB8,
    "win": 0x5B, "windows": 0x5B,
    
    # Extended keys
    "up": 0xC8, "arriba": 0xC8, "left": 0xCB, "izquierda": 0xCB, "right": 0xCD, "derecha": 0xCD, "down": 0xD0, "abajo": 0xD0
}

def press_key_raw(scan_code):
    """Press a key using scan code (KEYEVENTF_SCANCODE = 0x0008)"""
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, scan_code, 0x0008, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def release_key_raw(scan_code):
    """Release a key (KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP = 0x0008 | 0x0002 = 0x000A)"""
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, scan_code, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def press_key(key_name: str, duration: float = 0.1) -> bool:
    """Safely press and release a key by scan code mapping."""
    key_name = key_name.lower().strip()
    if key_name in SCAN_CODES:
        code = SCAN_CODES[key_name]
        press_key_raw(code)
        time.sleep(duration)
        release_key_raw(code)
        return True
    return False

def press_key_only(key_name: str) -> bool:
    """Press a key down without releasing it."""
    key_name = key_name.lower().strip()
    if key_name in SCAN_CODES:
        press_key_raw(SCAN_CODES[key_name])
        return True
    return False

def release_key(key_name: str) -> bool:
    """Release a key that is held down."""
    key_name = key_name.lower().strip()
    if key_name in SCAN_CODES:
        release_key_raw(SCAN_CODES[key_name])
        return True
    return False

def hold_key(key_name: str, duration: float) -> bool:
    """Hold a key (or combination) down for a specified amount of seconds, simulating hardware auto-repeat."""
    keys = [k.lower().strip() for k in key_name.replace(",", "+").split("+") if k.strip()]
    codes = []
    for k in keys:
        if k in SCAN_CODES:
            codes.append(SCAN_CODES[k])
        else:
            return False
            
    start_t = time.time()
    
    # Initial press all
    for code in codes:
        press_key_raw(code)
        
    last_code = codes[-1]
    
    elapsed = time.time() - start_t
    wait_time = duration - elapsed
    if wait_time > 0:
        time.sleep(wait_time)
            
    # Release in reverse order
    for code in reversed(codes):
        release_key_raw(code)
        
    return True

def press_hotkey(keys_list: list, duration: float = 0.1) -> bool:
    """Press and release a combination of keys in sequence (DirectInput)."""
    codes = []
    for k in keys_list:
        k = k.lower().strip()
        if k in SCAN_CODES:
            codes.append(SCAN_CODES[k])
        else:
            return False  # Fallback if any key is not in scan codes
            
    # Press all in sequence
    for code in codes:
        press_key_raw(code)
        time.sleep(0.01)
        
    time.sleep(duration)
    
    for code in reversed(codes):
        release_key_raw(code)
        time.sleep(0.01)
        
    return True

def _get_mouse_flags(button, is_down):
    button = str(button).lower().strip()
    if button in ["left", "1", "izquierdo", "izq"]:
        return MOUSEEVENTF_LEFTDOWN if is_down else MOUSEEVENTF_LEFTUP
    elif button in ["right", "3", "derecho", "der"]:
        return MOUSEEVENTF_RIGHTDOWN if is_down else MOUSEEVENTF_RIGHTUP
    elif button in ["middle", "2", "medio", "rueda"]:
        return MOUSEEVENTF_MIDDLEDOWN if is_down else MOUSEEVENTF_MIDDLEUP
    return 0

def mouse_down_raw(button="left"):
    flags = _get_mouse_flags(button, is_down=True)
    if not flags: return
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, 0, flags, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(0), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def mouse_up_raw(button="left"):
    flags = _get_mouse_flags(button, is_down=False)
    if not flags: return
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, 0, flags, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(0), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def mouse_click(button="left", duration=0.05):
    mouse_down_raw(button)
    time.sleep(duration)
    mouse_up_raw(button)

def mouse_move_raw(dx, dy):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(dx, dy, 0, MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(0), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def mouse_wheel_raw(delta):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    # Mouse data for wheel requires the delta to be in the mouseData field
    ii_.mi = MouseInput(0, 0, ctypes.c_ulong(delta), MOUSEEVENTF_WHEEL, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(0), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

