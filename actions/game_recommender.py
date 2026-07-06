import json
import requests
import psutil
from pathlib import Path
import subprocess

class GameRecommender:
    def __init__(self):
        self.installed_games = []
        self.steam_api_key = None
        self.load_config()
        
    def load_config(self):
        """Carga configuración de Steam"""
        config_file = Path("config/steam.json")
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding='utf-8'))
                self.steam_api_key = config.get('api_key')
            except:
                pass
                
    def detect_installed_games(self):
        """Detecta juegos instalados"""
        games = []
        
        # Buscar en Steam (carpeta común)
        steam_paths = [
            "C:/Program Files (x86)/Steam",
            "C:/Program Files/Steam"
        ]
        
        for path in steam_paths:
            steam_path = Path(path)
            if steam_path.exists():
                # Buscar en steamapps
                app_path = steam_path / "steamapps" / "common"
                if app_path.exists():
                    for game_dir in app_path.iterdir():
                        if game_dir.is_dir():
                            games.append(game_dir.name)
                            
        # Buscar en Epic Games
        epic_paths = [
            "C:/Program Files/Epic Games",
            "C:/Program Files (x86)/Epic Games"
        ]
        
        for path in epic_paths:
            epic_path = Path(path)
            if epic_path.exists():
                for game_dir in epic_path.iterdir():
                    if game_dir.is_dir():
                        games.append(game_dir.name)
                        
        # Buscar en Xbox Game Pass
        xbox_path = Path("C:/Program Files/WindowsApps")
        if xbox_path.exists():
            try:
                for game_dir in xbox_path.iterdir():
                    if "Microsoft" in str(game_dir):
                        games.append(game_dir.name.split('.')[-1])
            except:
                pass
                
        self.installed_games = list(set(games))
        return self.installed_games
        
    def recommend_games(self, genre=None, max_games=5):
        """Recomienda juegos basados en preferencias"""
        if not self.installed_games:
            self.detect_installed_games()
            
        recommendations = []
        
        # Si no hay juegos instalados, recomendar juegos populares
        if not self.installed_games:
            popular_games = [
                "Counter-Strike 2",
                "Dota 2",
                "Valorant",
                "League of Legends",
                "Fortnite"
            ]
            recommendations = popular_games[:max_games]
        else:
            # Recomendar juegos similares a los instalados
            recommendations = self.installed_games[:max_games]
            
        if genre:
            # Filtrar por género (simulación básica)
            genre_games = {
                'fps': ['Counter-Strike', 'Valorant', 'Call of Duty'],
                'rpg': ['The Witcher', 'Elden Ring', 'Cyberpunk 2077'],
                'strategy': ['Civilization', 'StarCraft', 'Age of Empires'],
                'adventure': ['Minecraft', 'Terraria', 'Stardew Valley'],
                'sports': ['FIFA', 'NBA 2K', 'Rocket League']
            }
            
            recommended = genre_games.get(genre, [])
            if recommended:
                recommendations = recommended[:max_games]
                
        return recommendations

def game_recommender(parameters: dict, player=None):
    """
    Recomendador de juegos para NEXUS
    
    Args:
        parameters: {
            'query': (opcional) género o texto de búsqueda,
            'max_games': (opcional) número de juegos a recomendar
        }
    """
    query = parameters.get('query', '')
    max_games = parameters.get('max_games', 5)
    
    # Singleton
    if not hasattr(game_recommender, 'instance'):
        game_recommender.instance = GameRecommender()
    
    gr = game_recommender.instance
    
    # Detectar juegos instalados
    games = gr.detect_installed_games()
    
    if query:
        # Buscar juegos por género
        recommendations = gr.recommend_games(query, max_games)
    else:
        recommendations = gr.recommend_games(max_games=max_games)
        
    result = f"🎮 RECOMENDACIONES DE JUEGOS:\n"
    if query:
        result += f"(Género: {query})\n\n"
    else:
        result += "(Basado en tus juegos instalados)\n\n"
        
    for i, game in enumerate(recommendations, 1):
        result += f"  {i}. {game}\n"
        
    return result