"""
Config Hot Reload Manager
Monitora arquivos de configuração e recarrega automaticamente sem reiniciar o bot

Features:
- Watchdog para detectar mudanças em arquivos
- Validação antes de aplicar mudanças
- Callbacks para notificar componentes
- Rollback em caso de erro
- Histórico de mudanças
"""
import os
import time
import yaml
import threading
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from copy import deepcopy


@dataclass
class ConfigChange:
    """Representa uma mudança de configuração"""
    timestamp: datetime
    file_path: str
    old_hash: str
    new_hash: str
    changes: Dict[str, tuple]  # key: (old_value, new_value)
    applied: bool = False
    error: Optional[str] = None


class ConfigHotReload:
    """
    Gerenciador de Hot Reload de Configurações
    
    Monitora arquivos de config e notifica componentes quando há mudanças
    """
    
    def __init__(
        self,
        config_manager,
        watch_paths: Optional[List[str]] = None,
        check_interval: float = 5.0,
        auto_reload: bool = True
    ):
        """
        Inicializa o Hot Reload Manager
        
        Args:
            config_manager: Instância do ConfigManager existente
            watch_paths: Lista de caminhos para monitorar
            check_interval: Intervalo de verificação em segundos
            auto_reload: Se deve recarregar automaticamente
        """
        self.config_manager = config_manager
        self.check_interval = check_interval
        self.auto_reload = auto_reload
        
        # Caminhos para monitorar
        self.watch_paths = watch_paths or [
            str(config_manager.config_path),
        ]
        
        # Estado
        self._file_hashes: Dict[str, str] = {}
        self._callbacks: List[Callable[[str, Dict], None]] = []
        self._change_history: List[ConfigChange] = []
        self._backup_config: Dict = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Inicializar hashes
        self._update_file_hashes()
        self._backup_config = deepcopy(config_manager.get_all())
        
        logger.info(
            f"🔄 Hot Reload Manager inicializado | "
            f"Paths: {len(self.watch_paths)} | "
            f"Interval: {check_interval}s | "
            f"Auto: {auto_reload}"
        )
    
    def _calculate_hash(self, file_path: str) -> str:
        """Calcula hash MD5 do arquivo"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _update_file_hashes(self):
        """Atualiza hashes de todos os arquivos monitorados"""
        for path in self.watch_paths:
            if os.path.exists(path):
                self._file_hashes[path] = self._calculate_hash(path)
    
    def _detect_changes(self, old_config: Dict, new_config: Dict, prefix: str = "") -> Dict[str, tuple]:
        """Detecta mudanças entre duas configurações"""
        changes = {}
        
        all_keys = set(old_config.keys()) | set(new_config.keys())
        
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_val = old_config.get(key)
            new_val = new_config.get(key)
            
            if old_val != new_val:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    # Recursivo para dicts aninhados
                    nested_changes = self._detect_changes(old_val, new_val, full_key)
                    changes.update(nested_changes)
                else:
                    changes[full_key] = (old_val, new_val)
        
        return changes
    
    def _validate_config(self, config: Dict) -> tuple[bool, Optional[str]]:
        """
        Valida configuração antes de aplicar
        
        Returns:
            (is_valid, error_message)
        """
        try:
            # Validações básicas
            required_sections = ['mt5', 'trading']
            for section in required_sections:
                if section not in config:
                    return False, f"Seção obrigatória ausente: {section}"
            
            # Validar tipos específicos
            if 'risk_management' in config:
                risk = config['risk_management']
                if 'max_risk_per_trade' in risk:
                    val = risk['max_risk_per_trade']
                    if not (0 < val <= 0.1):
                        return False, f"max_risk_per_trade deve estar entre 0 e 10%: {val}"
            
            # Validar trading
            if 'trading' in config:
                trading = config['trading']
                if 'max_positions' in trading:
                    if trading['max_positions'] < 1:
                        return False, "max_positions deve ser >= 1"
            
            return True, None
            
        except Exception as e:
            return False, f"Erro de validação: {str(e)}"
    
    def register_callback(self, callback: Callable[[str, Dict], None]):
        """
        Registra callback para ser chamado quando config mudar
        
        Args:
            callback: Função(config_key, new_value)
        """
        self._callbacks.append(callback)
        logger.debug(f"Callback registrado: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
    
    def unregister_callback(self, callback: Callable):
        """Remove callback registrado"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, changes: Dict[str, tuple]):
        """Notifica todos os callbacks sobre mudanças"""
        for key, (old_val, new_val) in changes.items():
            for callback in self._callbacks:
                try:
                    callback(key, new_val)
                except Exception as e:
                    logger.error(f"Erro em callback para {key}: {e}")
    
    def check_for_changes(self) -> bool:
        """
        Verifica se há mudanças nos arquivos de configuração
        
        Returns:
            True se houve mudanças
        """
        with self._lock:
            for path in self.watch_paths:
                if not os.path.exists(path):
                    continue
                
                new_hash = self._calculate_hash(path)
                old_hash = self._file_hashes.get(path, "")
                
                if new_hash != old_hash and old_hash:
                    logger.info(f"🔄 Mudança detectada em: {path}")
                    
                    if self.auto_reload:
                        success = self._reload_config(path, old_hash, new_hash)
                        if success:
                            self._file_hashes[path] = new_hash
                            return True
                    else:
                        # Apenas registrar a mudança
                        self._file_hashes[path] = new_hash
                        return True
                
                self._file_hashes[path] = new_hash
        
        return False
    
    def _reload_config(self, file_path: str, old_hash: str, new_hash: str) -> bool:
        """
        Recarrega configuração de um arquivo
        
        Returns:
            True se recarregou com sucesso
        """
        try:
            # Backup atual
            old_config = deepcopy(self.config_manager.get_all())
            
            # Ler novo arquivo
            with open(file_path, 'r', encoding='utf-8') as f:
                new_config_raw = yaml.safe_load(f)
            
            # Validar
            is_valid, error = self._validate_config(new_config_raw)
            if not is_valid:
                logger.error(f"❌ Config inválida: {error}")
                change = ConfigChange(
                    timestamp=datetime.now(),
                    file_path=file_path,
                    old_hash=old_hash,
                    new_hash=new_hash,
                    changes={},
                    applied=False,
                    error=error
                )
                self._change_history.append(change)
                return False
            
            # Aplicar
            self.config_manager.load_config()
            new_config = self.config_manager.get_all()
            
            # Detectar mudanças específicas
            changes = self._detect_changes(old_config, new_config)
            
            # Registrar
            change = ConfigChange(
                timestamp=datetime.now(),
                file_path=file_path,
                old_hash=old_hash,
                new_hash=new_hash,
                changes=changes,
                applied=True
            )
            self._change_history.append(change)
            
            # Log mudanças
            if changes:
                logger.success(f"✅ Config recarregada com {len(changes)} mudanças:")
                for key, (old_val, new_val) in list(changes.items())[:10]:  # Limitar log
                    logger.info(f"   {key}: {old_val} → {new_val}")
                if len(changes) > 10:
                    logger.info(f"   ... e mais {len(changes) - 10} mudanças")
            
            # Notificar callbacks
            self._notify_callbacks(changes)
            
            # Atualizar backup
            self._backup_config = deepcopy(new_config)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao recarregar config: {e}")
            
            # Tentar rollback
            try:
                self.rollback()
            except:
                pass
            
            change = ConfigChange(
                timestamp=datetime.now(),
                file_path=file_path,
                old_hash=old_hash,
                new_hash=new_hash,
                changes={},
                applied=False,
                error=str(e)
            )
            self._change_history.append(change)
            
            return False
    
    def rollback(self) -> bool:
        """
        Reverte para configuração anterior
        
        Returns:
            True se reverteu com sucesso
        """
        try:
            if not self._backup_config:
                logger.warning("Sem backup para rollback")
                return False
            
            # Restaurar config no manager
            self.config_manager.config = deepcopy(self._backup_config)
            
            logger.info("🔙 Configuração revertida para backup")
            return True
            
        except Exception as e:
            logger.error(f"Erro no rollback: {e}")
            return False
    
    def force_reload(self) -> bool:
        """Força recarregamento da configuração"""
        with self._lock:
            for path in self.watch_paths:
                if os.path.exists(path):
                    old_hash = self._file_hashes.get(path, "")
                    new_hash = self._calculate_hash(path)
                    return self._reload_config(path, old_hash, new_hash)
        return False
    
    def _watch_loop(self):
        """Loop de monitoramento em background"""
        while self._running:
            try:
                self.check_for_changes()
            except Exception as e:
                logger.error(f"Erro no watch loop: {e}")
            
            time.sleep(self.check_interval)
    
    def start(self):
        """Inicia monitoramento em background"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("👁️ Hot Reload watcher iniciado")
    
    def stop(self):
        """Para monitoramento"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("🛑 Hot Reload watcher parado")
    
    def get_change_history(self, limit: int = 10) -> List[ConfigChange]:
        """Retorna histórico de mudanças"""
        return self._change_history[-limit:]
    
    def get_watched_files(self) -> List[Dict[str, Any]]:
        """Retorna informações dos arquivos monitorados"""
        result = []
        for path in self.watch_paths:
            info = {
                'path': path,
                'exists': os.path.exists(path),
                'hash': self._file_hashes.get(path, ""),
            }
            if os.path.exists(path):
                info['modified'] = datetime.fromtimestamp(
                    os.path.getmtime(path)
                ).isoformat()
            result.append(info)
        return result
    
    def add_watch_path(self, path: str):
        """Adiciona caminho para monitorar"""
        if path not in self.watch_paths:
            self.watch_paths.append(path)
            if os.path.exists(path):
                self._file_hashes[path] = self._calculate_hash(path)
            logger.info(f"➕ Adicionado path para watch: {path}")


# Singleton
_hot_reload: Optional[ConfigHotReload] = None


def get_hot_reload(
    config_manager=None,
    **kwargs
) -> ConfigHotReload:
    """Obtém instância singleton do Hot Reload"""
    global _hot_reload
    if _hot_reload is None:
        if config_manager is None:
            raise ValueError("config_manager obrigatório na primeira chamada")
        _hot_reload = ConfigHotReload(config_manager, **kwargs)
    return _hot_reload


def setup_hot_reload(config_manager, auto_start: bool = True) -> ConfigHotReload:
    """
    Configura e inicia hot reload
    
    Args:
        config_manager: Instância do ConfigManager
        auto_start: Se deve iniciar watcher automaticamente
        
    Returns:
        Instância do ConfigHotReload
    """
    hot_reload = get_hot_reload(config_manager)
    
    if auto_start:
        hot_reload.start()
    
    return hot_reload


# Exemplo de uso:
"""
from core.config_manager import ConfigManager
from core.config_hot_reload import setup_hot_reload

# Inicializar
config = ConfigManager("config/config.yaml")
hot_reload = setup_hot_reload(config)

# Registrar callbacks para mudanças específicas
def on_risk_change(key: str, new_value):
    if key.startswith("risk_management"):
        print(f"Risk config mudou: {key} = {new_value}")
        # Atualizar risk_manager com novo valor

hot_reload.register_callback(on_risk_change)

# No main loop ou shutdown
# hot_reload.stop()
"""
