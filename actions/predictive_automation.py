import json
import time
from pathlib import Path
from datetime import datetime, timedelta
import threading
import pandas as pd
from collections import defaultdict
import numpy as np

class PredictiveAutomation:
    def __init__(self):
        self.history = defaultdict(list)
        self.patterns = {}
        self.history_file = Path("memory/action_history.json")
        self.load_history()
        self.learning = True
        
    def load_history(self):
        """Carga el historial de acciones"""
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text(encoding="utf-8"))
                self.history = defaultdict(list, data)
            except:
                pass
                
    def save_history(self):
        """Guarda el historial"""
        self.history_file.write_text(json.dumps(dict(self.history), indent=2), encoding="utf-8")
        
    def learn_action(self, action, context=None):
        """Aprende una acción del usuario"""
        timestamp = datetime.now().isoformat()
        hour = datetime.now().hour
        
        entry = {
            'timestamp': timestamp,
            'hour': hour,
            'context': context or {},
            'action': action
        }
        
        self.history[action].append(entry)
        
        # Mantener solo los últimos 100 registros por acción
        if len(self.history[action]) > 100:
            self.history[action] = self.history[action][-100:]
            
        self.save_history()
        return "Acción aprendida"
        
    def suggest_actions(self):
        """Sugiere acciones basadas en patrones"""
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()
        suggestions = []
        
        for action, records in self.history.items():
            # Analizar patrón de hora
            hour_counts = defaultdict(int)
            day_counts = defaultdict(int)
            
            for record in records:
                hour_counts[record['hour']] += 1
                day = datetime.fromisoformat(record['timestamp']).weekday()
                day_counts[day] += 1
                
            # Calcular probabilidad de acción en esta hora
            if hour_counts:
                hour_prob = hour_counts.get(current_hour, 0) / len(records)
                
                # Calcular probabilidad de día
                day_prob = day_counts.get(current_day, 0) / len(records)
                
                # Probabilidad compuesta
                prob = (hour_prob * 0.7 + day_prob * 0.3)
                
                if prob > 0.6:  # Umbral de sugerencia
                    suggestions.append({
                        'action': action,
                        'probability': prob,
                        'times': hour_counts.get(current_hour, 0)
                    })
                    
        # Ordenar por probabilidad
        suggestions.sort(key=lambda x: x['probability'], reverse=True)
        
        return suggestions[:5]  # Top 5 sugerencias
        
    def auto_execute(self, action):
        """Auto-ejecuta una acción sugerida"""
        # Aquí se conectaría con el sistema de herramientas de NEXUS
        return f"Auto-ejecutando: {action}"
        
    def start_learning(self):
        """Inicia el aprendizaje continuo"""
        def learn_loop():
            while self.learning:
                # Monitorear acciones del usuario (simplificado)
                # En implementación real, se conectaría con el sistema de eventos
                time.sleep(60)
                
        threading.Thread(target=learn_loop, daemon=True).start()
        return "Aprendizaje continuo iniciado"

def predictive_automation(parameters: dict, player=None):
    """
    Automatización predictiva para NEXUS
    
    Args:
        parameters: {
            'action': 'learn' | 'suggest' | 'auto_execute',
            'action_name': (opcional) nombre de la acción,
            'context': (opcional) contexto de la acción
        }
    """
    action = parameters.get('action', 'suggest')
    action_name = parameters.get('action_name', '')
    context = parameters.get('context', {})
    
    # Singleton
    if not hasattr(predictive_automation, 'instance'):
        predictive_automation.instance = PredictiveAutomation()
    
    pa = predictive_automation.instance
    
    if action == 'learn':
        if not action_name:
            return "Proporciona una acción para aprender"
        return pa.learn_action(action_name, context)
        
    elif action == 'suggest':
        suggestions = pa.suggest_actions()
        if not suggestions:
            return "No hay sugerencias disponibles aún"
            
        result = "🔮 Sugerencias predictivas:\n"
        for suggestion in suggestions:
            result += f"  • {suggestion['action']} (probabilidad: {suggestion['probability']:.0%})\n"
        return result
        
    elif action == 'auto_execute':
        if not action_name:
            return "Proporciona una acción para auto-ejecutar"
        return pa.auto_execute(action_name)
        
    else:
        return "Acción no reconocida. Usa: learn, suggest, auto_execute"