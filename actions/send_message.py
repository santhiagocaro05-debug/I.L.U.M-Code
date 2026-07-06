"""
send_message.py — Envío de mensajes multi-plataforma
Soporta: Telegram, Discord, Signal
"""

import json
import requests
import time
from pathlib import Path

# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
MESSAGES_CONFIG = Path(__file__).resolve().parent.parent / "config" / "messages.json"

def _get_config() -> dict:
    """Carga la configuración de mensajes."""
    if MESSAGES_CONFIG.exists():
        try:
            return json.loads(MESSAGES_CONFIG.read_text(encoding="utf-8"))
        except:
            pass
    
    default = {
        "telegram": {"bot_token": "", "chat_ids": {}},
        "discord": {"webhooks": {}},
        "signal": {"phone": "", "password": ""}
    }
    MESSAGES_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    MESSAGES_CONFIG.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default

def _save_config(config: dict):
    """Guarda la configuración."""
    MESSAGES_CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")

# ─── FUNCIONES DE ENVÍO ────────────────────────────────────────────────────

def _send_telegram(chat_id: str, message: str, token: str) -> bool:
    """Envía un mensaje por Telegram."""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def _send_discord(webhook_url: str, message: str) -> bool:
    """Envía un mensaje por Discord."""
    try:
        payload = {"content": message}
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code == 204
    except:
        return False

def _send_signal(phone: str, message: str, password: str) -> bool:
    """Envía un mensaje por Signal."""
    # Signal no tiene API pública simple
    # Esto es un placeholder - se requiere signal-cli
    return False

# ─── FUNCIÓN PRINCIPAL ──────────────────────────────────────────────────────

def send_message(parameters: dict, response=None, player=None, session_memory=None) -> str:
    """
    Envía mensajes a través de múltiples plataformas.
    
    Acciones:
    - send: Envía un mensaje
    - test: Prueba la conexión
    - config: Configura credenciales
    """
    
    action = parameters.get("action", "send").lower().strip()
    platform = parameters.get("platform", "").lower().strip()
    receiver = parameters.get("receiver", "")
    message = parameters.get("message_text", "") or parameters.get("message", "")
    
    config = _get_config()
    
    # ─── MAPEO DE ACCIONES ──────────────────────────────────────────────────
    
    # 1. ENVIAR MENSAJE
    if action == "send":
        if not platform:
            return "❌ Se requiere 'platform' (telegram, discord, signal)"
        if not receiver:
            return "❌ Se requiere 'receiver' (chat_id, webhook, número)"
        if not message:
            return "❌ Se requiere 'message_text'"
        
        if player: player.write_log(f"📤 Enviando mensaje a {receiver} via {platform}...")
        
        if platform == "telegram":
            token = config.get("telegram", {}).get("bot_token", "")
            if not token:
                return "❌ Telegram: Bot Token no configurado."
            
            # Verificar si el receiver es un nombre guardado
            chat_ids = config.get("telegram", {}).get("chat_ids", {})
            chat_id = chat_ids.get(receiver, receiver)
            
            if _send_telegram(chat_id, message, token):
                return f"✅ Mensaje enviado a {receiver} por Telegram."
            else:
                return "❌ Error enviando mensaje por Telegram."
        
        elif platform == "discord":
            webhooks = config.get("discord", {}).get("webhooks", {})
            webhook_url = webhooks.get(receiver, receiver)
            
            if not webhook_url:
                return "❌ Discord: Webhook no configurado para este receptor."
            
            if _send_discord(webhook_url, message):
                return f"✅ Mensaje enviado a {receiver} por Discord."
            else:
                return "❌ Error enviando mensaje por Discord."
        
        elif platform == "signal":
            phone = config.get("signal", {}).get("phone", "")
            password = config.get("signal", {}).get("password", "")
            
            if not phone or not password:
                return "❌ Signal: Credenciales no configuradas."
            
            if _send_signal(phone, message, password):
                return f"✅ Mensaje enviado a {receiver} por Signal."
            else:
                return "❌ Signal no está configurado o no es compatible."
        
        else:
            return f"❌ Plataforma '{platform}' no soportada. Opciones: telegram, discord, signal"
    
    # 2. CONFIGURAR
    elif action == "config":
        if platform == "telegram":
            token = parameters.get("token", "")
            if token:
                config["telegram"]["bot_token"] = token
                _save_config(config)
                return "✅ Token de Telegram configurado."
            else:
                return "❌ Se requiere 'token' para Telegram."
        
        elif platform == "discord":
            webhook = parameters.get("webhook", "")
            name = parameters.get("name", "default")
            if webhook:
                config["discord"]["webhooks"][name] = webhook
                _save_config(config)
                return f"✅ Webhook de Discord configurado para '{name}'."
            else:
                return "❌ Se requiere 'webhook' para Discord."
        
        elif platform == "signal":
            phone = parameters.get("phone", "")
            password = parameters.get("password", "")
            if phone and password:
                config["signal"]["phone"] = phone
                config["signal"]["password"] = password
                _save_config(config)
                return "✅ Credenciales de Signal configuradas."
            else:
                return "❌ Se requiere 'phone' y 'password' para Signal."
        
        else:
            return "❌ Plataforma no soportada para configuración."
    
    # 3. TEST
    elif action == "test":
        if not platform:
            return "❌ Se requiere 'platform' para probar."
        
        if platform == "telegram":
            token = config.get("telegram", {}).get("bot_token", "")
            if not token:
                return "❌ Token de Telegram no configurado."
            
            try:
                url = f"https://api.telegram.org/bot{token}/getMe"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    bot_info = response.json()
                    return f"✅ Conexión a Telegram exitosa. Bot: {bot_info.get('result', {}).get('username', 'N/A')}"
                else:
                    return "❌ Error conectando a Telegram."
            except:
                return "❌ Error conectando a Telegram."
        
        elif platform == "discord":
            webhook_url = parameters.get("webhook", "") or config.get("discord", {}).get("webhooks", {}).get("default", "")
            if not webhook_url:
                return "❌ Webhook de Discord no configurado."
            
            try:
                response = requests.get(webhook_url, timeout=10)
                if response.status_code == 200:
                    return f"✅ Conexión a Discord exitosa. Webhook: {response.json().get('name', 'N/A')}"
                else:
                    return "❌ Error conectando a Discord."
            except:
                return "❌ Error conectando a Discord."
        
        else:
            return f"❌ Test no soportado para '{platform}'."
    
    # 4. STATUS
    elif action == "status":
        telegram_ok = bool(config.get("telegram", {}).get("bot_token"))
        discord_ok = bool(config.get("discord", {}).get("webhooks"))
        signal_ok = bool(config.get("signal", {}).get("phone") and config.get("signal", {}).get("password"))
        
        return f"""
📊 ESTADO DE MENSAJERÍA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 Telegram: {'✅ Configurado' if telegram_ok else '❌ No configurado'}
💬 Discord: {'✅ Configurado' if discord_ok else '❌ No configurado'}
📶 Signal: {'✅ Configurado' if signal_ok else '❌ No configurado'}

📋 Acciones disponibles:
  • send → Enviar mensaje
  • config → Configurar plataforma
  • test → Probar conexión
  • status → Estado actual

📝 Ejemplos:
  {"action": "send", "platform": "telegram", "receiver": "@usuario", "message_text": "Hola!"}
  {"action": "config", "platform": "telegram", "token": "TU_TOKEN"}
  {"action": "test", "platform": "discord", "webhook": "TU_WEBHOOK"}
"""
    
    # 5. HELP
    else:
        return """
🎯 SEND MESSAGE - Comandos:

📤 Envío:
  • send → Envía un mensaje
  • config → Configura credenciales
  • test → Prueba conexión
  • status → Estado del sistema

📱 Plataformas soportadas:
  telegram, discord, signal

📝 Ejemplos:
  {"action": "send", "platform": "telegram", "receiver": "123456789", "message_text": "Hola Mundo"}
  {"action": "config", "platform": "telegram", "token": "BOT_TOKEN"}
  {"action": "test", "platform": "discord"}
"""
