"""
Game Companion
==============
Módulo especializado de visión para dar consejos tácticos en videojuegos.
"""

from actions.screen_vision import screen_vision

def game_companion(parameters: dict, player=None) -> str:
    game_name = parameters.get("game_name", "el juego actual")
    action = parameters.get("action", "analyze").lower()
    
    if action == "analyze":
        if player:
            player.write_log(f"🎮 Game Companion analizando {game_name}...")
            
        # Llamamos al módulo robusto de visión que ya tenemos,
        # pero con un prompt inyectado específico para gaming.
        custom_params = {
            "query": f"Soy un jugador de {game_name}. Analiza mi pantalla de juego. Si hay algo crítico en el minimapa, salud baja, o un consejo táctico obvio, dímelo en 1 oración muy breve. Si todo está normal, responde 'Todo despejado'.",
            "action": "describe"
        }
        
        response = screen_vision(custom_params, player)
        return f"🎮 Game Companion dice: {response}"
        
    return "❌ Acción no reconocida en Game Companion."
