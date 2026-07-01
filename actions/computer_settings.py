"""computer_settings.py — Clean Win32/system settings controls."""
import os
import sys

def computer_settings(parameters: dict, response=None, player=None) -> str:
    """Adjust system settings like volume, brightness, or active window states."""
    action = parameters.get("action", "").lower()
    value = parameters.get("value", "")
    
    if action == "volume":
        try:
            import pyautogui
            if str(value).isdigit():
                target = int(value)
                try:
                    from ctypes import cast, POINTER
                    from comtypes import CoInitialize, CoUninitialize
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                    CoInitialize()
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, 1, None)
                    volume_ctrl = cast(interface, POINTER(IAudioEndpointVolume))
                    scalar_vol = max(0.0, min(1.0, target / 100.0))
                    volume_ctrl.SetMasterVolumeLevelScalar(scalar_vol, None)
                    CoUninitialize()
                    msg = f"Master volume adjusted to {target}%."
                except Exception as e:
                    msg = f"Could not set absolute volume: {e}"
            else:
                if "up" in value.lower() or "subir" in value.lower():
                    pyautogui.press("volumeup", presses=5)
                    msg = "Volume increased."
                elif "down" in value.lower() or "bajar" in value.lower():
                    pyautogui.press("volumedown", presses=5)
                    msg = "Volume decreased."
                elif "mute" in value.lower() or "silenciar" in value.lower():
                    pyautogui.press("volumemute")
                    msg = "Volume muted."
                else:
                    msg = f"Unrecognized volume value: {value}"
            if player:
                player.write_log(f"🔊 {msg}")
            return msg
        except Exception as e:
            return f"Failed to adjust volume: {e}"
            
    elif action in ("minimize", "window_minimize"):
        try:
            import pygetwindow as gw
            window = gw.getActiveWindow()
            if window:
                window.minimize()
                return "Active window minimized."
            return "No active window found."
        except Exception as e:
            return f"Failed to minimize window: {e}"

    elif action in ("maximize", "window_maximize"):
        try:
            import pygetwindow as gw
            window = gw.getActiveWindow()
            if window:
                window.maximize()
                return "Active window maximized."
            return "No active window found."
        except Exception as e:
            return f"Failed to maximize window: {e}"
            
    elif action == "recent_apps":
        try:
            import winreg
            from datetime import datetime, timedelta
            
            def get_installed_apps(hive, subkey):
                apps = []
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        for i in range(0, winreg.QueryInfoKey(key)[0]):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as app_key:
                                    try:
                                        name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                                        date_str = winreg.QueryValueEx(app_key, "InstallDate")[0]
                                        # InstallDate is usually YYYYMMDD
                                        if len(date_str) == 8:
                                            install_date = datetime.strptime(date_str, "%Y%m%d")
                                            apps.append({"name": name, "date": install_date})
                                    except OSError:
                                        pass
                            except OSError:
                                pass
                except OSError:
                    pass
                return apps

            all_apps = []
            paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
            ]
            
            for hive, path in paths:
                all_apps.extend(get_installed_apps(hive, path))
                
            # Filter last 30 days and sort
            recent_limit = datetime.now() - timedelta(days=30)
            recent_apps = [app for app in all_apps if app["date"] >= recent_limit]
            recent_apps.sort(key=lambda x: x["date"], reverse=True)
            
            if not recent_apps:
                return "No se encontraron programas instalados recientemente (últimos 30 días)."
                
            # Format output
            lines = ["Programas instalados recientemente:"]
            seen = set()
            for app in recent_apps:
                if app["name"] not in seen:
                    lines.append(f"- {app['name']} (Instalado: {app['date'].strftime('%Y-%m-%d')})")
                    seen.add(app["name"])
                    
            msg = "\n".join(lines[:15]) # Top 15
            if player: player.write_log("Búsqueda de programas recientes completada.")
            return msg
        except Exception as e:
            return f"Error al buscar programas recientes: {e}"

    return f"Settings action '{action}' is not supported yet, sir."
