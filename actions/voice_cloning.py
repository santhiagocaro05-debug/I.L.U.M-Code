import json
import os
import threading
import time
from pathlib import Path
import numpy as np
import sounddevice as sd
import soundfile as sf
from TTS.api import TTS
import requests
import base64

class VoiceCloner:
    def __init__(self):
        self.tts_model = None
        self.voice_samples = []
        self.voice_profile = None
        self.target_language = 'es'
        self.languages = {
            'es': 'español',
            'en': 'inglés',
            'fr': 'francés',
            'de': 'alemán',
            'it': 'italiano',
            'pt': 'portugués',
            'ja': 'japonés',
            'zh': 'chino'
        }
        
    def load_model(self):
        """Carga el modelo XTTS-v2 para clonación de voz"""
        try:
            self.tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            return True
        except Exception as e:
            print(f"Error cargando modelo XTTS: {e}")
            return False
            
    def record_voice_sample(self, duration=10):
        """Graba una muestra de voz para entrenamiento"""
        print(f"🎤 Grabando muestra de voz ({duration} segundos)...")
        print("Habla de forma natural y clara")
        
        audio = sd.rec(int(duration * 16000), 
                      samplerate=16000, 
                      channels=1, 
                      dtype='float32')
        sd.wait()
        
        # Guardar muestra
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"voice_sample_{timestamp}.wav"
        sf.write(filename, audio, 16000)
        
        self.voice_samples.append({
            'filename': filename,
            'duration': duration,
            'timestamp': timestamp
        })
        
        print(f"✅ Muestra guardada: {filename}")
        return filename
        
    def train_voice(self):
        """Entrena el modelo con las muestras de voz"""
        if not self.voice_samples:
            return "No hay muestras de voz para entrenar"
            
        # Usar la última muestra para entrenamiento
        sample_path = self.voice_samples[-1]['filename']
        
        if not os.path.exists(sample_path):
            return f"Archivo no encontrado: {sample_path}"
            
        # XTTS entrena automáticamente con la muestra
        self.voice_profile = sample_path
        return f"Voz entrenada con {sample_path}"
        
    def speak_multilingual(self, text, language='es'):
        """Habla en múltiples idiomas con la voz clonada"""
        if not self.voice_profile or not self.tts_model:
            return "Modelo de voz no cargado o entrenado"
            
        # Mapear código de idioma a nombre completo
        lang_name = self.languages.get(language, 'es')
        
        try:
            # Sintetizar voz
            output_path = f"tts_output_{int(time.time())}.wav"
            self.tts_model.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=self.voice_profile,
                language=lang_name
            )
            
            # Reproducir
            audio, fs = sf.read(output_path)
            sd.play(audio, fs)
            sd.wait()
            
            return f"Voz generada en {lang_name}: {text[:50]}..."
            
        except Exception as e:
            return f"Error en síntesis de voz: {e}"
            
    def list_languages(self):
        """Lista los idiomas soportados"""
        result = "Idiomas soportados para clonación de voz:\n"
        for code, name in self.languages.items():
            result += f"  • {code}: {name}\n"
        return result

def voice_cloning(parameters: dict, player=None):
    """
    Clonación de voz multilingüe para NEXUS
    
    Args:
        parameters: {
            'action': 'train' | 'speak' | 'languages',
            'text': (opcional) texto para speak,
            'language': (opcional) código de idioma,
            'duration': (opcional) duración de grabación
        }
    """
    action = parameters.get('action', 'languages')
    text = parameters.get('text', '')
    language = parameters.get('language', 'es')
    duration = parameters.get('duration', 10)
    
    # Singleton
    if not hasattr(voice_cloning, 'instance'):
        voice_cloning.instance = VoiceCloner()
        voice_cloning.instance.load_model()
    
    cloner = voice_cloning.instance
    
    if action == 'train':
        result = cloner.record_voice_sample(duration)
        return cloner.train_voice()
    elif action == 'speak':
        if not text:
            return "Proporciona un texto para hablar"
        return cloner.speak_multilingual(text, language)
    elif action == 'languages':
        return cloner.list_languages()
    else:
        return "Acción no reconocida. Usa: train, speak, languages"