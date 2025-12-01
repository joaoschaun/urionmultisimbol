# -*- coding: utf-8 -*-
"""
State Manager & Disaster Recovery

Gerencia estado do bot com:
- Checkpoints periódicos
- Recovery após crash
- Sincronização com MT5
- Transações atômicas
"""

import json
import pickle
import threading
import time
import os
import shutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
import logging
import hashlib
import gzip

logger = logging.getLogger(__name__)


@dataclass
class PositionState:
    """Estado de uma posição"""
    ticket: int
    symbol: str
    direction: str
    volume: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    current_profit: float
    magic: int
    strategy: str


@dataclass
class OrderState:
    """Estado de uma ordem pendente"""
    ticket: int
    symbol: str
    order_type: str
    direction: str
    volume: float
    price: float
    stop_loss: float
    take_profit: float
    magic: int
    strategy: str


@dataclass
class MLModelState:
    """Estado de modelos ML"""
    model_name: str
    last_training: datetime
    accuracy: float
    sharpe_ratio: float
    is_valid: bool


@dataclass
class BotState:
    """Estado completo do bot"""
    # Identificação
    version: str = "2.2"
    instance_id: str = ""
    
    # Timestamp
    saved_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    
    # Trading
    positions: List[PositionState] = field(default_factory=list)
    pending_orders: List[OrderState] = field(default_factory=list)
    
    # Account
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    
    # Performance
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    total_trades_today: int = 0
    current_drawdown: float = 0.0
    
    # ML
    ml_models: List[MLModelState] = field(default_factory=list)
    
    # Estratégias
    active_strategies: List[str] = field(default_factory=list)
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    
    # Last processed
    last_bar_time: Dict[str, datetime] = field(default_factory=dict)
    last_signal_time: datetime = None
    
    # Errors
    last_error: str = ""
    error_count: int = 0
    
    # Checksum
    checksum: str = ""


class StateSerializer:
    """Serializa e deserializa estado"""
    
    @staticmethod
    def serialize(state: BotState) -> bytes:
        """Serializa estado para bytes"""
        # Converter para dict
        state_dict = StateSerializer._to_dict(state)
        
        # JSON -> bytes
        json_str = json.dumps(state_dict, default=str, indent=2)
        
        # Comprimir
        compressed = gzip.compress(json_str.encode('utf-8'))
        
        return compressed
    
    @staticmethod
    def deserialize(data: bytes) -> BotState:
        """Deserializa bytes para estado"""
        # Descomprimir
        json_str = gzip.decompress(data).decode('utf-8')
        
        # Parse JSON
        state_dict = json.loads(json_str)
        
        # Converter para BotState
        return StateSerializer._from_dict(state_dict)
    
    @staticmethod
    def _to_dict(state: BotState) -> Dict:
        """Converte BotState para dict"""
        d = {
            'version': state.version,
            'instance_id': state.instance_id,
            'saved_at': state.saved_at.isoformat() if state.saved_at else None,
            'last_heartbeat': state.last_heartbeat.isoformat() if state.last_heartbeat else None,
            'positions': [
                {
                    'ticket': p.ticket,
                    'symbol': p.symbol,
                    'direction': p.direction,
                    'volume': p.volume,
                    'entry_price': p.entry_price,
                    'entry_time': p.entry_time.isoformat() if p.entry_time else None,
                    'stop_loss': p.stop_loss,
                    'take_profit': p.take_profit,
                    'current_profit': p.current_profit,
                    'magic': p.magic,
                    'strategy': p.strategy
                }
                for p in state.positions
            ],
            'pending_orders': [
                {
                    'ticket': o.ticket,
                    'symbol': o.symbol,
                    'order_type': o.order_type,
                    'direction': o.direction,
                    'volume': o.volume,
                    'price': o.price,
                    'stop_loss': o.stop_loss,
                    'take_profit': o.take_profit,
                    'magic': o.magic,
                    'strategy': o.strategy
                }
                for o in state.pending_orders
            ],
            'balance': state.balance,
            'equity': state.equity,
            'margin': state.margin,
            'free_margin': state.free_margin,
            'daily_pnl': state.daily_pnl,
            'weekly_pnl': state.weekly_pnl,
            'total_trades_today': state.total_trades_today,
            'current_drawdown': state.current_drawdown,
            'ml_models': [
                {
                    'model_name': m.model_name,
                    'last_training': m.last_training.isoformat() if m.last_training else None,
                    'accuracy': m.accuracy,
                    'sharpe_ratio': m.sharpe_ratio,
                    'is_valid': m.is_valid
                }
                for m in state.ml_models
            ],
            'active_strategies': state.active_strategies,
            'strategy_weights': state.strategy_weights,
            'last_bar_time': {
                k: v.isoformat() if v else None 
                for k, v in state.last_bar_time.items()
            },
            'last_signal_time': state.last_signal_time.isoformat() if state.last_signal_time else None,
            'last_error': state.last_error,
            'error_count': state.error_count,
            'checksum': state.checksum
        }
        return d
    
    @staticmethod
    def _from_dict(d: Dict) -> BotState:
        """Converte dict para BotState"""
        state = BotState(
            version=d.get('version', '2.2'),
            instance_id=d.get('instance_id', ''),
            saved_at=datetime.fromisoformat(d['saved_at']) if d.get('saved_at') else None,
            last_heartbeat=datetime.fromisoformat(d['last_heartbeat']) if d.get('last_heartbeat') else None,
            balance=d.get('balance', 0.0),
            equity=d.get('equity', 0.0),
            margin=d.get('margin', 0.0),
            free_margin=d.get('free_margin', 0.0),
            daily_pnl=d.get('daily_pnl', 0.0),
            weekly_pnl=d.get('weekly_pnl', 0.0),
            total_trades_today=d.get('total_trades_today', 0),
            current_drawdown=d.get('current_drawdown', 0.0),
            active_strategies=d.get('active_strategies', []),
            strategy_weights=d.get('strategy_weights', {}),
            last_signal_time=datetime.fromisoformat(d['last_signal_time']) if d.get('last_signal_time') else None,
            last_error=d.get('last_error', ''),
            error_count=d.get('error_count', 0),
            checksum=d.get('checksum', '')
        )
        
        # Positions
        for p in d.get('positions', []):
            state.positions.append(PositionState(
                ticket=p['ticket'],
                symbol=p['symbol'],
                direction=p['direction'],
                volume=p['volume'],
                entry_price=p['entry_price'],
                entry_time=datetime.fromisoformat(p['entry_time']) if p.get('entry_time') else None,
                stop_loss=p['stop_loss'],
                take_profit=p['take_profit'],
                current_profit=p['current_profit'],
                magic=p['magic'],
                strategy=p['strategy']
            ))
        
        # Orders
        for o in d.get('pending_orders', []):
            state.pending_orders.append(OrderState(
                ticket=o['ticket'],
                symbol=o['symbol'],
                order_type=o['order_type'],
                direction=o['direction'],
                volume=o['volume'],
                price=o['price'],
                stop_loss=o['stop_loss'],
                take_profit=o['take_profit'],
                magic=o['magic'],
                strategy=o['strategy']
            ))
        
        # ML Models
        for m in d.get('ml_models', []):
            state.ml_models.append(MLModelState(
                model_name=m['model_name'],
                last_training=datetime.fromisoformat(m['last_training']) if m.get('last_training') else None,
                accuracy=m['accuracy'],
                sharpe_ratio=m['sharpe_ratio'],
                is_valid=m['is_valid']
            ))
        
        # Last bar times
        for k, v in d.get('last_bar_time', {}).items():
            state.last_bar_time[k] = datetime.fromisoformat(v) if v else None
        
        return state
    
    @staticmethod
    def calculate_checksum(state: BotState) -> str:
        """Calcula checksum do estado"""
        state_copy = BotState(**{
            k: v for k, v in state.__dict__.items() 
            if k != 'checksum'
        })
        
        state_copy.checksum = ""
        serialized = StateSerializer.serialize(state_copy)
        
        return hashlib.sha256(serialized).hexdigest()[:16]


class StateManager:
    """
    Gerenciador de Estado do Bot
    
    Features:
    - Checkpoints automáticos
    - Recovery após crash
    - Sincronização com MT5
    - Histórico de estados
    """
    
    def __init__(self, config: Dict[str, Any] = None, mt5_connector = None):
        self.config = config or {}
        self.mt5 = mt5_connector
        
        # Diretórios
        self.state_dir = Path(self.config.get('state_dir', 'data/state'))
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.backup_dir = self.state_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        
        # Arquivos
        self.current_state_file = self.state_dir / 'current_state.gz'
        self.checkpoint_file = self.state_dir / 'checkpoint.gz'
        
        # Estado atual
        self.current_state: Optional[BotState] = None
        
        # Configurações
        self.checkpoint_interval = self.config.get('checkpoint_interval', 60)  # segundos
        self.max_backups = self.config.get('max_backups', 100)
        
        # Threading
        self.running = False
        self._checkpoint_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Gerar instance ID único
        self.instance_id = f"urion_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
        
        logger.info(f"StateManager inicializado (instance: {self.instance_id})")
    
    def start(self):
        """Inicia o gerenciador de estado"""
        if self.running:
            return
        
        self.running = True
        
        # Tentar recuperar estado anterior
        self.current_state = self._recover_state()
        
        if self.current_state is None:
            self.current_state = BotState(instance_id=self.instance_id)
            logger.info("Novo estado criado")
        else:
            logger.info(f"Estado recuperado de {self.current_state.saved_at}")
            self._sync_with_mt5()
        
        # Iniciar thread de checkpoint
        self._checkpoint_thread = threading.Thread(
            target=self._checkpoint_loop,
            daemon=True,
            name="StateCheckpoint"
        )
        self._checkpoint_thread.start()
        
        logger.info("StateManager iniciado")
    
    def stop(self):
        """Para o gerenciador de estado"""
        self.running = False
        
        # Salvar estado final
        self.save_checkpoint("shutdown")
        
        logger.info("StateManager parado")
    
    def save_checkpoint(self, reason: str = "periodic"):
        """Salva checkpoint do estado atual"""
        with self._lock:
            if self.current_state is None:
                return
            
            try:
                # Atualizar timestamp
                self.current_state.saved_at = datetime.now()
                self.current_state.last_heartbeat = datetime.now()
                
                # Calcular checksum
                self.current_state.checksum = StateSerializer.calculate_checksum(
                    self.current_state
                )
                
                # Serializar
                data = StateSerializer.serialize(self.current_state)
                
                # Salvar estado atual (atômico)
                temp_file = self.current_state_file.with_suffix('.tmp')
                with open(temp_file, 'wb') as f:
                    f.write(data)
                
                # Mover atomicamente
                shutil.move(str(temp_file), str(self.current_state_file))
                
                # Criar backup periódico
                if reason in ['periodic', 'shutdown', 'error']:
                    self._create_backup(data, reason)
                
                logger.debug(f"Checkpoint salvo ({reason}): {len(data)} bytes")
                
            except Exception as e:
                logger.error(f"Erro ao salvar checkpoint: {e}")
    
    def _create_backup(self, data: bytes, reason: str):
        """Cria backup do estado"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = self.backup_dir / f"state_{timestamp}_{reason}.gz"
        
        with open(backup_file, 'wb') as f:
            f.write(data)
        
        # Limpar backups antigos
        self._cleanup_old_backups()
    
    def _cleanup_old_backups(self):
        """Remove backups antigos"""
        backups = sorted(
            self.backup_dir.glob('state_*.gz'),
            key=lambda f: f.stat().st_mtime
        )
        
        while len(backups) > self.max_backups:
            old_backup = backups.pop(0)
            old_backup.unlink()
            logger.debug(f"Backup removido: {old_backup}")
    
    def _recover_state(self) -> Optional[BotState]:
        """Tenta recuperar estado anterior"""
        
        # Tentar estado atual primeiro
        if self.current_state_file.exists():
            try:
                with open(self.current_state_file, 'rb') as f:
                    data = f.read()
                state = StateSerializer.deserialize(data)
                
                # Verificar checksum
                expected = StateSerializer.calculate_checksum(state)
                if expected == state.checksum:
                    logger.info("Estado atual recuperado e verificado")
                    return state
                else:
                    logger.warning("Checksum inválido no estado atual")
            except Exception as e:
                logger.warning(f"Erro ao recuperar estado atual: {e}")
        
        # Tentar checkpoint
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'rb') as f:
                    data = f.read()
                state = StateSerializer.deserialize(data)
                logger.info("Checkpoint recuperado")
                return state
            except Exception as e:
                logger.warning(f"Erro ao recuperar checkpoint: {e}")
        
        # Tentar último backup
        backups = sorted(
            self.backup_dir.glob('state_*.gz'),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        for backup in backups:
            try:
                with open(backup, 'rb') as f:
                    data = f.read()
                state = StateSerializer.deserialize(data)
                logger.info(f"Estado recuperado de backup: {backup}")
                return state
            except Exception as e:
                logger.warning(f"Erro ao recuperar backup {backup}: {e}")
        
        logger.warning("Nenhum estado anterior encontrado")
        return None
    
    def _sync_with_mt5(self):
        """Sincroniza estado com MT5"""
        if self.mt5 is None:
            logger.warning("MT5 não disponível para sincronização")
            return
        
        try:
            import MetaTrader5 as mt5
            
            # Obter posições reais do MT5
            mt5_positions = mt5.positions_get()
            
            if mt5_positions is None:
                logger.warning("Não foi possível obter posições do MT5")
                return
            
            mt5_tickets = {p.ticket for p in mt5_positions}
            state_tickets = {p.ticket for p in self.current_state.positions}
            
            # Posições que existem no MT5 mas não no estado
            missing_in_state = mt5_tickets - state_tickets
            if missing_in_state:
                logger.warning(f"Posições no MT5 não no estado: {missing_in_state}")
                for pos in mt5_positions:
                    if pos.ticket in missing_in_state:
                        self.current_state.positions.append(PositionState(
                            ticket=pos.ticket,
                            symbol=pos.symbol,
                            direction='buy' if pos.type == 0 else 'sell',
                            volume=pos.volume,
                            entry_price=pos.price_open,
                            entry_time=datetime.fromtimestamp(pos.time),
                            stop_loss=pos.sl,
                            take_profit=pos.tp,
                            current_profit=pos.profit,
                            magic=pos.magic,
                            strategy='unknown'  # Tentar inferir
                        ))
            
            # Posições no estado mas não no MT5 (foram fechadas)
            closed_in_mt5 = state_tickets - mt5_tickets
            if closed_in_mt5:
                logger.warning(f"Posições fechadas no MT5: {closed_in_mt5}")
                self.current_state.positions = [
                    p for p in self.current_state.positions 
                    if p.ticket not in closed_in_mt5
                ]
            
            # Atualizar info da conta
            account_info = mt5.account_info()
            if account_info:
                self.current_state.balance = account_info.balance
                self.current_state.equity = account_info.equity
                self.current_state.margin = account_info.margin
                self.current_state.free_margin = account_info.margin_free
            
            logger.info("Sincronização com MT5 concluída")
            
        except Exception as e:
            logger.error(f"Erro na sincronização com MT5: {e}")
    
    def _checkpoint_loop(self):
        """Loop de checkpoint em background"""
        while self.running:
            try:
                time.sleep(self.checkpoint_interval)
                
                if self.running:
                    self.save_checkpoint("periodic")
                    
            except Exception as e:
                logger.error(f"Erro no checkpoint loop: {e}")
                self.current_state.last_error = str(e)
                self.current_state.error_count += 1
    
    def update_position(self, position: PositionState):
        """Atualiza ou adiciona posição"""
        with self._lock:
            # Remover posição existente
            self.current_state.positions = [
                p for p in self.current_state.positions
                if p.ticket != position.ticket
            ]
            # Adicionar nova
            self.current_state.positions.append(position)
    
    def remove_position(self, ticket: int):
        """Remove posição"""
        with self._lock:
            self.current_state.positions = [
                p for p in self.current_state.positions
                if p.ticket != ticket
            ]
    
    def update_performance(
        self,
        daily_pnl: float = None,
        weekly_pnl: float = None,
        trades_today: int = None,
        drawdown: float = None
    ):
        """Atualiza métricas de performance"""
        with self._lock:
            if daily_pnl is not None:
                self.current_state.daily_pnl = daily_pnl
            if weekly_pnl is not None:
                self.current_state.weekly_pnl = weekly_pnl
            if trades_today is not None:
                self.current_state.total_trades_today = trades_today
            if drawdown is not None:
                self.current_state.current_drawdown = drawdown
    
    def update_ml_model(self, model: MLModelState):
        """Atualiza estado de modelo ML"""
        with self._lock:
            # Remover modelo existente
            self.current_state.ml_models = [
                m for m in self.current_state.ml_models
                if m.model_name != model.model_name
            ]
            # Adicionar novo
            self.current_state.ml_models.append(model)
    
    def record_error(self, error: str):
        """Registra erro"""
        with self._lock:
            self.current_state.last_error = error
            self.current_state.error_count += 1
            
            # Salvar checkpoint imediato em caso de erro
            self.save_checkpoint("error")
    
    def heartbeat(self):
        """Atualiza heartbeat"""
        with self._lock:
            self.current_state.last_heartbeat = datetime.now()
    
    def get_state(self) -> BotState:
        """Retorna estado atual"""
        with self._lock:
            return self.current_state
    
    def get_recovery_summary(self) -> Dict[str, Any]:
        """Retorna resumo de recovery"""
        if self.current_state is None:
            return {'status': 'no_state'}
        
        return {
            'status': 'recovered' if self.current_state.saved_at else 'new',
            'instance_id': self.current_state.instance_id,
            'last_saved': self.current_state.saved_at.isoformat() if self.current_state.saved_at else None,
            'positions': len(self.current_state.positions),
            'pending_orders': len(self.current_state.pending_orders),
            'error_count': self.current_state.error_count,
            'last_error': self.current_state.last_error,
            'checksum': self.current_state.checksum
        }


# Instância global
_state_manager: Optional[StateManager] = None


def get_state_manager(config: Dict[str, Any] = None, mt5 = None) -> StateManager:
    """Retorna instância singleton do state manager"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(config, mt5)
    return _state_manager


# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Criar manager
    manager = get_state_manager()
    manager.start()
    
    # Simular operações
    manager.update_position(PositionState(
        ticket=12345,
        symbol='XAUUSD',
        direction='buy',
        volume=0.1,
        entry_price=2650.0,
        entry_time=datetime.now(),
        stop_loss=2640.0,
        take_profit=2670.0,
        current_profit=25.0,
        magic=100001,
        strategy='scalping'
    ))
    
    manager.update_performance(
        daily_pnl=150.0,
        trades_today=5,
        drawdown=0.02
    )
    
    manager.save_checkpoint("manual")
    
    print("Estado salvo:", manager.get_recovery_summary())
    
    manager.stop()
