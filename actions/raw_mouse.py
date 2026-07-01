import ctypes
from ctypes import wintypes
import threading
import win32gui
import win32con

RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
WM_INPUT = 0x00FF

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]

class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("ulButtons", wintypes.ULONG),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]

class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", RAWMOUSE)
    ]

class RawMouseCapture:
    def __init__(self):
        self.running = False
        self.dx = 0
        self.dy = 0
        self.lock = threading.Lock()
        self.thread = None

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            size = wintypes.UINT(0)
            ctypes.windll.user32.GetRawInputData(
                ctypes.cast(lparam, wintypes.HANDLE),
                RID_INPUT,
                None,
                ctypes.byref(size),
                ctypes.sizeof(RAWINPUTHEADER)
            )
            if size.value > 0:
                raw = RAWINPUT()
                ctypes.windll.user32.GetRawInputData(
                    ctypes.cast(lparam, wintypes.HANDLE),
                    RID_INPUT,
                    ctypes.byref(raw),
                    ctypes.byref(size),
                    ctypes.sizeof(RAWINPUTHEADER)
                )
                if raw.header.dwType == RIM_TYPEMOUSE:
                    if raw.data.usFlags & 0x01 == 0: # Relative movement only
                        with self.lock:
                            self.dx += raw.data.lLastX
                            self.dy += raw.data.lLastY
            return 0
        elif msg == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _message_loop(self):
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = f"RawMouseCaptureWindow_{id(self)}"
        wc.hInstance = win32gui.GetModuleHandle(None)

        win32gui.RegisterClass(wc)

        self.hwnd = win32gui.CreateWindow(
            wc.lpszClassName, "RawMouseCapture", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None
        )

        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01
        rid.usUsage = 0x02
        rid.dwFlags = RIDEV_INPUTSINK
        rid.hwndTarget = self.hwnd

        ctypes.windll.user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))

        win32gui.PumpMessages()
        
        try:
            win32gui.UnregisterClass(wc.lpszClassName, wc.hInstance)
        except:
            pass

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._message_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if hasattr(self, 'hwnd'):
            win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)

    def get_and_reset_deltas(self):
        with self.lock:
            dx, dy = self.dx, self.dy
            self.dx, self.dy = 0, 0
            return dx, dy
