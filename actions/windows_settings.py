"""
windows_settings.py — Módulo de configuración de Windows para NEXUS.
Permite controlar ajustes del sistema, antivirus Defender y aplicaciones.
"""

import subprocess
import winreg
import ctypes
import os
from typing import Dict, Any, Optional, Tuple
import json
import re


class WindowsSettingsError(Exception):
    """Excepción para errores de configuración de Windows."""
    pass


def _is_admin() -> bool:
    """Verifica si el script se ejecuta con privilegios de administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def _run_powershell(command: str, admin: bool = False) -> Tuple[bool, str]:
    """
    Ejecuta un comando de PowerShell y retorna (éxito, salida).
    
    Args:
        command: Comando de PowerShell a ejecutar
        admin: Si es True, intenta ejecutar como administrador
    
    Returns:
        (bool, str): (éxito, salida del comando)
    """
    try:
        if admin and not _is_admin():
            # Intentar ejecutar como administrador
            ps_command = f'Start-Process powershell -Verb RunAs -ArgumentList "-Command {command}"'
            subprocess.run(["powershell", "-Command", ps_command], 
                         capture_output=True, check=False, shell=True)
            return True, "Comando ejecutado como administrador"
        else:
            result = subprocess.run(
                ["powershell", "-Command", command],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, f"Error: {result.stderr.strip()}"
    except Exception as e:
        return False, f"Excepción: {str(e)}"


def _get_registry_value(key_path: str, value_name: str, hive: int = winreg.HKEY_LOCAL_MACHINE) -> Optional[str]:
    """
    Obtiene un valor del registro de Windows.
    
    Args:
        key_path: Ruta de la clave del registro
        value_name: Nombre del valor
        hive: Hive del registro (por defecto HKEY_LOCAL_MACHINE)
    
    Returns:
        Valor del registro o None si no existe
    """
    try:
        key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return value
    except WindowsError:
        return None


def _set_registry_value(key_path: str, value_name: str, value: Any, 
                        value_type: int = winreg.REG_SZ, 
                        hive: int = winreg.HKEY_LOCAL_MACHINE) -> bool:
    """
    Establece un valor en el registro de Windows.
    
    Args:
        key_path: Ruta de la clave del registro
        value_name: Nombre del valor
        value: Valor a establecer
        value_type: Tipo del valor (REG_SZ, REG_DWORD, etc.)
        hive: Hive del registro
    
    Returns:
        True si fue exitoso, False en caso contrario
    """
    try:
        key = winreg.CreateKey(hive, key_path)
        winreg.SetValueEx(key, value_name, 0, value_type, value)
        winreg.CloseKey(key)
        return True
    except WindowsError:
        return False


def _open_windows_settings(category: str = "") -> bool:
    """
    Abre una categoría específica de Configuración de Windows.
    
    Args:
        category: Categoría a abrir (ej: "network", "bluetooth", "privacy")
    
    Returns:
        True si fue exitoso, False en caso contrario
    """
    # Mapeo de categorías a URIs de ms-settings
    settings_map = {
        "network": "ms-settings:network",
        "bluetooth": "ms-settings:bluetooth",
        "privacy": "ms-settings:privacy",
        "windowsupdate": "ms-settings:windowsupdate",
        "system": "ms-settings:system",
        "display": "ms-settings:display",
        "sound": "ms-settings:sound",
        "apps": "ms-settings:appsfeatures",
        "account": "ms-settings:accounts",
        "time": "ms-settings:dateandtime",
        "gaming": "ms-settings:gaming",
        "easeofaccess": "ms-settings:easeofaccess",
        "search": "ms-settings:cortana",
        "privacy_camera": "ms-settings:privacy-webcam",
        "privacy_microphone": "ms-settings:privacy-microphone",
        "privacy_location": "ms-settings:privacy-location",
        "defender": "windowsdefender:",
        "firewall": "ms-settings:network-firewall",
        "storage": "ms-settings:storagesense",
        "notifications": "ms-settings:notifications"
    }
    
    try:
        uri = settings_map.get(category.lower(), "ms-settings:")
        os.startfile(uri)
        return True
    except Exception:
        # Fallback: abrir configuración general
        try:
            os.startfile("ms-settings:")
            return True
        except:
            return False


def _manage_defender(action: str) -> str:
    """
    Gestiona Windows Defender Antivirus.
    
    Args:
        action: "enable", "disable", "status", "scan", "update"
    
    Returns:
        Mensaje de resultado
    """
    actions = {
        "enable": {
            "command": 'Set-MpPreference -DisableRealtimeMonitoring $false',
            "msg": "✅ Windows Defender activado"
        },
        "disable": {
            "command": 'Set-MpPreference -DisableRealtimeMonitoring $true',
            "msg": "⚠️ Windows Defender desactivado (requiere admin)"
        },
        "status": {
            "command": 'Get-MpPreference | Select-Object -ExpandProperty DisableRealtimeMonitoring',
            "msg": "📊 Estado de Defender"
        },
        "scan": {
            "command": 'Start-MpScan -ScanType QuickScan',
            "msg": "🔍 Escaneo rápido iniciado"
        },
        "fullscan": {
            "command": 'Start-MpScan -ScanType FullScan',
            "msg": "🔍 Escaneo completo iniciado"
        },
        "update": {
            "command": 'Update-MpSignature',
            "msg": "🔄 Actualizando definiciones de virus"
        },
        "exclusion_add": {
            "command": 'Add-MpPreference -ExclusionPath "C:\\Temp"',
            "msg": "📁 Exclusión añadida"
        },
        "exclusion_remove": {
            "command": 'Remove-MpPreference -ExclusionPath "C:\\Temp"',
            "msg": "🗑️ Exclusión removida"
        }
    }
    
    if action not in actions:
        return f"❌ Acción de Defender desconocida: {action}"
    
    # Ejecutar comando
    success, output = _run_powershell(actions[action]["command"], admin=True)
    
    if action == "status":
        if output.strip() == "False":
            return "✅ Windows Defender está ACTIVADO"
        elif output.strip() == "True":
            return "⚠️ Windows Defender está DESACTIVADO"
        else:
            return f"📊 Estado: {output}"
    
    if success:
        return actions[action]["msg"]
    else:
        return f"❌ Error: {output}"


def _manage_firewall(action: str) -> str:
    """
    Gestiona el Firewall de Windows.
    
    Args:
        action: "enable", "disable", "status"
    
    Returns:
        Mensaje de resultado
    """
    if action == "enable":
        success, output = _run_powershell('Set-NetFirewallProfile -All -Enabled True', admin=True)
        return "✅ Firewall activado" if success else f"❌ Error: {output}"
    elif action == "disable":
        success, output = _run_powershell('Set-NetFirewallProfile -All -Enabled False', admin=True)
        return "⚠️ Firewall desactivado" if success else f"❌ Error: {output}"
    elif action == "status":
        success, output = _run_powershell('Get-NetFirewallProfile | Select-Object Name,Enabled')
        return f"📊 Estado del Firewall:\n{output}" if success else f"❌ Error: {output}"
    else:
        return f"❌ Acción de firewall desconocida: {action}"


def _manage_services(action: str, service_name: str) -> str:
    """
    Gestiona servicios de Windows.
    
    Args:
        action: "start", "stop", "restart", "status"
        service_name: Nombre del servicio
    
    Returns:
        Mensaje de resultado
    """
    actions = {
        "start": f'Start-Service -Name "{service_name}"',
        "stop": f'Stop-Service -Name "{service_name}"',
        "restart": f'Restart-Service -Name "{service_name}"',
        "status": f'Get-Service -Name "{service_name}" | Select-Object Name,Status'
    }
    
    if action not in actions:
        return f"❌ Acción de servicio desconocida: {action}"
    
    success, output = _run_powershell(actions[action], admin=True)
    
    if action == "status":
        return f"📊 Estado de {service_name}:\n{output}" if success else f"❌ Error: {output}"
    
    return actions[action] if success else f"❌ Error: {output}"


def _toggle_windows_feature(feature: str, enable: bool) -> str:
    """
    Activa o desactiva características de Windows.
    
    Args:
        feature: Nombre de la característica
        enable: True para activar, False para desactivar
    
    Returns:
        Mensaje de resultado
    """
    cmd = f'Enable-WindowsOptionalFeature -Online -FeatureName {feature}' if enable else f'Disable-WindowsOptionalFeature -Online -FeatureName {feature}'
    success, output = _run_powershell(cmd, admin=True)
    return f"✅ {feature} {'activada' if enable else 'desactivada'}" if success else f"❌ Error: {output}"


def windows_settings(parameters: Dict[str, Any], player=None) -> str:
    """
    Gestiona configuraciones de Windows en tiempo real.
    
    Args:
        parameters: Diccionario con parámetros de configuración
            - action: "open", "defender", "firewall", "service", "power", 
                      "registry", "feature", "network"
            - target: Objetivo de la acción (categoría, servicio, etc.)
            - value: Valor para la acción (enable/disable, etc.)
    
    Returns:
        Mensaje de resultado
    """
    p = parameters or {}
    action = p.get("action", "").strip().lower()
    target = p.get("target", "").strip().lower()
    value = p.get("value", "").strip().lower()
    app_path = p.get("path", "").strip()
    
    # Verificar permisos para acciones que requieren admin
    admin_required = ["defender", "firewall", "service", "registry", "feature", "power"]
    if action in admin_required and not _is_admin():
        try:
            # Intentar elevar privilegios
            return "⚠️ Esta acción requiere permisos de administrador. Ejecuta NEXUS como administrador."
        except:
            return "⚠️ Permisos insuficientes. Ejecuta como administrador."
    
    # ─── ABRIR CONFIGURACIÓN ───────────────────────────────────────
    if action == "open":
        if target == "defender":
            os.startfile("windowsdefender:")
            return "🛡️ Abriendo Windows Security"
        elif target == "firewall":
            os.startfile("ms-settings:network-firewall")
            return "🛡️ Abriendo configuración de firewall"
        elif target == "update":
            os.startfile("ms-settings:windowsupdate")
            return "🔄 Abriendo Windows Update"
        elif target == "network":
            os.startfile("ms-settings:network")
            return "🌐 Abriendo configuración de red"
        elif target == "bluetooth":
            os.startfile("ms-settings:bluetooth")
            return "📡 Abriendo configuración de Bluetooth"
        elif target == "privacy":
            os.startfile("ms-settings:privacy")
            return "🔒 Abriendo configuración de privacidad"
        elif target == "system":
            os.startfile("ms-settings:system")
            return "⚙️ Abriendo configuración del sistema"
        elif target == "display":
            os.startfile("ms-settings:display")
            return "🖥️ Abriendo configuración de pantalla"
        elif target == "sound":
            os.startfile("ms-settings:sound")
            return "🔊 Abriendo configuración de sonido"
        elif target == "apps":
            os.startfile("ms-settings:appsfeatures")
            return "📱 Abriendo aplicaciones"
        elif target == "storage":
            os.startfile("ms-settings:storagesense")
            return "💾 Abriendo almacenamiento"
        elif target == "gaming":
            os.startfile("ms-settings:gaming")
            return "🎮 Abriendo configuración de juegos"
        elif target == "account":
            os.startfile("ms-settings:accounts")
            return "👤 Abriendo configuración de cuentas"
        elif target == "time":
            os.startfile("ms-settings:dateandtime")
            return "🕐 Abriendo fecha y hora"
        elif target == "notifications":
            os.startfile("ms-settings:notifications")
            return "🔔 Abriendo notificaciones"
        elif target == "taskbar":
            os.startfile("ms-settings:taskbar")
            return "📌 Abriendo configuración de la barra de tareas"
        elif target == "start":
            os.startfile("ms-settings:start")
            return "🏠 Abriendo configuración del menú inicio"
        else:
            # Abrir configuración general
            os.startfile("ms-settings:")
            return "⚙️ Abriendo Configuración de Windows"
    
    # ─── GESTIÓN DE DEFENDER ───────────────────────────────────────
    elif action == "defender":
        if target == "enable" or target == "on":
            return _manage_defender("enable")
        elif target == "disable" or target == "off":
            return _manage_defender("disable")
        elif target == "status":
            return _manage_defender("status")
        elif target == "scan" or target == "scann":
            return _manage_defender("scan")
        elif target == "fullscan":
            return _manage_defender("fullscan")
        elif target == "update":
            return _manage_defender("update")
        elif target == "exclude":
            if value:
                # Agregar exclusión
                success, output = _run_powershell(f'Add-MpPreference -ExclusionPath "{value}"', admin=True)
                return f"📁 Exclusión añadida: {value}" if success else f"❌ Error: {output}"
            else:
                return "ℹ️ Especifica una ruta para excluir (path='C:\\carpeta')"
        else:
            return f"❌ Acción de Defender desconocida: {target}"
    
    # ─── GESTIÓN DE FIREWALL ──────────────────────────────────────
    elif action == "firewall":
        if target == "enable" or target == "on":
            return _manage_firewall("enable")
        elif target == "disable" or target == "off":
            return _manage_firewall("disable")
        elif target == "status":
            return _manage_firewall("status")
        else:
            return f"❌ Acción de firewall desconocida: {target}"
    
    # ─── GESTIÓN DE SERVICIOS ─────────────────────────────────────
    elif action == "service":
        if not target:
            return "ℹ️ Especifica un servicio (target='wuauserv' para Windows Update)"
        
        if value in ["start", "stop", "restart", "status"]:
            return _manage_services(value, target)
        else:
            return f"ℹ️ Acción de servicio: {value}. Usa start, stop, restart o status"
    
    # ─── REGISTRO DE WINDOWS ──────────────────────────────────────
    elif action == "registry":
        if target == "set":
            key_path = p.get("key", "").strip()
            value_name = p.get("value_name", "").strip()
            reg_value = p.get("reg_value", "").strip()
            
            if not key_path or not value_name:
                return "ℹ️ Especifica key='ruta', value_name='nombre', reg_value='valor'"
            
            # Determinar tipo automáticamente
            if reg_value.isdigit():
                value_type = winreg.REG_DWORD
                reg_value = int(reg_value)
            else:
                value_type = winreg.REG_SZ
            
            if _set_registry_value(key_path, value_name, reg_value, value_type):
                return f"✅ Registro actualizado: {key_path}\\{value_name} = {reg_value}"
            else:
                return "❌ Error al actualizar el registro"
        
        elif target == "get":
            key_path = p.get("key", "").strip()
            value_name = p.get("value_name", "").strip()
            
            if not key_path or not value_name:
                return "ℹ️ Especifica key='ruta', value_name='nombre'"
            
            value = _get_registry_value(key_path, value_name)
            if value is not None:
                return f"📊 {key_path}\\{value_name} = {value}"
            else:
                return f"❌ Valor no encontrado"
        else:
            return "ℹ️ Usa registry target='set' o 'get'"
    
    # ─── CARACTERÍSTICAS DE WINDOWS ──────────────────────────────
    elif action == "feature":
        if not target:
            return "ℹ️ Especifica una característica (target='Microsoft-Windows-Subsystem-Linux')"
        
        if value in ["enable", "on", "true"]:
            return _toggle_windows_feature(target, True)
        elif value in ["disable", "off", "false"]:
            return _toggle_windows_feature(target, False)
        else:
            return f"ℹ️ Usa value='enable' o 'disable'"
    
    # ─── GESTIÓN DE ENERGÍA ──────────────────────────────────────
    elif action == "power":
        if target == "high":
            success, _ = _run_powershell('powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c', admin=True)
            return "⚡ Plan de alto rendimiento activado" if success else "❌ Error al cambiar plan"
        elif target == "balanced":
            success, _ = _run_powershell('powercfg -setactive 381b4222-f694-41f0-9685-ff5bb260df2e', admin=True)
            return "⚖️ Plan equilibrado activado" if success else "❌ Error al cambiar plan"
        elif target == "powersaver":
            success, _ = _run_powershell('powercfg -setactive a1841308-3541-4fab-bc81-f71556f20b4a', admin=True)
            return "💚 Plan de ahorro de energía activado" if success else "❌ Error al cambiar plan"
        elif target == "shutdown" or target == "apagar":
            os.system("shutdown /s /t 5")
            return "⏰ Apagando en 5 segundos..."
        elif target == "restart" or target == "reiniciar":
            os.system("shutdown /r /t 5")
            return "🔄 Reiniciando en 5 segundos..."
        elif target == "sleep" or target == "suspender":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "💤 Suspendiendo sistema..."
        elif target == "lock" or target == "bloquear":
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return "🔒 Bloqueando pantalla"
        else:
            return "ℹ️ Opciones de energía: high, balanced, powersaver, shutdown, restart, sleep, lock"
    
    # ─── GESTIÓN DE RED ──────────────────────────────────────────
    elif action == "network":
        if target == "flushdns":
            success, output = _run_powershell('ipconfig /flushdns', admin=True)
            return "🧹 DNS cache limpiado" if success else f"❌ Error: {output}"
        elif target == "reset":
            success, output = _run_powershell('netsh winsock reset && netsh int ip reset', admin=True)
            return "🔁 Red reiniciada (requiere reinicio)" if success else f"❌ Error: {output}"
        elif target == "status":
            success, output = _run_powershell('Get-NetIPConfiguration')
            return f"📊 Estado de red:\n{output}" if success else f"❌ Error: {output}"
        else:
            return "ℹ️ Red: flushdns, reset, status"
    
    # ─── ABRIR APLICACIÓN ────────────────────────────────────────
    elif action == "app":
        if target == "powershell":
            os.system("start powershell")
            return "🖥️ PowerShell abierto"
        elif target == "cmd" or target == "terminal":
            os.system("start cmd")
            return "⌨️ Terminal abierta"
        elif target == "explorer":
            os.system("start explorer")
            return "📁 Explorador de archivos abierto"
        elif target == "taskmgr":
            os.system("start taskmgr")
            return "🔧 Administrador de tareas abierto"
        elif target == "control":
            os.system("start control")
            return "⚙️ Panel de Control abierto"
        elif target == "device" or target == "devices":
            os.system("start devmgmt.msc")
            return "🔌 Administrador de dispositivos abierto"
        elif target == "disk":
            os.system("start diskmgmt.msc")
            return "💾 Administrador de discos abierto"
        elif target == "services":
            os.system("start services.msc")
            return "🔄 Servicios abiertos"
        elif target == "event":
            os.system("start eventvwr.msc")
            return "📋 Visor de eventos abierto"
        elif target == "calc":
            os.system("start calc")
            return "🧮 Calculadora abierta"
        elif app_path:
            try:
                os.startfile(app_path)
                return f"📂 Abriendo: {app_path}"
            except:
                return f"❌ No se pudo abrir: {app_path}"
        else:
            return "ℹ️ Apps: powershell, cmd, explorer, taskmgr, control, device, disk, services, event, calc"
    
    # ─── AYUDA ────────────────────────────────────────────────────
    else:
        return (
            "📖 Comandos disponibles para Windows Settings:\n\n"
            "🔹 Abrir configuraciones:\n"
            "  action='open' target='defender|firewall|update|network|bluetooth|privacy|system|display|sound|apps|storage|gaming|account|time|notifications|taskbar|start'\n\n"
            "🔹 Windows Defender:\n"
            "  action='defender' target='enable|disable|status|scan|fullscan|update|exclude' [path='C:\\ruta']\n\n"
            "🔹 Firewall:\n"
            "  action='firewall' target='enable|disable|status'\n\n"
            "🔹 Servicios:\n"
            "  action='service' target='nombre_servicio' value='start|stop|restart|status'\n\n"
            "🔹 Registro:\n"
            "  action='registry' target='set|get' key='ruta' value_name='nombre' [reg_value='valor']\n\n"
            "🔹 Características de Windows:\n"
            "  action='feature' target='feature_name' value='enable|disable'\n\n"
            "🔹 Energía:\n"
            "  action='power' target='high|balanced|powersaver|shutdown|restart|sleep|lock'\n\n"
            "🔹 Red:\n"
            "  action='network' target='flushdns|reset|status'\n\n"
            "🔹 Apps:\n"
            "  action='app' target='powershell|cmd|explorer|taskmgr|control|device|disk|services|event|calc' [path='ruta']\n\n"
            "📌 Ejemplos:\n"
            "  {'action':'open','target':'defender'}\n"
            "  {'action':'defender','target':'enable'}\n"
            "  {'action':'power','target':'shutdown'}\n"
            "  {'action':'service','target':'wuauserv','value':'restart'}"
        )