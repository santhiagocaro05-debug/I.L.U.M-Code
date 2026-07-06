import asyncio
import threading
import time
import json
from pathlib import Path
from datetime import datetime
import speech_recognition as sr
from google import genai
import pyautogui
import numpy as np

class MeetingBot:
    def __init__(self):
        self.recording = False
        self.transcript = []
        self.summary = ""
        self.meeting_name = ""
        self.recognizer = sr.Recognizer()
        self.client = None
        self.api_key = ""
        
    def set_api_key(self, api_key):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        
    def start_recording(self, meeting_name="Reunión"):
        """Inicia la grabación de audio del sistema"""
        self.meeting_name = meeting_name
        self.recording = True
        self.transcript = []
        
        def record_loop():
            # Usar el micrófono del sistema
            with sr.Microphone() as source:
                print("🎙️ Grabando reunión...")
                self.recognizer.adjust_for_ambient_noise(source)
                
                while self.recording:
                    try:
                        audio = self.recognizer.listen(source, timeout=5)
                        text = self.recognizer.recognize_google(audio, language='es-ES')
                        timestamp = datetime.now().isoformat()
                        self.transcript.append({
                            'timestamp': timestamp,
                            'text': text,
                            'speaker': 'unknown'  # Se puede mejorar con diarización
                        })
                        print(f"📝 {text}")
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as e:
                        print(f"Error: {e}")
                        continue
                        
        threading.Thread(target=record_loop, daemon=True).start()
        return f"Grabando reunión: {meeting_name}"
    
    def stop_recording(self):
        """Detiene la grabación"""
        self.recording = False
        return f"Grabación detenida. {len(self.transcript)} segmentos transcritos."
    
    def summarize(self):
        """Genera un resumen de la reunión usando Gemini"""
        if not self.transcript:
            return "No hay transcripción para resumir"
            
        # Unir todos los textos
        full_text = "\n".join([f"[{t['timestamp']}] {t['text']}" for t in self.transcript])
        
        prompt = f"""
        Analiza esta transcripción de reunión y genera:
        1. Resumen ejecutivo (3-5 líneas)
        2. Puntos clave discutidos
        3. Decisiones tomadas
        4. Tareas asignadas (con responsables si se mencionan)
        5. Próximos pasos
        
        Transcripción:
        {full_text}
        """
        
        if not self.client:
            return "API Key no configurada"
            
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        self.summary = response.text
        
        # Guardar resumen
        summary_file = Path("memory/meeting_summaries.json")
        summaries = []
        if summary_file.exists():
            summaries = json.loads(summary_file.read_text(encoding="utf-8"))
            
        summaries.append({
            'meeting_name': self.meeting_name,
            'date': datetime.now().isoformat(),
            'summary': self.summary,
            'full_transcript': full_text
        })
        
        summary_file.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
        
        return self.summary
    
    def export_notes(self, format='txt'):
        """Exporta las notas de la reunión"""
        if not self.transcript:
            return "No hay datos para exportar"
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"meeting_notes_{self.meeting_name}_{timestamp}"
        
        if format == 'txt':
            with open(f"{filename}.txt", 'w', encoding='utf-8') as f:
                f.write(f"REUNIÓN: {self.meeting_name}\n")
                f.write(f"FECHA: {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")
                f.write("TRANSCRIPCIÓN:\n")
                for t in self.transcript:
                    f.write(f"[{t['timestamp']}] {t['text']}\n")
                f.write("\n" + "=" * 50 + "\n")
                f.write("RESUMEN:\n")
                f.write(self.summary)
                
        elif format == 'json':
            data = {
                'meeting_name': self.meeting_name,
                'date': datetime.now().isoformat(),
                'transcript': self.transcript,
                'summary': self.summary
            }
            with open(f"{filename}.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        return f"Notas exportadas a {filename}.{format}"

def meeting_bot(parameters: dict, player=None):
    """
    Bot de reuniones para NEXUS
    
    Args:
        parameters: {
            'action': 'join' | 'transcribe' | 'summarize' | 'export_notes',
            'meeting_name': (opcional) nombre de la reunión,
            'format': (opcional) 'txt' o 'json'
        }
    """
    action = parameters.get('action', 'join')
    meeting_name = parameters.get('meeting_name', 'Reunión')
    format_type = parameters.get('format', 'txt')
    
    # Singleton
    if not hasattr(meeting_bot, 'instance'):
        meeting_bot.instance = MeetingBot()
        try:
            from main import _get_api_key
            meeting_bot.instance.set_api_key(_get_api_key())
        except:
            pass
    
    bot = meeting_bot.instance
    
    if action == 'join':
        return bot.start_recording(meeting_name)
    elif action == 'transcribe':
        # Solo muestra el estado actual
        count = len(bot.transcript)
        return f"Transcripción activa: {count} segmentos grabados"
    elif action == 'summarize':
        bot.stop_recording()
        return bot.summarize()
    elif action == 'export_notes':
        return bot.export_notes(format_type)
    else:
        return "Acción no reconocida. Usa: join, transcribe, summarize, export_notes"