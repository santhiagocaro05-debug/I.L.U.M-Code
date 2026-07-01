# -*- coding: utf-8 -*-
"""
close_app.py — Robust process manager and app closing tool for ILUM.
"""
import os
import psutil
import subprocess
import traceback

def close_app(parameters: dict, response=None, player=None) -> str:
    """Close a running local desktop application by matching its name to running processes."""
    app_name = parameters.get("app_name", "").strip()
    if not app_name:
        return "Error: Se requiere el parámetro 'app_name'."

    app_lower = app_name.lower().strip()
    
    # Static mappings for process names
    process_mappings = {
        "notepad": "notepad.exe",
        "bloc de notas": "notepad.exe",
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "calculator": "calc.exe",
        "calculadora": "CalculatorApp.exe",
        "paint": "mspaint.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "spotify": "spotify.exe",
        "discord": "discord.exe",
        "steam": "steam.exe",
        "minecraft": "javaw.exe"
    }
    
    target_process = process_mappings.get(app_lower, None)
    if not target_process:
        try:
            from actions.open_app import find_executable
            found_exe = find_executable(app_name)
            if found_exe:
                target_process = os.path.basename(found_exe)
        except Exception:
            pass
            
    killed = False
    error_list = []
    
    # Try finding process by matching name iteration
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pinfo = proc.info
            pname = pinfo['name'].lower()
            if target_process:
                if pname == target_process.lower() or pname == target_process.lower().replace(".exe", ""):
                    proc.kill()
                    killed = True
            else:
                if app_lower in pname or pname.startswith(app_lower) or pname.replace(".exe", "") == app_lower:
                    proc.kill()
                    killed = True
        except Exception as e:
            error_list.append(str(e))
            pass

    if killed:
        msg = f"Aplicación '{app_name}' cerrada correctamente."
        if player:
            player.write_log(f"🚀 {msg}")
        return msg
    else:
        # Fallback to taskkill /F /IM via command shell
        guess_exe = target_process or (app_name + ".exe" if not app_name.endswith(".exe") else app_name)
        try:
            res = subprocess.run(f'taskkill /F /IM "{guess_exe}"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                msg = f"Aplicación '{app_name}' cerrada forzadamente."
                if player:
                    player.write_log(f"🚀 {msg}")
                return msg
            
            # Second guess without .exe
            guess_no_exe = guess_exe.replace(".exe", "")
            res2 = subprocess.run(f'taskkill /F /IM "{guess_no_exe}"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res2.returncode == 0:
                msg = f"Aplicación '{app_name}' cerrada forzadamente."
                if player:
                    player.write_log(f"🚀 {msg}")
                return msg
                
            return f"No se encontró ningún proceso en ejecución que coincida con '{app_name}'."
        except Exception as e:
            return f"No se pudo cerrar '{app_name}': {e}"
