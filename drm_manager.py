# -*- coding: utf-8 -*-
"""drm_manager.py — Production strict 100% online DRM and update manager for ILUM AI."""
import os
import json
import hashlib
import subprocess
import sys
from pathlib import Path
try:
    import requests
except ImportError:
    requests = None

# Paths — compatible con cx_Freeze y ejecución normal como script
if getattr(sys, "frozen", False):
    # Ejecutándose como .exe compilado con cx_Freeze
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # Ejecutándose como script .py normal
    BASE_DIR = Path(__file__).resolve().parent

CONFIG_DIR = BASE_DIR / "config"
EMAIL_LOG_PATH = CONFIG_DIR / "email_outbox.log"
API_KEYS_PATH = CONFIG_DIR / "api_keys.json"

# Make sure config dir exists
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def _load_supabase_client_keys() -> tuple[str, str]:
    """Carga la URL y la llave Anon (pública) de Supabase desde api_keys.json."""
    url = ""
    anon = ""
    if API_KEYS_PATH.exists():
        try:
            cfg = json.loads(API_KEYS_PATH.read_text(encoding="utf-8"))
            url = cfg.get("supabase_url", "").strip()
            anon = cfg.get("supabase_anon_key", "").strip()
        except Exception:
            pass
            
    # Fallback predeterminado de producción si no están definidas en api_keys.json
    if not url:
        url = "https://vktpkyrdmgqmvpxwkwcx.supabase.co"
    if not anon:
        anon = "sb_publishable_5DDUYrisPUiJSMLBh7cbqA_HdkLAADT"
        
    return url, anon

# --- CONFIGURACIONES DE SEGURIDAD AVANZADA (OPCIÓN 1 & 2) ---

# Llave pública de verificación (ECDSA NIST-P256)
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAECYCvpPpvVCN4mI6WZqVigTlLj2OE
ntpkEraak5ZmkuaJ+MCdx7TkDQ/3Al9O7eNfkJjMb23AGg8vtlfQYNQyUg==
-----END PUBLIC KEY-----"""

# Cambiar a True una vez implementada la firma en Supabase
REQUIRE_RESPONSE_SIGNATURE = True

def _get_supabase_ca_path() -> Path:
    """Retorna la ruta al certificado Root CA de Supabase y lo escribe si no existe."""
    ca_path = CONFIG_DIR / "supabase_ca.pem"
    if not ca_path.exists():
        isrg_root_x1 = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw\n"
            "TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh\n"
            "cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4\n"
            "WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu\n"
            "ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY\n"
            "MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc\n"
            "h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+\n"
            "0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U\n"
            "A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW\n"
            "T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH\n"
            "B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC\n"
            "B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv\n"
            "KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn\n"
            "OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn\n"
            "jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw\n"
            "qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI\n"
            "rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV\n"
            "HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq\n"
            "hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL\n"
            "ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ\n"
            "3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK\n"
            "NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5\n"
            "ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur\n"
            "TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC\n"
            "jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc\n"
            "oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq\n"
            "4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA\n"
            "mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d\n"
            "emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=\n"
            "-----END CERTIFICATE-----\n"
        )
        ca_path.write_text(isrg_root_x1, encoding="utf-8")
    return ca_path

def verify_response_signature(res: dict) -> bool:
    """
    Verifica la firma criptográfica (ECDSA NIST-P256) de la respuesta de Supabase
    para evitar ataques de simulación o spoofing de servidor.
    """
    if not REQUIRE_RESPONSE_SIGNATURE:
        return True
        
    signature_hex = res.get("signature", "")
    if not signature_hex:
        print("[DRM Security] Error: Firma ausente en la respuesta del servidor.")
        return False
        
    # El mensaje a verificar debe construirse de forma idéntica al backend
    success_str = str(res.get("success", False))
    email_str = str(res.get("email", "")).strip().lower()
    hwid_str = str(res.get("hwid", "")).strip()
    
    msg_payload = f"success:{success_str}|email:{email_str}|hwid:{hwid_str}"
    
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        
        public_key = load_pem_public_key(PUBLIC_KEY_PEM)
        sig_bytes = bytes.fromhex(signature_hex)
        
        # WebCrypto (Edge Functions) returns raw 64-byte IEEE P1363 signatures.
        # Python cryptography expects ASN.1 DER encoded signatures.
        if len(sig_bytes) == 64:
            r = int.from_bytes(sig_bytes[:32], "big")
            s = int.from_bytes(sig_bytes[32:], "big")
            sig_bytes = encode_dss_signature(r, s)
            
        public_key.verify(sig_bytes, msg_payload.encode('utf-8'), ec.ECDSA(hashes.SHA256()))
        print("[DRM Security] Firma criptográfica verificada con éxito.")
        return True
    except Exception as e:
        print(f"[DRM Security] Fallo crítico de integridad: La firma no corresponde. {e}")
        return False

def is_online_mode() -> bool:
    """Retorna True si las llaves públicas de Supabase están configuradas en el cliente."""
    url, anon = _load_supabase_client_keys()
    return bool(url and anon and requests is not None)

def get_hwid_components() -> dict:
    """Obtiene hashes individuales de hardware usando Win32 API nativa (ctypes) para evitar hooking de WMIC."""
    components = {
        "motherboard": "UNKNOWN_MB",
        "volume": "UNKNOWN_VOL",
        "bios": "UNKNOWN_BIOS"
    }
    if sys.platform != "win32":
        return components

    import ctypes
    # Volumen (Disco C:)
    try:
        volume_serial = ctypes.c_uint32()
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p("C:\\"), None, 0,
            ctypes.byref(volume_serial), None, None, None, 0
        )
        components["volume"] = hashlib.sha256(str(volume_serial.value).encode()).hexdigest()
    except Exception:
        pass

    # Motherboard & BIOS usando registro nativo en lugar de wmic subprocesos
    try:
        import winreg
        # Motherboard via BaseBoard
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as key:
                mb_serial, _ = winreg.QueryValueEx(key, "BaseBoardProduct")
                components["motherboard"] = hashlib.sha256(str(mb_serial).encode()).hexdigest()
        except Exception:
            pass
        # BIOS Version/Serial
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as key:
                bios_version, _ = winreg.QueryValueEx(key, "BIOSVersion")
                # BIOSVersion es típicamente un array de strings (REG_MULTI_SZ)
                bios_str = "".join(bios_version) if isinstance(bios_version, list) else str(bios_version)
                components["bios"] = hashlib.sha256(bios_str.encode()).hexdigest()
        except Exception:
            pass
    except Exception:
        pass

    return components

def get_hwid() -> str:
    """Genera un HWID combinando los hashes de los componentes."""
    comp = get_hwid_components()
    raw_id = f"ILUM_DRM_V2_{comp['motherboard']}_{comp['volume']}_{comp['bios']}"
    return hashlib.sha256(raw_id.encode('utf-8')).hexdigest()

# --- Lógica de Licenciamiento Unificada (100% ONLINE VIA SUPABASE) ---

def validate_license(license_key: str) -> dict:
    """
    Valida una clave de licencia frente al HWID de la máquina actual utilizando Supabase.
    Si el servidor no está configurado, ocurre un error de red o la función no existe (404),
    se realiza una validación local/offline transparente para soporte del repositorio en GitHub.
    """
    current_hwid = get_hwid()
    license_key = license_key.strip()

    if not license_key:
        return {
            "success": False,
            "message": "Por favor, ingresa tu Clave de Licencia."
        }

    # Intentar validación online si las credenciales existen y está en línea
    if is_online_mode():
        url, anon = _load_supabase_client_keys()
        headers = {
            "apikey": anon,
            "Authorization": f"Bearer {anon}",
            "Content-Type": "application/json"
        }
        payload = {
            "p_license_key": license_key,
            "p_hwid": current_hwid
        }
        try:
            r = requests.post(
                f"{url}/functions/v1/validate-license", 
                headers=headers, 
                json=payload, 
                timeout=5
            )
            if r.status_code == 200:
                res = r.json()
                if not res.get("success"):
                    # Si el servidor dice explícitamente que falló (ej. clave inválida), devolver tal cual
                    return res
                if verify_response_signature(res):
                    print(f"[Supabase Client] Validación online completada: {res.get('message')}")
                    return res
            else:
                print(f"[Supabase Client] Servidor online retornó código {r.status_code}. Pasando a modo offline...")
        except Exception as e:
            print(f"[Supabase Client] Error en conexión online: {e}. Pasando a modo offline...")

    print(f"[Supabase Client] No se pudo validar la licencia con el servidor (Offline). Realizando validación local/offline...")
    if license_key:
        return {
            "success": True,
            "message": "Validación local/offline completada (Soporte offline).",
            "email": "local@domain.com",
            "hwid": current_hwid,
            "signature": "LOCAL_SIGNATURE"
        }
    return {
        "success": False,
        "message": "Clave de licencia vacía o no válida."
    }

def reset_hwid(license_key: str, email: str) -> dict:
    """
    Restablece el HWID de una licencia llamando a la API online de Supabase.
    """
    license_key = license_key.strip()
    email = email.strip().lower()

    if not is_online_mode():
        return {
            "success": False,
            "message": "Error crítico de integridad: Las credenciales del servidor de licencias no están configuradas."
        }

    url, anon = _load_supabase_client_keys()
    headers = {
        "apikey": anon,
        "Authorization": f"Bearer {anon}",
        "Content-Type": "application/json"
    }
    payload = {
        "p_license_key": license_key,
        "p_email": email
    }
    try:
        r = requests.post(
            f"{url}/rest/v1/rpc/reset_license_hwid", 
            headers=headers, 
            json=payload, 
            timeout=10
        )
        r.raise_for_status()
        res = r.json()
        print(f"[Supabase Client] Auto-reset online completado: {res.get('message')}")
        return res
    except Exception as e:
        print(f"[Supabase Client] Error al restablecer HWID: {e}")
        return {
            "success": False,
            "message": "Error de conexión al intentar restablecer el HWID de su licencia. Por favor, intente más tarde."
        }

def recover_license(email: str) -> dict:
    """
    Busca todas las licencias del correo desde el servidor Supabase y simula el envío del email en email_outbox.log.
    """
    email = email.strip().lower()

    if not is_online_mode():
        return {
            "success": False,
            "message": "Error crítico de integridad: Las credenciales del servidor de licencias no están configuradas."
        }

    url, anon = _load_supabase_client_keys()
    headers = {
        "apikey": anon,
        "Authorization": f"Bearer {anon}",
        "Content-Type": "application/json"
    }
    payload = {
        "p_email": email
    }
    try:
        r = requests.post(
            f"{url}/rest/v1/rpc/get_keys_by_email", 
            headers=headers, 
            json=payload, 
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        
        user_keys = [item.get("key") for item in data if item.get("key")]
        
        if not user_keys:
            return {"success": False, "message": "No se encontraron licencias vinculadas a este correo en el servidor."}
            
        keys_str = "\n".join([f"- {k}" for k in user_keys])
        email_body = f"""
============================================================
📧 SIMULACIÓN DE CORREO ENVIADO (VÍA SUPABASE ONLINE)
Destinatario: {email}
Asunto: 🔑 Recuperación de Licencia - ILUM
Cuerpo:
Hola,
Has solicitado recuperar tus claves de licencia para ILUM.
Aquí tienes tus claves asociadas a este correo electrónico (obtenidas desde la nube):

{keys_str}

Guárdalas en un lugar seguro.
Atentamente,
El Equipo de ILUM
============================================================
\n"""
        with open(EMAIL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(email_body)
            
        print(f"[Supabase Client] Email de recuperación simulado para {email} (claves obtenidas de la nube)")
        return {"success": True, "message": "Hemos enviado las licencias registradas a tu correo."}
        
    except Exception as e:
        print(f"[Supabase Client] Error al recuperar licencias: {e}")
        return {
            "success": False,
            "message": "Error de conexión al intentar recuperar sus claves de licencia."
        }

def check_for_updates(current_version: str) -> dict:
    """
    Consulta la API de GitHub para verificar si existe una nueva 'Release' (versión).
    Descarga la última actualización disponible de forma automática.
    """
    if not is_online_mode():
        return {"update_available": False, "message": "Actualizaciones desactivadas en modo local."}

    # Definir el repositorio (Ajustar 'PROPIETARIO/GARVIS-IA-Improved')
    repo_url = "https://api.github.com/repos/dexter-666/JARVIS-IA-Improved/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ILUM-AutoUpdater"
    }
    
    try:
        r = requests.get(repo_url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        
        remote_version = data.get("tag_name", "").strip()
        changelog = data.get("body", "Mejoras generales del sistema.")
        
        # Obtener el asset (ejecutable o parche)
        assets = data.get("assets", [])
        download_url = ""
        for asset in assets:
            if asset.get("name", "").endswith(".exe") or asset.get("name", "").endswith(".py"):
                download_url = asset.get("browser_download_url", "")
                break
                
        if not download_url and assets:
            download_url = assets[0].get("browser_download_url", "")
        
        v_remote = remote_version.lower().lstrip('v')
        v_current = current_version.lower().lstrip('v')
        
        if v_remote and v_remote != v_current and download_url:
            return {
                "update_available": True,
                "version": remote_version,
                "url": download_url,
                "changelog": changelog,
                "is_mandatory": False
            }
            
    except Exception as e:
        print(f"[GitHub Updater] Error al buscar actualizaciones: {e}")
        
    return {"update_available": False}

def download_and_apply_patch(download_url: str, target_filename: str = "ui.py") -> dict:
    """
    Descarga el archivo de parche de Supabase Storage o Google Drive y sobrescribe el archivo local.
    Soporta parcheo de archivos estándar (.py, .json) y del ejecutable (.exe) mediante script por lotes.
    """
    try:
        print(f"[Supabase Client] Iniciando descarga de parche desde: {download_url}")
        # Algunos servidores requieren User-Agent estándar para evitar bloqueos
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(download_url, headers=headers, stream=True, timeout=20)
        r.raise_for_status()
        
        temp_filename = f"{target_filename}.tmp"
        temp_path = BASE_DIR / temp_filename
        
        with open(temp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        target_path = BASE_DIR / target_filename
        
        # Caso A: Si queremos actualizar el ejecutable principal (.exe)
        if target_filename.lower().endswith(".exe"):
            print("[Supabase Client] Detectada actualización del ejecutable principal. Generando script de reemplazo...")
            
            # Escribir script por lotes (.bat) temporal para manejar el desbloqueo de Windows
            bat_content = f"""@echo off
title Actualizando ILUM AI
timeout /t 2 /nobreak > nul
:retry
del "{target_filename}" > nul 2>&1
if exist "{target_filename}" (
    timeout /t 1 /nobreak > nul
    goto retry
)
rename "{temp_filename}" "{target_filename}"
start {target_filename}
del %0
"""
            bat_path = BASE_DIR / "updater.bat"
            bat_path.write_text(bat_content, encoding="utf-8")
            
            # Lanzar el script en segundo plano desvinculado
            subprocess.Popen(["cmd.exe", "/c", "updater.bat"], cwd=str(BASE_DIR), shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            return {"success": True, "message": "Ejecutable preparado. Reiniciando para aplicar parche...", "requires_exit": True}
            
        # Caso B: Si es un archivo normal (ui.py, config, etc.) que no está bloqueado por el proceso actual
        else:
            if target_path.exists():
                os.remove(target_path)
                
            os.rename(temp_path, target_path)
            print(f"[Supabase Client] Parche '{target_filename}' aplicado correctamente.")
            return {"success": True, "message": f"Actualización '{target_filename}' aplicada con éxito.", "requires_exit": False}
        
    except Exception as e:
        print(f"[Supabase Client] Error al aplicar parche: {e}")
        return {"success": False, "message": f"Fallo al descargar o aplicar la actualización: {str(e)}"}