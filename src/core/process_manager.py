"""
Process Manager
Gerenciador profissional de processo único com PID file e restart automático
"""

import os
import sys
import time
import signal
import atexit
import psutil
from pathlib import Path
from loguru import logger
from typing import Optional


class ProcessManager:
    """
    Gerenciador de processo único
    - Garante apenas 1 instância rodando
    - PID file para controle
    - Cleanup adequado de recursos
    - Suporte a restart
    """
    
    def __init__(self, app_name: str = "urion_bot"):
        self.app_name = app_name
        self.base_dir = Path(__file__).parent.parent.parent
        self.pid_file = self.base_dir / f"{app_name}.pid"
        self.lock_file = self.base_dir / f"{app_name}.lock"
        self.current_pid = os.getpid()
        
    def is_running(self) -> bool:
        """Verifica se já existe instância rodando"""
        if not self.pid_file.exists():
            return False
            
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
                
            # Verificar se o processo existe
            if psutil.pid_exists(pid):
                try:
                    process = psutil.Process(pid)
                    # Verificar se é realmente o nosso processo
                    if 'python' in process.name().lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
            # PID file órfão, remover
            self.pid_file.unlink(missing_ok=True)
            return False
            
        except (ValueError, FileNotFoundError):
            return False
    
    def kill_existing_instance(self) -> bool:
        """Mata instância existente se houver"""
        if not self.pid_file.exists():
            return True
            
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
                
            if not psutil.pid_exists(pid):
                self.pid_file.unlink(missing_ok=True)
                return True
                
            logger.warning(f"🔴 Matando instância existente (PID: {pid})")
            
            try:
                process = psutil.Process(pid)
                
                # Tentar encerramento gracioso primeiro
                process.terminate()
                try:
                    process.wait(timeout=10)
                    logger.success("✅ Instância anterior encerrada graciosamente")
                except psutil.TimeoutExpired:
                    # Force kill se não responder
                    process.kill()
                    process.wait(timeout=5)
                    logger.warning("⚠️ Instância anterior forçada a encerrar")
                    
                # Matar processos filhos também
                for child in process.children(recursive=True):
                    try:
                        child.kill()
                    except:
                        pass
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
            self.pid_file.unlink(missing_ok=True)
            time.sleep(2)  # Aguardar cleanup do OS
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao matar instância existente: {e}")
            return False
    
    def acquire_lock(self, force: bool = False) -> bool:
        """Adquire lock de execução"""
        if self.is_running() and not force:
            logger.error(f"❌ {self.app_name} já está rodando (PID: {self.get_running_pid()})")
            logger.info("💡 Use --force para matar e reiniciar")
            return False
            
        if force:
            if not self.kill_existing_instance():
                return False
                
        # Criar PID file
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(self.current_pid))
            logger.success(f"✅ Lock adquirido (PID: {self.current_pid})")
            
            # Registrar cleanup
            atexit.register(self.release_lock)
            
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao criar PID file: {e}")
            return False
    
    def release_lock(self):
        """Libera lock de execução"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.info("🔓 Lock liberado")
        except Exception as e:
            logger.error(f"❌ Erro ao liberar lock: {e}")
    
    def get_running_pid(self) -> Optional[int]:
        """Retorna PID da instância rodando"""
        try:
            if self.pid_file.exists():
                with open(self.pid_file, 'r') as f:
                    return int(f.read().strip())
        except:
            pass
        return None
    
    def setup_signal_handlers(self, shutdown_callback):
        """Configura handlers de sinais"""
        def signal_handler(signum, frame):
            sig_name = signal.Signals(signum).name
            logger.info(f"🛑 Recebido sinal {sig_name}")
            self.release_lock()
            shutdown_callback()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if sys.platform == 'win32':
            signal.signal(signal.SIGBREAK, signal_handler)
            
        logger.success("✅ Signal handlers configurados")
    
    def get_process_info(self) -> dict:
        """Retorna informações do processo atual"""
        try:
            process = psutil.Process(self.current_pid)
            
            return {
                'pid': self.current_pid,
                'name': process.name(),
                'status': process.status(),
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'num_threads': process.num_threads(),
                'create_time': time.strftime('%Y-%m-%d %H:%M:%S', 
                                            time.localtime(process.create_time())),
                'running_time': time.time() - process.create_time()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def cleanup_zombie_processes(self):
        """Limpa processos Python zumbis relacionados"""
        cleaned = 0
        try:
            current_name = psutil.Process(self.current_pid).name()
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.pid == self.current_pid:
                        continue
                        
                    if 'python' in proc.name().lower():
                        cmdline = proc.cmdline()
                        # Verificar apenas se main.py esta nos argumentos, ignorando paths
                        script_args = [cmd for cmd in cmdline if not cmd.startswith('C:') and not cmd.startswith('/')]
                        if any('main.py' in cmd for cmd in script_args):
                            logger.warning(f"Limpando processo zumbi: PID {proc.pid}")
                            proc.kill()
                            cleaned += 1
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            if cleaned > 0:
                logger.success(f"{cleaned} processo(s) zumbi limpos")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Erro ao limpar zumbis: {e}")
