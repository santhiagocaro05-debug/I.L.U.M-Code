import json
import requests
import threading
import time
import asyncio
from pathlib import Path
from datetime import datetime
from collections import deque
import re
from typing import Optional, Dict, List
import obsws_python as obs
from twitchio.ext import commands
from twitchio.client import Client
from twitchio import Channel, User
from google import genai
import numpy as np
from dataclasses import dataclass
from enum import Enum
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamStatus(Enum):
    OFFLINE = "offline"
    LIVE = "live"
    STARTING = "starting"
    ENDING = "ending"

@dataclass
class ChatMessage:
    """Estructura de mensaje de chat"""
    author: str
    content: str
    timestamp: datetime
    is_sub: bool = False
    is_mod: bool = False
    bits: int = 0
    emotes: List[str] = None

@dataclass
class DonationAlert:
    """Estructura de donación"""
    donor: str
    amount: float
    currency: str
    message: str
    timestamp: datetime

class TwitchChatBot(commands.Bot):
    """Bot real de Twitch usando TwitchIO"""
    
    def __init__(self, token, client_id, client_secret, channels, nexus_controller):
        self.nexus = nexus_controller
        super().__init__(
            token=token,
            client_id=client_id,
            client_secret=client_secret,
            prefix='!',
            initial_channels=channels
        )
        
    async def event_ready(self):
        """Bot conectado y listo"""
        logger.info(f'✅ Bot conectado como {self.nick}')
        logger.info(f'📡 Canales: {self.connected_channels}')
        
    async def event_message(self, message):
        """Procesa cada mensaje del chat"""
        if message.echo:
            return
            
        # Crear objeto ChatMessage
        chat_msg = ChatMessage(
            author=message.author.name if message.author else "Unknown",
            content=message.content,
            timestamp=datetime.now(),
            is_sub=message.author.is_subscriber if message.author else False,
            is_mod=message.author.is_mod if message.author else False,
            bits=message.bits if hasattr(message, 'bits') else 0
        )
        
        # Enviar a NEXUS para procesamiento
        await self.nexus.process_chat_message(chat_msg, message.channel.name)
        
        # Comandos del bot
        await self.handle_commands(message)
        
    async def handle_commands(self, message):
        """Maneja comandos personalizados"""
        content = message.content.lower()
        
        if content == '!nexus':
            await message.channel.send("🦾 NEXUS AI está aquí! Pregúntame lo que quieras.")
            
        elif content.startswith('!pregunta '):
            question = message.content[10:]
            response = await self.nexus.ai_response(question)
            await message.channel.send(f"@{message.author.name} {response[:500]}")
            
        elif content == '!stream':
            status = self.nexus.get_stream_status()
            await message.channel.send(f"🎥 Stream: {status}")
            
        elif content == '!redes':
            await message.channel.send(
                "🌐 Síguenos: Twitter: @nexus_ai | Discord: discord.gg/nexus | GitHub: github.com/nexus"
            )

class OBSController:
    """Control real de OBS via obs-websocket"""
    
    def __init__(self, host='localhost', port=4455, password=None):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
        self.connected = False
        
    def connect(self):
        """Conecta con OBS"""
        try:
            self.client = obs.ReqClient(
                host=self.host,
                port=self.port,
                password=self.password
            )
            self.connected = True
            logger.info("✅ Conectado a OBS Studio")
            return True
        except Exception as e:
            logger.error(f"❌ Error conectando a OBS: {e}")
            return False
    
    def get_scenes(self):
        """Obtiene lista de escenas"""
        if not self.connected:
            return []
        try:
            scenes = self.client.get_scene_list()
            return [scene['sceneName'] for scene in scenes.scenes]
        except:
            return []
    
    def switch_scene(self, scene_name):
        """Cambia a una escena específica"""
        if not self.connected:
            return False
        try:
            self.client.set_current_program_scene(scene_name)
            logger.info(f"🎬 Escena cambiada a: {scene_name}")
            return True
        except Exception as e:
            logger.error(f"Error cambiando escena: {e}")
            return False
    
    def start_stream(self):
        """Inicia transmisión"""
        if not self.connected:
            return False
        try:
            self.client.start_stream()
            logger.info("🔴 Transmisión iniciada")
            return True
        except Exception as e:
            logger.error(f"Error iniciando stream: {e}")
            return False
    
    def stop_stream(self):
        """Detiene transmisión"""
        if not self.connected:
            return False
        try:
            self.client.stop_stream()
            logger.info("⏹️ Transmisión detenida")
            return True
        except Exception as e:
            logger.error(f"Error deteniendo stream: {e}")
            return False
    
    def get_stream_status(self):
        """Obtiene estado del stream"""
        if not self.connected:
            return None
        try:
            status = self.client.get_stream_status()
            return {
                'active': status.output_active,
                'time': status.output_timecode if status.output_active else None,
                'fps': status.output_skipped_frames if hasattr(status, 'output_skipped_frames') else 0
            }
        except:
            return None
    
    def toggle_mute(self, source_name):
        """Silencia/activa fuente de audio"""
        if not self.connected:
            return False
        try:
            current_mute = self.client.get_input_mute(source_name)
            self.client.set_input_mute(source_name, not current_mute.input_muted)
            return True
        except:
            return False
    
    def show_source(self, source_name, visible=True):
        """Muestra/oculta fuente"""
        if not self.connected:
            return False
        try:
            self.client.set_scene_item_enabled(
                self.get_current_scene(),
                source_name,
                visible
            )
            return True
        except:
            return False

class StreamAnalytics:
    """Análisis inteligente del chat y stream"""
    
    def __init__(self, max_messages=100):
        self.messages = deque(maxlen=max_messages)
        self.donations = deque(maxlen=50)
        self.spam_detector = {}
        self.sentiment_history = []
        
    def add_message(self, msg: ChatMessage):
        """Agrega mensaje para análisis"""
        self.messages.append(msg)
        self._check_spam(msg)
        self._analyze_sentiment(msg)
        
    def _check_spam(self, msg: ChatMessage):
        """Detecta spam en el chat"""
        author = msg.author
        content = msg.content.lower()
        
        if author not in self.spam_detector:
            self.spam_detector[author] = {
                'messages': deque(maxlen=10),
                'repeated': 0,
                'last_time': time.time()
            }
        
        user_data = self.spam_detector[author]
        user_data['messages'].append(content)
        
        # Verificar mensajes repetidos
        if content in user_data['messages']:
            user_data['repeated'] += 1
        
        # Verificar frecuencia
        current_time = time.time()
        if current_time - user_data['last_time'] < 0.5:  # Mensajes muy rápidos
            user_data['repeated'] += 2
        
        user_data['last_time'] = current_time
        
        if user_data['repeated'] > 5:
            logger.warning(f"⚠️ Posible spam detectado: {author}")
            return True
        return False
    
    def _analyze_sentiment(self, msg: ChatMessage):
        """Análisis básico de sentimiento"""
        positive_words = ['bueno', 'genial', 'excelente', 'amazing', 'good', 'love', '❤️', '🔥']
        negative_words = ['malo', 'horrible', 'bad', 'hate', '👎', '💩']
        
        content_lower = msg.content.lower()
        score = 0
        
        for word in positive_words:
            if word in content_lower:
                score += 1
        for word in negative_words:
            if word in content_lower:
                score -= 1
        
        self.sentiment_history.append({
            'timestamp': msg.timestamp,
            'score': score,
            'author': msg.author
        })
    
    def get_chat_summary(self):
        """Genera resumen del chat"""
        if not self.messages:
            return "No hay mensajes recientes"
        
        # Palabras más mencionadas
        all_words = []
        for msg in self.messages:
            words = msg.content.lower().split()
            all_words.extend([w for w in words if len(w) > 3])
        
        word_freq = {}
        for word in all_words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Usuarios más activos
        user_activity = {}
        for msg in self.messages:
            user_activity[msg.author] = user_activity.get(msg.author, 0) + 1
        
        top_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]
        
        summary = "📊 **Resumen del chat:**\n"
        summary += f"📝 Mensajes recientes: {len(self.messages)}\n\n"
        
        summary += "🔥 **Temas populares:**\n"
        for word, freq in top_words:
            summary += f"• {word}: {freq} veces\n"
        
        summary += "\n👥 **Usuarios más activos:**\n"
        for user, msgs in top_users:
            summary += f"• {user}: {msgs} mensajes\n"
        
        # Sentimiento general
        if self.sentiment_history:
            avg_sentiment = np.mean([s['score'] for s in self.sentiment_history])
            sentiment_text = "positivo 😊" if avg_sentiment > 0 else "negativo 😟" if avg_sentiment < 0 else "neutral 😐"
            summary += f"\n😊 **Sentimiento general:** {sentiment_text}"
        
        return summary
    
    def add_donation(self, donation: DonationAlert):
        """Registra donación"""
        self.donations.append(donation)

class RealStreamController:
    """Controlador REAL de streaming con todas las funciones"""
    
    def __init__(self):
        # Configuración
        self.config = self.load_config()
        
        # OBS Controller
        self.obs = OBSController(
            password=self.config.get('obs_password')
        )
        
        # Analytics
        self.analytics = StreamAnalytics()
        
        # Bot de Twitch
        self.bot = None
        
        # IA
        self.ai_client = None
        self.init_ai()
        
        # Estado
        self.stream_status = StreamStatus.OFFLINE
        self.current_viewers = 0
        self.stream_start_time = None
        
    def load_config(self):
        """Carga configuración completa"""
        config_file = Path("config/twitch.json")
        if config_file.exists():
            try:
                return json.loads(config_file.read_text(encoding='utf-8'))
            except:
                pass
        return {}
    
    def init_ai(self):
        """Inicializa Gemini"""
        try:
            from main import _get_api_key
            self.ai_client = genai.Client(api_key=_get_api_key())
        except:
            logger.warning("IA no disponible")
    
    def connect_obs(self):
        """Conecta con OBS Studio"""
        if self.obs.connect():
            scenes = self.obs.get_scenes()
            logger.info(f"Escenas disponibles: {scenes}")
            return True
        return False
    
    def start_twitch_bot(self):
        """Inicia el bot de Twitch"""
        token = self.config.get('access_token')
        client_id = self.config.get('client_id')
        client_secret = self.config.get('client_secret')
        channels = self.config.get('channels', [])
        
        if not all([token, client_id, client_secret, channels]):
            logger.error("Falta configuración para el bot")
            return False
        
        try:
            self.bot = TwitchChatBot(
                token=token,
                client_id=client_id,
                client_secret=client_secret,
                channels=channels,
                nexus_controller=self
            )
            
            # Ejecutar bot en thread separado
            bot_thread = threading.Thread(
                target=self.bot.run,
                daemon=True
            )
            bot_thread.start()
            
            logger.info("✅ Bot de Twitch iniciado")
            return True
        except Exception as e:
            logger.error(f"Error iniciando bot: {e}")
            return False
    
    async def process_chat_message(self, msg: ChatMessage, channel: str):
        """Procesa mensajes del chat en tiempo real"""
        # Agregar a analytics
        self.analytics.add_message(msg)
        
        # Detectar comandos especiales
        content = msg.content.lower()
        
        # Saludar a NEXUS
        if 'hola nexus' in content or 'hey nexus' in content:
            response = await self.generate_response(
                f"Saluda a {msg.author} de forma amigable"
            )
            if self.bot:
                channel_obj = self.bot.get_channel(channel)
                if channel_obj:
                    await channel_obj.send(f"@{msg.author} {response[:400]}")
        
        # Detectar preguntas
        if '?' in content and len(content) > 10:
            response = await self.generate_response(content)
            # No responder automáticamente a todas las preguntas para no spammear
    
    async def generate_response(self, message: str) -> str:
        """Genera respuesta con IA"""
        if not self.ai_client:
            return "IA no disponible"
        
        try:
            response = self.ai_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"""Eres NEXUS, un asistente IA en un stream de Twitch.
                Responde de forma amigable, concisa y en español.
                Máximo 400 caracteres.
                Mensaje: {message}"""
            )
            return response.text
        except:
            return "Procesando..."
    
    def get_stream_status(self) -> str:
        """Obtiene estado actual del stream"""
        if self.stream_status == StreamStatus.LIVE:
            elapsed = time.time() - self.stream_start_time if self.stream_start_time else 0
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            
            obs_status = self.obs.get_stream_status()
            
            status = f"🔴 EN VIVO - {hours}h {minutes}m"
            if obs_status:
                status += f"\n📊 FPS: {obs_status.get('fps', 'N/A')}"
            status += f"\n👥 Viewers: {self.current_viewers}"
            return status
        else:
            return "⚫ OFFLINE"
    
    def control_scene(self, scene_name: str):
        """Controla escenas de OBS"""
        if not self.obs.connected:
            return "OBS no conectado"
        
        if self.obs.switch_scene(scene_name):
            return f"🎬 Escena cambiada a: {scene_name}"
        return "Error cambiando escena"

def stream_control(parameters: dict, player=None):
    """
    Control REAL de streaming para NEXUS
    
    Args:
        parameters: {
            'action': 'start_stream' | 'stop_stream' | 'switch_scene' | 
                      'read_chat' | 'chat_summary' | 'toggle_mute' |
                      'stream_status' | 'show_source' | 'hide_source',
            'scene_name': str (para cambiar escenas),
            'source_name': str (para mostrar/ocultar fuentes),
            'channel': str (canal de Twitch)
        }
    """
    action = parameters.get('action', 'stream_status')
    
    # Singleton
    if not hasattr(stream_control, 'instance'):
        stream_control.instance = RealStreamController()
        stream_control.instance.connect_obs()
    
    sc = stream_control.instance
    
    try:
        if action == 'start_stream':
            if sc.obs.start_stream():
                sc.stream_status = StreamStatus.LIVE
                sc.stream_start_time = time.time()
                return "🔴 ¡Stream iniciado correctamente!"
            return "❌ Error al iniciar stream"
        
        elif action == 'stop_stream':
            if sc.obs.stop_stream():
                sc.stream_status = StreamStatus.OFFLINE
                return "⏹️ Stream detenido"
            return "❌ Error al detener stream"
        
        elif action == 'switch_scene':
            scene = parameters.get('scene_name')
            if not scene:
                return "Especifica el nombre de la escena"
            return sc.control_scene(scene)
        
        elif action == 'read_chat':
            if not sc.bot:
                return "Bot de chat no iniciado"
            return "📡 Leyendo chat en tiempo real..."
        
        elif action == 'chat_summary':
            return sc.analytics.get_chat_summary()
        
        elif action == 'stream_status':
            return sc.get_stream_status()
        
        elif action == 'toggle_mute':
            source = parameters.get('source_name', 'Mic/Aux')
            if sc.obs.toggle_mute(source):
                return f"🔇 Fuente {source} silenciada/activada"
            return "Error controlando audio"
        
        elif action == 'show_source':
            source = parameters.get('source_name')
            if source and sc.obs.show_source(source, True):
                return f"👁️ Mostrando {source}"
            return "Error mostrando fuente"
        
        elif action == 'hide_source':
            source = parameters.get('source_name')
            if source and sc.obs.show_source(source, False):
                return f"🙈 Ocultando {source}"
            return "Error ocultando fuente"
        
        elif action == 'start_bot':
            if sc.start_twitch_bot():
                return "🤖 Bot de Twitch iniciado"
            return "Error iniciando bot"
        
        else:
            return "Acción no reconocida"
            
    except Exception as e:
        return f"❌ Error: {str(e)}"

