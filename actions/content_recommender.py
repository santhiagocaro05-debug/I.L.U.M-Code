import json
import random
from pathlib import Path
from datetime import datetime
import requests
from google import genai

class ContentRecommender:
    def __init__(self):
        self.history = []
        self.preferences = {}
        self.recommendations = []
        self.history_file = Path("memory/content_history.json")
        self.load_history()
        self.client = None
        try:
            from main import _get_api_key
            self.client = genai.Client(api_key=_get_api_key())
        except:
            pass
            
    def load_history(self):
        """Carga el historial de contenido"""
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text(encoding="utf-8"))
                self.history = data.get('history', [])
                self.preferences = data.get('preferences', {})
            except:
                pass
                
    def save_history(self):
        """Guarda el historial"""
        data = {
            'history': self.history,
            'preferences': self.preferences,
            'last_update': datetime.now().isoformat()
        }
        self.history_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        
    def recommend_video(self, genre=None):
        """Recomienda videos de YouTube"""
        if not genre:
            genres = ['technology', 'education', 'entertainment', 'music', 'gaming']
            genre = random.choice(genres)
            
        # Buscar videos en YouTube
        # Usando la API de YouTube
        try:
            import yt_dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Buscar en YouTube
                search_query = f"best {genre} videos 2026"
                info = ydl.extract_info(f"ytsearch3:{search_query}", download=False)
                
                recommendations = []
                for entry in info['entries']:
                    recommendations.append({
                        'title': entry['title'],
                        'url': f"https://youtube.com/watch?v={entry['id']}",
                        'genre': genre,
                        'duration': entry.get('duration', 0)
                    })
                    
            self.save_history()
            return recommendations
            
        except Exception as e:
            return f"Error buscando videos: {e}"
            
    def recommend_music(self, mood=None):
        """Recomienda música basada en el estado de ánimo"""
        if not mood:
            moods = ['energetic', 'relaxing', 'focus', 'happy', 'sad']
            mood = random.choice(moods)
            
        # Recomendaciones simuladas
        music_recommendations = {
            'energetic': ['Daft Punk - Harder Better Faster', 'The Prodigy - Firestarter'],
            'relaxing': ['Beethoven - Moonlight Sonata', 'Enya - Orinoco Flow'],
            'focus': ['Hans Zimmer - Interstellar', 'Brian Eno - Ambient 1'],
            'happy': ['Pharrell Williams - Happy', 'Bruno Mars - Uptown Funk'],
            'sad': ['Adele - Someone Like You', 'Radiohead - Creep']
        }
        
        return {
            'mood': mood,
            'suggestions': music_recommendations.get(mood, ['Música clásica - Canon in D'])
        }
        
    def recommend_article(self, topic=None):
        """Recomienda artículos de interés"""
        if not topic:
            topics = ['technology', 'science', 'health', 'business', 'lifestyle']
            topic = random.choice(topics)
            
        # Simular recomendación de artículos
        return {
            'topic': topic,
            'suggestions': [
                f"Artículo reciente sobre {topic}: Tendencias 2026",
                f"5 cosas que debes saber sobre {topic}",
                f"El futuro de {topic}: Predicciones"
            ]
        }
        
    def recommend_tool(self, task=None):
        """Recomienda herramientas para tareas específicas"""
        tools = {
            'programming': ['VS Code', 'PyCharm', 'Git', 'Docker', 'Kubernetes'],
            'design': ['Figma', 'Adobe Photoshop', 'Illustrator', 'Canva'],
            'office': ['Microsoft Office', 'Google Workspace', 'Notion', 'Trello'],
            'video': ['DaVinci Resolve', 'Adobe Premiere', 'Final Cut Pro'],
            'audio': ['Audacity', 'FL Studio', 'Ableton Live']
        }
        
        if not task:
            task = random.choice(list(tools.keys()))
            
        return {
            'task': task,
            'tools': tools.get(task, ['Nexus AI'])
        }

def recommend(parameters: dict, player=None):
    """
    Sistema de recomendación de contenido para NEXUS
    
    Args:
        parameters: {
            'action': 'video' | 'music' | 'article' | 'tool',
            'genre': (opcional) para videos,
            'mood': (opcional) para música,
            'topic': (opcional) para artículos,
            'task': (opcional) para herramientas
        }
    """
    action = parameters.get('action', 'video')
    genre = parameters.get('genre')
    mood = parameters.get('mood')
    topic = parameters.get('topic')
    task = parameters.get('task')
    
    # Singleton
    if not hasattr(recommend, 'instance'):
        recommend.instance = ContentRecommender()
    
    cr = recommend.instance
    
    if action == 'video':
        recommendations = cr.recommend_video(genre)
        if isinstance(recommendations, str):
            return recommendations
            
        result = "🎬 RECOMENDACIONES DE VIDEOS:\n"
        for rec in recommendations:
            result += f"  • {rec['title']}\n    {rec['url']}\n"
        return result
        
    elif action == 'music':
        rec = cr.recommend_music(mood)
        result = f"🎵 MÚSICA PARA TU ESTADO DE ÁNIMO ({rec['mood']}):\n"
        for song in rec['suggestions']:
            result += f"  • {song}\n"
        return result
        
    elif action == 'article':
        rec = cr.recommend_article(topic)
        result = f"📰 ARTÍCULOS SOBRE {rec['topic'].upper()}:\n"
        for article in rec['suggestions']:
            result += f"  • {article}\n"
        return result
        
    elif action == 'tool':
        rec = cr.recommend_tool(task)
        result = f"🛠️ HERRAMIENTAS PARA {rec['task'].upper()}:\n"
        for tool in rec['tools']:
            result += f"  • {tool}\n"
        return result
        
    else:
        return "Acción no reconocida. Usa: video, music, article, tool"