# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import shutil
import time

def print_banner():
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    reset = "\033[0m"
    
    # Activar colores ANSI en Windows
    os.system("") 
    
    print(f"{cyan}======================================================================={reset}")
    print(f"{cyan}      __  ___   ____   _    __  ____   _____                           {reset}")
    print(f"{cyan}     / / /   | / __ \\\\ / /  / / / __ \\\\ / ___/                           {reset}")
    print(f"{cyan} __  / / / /| |/ /_/ // /  / / / /_/ / \\\\__ \\\\                            {reset}")
    print(f"{cyan}/ /_/ / / ___ // _, _// /__/ /  / _, _/ ___/ /                            {reset}")
    print(f"{cyan}\\\\____/ /_/  |_|/_/ |_|/____/_/  /_/ |_|/____/                             {reset}")
    print("                                                                       ")
    print(f"{green}                  SISTEMA DE INSTALACIÓN INTELIGENTE                   {reset}")
    print(f"{cyan}======================================================================={reset}")
    print()

def main():
    print_banner()
    print("Este asistente preparará a ILUM para funcionar de forma óptima.")
    print()
    print(" [1] Comenzar instalación limpia (Recomendado)")
    print(" [2] Salir")
    print()
    
    try:
        opt = input("Selecciona una opción (1-2): ").strip()
    except (KeyboardInterrupt, EOFError):
        opt = "2"
        
    if opt != "1":
        print("\nSaliendo del instalador...")
        time.sleep(1.5)
        sys.exit(0)
        
    # FASE 1: Verificación de requisitos
    os.system("cls")
    print_banner()
    print("\033[36m [FASE 1/5] - Verificando requisitos del sistema...\033[0m")
    print()
    
    print(f"[OK] Python detectado: {sys.version.split()[0]}")
    
    # Limpieza de residuos antiguos
    print("\033[33m[INFO] Limpiando archivos temporales viejos y cachés...\033[0m")
    
    basura = ["build", "dist"]
    for folder in basura:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except Exception:
                pass
                
    archivos_basura = ["ilum.log", "ILUM_Beta_Installer.exe"]
    for f in os.listdir("."):
        if f.endswith(".spec") or f in archivos_basura:
            try:
                os.remove(f)
            except Exception:
                pass
                
    print("\033[32m[OK] Limpieza de residuos completada.\033[0m")
    time.sleep(1)
    
    # FASE 2: Entorno Virtual
    os.system("cls")
    print_banner()
    print("\033[36m [FASE 2/5] - Configurando Entorno Virtual (.venv)...\033[0m")
    print()
    
    if not os.path.exists(".venv"):
        print("\033[33m[INFO] Creando un entorno virtual de Python limpio...\033[0m")
        try:
            subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
            print("\033[32m[OK] Entorno virtual creado exitosamente.\033[0m")
        except Exception as e:
            print(f"\033[31m[ERROR] No se pudo crear el entorno virtual: {e}\033[0m")
            input("Presiona Enter para salir...")
            sys.exit(1)
    else:
        print("\033[32m[OK] Entorno virtual existente detectado.\033[0m")
        
    time.sleep(1)
    
    # FASE 3: Instalación de dependencias
    os.system("cls")
    print_banner()
    print("\033[36m [FASE 3/5] - Instalando dependencias de ILUM...\033[0m")
    print()
    print("Esto puede tomar unos minutos dependiendo de tu conexión a Internet.")
    print("Instalando requerimientos de forma segura...")
    print()
    
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = "python" # Fallback
        
    try:
        # Upgrade pip
        subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        
        # Check if Python is 3.13 or newer
        is_python_313 = sys.version_info >= (3, 13)
        
        if is_python_313:
            print("\033[33m[INFO] Python 3.13+ detectado. Omitiendo 'mediapipe' temporalmente durante la instalacion principal...\033[0m")
            # Read requirements.txt and filter out mediapipe
            temp_req_path = "requirements_temp.txt"
            with open("requirements.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            with open(temp_req_path, "w", encoding="utf-8") as f:
                for line in lines:
                    if "mediapipe" not in line.lower().strip():
                        f.write(line)
            
            try:
                subprocess.run([venv_python, "-m", "pip", "install", "-r", temp_req_path], check=True)
                print("\033[32m\n[OK] Dependencias principales instaladas correctamente (sin mediapipe).\033[0m")
                print("\033[33m[ADVERTENCIA] 'mediapipe' no cuenta con soporte oficial en Python 3.13 en Windows aun.")
                print("El piloto gestual por camara estara desactivado. El resto de ILUM funcionara al 100%.")
                print("Para contar con la experiencia gestual completa, se recomienda usar Python 3.12.\033[0m")
                time.sleep(4)
            finally:
                if os.path.exists(temp_req_path):
                    os.remove(temp_req_path)
        else:
            # Install requirements normally
            subprocess.run([venv_python, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
            print("\033[32m\n[OK] Todas las dependencias se instalaron correctamente.\033[0m")
    except Exception as e:
        print(f"\033[31m\n[ERROR] Ocurrió un error al instalar dependencias: {e}\033[0m")
        input("Presiona Enter para salir...")
        sys.exit(1)
        
    time.sleep(1)
    
    # FASE 4: Configuración inicial
    os.system("cls")
    print_banner()
    print("\033[36m [FASE 4/5] - Configuración Inicial...\033[0m")
    print()
    
    config_dir = os.path.join(".", "config")
    api_keys_path = os.path.join(config_dir, "api_keys.json")
    api_keys_template = os.path.join(config_dir, "api_keys.example.json")
    rules_path = os.path.join(config_dir, "rules.json")
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
        print("\033[32m[OK] Directorio config/ creado.\033[0m")
    
    if not os.path.exists(api_keys_path):
        if os.path.exists(api_keys_template):
            shutil.copy2(api_keys_template, api_keys_path)
            print("\033[32m[OK] Archivo api_keys.json creado desde plantilla.\033[0m")
            print("\033[33m[INFO] Al iniciar ILUM se te pedirán tus API Keys de Gemini y OpenRouter.\033[0m")
        else:
            # Crear un archivo mínimo con campos vacíos
            import json
            default_config = {
                "supabase_url": "https://vktpkyrdmgqmvpxwkwcx.supabase.co",
                "supabase_anon_key": "sb_publishable_5DDUYrisPUiJSMLBh7cbqA_HdkLAADT",
                "gemini_api_key": "",
                "os_system": "windows",
                "camera_index": 0,
                "mic_device": 0,
                "spk_device": 0,
                "chrome_google_profile": "Default",
                "chrome_exe_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "timezone": "America/Bogota",
                "language": "es-ES",
                "thinking_sound": True,
                "ilum_voice": "Charon",
                "spotify_client_id": "",
                "spotify_client_secret": "",
                "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
                "tmdb_api_key": "",
                "openrouter_api_key": "",
                "ilum_theme": "gold",
                "gpu_acceleration": False
            }
            with open(api_keys_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            print("\033[32m[OK] Archivo api_keys.json creado con valores por defecto.\033[0m")
            print("\033[33m[INFO] Al iniciar ILUM se te pedirán tus API Keys de Gemini y OpenRouter.\033[0m")
    else:
        print("\033[32m[OK] Archivo api_keys.json existente detectado.\033[0m")
    
    if not os.path.exists(rules_path):
        import json
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump({"rules": []}, f, indent=4)
        print("\033[32m[OK] Archivo rules.json creado.\033[0m")
    else:
        print("\033[32m[OK] Archivo rules.json existente detectado.\033[0m")
    # Descarga automática de FFmpeg para máxima calidad de YouTube
    if not os.path.exists("ffmpeg.exe"):
        print()
        print("\033[36m[INFO] Verificando dependencias multimedia (FFmpeg)...\033[0m")
        print("Se requiere FFmpeg para fusionar audio y video de YouTube a máxima calidad (1080p, 4K).")
        try:
            import urllib.request
            import zipfile
            
            ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            zip_path = "ffmpeg.zip"
            
            print("\033[33mDescargando FFmpeg (Aprox. 130MB). Esto puede tomar unos minutos...\033[0m")
            urllib.request.urlretrieve(ffmpeg_url, zip_path)
            
            print("Extrayendo FFmpeg...")
            with zipfile.ZipFile(zip_path, 'r') as z:
                for file_info in z.infolist():
                    if file_info.filename.endswith('ffmpeg.exe'):
                        file_info.filename = 'ffmpeg.exe'
                        z.extract(file_info, '.')
                    elif file_info.filename.endswith('ffprobe.exe'):
                        file_info.filename = 'ffprobe.exe'
                        z.extract(file_info, '.')
            
            print("Limpiando archivos temporales...")
            if os.path.exists(zip_path):
                os.remove(zip_path)
            print("\033[32m[OK] FFmpeg instalado con éxito.\033[0m")
        except Exception as e:
            print(f"\033[31m[ERROR] No se pudo instalar FFmpeg automáticamente: {e}\033[0m")
            if os.path.exists("ffmpeg.zip"):
                try: os.remove("ffmpeg.zip")
                except: pass
    else:
        print("\033[32m[OK] Ejecutables ffmpeg.exe y ffprobe.exe existentes detectados.\033[0m")

    # Descarga opcional del Modelo Vosk
    vosk_path = os.path.join(config_dir, "vosk_model")
    if not os.path.exists(vosk_path):
        print()
        print("\033[36m[INFO] Verificando el modelo de voz offline (Vosk)...\033[0m")
        print("El modelo Vosk en español permite el Modo Suspensión y Wake Word offline.")
        try:
            import urllib.request
            import zipfile
            
            url = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
            zip_path = "vosk_model.zip"
            extract_path = os.path.join(config_dir, "vosk-model-small-es-0.42")
            
            print("\033[33mDescargando modelo offline Vosk en español (39MB)...\033[0m")
            urllib.request.urlretrieve(url, zip_path)
            
            print("Extrayendo archivos del modelo...")
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(config_dir)
                
            print("Configurando estructura del modelo...")
            if os.path.exists(vosk_path):
                shutil.rmtree(vosk_path)
            os.rename(extract_path, vosk_path)
            
            print("Limpiando archivos temporales...")
            os.remove(zip_path)
            print("\033[32m[OK] Modelo Vosk instalado con éxito.\033[0m")
        except Exception as e:
            print(f"\033[33m[ADVERTENCIA] No se pudo instalar Vosk automáticamente: {e}\033[0m")
            print("No te preocupes, ILUM iniciará igual y puedes descargarlo más tarde con 'download_vosk.py'.")
    else:
        print("\033[32m[OK] Modelo offline Vosk existente detectado.\033[0m")
    
    time.sleep(1)
    
    # FASE 5: Acceso directo
    os.system("cls")
    print_banner()
    print("\033[36m [FASE 5/5] - Creación de Accesos Directos...\033[0m")
    print()
    print("Creando acceso directo en tu Escritorio para un inicio rápido...")
    print()
    
    try:
        current_dir = os.getcwd()
        icon_path = os.path.join(current_dir, "assets", "ilum_icono.ico")
        target_vbs = os.path.join(current_dir, "Iniciar ILUM Beta.vbs")
        
        # Crear acceso directo con PowerShell
        ps_cmd = (
            f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut(([System.Environment]::GetFolderPath('Desktop')+'\\ILUM AI.lnk'));"
            f"$s.TargetPath='{target_vbs}';"
            f"$s.WorkingDirectory='{current_dir}';"
            f"$s.IconLocation='{icon_path}';"
            f"$s.Description='Lanzador de ILUM AI (Admin)';"
            f"$s.Save()"
        )
        
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
        
        # Marcar el .lnk como "Ejecutar como Administrador"
        # El flag está en el byte 21 del archivo .lnk (bit 0x20)
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            lnk_path = os.path.join(desktop, "ILUM AI.lnk")
            if os.path.exists(lnk_path):
                with open(lnk_path, "rb") as f:
                    data = bytearray(f.read())
                data[21] = data[21] | 0x20  # Set RunAsAdmin flag
                with open(lnk_path, "wb") as f:
                    f.write(data)
        except Exception:
            pass  # El VBS ya tiene auto-elevación, esto es redundante
        
        print("\033[32m[OK] Acceso directo 'ILUM AI' creado en el Escritorio (con permisos de Admin).\033[0m")
    except Exception as e:
        print(f"\033[33m[ADVERTENCIA] No se pudo crear el acceso directo de forma automática: {e}\033[0m")
        
    time.sleep(1)
    
    # Pantalla Final
    os.system("cls")
    print_banner()
    print("\033[32m=======================================================================")
    print("     ¡INSTALACIÓN Y CONFIGURACIÓN COMPLETADA CON ÉXITO!")
    print("=======================================================================\033[0m")
    print()
    print("ILUM está listo para servirte.")
    print("Al iniciar el sistema por primera vez se te solicitarán tus API Keys")
    print("para Gemini y OpenRouter automáticamente de forma visual.")
    print()
    print(" [1] Iniciar ILUM ahora mismo")
    print(" [2] Salir")
    print()
    
    try:
        launch_opt = input("Selecciona una opción (1-2): ").strip()
    except (KeyboardInterrupt, EOFError):
        launch_opt = "2"
        
    if launch_opt == "1":
        print("Iniciando ILUM...")
        try:
            # Ejecutar el VBS silencioso
            os.startfile("Iniciar ILUM Beta.vbs")
        except Exception:
            # Fallback si no está asociado
            subprocess.Popen(["wscript.exe", "Iniciar ILUM Beta.vbs"])
            
    print("\nGracias por usar el instalador de ILUM AI.")
    time.sleep(2)

if __name__ == "__main__":
    main()
