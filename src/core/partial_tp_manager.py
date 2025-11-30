"""
Partial Take Profit Manager - Sistema Multinível
Inspirado em Freqtrade/Jesse para maximizar lucros com múltiplos alvos

Features:
- Múltiplos níveis de TP configuráveis
- Risk-free após primeiro TP
- Trailing do restante
- Integração com Kelly Criterion
"""
import MetaTrader5 as mt5
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import json
import os


class PartialTPMode(Enum):
    """Modos de Partial Take Profit"""
    FIXED_LEVELS = "fixed"           # Níveis fixos de preço
    RISK_REWARD = "risk_reward"      # Baseado em múltiplos de risco
    ATR_BASED = "atr_based"          # Baseado em ATR
    FIBONACCI = "fibonacci"          # Níveis de Fibonacci
    DYNAMIC = "dynamic"              # Ajuste dinâmico baseado em momentum


@dataclass
class PartialTPLevel:
    """Representa um nível de take profit parcial"""
    level_id: int
    trigger_type: str               # 'price', 'rr_ratio', 'atr_multiple', 'fib_level'
    trigger_value: float            # Valor do trigger
    close_percent: float            # Porcentagem do volume a fechar (0.0-1.0)
    move_sl_to: Optional[str]       # 'breakeven', 'entry', 'previous_tp', None
    trail_remainder: bool = False   # Se deve iniciar trailing após este TP
    
    executed: bool = False
    executed_at: Optional[datetime] = None
    executed_price: Optional[float] = None


@dataclass
class PositionTPState:
    """Estado de TP para uma posição específica"""
    ticket: int
    symbol: str
    position_type: int              # 0=BUY, 1=SELL
    entry_price: float
    original_volume: float
    current_volume: float
    original_sl: float
    current_sl: float
    tp_levels: List[PartialTPLevel]
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def remaining_percent(self) -> float:
        """Porcentagem do volume restante"""
        if self.original_volume == 0:
            return 0.0
        return self.current_volume / self.original_volume
    
    @property
    def all_levels_executed(self) -> bool:
        """Todos os níveis foram executados?"""
        return all(level.executed for level in self.tp_levels)
    
    @property
    def next_level(self) -> Optional[PartialTPLevel]:
        """Próximo nível a ser executado"""
        for level in sorted(self.tp_levels, key=lambda x: x.level_id):
            if not level.executed:
                return level
        return None


class PartialTPManager:
    """
    Gerenciador de Take Profit Parcial Multinível
    
    Implementa estratégias avançadas de saída como:
    - Múltiplos níveis de TP (ex: 33% em 1R, 33% em 2R, 34% em 3R)
    - Move SL para breakeven após primeiro TP
    - Trailing stop no restante
    - Configuração via JSON
    """
    
    # Presets de configuração
    PRESETS = {
        "conservative": [
            {"trigger_type": "rr_ratio", "trigger_value": 1.0, "close_percent": 0.50, "move_sl_to": "breakeven"},
            {"trigger_type": "rr_ratio", "trigger_value": 2.0, "close_percent": 0.50, "move_sl_to": None},
        ],
        "balanced": [
            {"trigger_type": "rr_ratio", "trigger_value": 1.0, "close_percent": 0.33, "move_sl_to": "breakeven"},
            {"trigger_type": "rr_ratio", "trigger_value": 2.0, "close_percent": 0.33, "move_sl_to": "previous_tp"},
            {"trigger_type": "rr_ratio", "trigger_value": 3.0, "close_percent": 0.34, "move_sl_to": None, "trail_remainder": True},
        ],
        "aggressive": [
            {"trigger_type": "rr_ratio", "trigger_value": 1.5, "close_percent": 0.25, "move_sl_to": "breakeven"},
            {"trigger_type": "rr_ratio", "trigger_value": 3.0, "close_percent": 0.25, "move_sl_to": "previous_tp"},
            {"trigger_type": "rr_ratio", "trigger_value": 5.0, "close_percent": 0.50, "move_sl_to": None, "trail_remainder": True},
        ],
        "fibonacci": [
            {"trigger_type": "fib_level", "trigger_value": 1.618, "close_percent": 0.33, "move_sl_to": "breakeven"},
            {"trigger_type": "fib_level", "trigger_value": 2.618, "close_percent": 0.33, "move_sl_to": "previous_tp"},
            {"trigger_type": "fib_level", "trigger_value": 4.236, "close_percent": 0.34, "move_sl_to": None},
        ],
        "scalping": [
            {"trigger_type": "rr_ratio", "trigger_value": 0.5, "close_percent": 0.50, "move_sl_to": "breakeven"},
            {"trigger_type": "rr_ratio", "trigger_value": 1.0, "close_percent": 0.50, "move_sl_to": None},
        ],
    }
    
    def __init__(self, mt5_connector, config: Optional[Dict] = None):
        """
        Inicializa o Partial TP Manager
        
        Args:
            mt5_connector: Instância do MT5Connector
            config: Configuração com níveis de TP
        """
        self.mt5 = mt5_connector
        self.config = config or {}
        
        # Configurações
        ptp_config = self.config.get('partial_tp', {})
        self.enabled = ptp_config.get('enabled', True)
        self.preset = ptp_config.get('preset', 'balanced')
        self.custom_levels = ptp_config.get('levels', [])
        self.min_volume_for_partial = ptp_config.get('min_volume', 0.02)
        
        # Estado das posições
        self._position_states: Dict[int, PositionTPState] = {}
        
        # Carregar estado persistido
        self._state_file = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 'data', 'partial_tp_state.json'
        )
        self._load_state()
        
        logger.info(
            f"🎯 Partial TP Manager inicializado | "
            f"Enabled: {self.enabled} | "
            f"Preset: {self.preset} | "
            f"Min Volume: {self.min_volume_for_partial}"
        )
    
    def _load_state(self):
        """Carrega estado persistido"""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, 'r') as f:
                    data = json.load(f)
                    # Reconstruir estados (simplificado - em produção usar serialização completa)
                    logger.debug(f"Loaded {len(data)} partial TP states")
        except Exception as e:
            logger.warning(f"Erro ao carregar estado de partial TP: {e}")
    
    def _save_state(self):
        """Persiste estado atual"""
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            # Serializar estados
            data = {}
            for ticket, state in self._position_states.items():
                data[str(ticket)] = {
                    'symbol': state.symbol,
                    'entry_price': state.entry_price,
                    'levels_executed': [l.level_id for l in state.tp_levels if l.executed]
                }
            
            with open(self._state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Erro ao salvar estado de partial TP: {e}")
    
    def _get_tp_levels(self) -> List[Dict]:
        """Obtém níveis de TP configurados"""
        if self.custom_levels:
            return self.custom_levels
        return self.PRESETS.get(self.preset, self.PRESETS['balanced'])
    
    def _calculate_atr(self, symbol: str, period: int = 14) -> float:
        """Calcula ATR para o símbolo"""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, period + 5)
            if rates is None or len(rates) < period:
                return 0.0
            
            import numpy as np
            true_ranges = []
            for i in range(1, len(rates)):
                high = rates[i]['high']
                low = rates[i]['low']
                prev_close = rates[i-1]['close']
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                true_ranges.append(tr)
            
            return np.mean(true_ranges[-period:])
        except Exception as e:
            logger.error(f"Erro ao calcular ATR: {e}")
            return 0.0
    
    def register_position(
        self,
        position: Dict,
        sl_price: Optional[float] = None,
        custom_levels: Optional[List[Dict]] = None
    ) -> PositionTPState:
        """
        Registra uma posição para gerenciamento de partial TP
        
        Args:
            position: Dados da posição do MT5
            sl_price: Preço do stop loss (para calcular R)
            custom_levels: Níveis customizados (override config)
            
        Returns:
            Estado da posição criado
        """
        ticket = position['ticket']
        symbol = position['symbol']
        pos_type = position['type']
        entry_price = position['price_open']
        volume = position['volume']
        sl = sl_price or position.get('sl', 0)
        
        # Calcular R (risco por unidade)
        if sl == 0:
            # Usar ATR como proxy
            atr = self._calculate_atr(symbol)
            if pos_type == 0:  # BUY
                sl = entry_price - (atr * 2)
            else:  # SELL
                sl = entry_price + (atr * 2)
        
        risk_per_unit = abs(entry_price - sl)
        
        # Criar níveis de TP
        levels_config = custom_levels or self._get_tp_levels()
        tp_levels = []
        
        for i, level_cfg in enumerate(levels_config):
            # Calcular preço trigger
            trigger_type = level_cfg.get('trigger_type', 'rr_ratio')
            trigger_value = level_cfg.get('trigger_value', 1.0)
            
            if trigger_type == 'rr_ratio':
                # Múltiplo de R
                if pos_type == 0:  # BUY
                    trigger_price = entry_price + (risk_per_unit * trigger_value)
                else:  # SELL
                    trigger_price = entry_price - (risk_per_unit * trigger_value)
                    
            elif trigger_type == 'atr_multiple':
                atr = self._calculate_atr(symbol)
                if pos_type == 0:
                    trigger_price = entry_price + (atr * trigger_value)
                else:
                    trigger_price = entry_price - (atr * trigger_value)
                    
            elif trigger_type == 'fib_level':
                # Fibonacci extension
                if pos_type == 0:
                    trigger_price = entry_price + (risk_per_unit * trigger_value)
                else:
                    trigger_price = entry_price - (risk_per_unit * trigger_value)
                    
            else:  # price
                trigger_price = trigger_value
            
            tp_level = PartialTPLevel(
                level_id=i + 1,
                trigger_type=trigger_type,
                trigger_value=trigger_price,  # Armazena preço calculado
                close_percent=level_cfg.get('close_percent', 0.33),
                move_sl_to=level_cfg.get('move_sl_to'),
                trail_remainder=level_cfg.get('trail_remainder', False)
            )
            tp_levels.append(tp_level)
        
        # Criar estado
        state = PositionTPState(
            ticket=ticket,
            symbol=symbol,
            position_type=pos_type,
            entry_price=entry_price,
            original_volume=volume,
            current_volume=volume,
            original_sl=sl,
            current_sl=sl,
            tp_levels=tp_levels
        )
        
        self._position_states[ticket] = state
        self._save_state()
        
        logger.info(
            f"📊 Partial TP registrado | #{ticket} {symbol} | "
            f"Entry: {entry_price:.5f} | SL: {sl:.5f} | "
            f"Níveis: {len(tp_levels)}"
        )
        
        for level in tp_levels:
            logger.debug(
                f"   Level {level.level_id}: TP @ {level.trigger_value:.5f} | "
                f"Close {level.close_percent*100:.0f}% | SL -> {level.move_sl_to}"
            )
        
        return state
    
    def check_position(
        self,
        position: Dict,
        current_price: float
    ) -> List[Dict[str, Any]]:
        """
        Verifica e retorna ações necessárias para uma posição
        
        Args:
            position: Dados da posição
            current_price: Preço atual
            
        Returns:
            Lista de ações a executar
        """
        ticket = position['ticket']
        
        # Verificar se posição está registrada
        if ticket not in self._position_states:
            # Auto-registrar com config padrão
            self.register_position(position)
        
        state = self._position_states[ticket]
        actions = []
        
        # Verificar cada nível não executado
        for level in sorted(state.tp_levels, key=lambda x: x.level_id):
            if level.executed:
                continue
            
            triggered = False
            
            if state.position_type == 0:  # BUY
                if current_price >= level.trigger_value:
                    triggered = True
            else:  # SELL
                if current_price <= level.trigger_value:
                    triggered = True
            
            if triggered:
                # Calcular volume a fechar
                close_volume = round(state.current_volume * level.close_percent, 2)
                
                # Verificar volume mínimo
                if close_volume < self.min_volume_for_partial:
                    # Se volume muito pequeno, fechar tudo que resta
                    close_volume = state.current_volume
                
                # Criar ação
                action = {
                    'type': 'partial_close',
                    'ticket': ticket,
                    'level_id': level.level_id,
                    'close_volume': close_volume,
                    'trigger_price': level.trigger_value,
                    'current_price': current_price,
                }
                
                # Mover SL?
                if level.move_sl_to:
                    new_sl = self._calculate_new_sl(state, level)
                    if new_sl:
                        action['move_sl'] = new_sl
                
                # Iniciar trailing?
                if level.trail_remainder:
                    action['start_trailing'] = True
                
                actions.append(action)
                break  # Processar um nível por vez
        
        return actions
    
    def _calculate_new_sl(
        self,
        state: PositionTPState,
        level: PartialTPLevel
    ) -> Optional[float]:
        """Calcula novo SL após partial TP"""
        
        if level.move_sl_to == 'breakeven':
            # Mover para preço de entrada + pequeno buffer
            symbol_info = mt5.symbol_info(state.symbol)
            if symbol_info:
                buffer = symbol_info.point * 30  # ~3 pips
                if state.position_type == 0:  # BUY
                    return state.entry_price + buffer
                else:
                    return state.entry_price - buffer
            return state.entry_price
            
        elif level.move_sl_to == 'entry':
            return state.entry_price
            
        elif level.move_sl_to == 'previous_tp':
            # Mover para o TP anterior
            prev_levels = [l for l in state.tp_levels if l.executed and l.level_id < level.level_id]
            if prev_levels:
                last_tp = max(prev_levels, key=lambda x: x.level_id)
                return last_tp.trigger_value
            return state.entry_price
        
        return None
    
    def execute_action(
        self,
        action: Dict[str, Any],
        executor_callback: Optional[callable] = None
    ) -> bool:
        """
        Executa uma ação de partial TP
        
        Args:
            action: Ação retornada por check_position
            executor_callback: Callback para executar no MT5
            
        Returns:
            True se executou com sucesso
        """
        ticket = action['ticket']
        
        if ticket not in self._position_states:
            logger.error(f"Posição #{ticket} não encontrada no estado")
            return False
        
        state = self._position_states[ticket]
        level_id = action['level_id']
        
        try:
            success = True
            
            # 1. Fechar parcial
            close_volume = action['close_volume']
            
            if executor_callback:
                # Usar callback personalizado
                result = executor_callback('partial_close', ticket, close_volume)
                success = result.get('success', False)
            else:
                # Executar diretamente no MT5
                position_info = mt5.positions_get(ticket=ticket)
                if position_info:
                    pos = position_info[0]
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": state.symbol,
                        "volume": close_volume,
                        "type": mt5.ORDER_TYPE_SELL if state.position_type == 0 else mt5.ORDER_TYPE_BUY,
                        "position": ticket,
                        "deviation": 20,
                        "magic": pos.magic,
                        "comment": f"Partial TP L{level_id}",
                    }
                    result = mt5.order_send(request)
                    success = result and result.retcode == mt5.TRADE_RETCODE_DONE
            
            if not success:
                logger.error(f"Falha ao executar partial close #{ticket}")
                return False
            
            # 2. Atualizar estado
            level = next((l for l in state.tp_levels if l.level_id == level_id), None)
            if level:
                level.executed = True
                level.executed_at = datetime.now()
                level.executed_price = action['current_price']
            
            state.current_volume -= close_volume
            state.last_updated = datetime.now()
            
            logger.success(
                f"✅ Partial TP executado | #{ticket} Level {level_id} | "
                f"Fechado: {close_volume} | Restante: {state.current_volume:.2f}"
            )
            
            # 3. Mover SL se necessário
            if 'move_sl' in action and action['move_sl']:
                new_sl = action['move_sl']
                
                if executor_callback:
                    result = executor_callback('modify_sl', ticket, new_sl)
                else:
                    position_info = mt5.positions_get(ticket=ticket)
                    if position_info:
                        pos = position_info[0]
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "symbol": state.symbol,
                            "position": ticket,
                            "sl": new_sl,
                            "tp": pos.tp,
                        }
                        result = mt5.order_send(request)
                        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                            state.current_sl = new_sl
                            logger.info(f"🔒 SL movido para {new_sl:.5f}")
            
            self._save_state()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao executar partial TP: {e}")
            return False
    
    def remove_position(self, ticket: int):
        """Remove posição do gerenciamento"""
        if ticket in self._position_states:
            del self._position_states[ticket]
            self._save_state()
            logger.debug(f"Posição #{ticket} removida do Partial TP Manager")
    
    def get_position_state(self, ticket: int) -> Optional[PositionTPState]:
        """Obtém estado de uma posição"""
        return self._position_states.get(ticket)
    
    def get_all_states(self) -> Dict[int, PositionTPState]:
        """Obtém todos os estados"""
        return self._position_states.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo do manager"""
        total_positions = len(self._position_states)
        total_partials = sum(
            sum(1 for l in s.tp_levels if l.executed)
            for s in self._position_states.values()
        )
        
        return {
            'enabled': self.enabled,
            'preset': self.preset,
            'positions_managed': total_positions,
            'partials_executed': total_partials,
            'positions': [
                {
                    'ticket': state.ticket,
                    'symbol': state.symbol,
                    'remaining_percent': state.remaining_percent * 100,
                    'levels_executed': sum(1 for l in state.tp_levels if l.executed),
                    'total_levels': len(state.tp_levels)
                }
                for state in self._position_states.values()
            ]
        }


# Singleton
_partial_tp_manager: Optional[PartialTPManager] = None


def get_partial_tp_manager(
    mt5_connector=None,
    config: Optional[Dict] = None
) -> PartialTPManager:
    """Obtém instância singleton do Partial TP Manager"""
    global _partial_tp_manager
    if _partial_tp_manager is None:
        _partial_tp_manager = PartialTPManager(mt5_connector, config)
    return _partial_tp_manager


# Exemplo de configuração no config.yaml:
"""
partial_tp:
  enabled: true
  preset: "balanced"  # conservative, balanced, aggressive, fibonacci, scalping
  min_volume: 0.02
  
  # OU níveis customizados:
  levels:
    - trigger_type: "rr_ratio"
      trigger_value: 1.0
      close_percent: 0.33
      move_sl_to: "breakeven"
    
    - trigger_type: "rr_ratio"
      trigger_value: 2.0
      close_percent: 0.33
      move_sl_to: "previous_tp"
    
    - trigger_type: "rr_ratio"
      trigger_value: 3.0
      close_percent: 0.34
      move_sl_to: null
      trail_remainder: true
"""
