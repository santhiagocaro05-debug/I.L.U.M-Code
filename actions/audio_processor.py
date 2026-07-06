import numpy as np
import sounddevice as sd
import noisereduce as nr
from scipy import signal
import audioop
import wave
import threading
import time
from pathlib import Path

class AudioProcessor:
    def __init__(self):
        self.noise_profile = None
        self.processing = False
        self.filtered_stream = None
        self.raw_audio_buffer = []
        self.processed_audio_buffer = []
        self.sample_rate = 16000
        
    def capture_noise_profile(self, duration=2.0):
        """Captura el perfil de ruido de fondo"""
        print("🎤 Capturando perfil de ruido... (habla en 2 segundos)")
        audio = sd.rec(int(duration * self.sample_rate), 
                       samplerate=self.sample_rate, 
                       channels=1, 
                       dtype='float32')
        sd.wait()
        self.noise_profile = audio.flatten()
        return "Perfil de ruido capturado"
    
    def reduce_noise(self, audio_data, sample_rate=None):
        """Reduce el ruido usando noisereduce"""
        if self.noise_profile is None:
            return audio_data
            
        if sample_rate is None:
            sample_rate = self.sample_rate
            
        # Reducir ruido
        reduced = nr.reduce_noise(
            y=audio_data,
            sr=sample_rate,
            y_noise=self.noise_profile,
            prop_decrease=0.8,
            n_fft=1024,
            win_length=512,
            hop_length=256
        )
        return reduced
    
    def process_audio_stream(self, indata, frames, time_info, status):
        """Callback para procesar audio en tiempo real"""
        if not self.processing:
            return
            
        # Convertir a float32 para procesar
        audio_float = indata.flatten().astype(np.float32)
        
        # Reducir ruido
        processed = self.reduce_noise(audio_float)
        
        # Convertir de vuelta a int16
        processed_int16 = (processed * 32767).astype(np.int16)
        
        # Encolar para salida
        self.processed_audio_buffer.append(processed_int16.tobytes())
        
    def start_processing(self):
        """Inicia el procesamiento de audio en tiempo real"""
        self.processing = True
        
        def processing_thread():
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                callback=self.process_audio_stream,
                blocksize=1024
            )
            with stream:
                while self.processing:
                    time.sleep(0.1)
                    
        threading.Thread(target=processing_thread, daemon=True).start()
        return "Procesamiento de audio iniciado"
    
    def stop_processing(self):
        """Detiene el procesamiento de audio"""
        self.processing = False
        return "Procesamiento de audio detenido"
    
    def save_processed_audio(self, filename="processed_audio.wav"):
        """Guarda el audio procesado"""
        if not self.processed_audio_buffer:
            return "No hay audio procesado para guardar"
            
        audio_data = b''.join(self.processed_audio_buffer)
        
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data)
            
        return f"Audio guardado en {filename}"

def audio_processor(parameters: dict, player=None):
    """
    Procesador de audio para NEXUS
    
    Args:
        parameters: {
            'action': 'capture_noise' | 'start' | 'stop' | 'save',
            'duration': (opcional) segundos para capturar ruido
        }
    """
    action = parameters.get('action', 'start')
    duration = parameters.get('duration', 2.0)
    
    # Singleton
    if not hasattr(audio_processor, 'instance'):
        audio_processor.instance = AudioProcessor()
    
    processor = audio_processor.instance
    
    if action == 'capture_noise':
        return processor.capture_noise_profile(duration)
    elif action == 'start':
        return processor.start_processing()
    elif action == 'stop':
        return processor.stop_processing()
    elif action == 'save':
        filename = parameters.get('filename', 'processed_audio.wav')
        return processor.save_processed_audio(filename)
    else:
        return "Acción no reconocida. Usa: capture_noise, start, stop, save"