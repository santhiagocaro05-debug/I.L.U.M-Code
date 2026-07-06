import json
import time
from pathlib import Path
from datetime import datetime, timedelta
import psutil
import platform
import win32api
import win32con
from collections import defaultdict

class DailyReport:
    def __init__(self):
        self.report_file = Path("memory/daily_reports.json")
        self.app_usage = defaultdict(int)
        self.screen_time = 0
        self.tasks_completed = []
        self.load_data()
        
    def load_data(self):
        """Carga datos existentes"""
        if self.report_file.exists():
            try:
                data = json.loads(self.report_file.read_text(encoding="utf-8"))
                self.app_usage = defaultdict(int, data.get('app_usage', {}))
                self.tasks_completed = data.get('tasks', [])
            except:
                pass
                
    def save_data(self):
        """Guarda datos"""
        data = {
            'app_usage': dict(self.app_usage),
            'tasks': self.tasks_completed,
            'last_update': datetime.now().isoformat()
        }
        self.report_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        
    def collect_today_usage(self):
        """Recolecta el uso de aplicaciones del día"""
        today = datetime.now().date()
        
        # Obtener procesos en ejecución
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                name = proc.info['name']
                if name not in ['System Idle Process', 'svchost.exe']:
                    self.app_usage[name] += 1
            except:
                pass
                
        self.save_data()
        
    def generate_report(self):
        """Genera el reporte diario"""
        today = datetime.now().strftime("%A, %d de %B de %Y")
        
        report = f"📊 REPORTE DIARIO - {today}\n"
        report += "=" * 50 + "\n\n"
        
        # Uso de aplicaciones
        report += "📱 APLICACIONES MÁS USADAS:\n"
        sorted_apps = sorted(self.app_usage.items(), key=lambda x: x[1], reverse=True)
        for i, (app, count) in enumerate(sorted_apps[:10], 1):
            report += f"  {i}. {app} - {count} minutos\n"
            
        # Estadísticas del sistema
        report += "\n💻 ESTADÍSTICAS DEL SISTEMA:\n"
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        report += f"  CPU: {cpu}%\n"
        report += f"  RAM: {memory.percent}% usado ({memory.used // (1024**3)} GB / {memory.total // (1024**3)} GB)\n"
        report += f"  Disco: {disk.percent}% usado\n"
        
        # Tareas completadas
        if self.tasks_completed:
            report += "\n✅ TAREAS COMPLETADAS:\n"
            for task in self.tasks_completed[-10:]:
                report += f"  • {task}\n"
                
        # Recomendaciones
        report += "\n💡 RECOMENDACIONES:\n"
        
        if cpu > 80:
            report += "  • Alta carga de CPU. Considera cerrar aplicaciones pesadas.\n"
        if memory.percent > 85:
            report += "  • Memoria RAM alta. Reinicia para liberar recursos.\n"
        if disk.percent > 90:
            report += "  • Disco casi lleno. Realiza limpieza de archivos temporales.\n"
            
        if not self.tasks_completed:
            report += "  • No hay tareas registradas. ¿Qué lograste hoy?\n"
            
        return report
        
    def send_email(self, email):
        """Envía el reporte por email"""
        report = self.generate_report()
        # Aquí se conectaría con Gmail para enviar el reporte
        return f"Reporte enviado a {email}"
        
    def reset_daily_stats(self):
        """Reinicia las estadísticas diarias"""
        self.app_usage = defaultdict(int)
        self.tasks_completed = []
        self.save_data()
        return "Estadísticas diarias reiniciadas"

def daily_report(parameters: dict, player=None):
    """
    Generador de reportes diarios para NEXUS
    
    Args:
        parameters: {
            'action': 'generate' | 'send_email',
            'email': (opcional) email para enviar el reporte
        }
    """
    action = parameters.get('action', 'generate')
    email = parameters.get('email')
    
    # Singleton
    if not hasattr(daily_report, 'instance'):
        daily_report.instance = DailyReport()
    
    dr = daily_report.instance
    
    if action == 'generate':
        return dr.generate_report()
        
    elif action == 'send_email':
        if not email:
            return "Proporciona un email para enviar el reporte"
        return dr.send_email(email)
        
    elif action == 'reset':
        return dr.reset_daily_stats()
        
    else:
        return "Acción no reconocida. Usa: generate, send_email, reset"