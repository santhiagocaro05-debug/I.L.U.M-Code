import requests
import json
import threading
import time
from pathlib import Path

class WebhookManager:
    def __init__(self):
        self.webhooks = {}
        self.load_webhooks()
        
    def load_webhooks(self):
        """Carga webhooks configurados"""
        config_file = Path("config/webhooks.json")
        if config_file.exists():
            try:
                self.webhooks = json.loads(config_file.read_text(encoding="utf-8"))
            except:
                pass
                
    def save_webhooks(self):
        """Guarda configuración de webhooks"""
        config_file = Path("config/webhooks.json")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(self.webhooks, indent=2), encoding="utf-8")
        
    def add_webhook(self, name, url, headers=None):
        """Añade un webhook"""
        self.webhooks[name] = {
            'url': url,
            'headers': headers or {},
            'status': 'inactive'
        }
        self.save_webhooks()
        return f"Webhook '{name}' añadido"
        
    def trigger_webhook(self, name, payload):
        """Dispara un webhook"""
        if name not in self.webhooks:
            return f"Webhook '{name}' no encontrado"
            
        webhook = self.webhooks[name]
        url = webhook['url']
        headers = webhook['headers']
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            webhook['status'] = 'success'
            self.save_webhooks()
            return f"Webhook '{name}' disparado. Status: {response.status_code}"
        except Exception as e:
            webhook['status'] = 'error'
            self.save_webhooks()
            return f"Error en webhook: {e}"

def webhook_trigger(parameters: dict, player=None):
    """
    Disparador de webhooks para IFTTT/Zapier
    
    Args:
        parameters: {
            'url': (opcional) URL del webhook,
            'payload': (opcional) datos a enviar,
            'webhook_name': (opcional) nombre del webhook guardado,
            'action': 'trigger' | 'add_webhook'
        }
    """
    action = parameters.get('action', 'trigger')
    url = parameters.get('url')
    payload = parameters.get('payload', {})
    webhook_name = parameters.get('webhook_name', 'default')
    
    # Singleton
    if not hasattr(webhook_trigger, 'instance'):
        webhook_trigger.instance = WebhookManager()
    
    manager = webhook_trigger.instance
    
    if action == 'add_webhook':
        headers = parameters.get('headers', {})
        return manager.add_webhook(webhook_name, url, headers)
        
    elif action == 'trigger':
        if url:
            # Trigger directo
            try:
                response = requests.post(url, json=payload, timeout=10)
                return f"Webhook disparado. Status: {response.status_code}"
            except Exception as e:
                return f"Error en webhook: {e}"
        else:
            # Trigger guardado
            return manager.trigger_webhook(webhook_name, payload)
            
    else:
        return "Acción no reconocida. Usa: trigger, add_webhook"