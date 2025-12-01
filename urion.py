# -*- coding: utf-8 -*-
"""
Urion Trading Bot - Executável Principal
=========================================
Gerenciador de processos robusto sem processos zumbis.

Uso:
    python urion.py start       # Inicia o bot
    python urion.py stop        # Para o bot
    python urion.py restart     # Reinicia
    python urion.py status      # Verifica status
    python urion.py dashboard   # Abre dashboard web
"""

import os
import sys
import signal
import psutil
import subprocess
import time
import json
import atexit
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import threading
import queue

# Diretório base
BASE_DIR = Path(__file__).parent.absolute()
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
PID_FILE = DATA_DIR / "urion.pid"
PROCESS_FILE = DATA_DIR / "urion_processes.json"

# Garantir diretórios
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Cores para terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


class ProcessManager:
    """Gerenciador de processos do Urion Bot"""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = False
        self.main_pid = os.getpid()
        self._shutdown_event = threading.Event()
        self._process_lock = threading.Lock()
        
        # Registrar handlers de sinal
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        if sys.platform == 'win32':
            signal.signal(signal.SIGBREAK, self._signal_handler)
        
        # Registrar cleanup no exit
        atexit.register(self._cleanup_all)
    
    def _signal_handler(self, signum, frame):
        """Handler para sinais de término"""
        print(f"\n{Colors.YELLOW}⚠️  Sinal recebido ({signum}). Encerrando...{Colors.END}")
        self._shutdown_event.set()
        self.stop_all()
        sys.exit(0)
    
    def _save_processes(self):
        """Salva PIDs dos processos para rastreamento"""
        with self._process_lock:
            data = {
                'main_pid': self.main_pid,
                'started_at': datetime.now().isoformat(),
                'processes': {}
            }
            for name, proc in self.processes.items():
                if proc.poll() is None:  # Ainda rodando
                    data['processes'][name] = {
                        'pid': proc.pid,
                        'started': datetime.now().isoformat()
                    }
            
            with open(PROCESS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
    
    def _load_processes(self) -> Dict:
        """Carrega PIDs salvos"""
        if PROCESS_FILE.exists():
            try:
                with open(PROCESS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _cleanup_all(self):
        """Limpa todos os processos ao sair"""
        self.stop_all()
        
        # Remover arquivos de PID
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
            if PROCESS_FILE.exists():
                PROCESS_FILE.unlink()
        except:
            pass
    
    def _kill_process_tree(self, pid: int, timeout: int = 5):
        """Mata um processo e todos seus filhos"""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            # Primeiro tenta SIGTERM
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            
            try:
                parent.terminate()
            except psutil.NoSuchProcess:
                pass
            
            # Espera um pouco
            gone, alive = psutil.wait_procs(children + [parent], timeout=timeout)
            
            # Se ainda tiver processos vivos, força SIGKILL
            for proc in alive:
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
                    
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            print(f"{Colors.RED}Erro ao matar processo {pid}: {e}{Colors.END}")
    
    def start_process(self, name: str, command: List[str], 
                      env: Optional[Dict] = None,
                      cwd: Optional[str] = None) -> Optional[subprocess.Popen]:
        """Inicia um processo gerenciado"""
        with self._process_lock:
            if name in self.processes and self.processes[name].poll() is None:
                print(f"{Colors.YELLOW}⚠️  {name} já está rodando{Colors.END}")
                return self.processes[name]
            
            # Preparar ambiente
            process_env = os.environ.copy()
            if env:
                process_env.update(env)
            
            # Diretório de trabalho
            work_dir = cwd if cwd else str(BASE_DIR)
            
            # Criar arquivo de log
            log_file = LOGS_DIR / f"{name}.log"
            
            try:
                with open(log_file, 'a') as log:
                    log.write(f"\n{'='*60}\n")
                    log.write(f"Iniciado em: {datetime.now().isoformat()}\n")
                    log.write(f"Comando: {' '.join(command)}\n")
                    log.write(f"Diretorio: {work_dir}\n")
                    log.write(f"{'='*60}\n\n")
                
                # Iniciar processo
                proc = subprocess.Popen(
                    command,
                    cwd=work_dir,
                    env=process_env,
                    stdout=open(log_file, 'a'),
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
                )
                
                self.processes[name] = proc
                self._save_processes()
                
                print(f"{Colors.GREEN}✅ {name} iniciado (PID: {proc.pid}){Colors.END}")
                return proc
                
            except Exception as e:
                print(f"{Colors.RED}❌ Erro ao iniciar {name}: {e}{Colors.END}")
                return None
    
    def stop_process(self, name: str, timeout: int = 10) -> bool:
        """Para um processo específico"""
        with self._process_lock:
            if name not in self.processes:
                print(f"{Colors.YELLOW}⚠️  {name} não está registrado{Colors.END}")
                return True
            
            proc = self.processes[name]
            if proc.poll() is not None:
                print(f"{Colors.YELLOW}⚠️  {name} já estava parado{Colors.END}")
                del self.processes[name]
                return True
            
            print(f"{Colors.CYAN}🛑 Parando {name} (PID: {proc.pid})...{Colors.END}")
            
            try:
                self._kill_process_tree(proc.pid, timeout)
                del self.processes[name]
                self._save_processes()
                print(f"{Colors.GREEN}✅ {name} parado com sucesso{Colors.END}")
                return True
            except Exception as e:
                print(f"{Colors.RED}❌ Erro ao parar {name}: {e}{Colors.END}")
                return False
    
    def stop_all(self):
        """Para todos os processos"""
        print(f"\n{Colors.CYAN}🛑 Parando todos os processos...{Colors.END}")
        
        # Parar processos ativos
        names = list(self.processes.keys())
        for name in names:
            self.stop_process(name)
        
        # Verificar processos órfãos do arquivo salvo
        saved = self._load_processes()
        for name, info in saved.get('processes', {}).items():
            pid = info.get('pid')
            if pid and psutil.pid_exists(pid):
                print(f"{Colors.YELLOW}⚠️  Matando processo órfão: {name} (PID: {pid}){Colors.END}")
                self._kill_process_tree(pid)
        
        # Limpar arquivos
        try:
            if PROCESS_FILE.exists():
                PROCESS_FILE.unlink()
        except:
            pass
        
        print(f"{Colors.GREEN}✅ Todos os processos finalizados{Colors.END}")
    
    def get_status(self) -> Dict:
        """Retorna status de todos os processos"""
        status = {
            'main_pid': self.main_pid,
            'running': self.running,
            'processes': {}
        }
        
        with self._process_lock:
            for name, proc in self.processes.items():
                is_running = proc.poll() is None
                status['processes'][name] = {
                    'pid': proc.pid,
                    'running': is_running,
                    'returncode': proc.returncode if not is_running else None
                }
        
        return status


class UrionBot:
    """Classe principal do Urion Bot"""
    
    def __init__(self):
        self.pm = ProcessManager()
        self.venv_python = str(BASE_DIR / "venv" / "Scripts" / "python.exe")
        
        # Verificar se venv existe
        if not Path(self.venv_python).exists():
            print(f"{Colors.RED}❌ Virtual environment não encontrado!{Colors.END}")
            print(f"   Execute: python -m venv venv")
            sys.exit(1)
    
    def print_banner(self):
        """Imprime banner do bot"""
        banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║  {Colors.BOLD}██╗   ██╗██████╗ ██╗ ██████╗ ███╗   ██╗{Colors.CYAN}                        ║
║  {Colors.BOLD}██║   ██║██╔══██╗██║██╔═══██╗████╗  ██║{Colors.CYAN}                        ║
║  {Colors.BOLD}██║   ██║██████╔╝██║██║   ██║██╔██╗ ██║{Colors.CYAN}                        ║
║  {Colors.BOLD}██║   ██║██╔══██╗██║██║   ██║██║╚██╗██║{Colors.CYAN}                        ║
║  {Colors.BOLD}╚██████╔╝██║  ██║██║╚██████╔╝██║ ╚████║{Colors.CYAN}                        ║
║  {Colors.BOLD} ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝{Colors.CYAN}                        ║
║                                                                  ║
║  {Colors.GREEN}ELITE TRADING BOT v2.0{Colors.CYAN}                                       ║
║  {Colors.YELLOW}Powered by ML & Advanced Risk Management{Colors.CYAN}                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Colors.END}
"""
        print(banner)
    
    def start(self, mode: str = "full"):
        """Inicia o bot com todos os componentes integrados"""
        self.print_banner()
        
        print(f"{Colors.CYAN}🚀 Iniciando Urion Bot...{Colors.END}")
        print(f"   Modo: {mode.upper()}")
        print(f"   Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Verificar se já está rodando
        saved = self.pm._load_processes()
        if saved.get('main_pid') and psutil.pid_exists(saved['main_pid']):
            print(f"{Colors.YELLOW}⚠️  Bot já está rodando (PID: {saved['main_pid']}){Colors.END}")
            print(f"   Use 'python urion.py stop' para parar primeiro")
            return False
        
        # Limpar processos órfãos antes de iniciar
        self._cleanup_orphans()
        
        # Salvar PID principal
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        self.pm.running = True
        
        # 1. Iniciar Backend API
        print(f"\n{Colors.BLUE}[1/4] Iniciando Backend API...{Colors.END}")
        self.pm.start_process(
            "backend",
            [self.venv_python, str(BASE_DIR / "backend" / "server.py")],
            {"PYTHONPATH": str(SRC_DIR)}
        )
        time.sleep(3)
        
        # 2. Iniciar Trading Engine (main.py na raiz)
        print(f"\n{Colors.BLUE}[2/4] Iniciando Trading Engine...{Colors.END}")
        self.pm.start_process(
            "trading",
            [self.venv_python, str(BASE_DIR / "main.py")],
            {"PYTHONPATH": str(SRC_DIR)}
        )
        time.sleep(3)
        
        # 3. Iniciar Frontend (Node.js)
        print(f"\n{Colors.BLUE}[3/4] Iniciando Frontend...{Colors.END}")
        frontend_dir = BASE_DIR / "frontend"
        if frontend_dir.exists() and (frontend_dir / "package.json").exists():
            npm_cmd = "npm.cmd" if sys.platform == 'win32' else "npm"
            self.pm.start_process(
                "frontend",
                [npm_cmd, "run", "dev"],
                env=None,
                cwd=str(frontend_dir)
            )
        else:
            print(f"{Colors.YELLOW}   ⚠️  Frontend não encontrado, pulando...{Colors.END}")
        time.sleep(3)
        
        # 4. Iniciar Monitor 24h
        print(f"\n{Colors.BLUE}[4/4] Iniciando Monitor 24h...{Colors.END}")
        monitor_file = BASE_DIR / "monitor_24h.py"
        if monitor_file.exists():
            self.pm.start_process(
                "monitor",
                [self.venv_python, str(monitor_file)],
                {"PYTHONPATH": str(SRC_DIR)}
            )
        time.sleep(2)
        
        # Iniciar thread de monitoramento interno
        self._start_monitor()
        
        print(f"\n{Colors.GREEN}{'='*60}{Colors.END}")
        print(f"{Colors.GREEN}✅ URION BOT INICIADO COM SUCESSO!{Colors.END}")
        print(f"{Colors.GREEN}{'='*60}{Colors.END}")
        print(f"\n   📊 Dashboard: http://localhost:3000")
        print(f"   🔌 API: http://localhost:8080")
        print(f"   � Trading: ATIVO")
        print(f"   🔍 Monitor: ATIVO")
        print(f"\n   Use Ctrl+C para parar o bot")
        print()
        
        # Abrir dashboard automaticamente
        try:
            import webbrowser
            webbrowser.open("http://localhost:3000")
        except:
            pass
        
        # Manter rodando
        try:
            while self.pm.running and not self.pm._shutdown_event.is_set():
                time.sleep(1)
                
                # Verificar saúde dos processos
                for name, proc in list(self.pm.processes.items()):
                    if proc.poll() is not None:
                        print(f"{Colors.RED}⚠️  {name} morreu inesperadamente!{Colors.END}")
                        # Tentar reiniciar processos críticos
                        if name == "trading":
                            print(f"{Colors.YELLOW}   Reiniciando Trading Engine...{Colors.END}")
                            time.sleep(2)
                            self.pm.start_process(
                                "trading",
                                [self.venv_python, str(BASE_DIR / "main.py")],
                                {"PYTHONPATH": str(SRC_DIR)}
                            )
                        elif name == "backend":
                            print(f"{Colors.YELLOW}   Reiniciando Backend API...{Colors.END}")
                            time.sleep(2)
                            self.pm.start_process(
                                "backend",
                                [self.venv_python, str(BASE_DIR / "backend" / "server.py")],
                                {"PYTHONPATH": str(SRC_DIR)}
                            )
                        
        except KeyboardInterrupt:
            pass
        
        return True
    
    def _start_monitor(self):
        """Inicia thread de monitoramento"""
        def monitor():
            while self.pm.running and not self.pm._shutdown_event.is_set():
                time.sleep(5)
                # Verificar processos
                status = self.pm.get_status()
                for name, info in status['processes'].items():
                    if not info['running']:
                        print(f"{Colors.YELLOW}⚠️  {name} parou (code: {info['returncode']}){Colors.END}")
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def stop(self):
        """Para o bot"""
        self.print_banner()
        print(f"{Colors.CYAN}🛑 Parando Urion Bot...{Colors.END}\n")
        
        self.pm.running = False
        self.pm.stop_all()
        
        # Verificar processos python do urion que podem ter ficado
        self._cleanup_orphans()
        
        print(f"\n{Colors.GREEN}✅ Urion Bot finalizado com sucesso{Colors.END}")
    
    def _cleanup_orphans(self):
        """Limpa processos órfãos"""
        print(f"\n{Colors.CYAN}🔍 Verificando processos órfãos...{Colors.END}")
        
        current_pid = os.getpid()
        killed = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.pid == current_pid:
                    continue
                    
                cmdline = ' '.join(proc.info['cmdline'] or [])
                
                # Verificar se é processo do urion
                if 'urion' in cmdline.lower() and 'python' in proc.info['name'].lower():
                    print(f"   Matando: PID {proc.pid} - {cmdline[:50]}...")
                    proc.kill()
                    killed += 1
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed > 0:
            print(f"   {Colors.GREEN}✅ {killed} processos órfãos removidos{Colors.END}")
        else:
            print(f"   {Colors.GREEN}✅ Nenhum processo órfão encontrado{Colors.END}")
    
    def status(self):
        """Mostra status do bot"""
        self.print_banner()
        
        print(f"{Colors.CYAN}📊 STATUS DO URION BOT{Colors.END}\n")
        
        # Verificar PID file
        if PID_FILE.exists():
            with open(PID_FILE, 'r') as f:
                main_pid = int(f.read().strip())
            
            if psutil.pid_exists(main_pid):
                print(f"   {Colors.GREEN}●{Colors.END} Bot Principal: RODANDO (PID: {main_pid})")
            else:
                print(f"   {Colors.RED}●{Colors.END} Bot Principal: PARADO (PID antigo: {main_pid})")
        else:
            print(f"   {Colors.RED}●{Colors.END} Bot Principal: PARADO")
        
        # Verificar processos salvos
        saved = self.pm._load_processes()
        for name, info in saved.get('processes', {}).items():
            pid = info.get('pid')
            if pid and psutil.pid_exists(pid):
                print(f"   {Colors.GREEN}●{Colors.END} {name}: RODANDO (PID: {pid})")
            else:
                print(f"   {Colors.RED}●{Colors.END} {name}: PARADO")
        
        # Mostrar recursos
        print(f"\n{Colors.CYAN}💻 RECURSOS DO SISTEMA{Colors.END}")
        print(f"   CPU: {psutil.cpu_percent()}%")
        print(f"   RAM: {psutil.virtual_memory().percent}%")
        print(f"   Disco: {psutil.disk_usage('/').percent}%")
        
        print()
    
    def restart(self, mode: str = "full"):
        """Reinicia o bot"""
        self.stop()
        time.sleep(2)
        self.start(mode)
    
    def dashboard(self):
        """Abre o dashboard no navegador"""
        import webbrowser
        
        print(f"{Colors.CYAN}🌐 Abrindo Dashboard...{Colors.END}")
        webbrowser.open("http://localhost:3000")


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Urion Trading Bot - Gerenciador',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python urion.py start           Inicia o bot
  python urion.py start --mode api  Inicia apenas a API
  python urion.py stop            Para o bot
  python urion.py restart         Reinicia o bot
  python urion.py status          Verifica status
  python urion.py dashboard       Abre dashboard web
        """
    )
    
    parser.add_argument('command', 
                        choices=['start', 'stop', 'restart', 'status', 'dashboard'],
                        help='Comando a executar')
    parser.add_argument('--mode', type=str, 
                        choices=['full', 'generator', 'manager', 'api'],
                        default='full',
                        help='Modo de operação (default: full)')
    
    args = parser.parse_args()
    
    bot = UrionBot()
    
    if args.command == 'start':
        bot.start(args.mode)
    elif args.command == 'stop':
        bot.stop()
    elif args.command == 'restart':
        bot.restart(args.mode)
    elif args.command == 'status':
        bot.status()
    elif args.command == 'dashboard':
        bot.dashboard()


if __name__ == "__main__":
    main()
