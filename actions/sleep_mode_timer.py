
import time
import threading

_sleep_timer = None
_is_sleeping = False

def sleep_mode_timer(parameters: dict, player=None, speak=None):
    global _is_sleeping, _sleep_timer

    duration_minutes = parameters.get("duration_minutes", 5)
    _is_sleeping = True

    # speak function is handled by the main process context, not directly here due to sandbox
    # The main process must check is_sleeping() before processing commands

    def timer_finished():
        global _is_sleeping, _sleep_timer
        _is_sleeping = False
        _sleep_timer = None
        # Notification handled by main process loop

    _sleep_timer = threading.Timer(duration_minutes * 60, timer_finished)
    _sleep_timer.start()
    return f"Modo de espera activado por {duration_minutes} minutos."

def is_sleeping():
    global _is_sleeping
    return _is_sleeping

def stop_sleep():
    global _is_sleeping, _sleep_timer
    if _is_sleeping:
        if _sleep_timer:
            _sleep_timer.cancel()
            _sleep_timer = None
        _is_sleeping = False
        return "Modo de espera detenido."
    return "El asistente no estaba en modo de espera."
