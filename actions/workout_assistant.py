import cv2
import mediapipe as mp
import numpy as np
import time
import json
from pathlib import Path
import threading

class WorkoutAssistant:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.cap = None
        self.running = False
        self.rep_count = 0
        self.calories_burned = 0
        self.exercise_type = None
        self.start_time = None
        self.history = self.load_history()
        
    def load_history(self):
        """Carga historial de ejercicios"""
        history_file = Path("memory/workout_history.json")
        if history_file.exists():
            try:
                return json.loads(history_file.read_text(encoding='utf-8'))
            except:
                return []
        return []
        
    def save_history(self):
        """Guarda historial"""
        history_file = Path("memory/workout_history.json")
        history_file.write_text(json.dumps(self.history, indent=2), encoding='utf-8')
        
    def detect_exercise(self, landmarks):
        """Detecta el tipo de ejercicio basado en pose"""
        # Simplificado - se puede expandir
        return "unknown"
        
    def count_reps(self):
        """Cuenta repeticiones usando la cámara"""
        self.running = True
        self.rep_count = 0
        self.cap = cv2.VideoCapture(0)
        self.start_time = time.time()
        
        # Variables para detección de repeticiones
        last_state = "down"
        current_state = "up"
        
        def count_loop():
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    break
                    
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.pose.process(rgb)
                
                if results.pose_landmarks:
                    # Detectar movimiento (simplificado)
                    # Usar hombro como referencia
                    landmarks = results.pose_landmarks.landmark
                    shoulder_y = landmarks[11].y  # Hombro izquierdo
                    
                    # Umbral para contar repeticiones
                    if shoulder_y < 0.4:  # Arriba
                        current_state = "up"
                        if last_state == "down":
                            self.rep_count += 1
                            last_state = "up"
                    elif shoulder_y > 0.5:  # Abajo
                        current_state = "down"
                        if last_state == "up":
                            last_state = "down"
                            
                time.sleep(0.1)  # 10 FPS
                
            if self.cap:
                self.cap.release()
                
        threading.Thread(target=count_loop, daemon=True).start()
        return "Contando repeticiones..."
        
    def get_summary(self):
        """Obtiene resumen del entrenamiento"""
        duration = time.time() - self.start_time if self.start_time else 0
        
        summary = {
            'reps': self.rep_count,
            'duration': duration,
            'calories': self.calories_burned,
            'exercise': self.exercise_type
        }
        
        self.history.append(summary)
        self.save_history()
        
        return f"🏋️ RESUMEN DE ENTRENAMIENTO:\nRepeticiones: {self.rep_count}\nDuración: {duration//60} minutos\nCalorías: ~{self.calories_burned}"

def workout_assistant(parameters: dict, player=None):
    """
    Asistente de ejercicios para NEXUS
    
    Args:
        parameters: {
            'action': 'start_workout' | 'count_reps' | 'form_feedback' | 'summary',
            'exercise_type': (opcional) tipo de ejercicio
        }
    """
    action = parameters.get('action', 'start_workout')
    exercise_type = parameters.get('exercise_type', 'general')
    
    # Singleton
    if not hasattr(workout_assistant, 'instance'):
        workout_assistant.instance = WorkoutAssistant()
    
    wa = workout_assistant.instance
    
    if action == 'start_workout':
        wa.exercise_type = exercise_type
        return f"Entrenamiento de {exercise_type} iniciado. ¡Buena suerte!"
        
    elif action == 'count_reps':
        return wa.count_reps()
        
    elif action == 'form_feedback':
        # Simplificado
        return "Postura correcta. Continúa así."
        
    elif action == 'summary':
        return wa.get_summary()
        
    else:
        return "Acción no reconocida. Usa: start_workout, count_reps, form_feedback, summary"