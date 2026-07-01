# -*- coding: utf-8 -*-
"""
macros.py — Advanced keyboard macros, key press simulation, and typing automation tool for ILUM.
"""
import time
import os
import subprocess
import pyautogui
import pyperclip
import traceback
import actions.direct_input as direct_input

def macros(parameters: dict, player=None) -> str:
    """
    Simulates advanced macro sequences, direct keystrokes, and predefined automated actions.
    """
    action = parameters.get("action", "").lower().strip()
    macro_name = parameters.get("macro_name", "").lower().strip()
    text = parameters.get("text", "")
    key = parameters.get("key", "").lower().strip()
    sequence = parameters.get("sequence", "")

    if not action:
        return "Error: Se requiere especificar la propiedad 'action' en macros."

    try:
        # Action 1: Predefined Macro Name
        if action == "execute_macro":
            if not macro_name:
                return "Error: Debes proporcionar un 'macro_name' para ejecutar un macro predefinido."

            if macro_name == "minimize_all":
                pyautogui.hotkey("win", "d")
                msg = "Macro ejecutado: Minimizar todas las ventanas (WIN+D)."
            elif macro_name == "close_window":
                pyautogui.hotkey("alt", "f4")
                msg = "Macro ejecutado: Cerrar la ventana activa (ALT+F4)."
            elif macro_name == "lock_pc":
                pyautogui.hotkey("win", "l")
                msg = "Macro ejecutado: Bloquear PC (WIN+L)."
            elif macro_name == "new_virtual_desktop":
                pyautogui.hotkey("ctrl", "win", "d")
                msg = "Macro ejecutado: Crear nuevo escritorio virtual (CTRL+WIN+D)."
            elif macro_name == "write_note":
                subprocess.Popen("notepad.exe")
                time.sleep(0.8) # esperar a que se abra
                pyperclip.copy("Nota rápida de ILUM: ")
                pyautogui.hotkey("ctrl", "v")
                msg = "Macro ejecutado: Bloc de notas iniciado y listo para escribir."
            elif macro_name == "google_search":
                pyautogui.hotkey("win", "r")
                time.sleep(0.3)
                pyautogui.write("https://www.google.com")
                pyautogui.press("enter")
                msg = "Macro ejecutado: Navegador abierto para búsqueda en Google."
            else:
                loop = parameters.get("loop", False)
                times = int(parameters.get("times", 1) or 1)
                
                from actions.macro_recorder import play_macro
                success, best_match = play_macro(macro_name, loop=loop, times=times)
                
                if success:
                    loop_msg = "en bucle infinito" if loop else (f"{times} vez" if times == 1 else f"{times} veces")
                    msg = f"Macro guardado como '{best_match}' ejecutado exitosamente ({loop_msg})."
                else:
                    return f"Error: {best_match}"

        # Action 0.6: Delete macro
        elif action == "delete_macro":
            if not macro_name:
                return "Error: Se requiere 'macro_name' para eliminar un macro."
            import actions.macro_recorder as macro_recorder
            success, result_msg = macro_recorder.delete_macro(macro_name)
            if success:
                msg = f"El macro '{result_msg}' ha sido eliminado exitosamente."
            else:
                msg = result_msg

        # Action 0.8: List macros
        elif action == "list_macros":
            import json
            from actions.macro_recorder import MACROS_FILE
            if not MACROS_FILE.exists():
                msg = "No hay macros guardados actualmente."
            else:
                try:
                    with open(MACROS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not data:
                        msg = "No hay macros guardados actualmente."
                    else:
                        macros_list = ", ".join(data.keys())
                        msg = f"Tus macros guardadas son: {macros_list}"
                except Exception as e:
                    msg = f"Error al leer la lista de macros: {e}"

        # Action 1.2: Stop Macro
        elif action == "stop_macro":
            import actions.macro_recorder as macro_recorder
            macro_recorder.GLOBAL_STOP_MACRO = True
            msg = "Señal de detención enviada. Cualquier macro o bucle en ejecución se abortará."

        # Action 1.5: Record Macro
        elif action == "record_macro":
            if not macro_name:
                return "Error: Debes proporcionar un 'macro_name' para grabar."
            from actions.macro_recorder import record_macro_until_esc
            import threading
            threading.Thread(target=record_macro_until_esc, args=(macro_name,), daemon=True).start()
            msg = f"Grabación del macro '{macro_name}' iniciada. Comenzará en 3 segundos tras un pitido. Presiona ESC para detener la grabación."

        # Action 2: Type Text directly
        elif action == "type_text":
            times = int(parameters.get("times", 1) or 1)
            if not text:
                return "Error: Se requiere el parámetro 'text' para teclear."
            # Usar portapapeles es sumamente robusto en español
            pyperclip.copy(text)
            for _ in range(times):
                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "v")
            msg = f"Texto tecleado directamente {times} veces: '{text}'"

        # Action 3: Press key or hotkey shortcut
        elif action == "press_key":
            times = int(parameters.get("times", 1) or 1)
            if not key:
                return "Error: Se requiere el parámetro 'key' para presionar una tecla."
            
            for _ in range(times):
                if "+" in key or "," in key:
                    k_list = [k.strip().lower() for k in key.replace(",", "+").split("+")]
                    if direct_input.press_hotkey(k_list):
                        pass
                    else:
                        pyautogui.hotkey(*k_list)
                else:
                    if direct_input.press_key(key):
                        pass
                    else:
                        pyautogui.press(key)
                if times > 1:
                    time.sleep(0.1)
            
            msg = f"Tecla/atajo presionada {times} veces: '{key}'"

        # Action 3.5: Hold key for duration
        elif action == "hold_key":
            duration = float(parameters.get("duration", 1.0) or 1.0)
            loop = parameters.get("loop", False)
            if not key:
                return "Error: Se requiere el parámetro 'key' para mantener presionada una tecla."
            
            def _do_hold():
                import actions.macro_recorder as macro_recorder
                macro_recorder.GLOBAL_STOP_MACRO = False
                
                if loop:
                    try:
                        import keyboard
                        keyboard.add_hotkey("esc", lambda: setattr(macro_recorder, 'GLOBAL_STOP_MACRO', True))
                    except: pass
                    keys_to_hold = [k.lower().strip() for k in key.replace(",", "+").split("+") if k.strip()]
                    valid_codes = [direct_input.SCAN_CODES.get(k, 0) for k in keys_to_hold if direct_input.SCAN_CODES.get(k, 0)]
                    
                    if valid_codes:
                        for c in valid_codes:
                            direct_input.press_key_raw(c)
                        
                        while not macro_recorder.GLOBAL_STOP_MACRO:
                            time.sleep(0.1)
                            
                        for c in reversed(valid_codes):
                            direct_input.release_key_raw(c)
                    try:
                        import keyboard
                        keyboard.remove_hotkey("esc")
                    except: pass
                else:
                    if direct_input.hold_key(key, duration):
                        pass
                    else:
                        # PyAutoGUI fallback
                        try:
                            import keyboard
                            keyboard.press(key)
                            time.sleep(duration)
                            keyboard.release(key)
                        except:
                            pyautogui.keyDown(key)
                            time.sleep(duration)
                            pyautogui.keyUp(key)
                    
            import threading
            threading.Thread(target=_do_hold, daemon=True).start()
            loop_msg = "infinitamente" if loop else f"por {duration} segundos"
            msg = f"Manteniendo atajo '{key}' {loop_msg} en segundo plano."

        # Action 3.6: Mouse macros (click, move)
        elif action == "mouse_macro":
            mouse_action = parameters.get("mouse_action", "click").lower()
            x = parameters.get("x")
            y = parameters.get("y")
            button = parameters.get("button", "left").lower()
            times = int(parameters.get("times", 1) or 1)
            loop = parameters.get("loop", False)
            
            try:
                px = int(float(str(x).strip())) if x and str(x).strip() else None
                py = int(float(str(y).strip())) if y and str(y).strip() else None
            except ValueError:
                px, py = None, None

            def _do_mouse():
                import actions.macro_recorder as macro_recorder
                macro_recorder.GLOBAL_STOP_MACRO = False
                
                if mouse_action == "click":
                    if px is not None and py is not None:
                        pyautogui.moveTo(px, py)
                        time.sleep(0.05)
                        
                    if loop:
                        try:
                            import keyboard
                            keyboard.add_hotkey("esc", lambda: setattr(macro_recorder, 'GLOBAL_STOP_MACRO', True))
                        except: pass
                        while not macro_recorder.GLOBAL_STOP_MACRO:
                            direct_input.mouse_click(button)
                            time.sleep(0.1)
                        try:
                            import keyboard
                            keyboard.remove_hotkey("esc")
                        except: pass
                    else:
                        for _ in range(times):
                            direct_input.mouse_click(button)
                            if times > 1:
                                time.sleep(0.1)
                                
                elif mouse_action == "move":
                    if px is not None and py is not None:
                        dur = float(parameters.get("duration", 0.5) or 0.5)
                        pyautogui.moveTo(px, py, duration=dur)

            import threading
            threading.Thread(target=_do_mouse, daemon=True).start()
            
            if mouse_action == "click":
                loop_msg = "infinitamente" if loop else f"{times} veces"
                msg = f"Clic {button} de ratón ejecutado {loop_msg} en segundo plano."
            else:
                msg = f"Ratón movido a {px}, {py} en segundo plano."

        # Action 4: Custom string sequence
        elif action == "custom_sequence" or sequence:
            seq_str = sequence or text
            if not seq_str:
                return "Error: Se requiere una secuencia de pasos para el macro."
                
            steps = [s.strip() for s in seq_str.split(",")]
            executed_steps = []
            for step in steps:
                if ":" not in step:
                    continue
                cmd, val = step.split(":", 1)
                cmd = cmd.strip().lower()
                val = val.strip()

                if cmd == "open":
                    subprocess.Popen(val, shell=True)
                    executed_steps.append(f"Abrir '{val}'")
                elif cmd == "wait":
                    try:
                        time.sleep(float(val))
                        executed_steps.append(f"Esperar {val}s")
                    except ValueError:
                        time.sleep(0.5)
                elif cmd == "type":
                    pyperclip.copy(val)
                    time.sleep(0.05)
                    pyautogui.hotkey("ctrl", "v")
                    executed_steps.append(f"Escribir '{val}'")
                elif cmd == "press":
                    if direct_input.press_key(val):
                        executed_steps.append(f"Presionar (DirectInput) '{val}'")
                    else:
                        pyautogui.press(val)
                        executed_steps.append(f"Presionar (PyAutoGUI) '{val}'")
                elif cmd == "hotkey":
                    k_list = [k.strip().lower() for k in val.replace(",", "+").split("+")]
                    if direct_input.press_hotkey(k_list):
                        executed_steps.append(f"Atajo (DirectInput) '{val}'")
                    else:
                        pyautogui.hotkey(*k_list)
                        executed_steps.append(f"Atajo (PyAutoGUI) '{val}'")

            msg = f"Secuencia de macro personalizada completada: {', '.join(executed_steps)}"

        else:
            return f"Error: Acción de macro desconocida: '{action}'."

        if player:
            player.write_log(f"🔧 Macro: {msg}")
        return msg

    except Exception as e:
        traceback.print_exc()
        err_msg = f"Fallo al ejecutar el macro: {str(e)}"
        if player:
            player.write_log(f"⚠️ {err_msg}")
        return err_msg
