import asyncio
import threading
from datetime import timedelta
from PyQt6.QtCore import QThread, pyqtSignal
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager

class MediaMonitorWorker(QThread):
    # Emitimos señales con (título, artista, reproduciendo, url_miniatura)
    media_updated = pyqtSignal(str, str, bool, object)
    # Emitimos señal para el progreso (posicion_segundos, duracion_segundos)
    timeline_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self._loop = None

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self.monitor_loop())
        except Exception as e:
            print(f"[MediaMonitor] Error: {e}")
        finally:
            self._loop.close()

    async def monitor_loop(self):
        try:
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        except Exception as e:
            print(f"[MediaMonitor] No se pudo obtener el manager: {e}")
            return

        last_title = None
        last_artist = None
        last_state = None

        while self.running:
            try:
                session = manager.get_current_session()
                if session:
                    info = await session.try_get_media_properties_async()
                    playback_info = session.get_playback_info()

                    title = info.title if info else "Unknown"
                    artist = info.artist if info else "Unknown"
                    # playback_status: 4 = Playing, 5 = Paused
                    is_playing = (playback_info.playback_status == 4) if playback_info else False

                    if (title != last_title) or (artist != last_artist) or (is_playing != last_state):
                        last_title = title
                        last_artist = artist
                        last_state = is_playing
                        self.media_updated.emit(title, artist, is_playing, None)
                    
                    # Update timeline
                    tl = session.get_timeline_properties()
                    if tl:
                        dur = int(tl.end_time.total_seconds() - tl.start_time.total_seconds()) if tl.end_time else 0
                        pos = int(tl.position.total_seconds()) if tl.position else 0
                        self.timeline_updated.emit(pos, max(dur, 0))

                else:
                    if last_title is not None:
                        last_title = None
                        last_artist = None
                        last_state = None
                        self.media_updated.emit("", "", False, None)

            except Exception as e:
                print(f"[MediaMonitor] Error en loop: {e}")

            await asyncio.sleep(0.5)

    def seek(self, pos_sec):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._seek_async(pos_sec), self._loop)

    async def _seek_async(self, pos_sec):
        try:
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            session = manager.get_current_session()
            if session:
                # El argumento pos_sec debe convertirse a TimeSpan. winsdk lo interpreta desde timedelta o como long integer de ticks.
                # En python winsdk 1.0.0b10, timedelta(seconds=X) no siempre funciona, pero multiplicando por 10,000,000 (ticks) es la API subyacente.
                # Sin embargo, como pide Windows.Foundation.TimeSpan, normalmente se le pasa un integer en ticks.
                ticks = int(pos_sec * 10_000_000)
                await session.try_change_playback_position_async(ticks)
        except Exception as e:
            print(f"[MediaMonitor] Error en seek: {e}")

    def stop(self):
        self.running = False
        self.wait()
