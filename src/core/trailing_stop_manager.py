"""
Intelligent Trailing Stop Manager
Gerencia trailing stop baseado em ATR, estrutura de preço e momentum

Métodos:
1. ATR Trailing - Segue preço com distância baseada em ATR
2. Chandelier Exit - Trailing baseado em máximas/mínimas
3. Parabolic SAR - Acelera conforme tendência
4. Structure-based - Segue swing highs/lows
"""
import MetaTrader5 as mt5
import numpy as np
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime
from loguru import logger
from enum import Enum


class TrailingMethod(Enum):
    """Métodos de trailing stop"""
    ATR = "atr"                     # Distância baseada em ATR
    CHANDELIER = "chandelier"       # Baseado em High/Low
    PARABOLIC = "parabolic"         # Aceleração progressiva
    STRUCTURE = "structure"         # Baseado em swing points
    BREAKEVEN_PLUS = "breakeven_plus"  # Move para BE+X pips


class TrailingStopManager:
    """
    Gerenciador de Trailing Stop Inteligente
    
    Features:
    - Múltiplos métodos de trailing
    - ATR-adjusted trailing distance
    - Break-even automático
    - Partial take profit
    - Lock-in profits
    """
    
    def __init__(self, mt5_connector, config: Optional[Dict] = None):
        """
        Inicializa o trailing manager
        
        Args:
            mt5_connector: Instância do MT5Connector
            config: Configuração opcional
        """
        self.mt5 = mt5_connector
        self.config = config or {}
        
        # Configurações
        trailing_config = self.config.get('trailing', {})
        self.default_method = TrailingMethod(
            trailing_config.get('method', 'atr')
        )
        self.atr_multiplier = trailing_config.get('atr_multiplier', 2.0)
        self.breakeven_trigger_pips = trailing_config.get('breakeven_trigger', 15)
        self.breakeven_offset_pips = trailing_config.get('breakeven_offset', 3)
        self.min_trail_distance_pips = trailing_config.get('min_distance', 5)
        
        # Estado de posições (para Parabolic SAR)
        self._position_states: Dict[int, Dict] = {}
        
        logger.info(
            f"🎯 Trailing Stop Manager inicializado | "
            f"Method: {self.default_method.value} | "
            f"ATR mult: {self.atr_multiplier}x | "
            f"BE trigger: {self.breakeven_trigger_pips} pips"
        )
    
    def calculate_atr(
        self,
        symbol: str,
        timeframe: int = mt5.TIMEFRAME_H1,
        period: int = 14
    ) -> float:
        """Calcula ATR para o símbolo"""
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 5)
            if rates is None or len(rates) < period:
                return 0.0
            
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
    
    def get_swing_points(
        self,
        symbol: str,
        timeframe: int = mt5.TIMEFRAME_M15,
        lookback: int = 20
    ) -> Dict[str, List[float]]:
        """
        Identifica swing highs e lows recentes
        
        Returns:
            Dict com listas de swing highs e lows
        """
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
            if rates is None or len(rates) < 5:
                return {"highs": [], "lows": []}
            
            swing_highs = []
            swing_lows = []
            
            for i in range(2, len(rates) - 2):
                high = rates[i]['high']
                low = rates[i]['low']
                
                # Swing High: maior que vizinhos
                if (high > rates[i-1]['high'] and 
                    high > rates[i-2]['high'] and
                    high > rates[i+1]['high'] and 
                    high > rates[i+2]['high']):
                    swing_highs.append(high)
                
                # Swing Low: menor que vizinhos
                if (low < rates[i-1]['low'] and 
                    low < rates[i-2]['low'] and
                    low < rates[i+1]['low'] and 
                    low < rates[i+2]['low']):
                    swing_lows.append(low)
            
            return {
                "highs": sorted(swing_highs, reverse=True)[:5],
                "lows": sorted(swing_lows)[:5],
            }
            
        except Exception as e:
            logger.error(f"Erro ao identificar swing points: {e}")
            return {"highs": [], "lows": []}
    
    def calculate_trailing_atr(
        self,
        position: Dict,
        current_price: float,
        atr_value: Optional[float] = None
    ) -> Optional[float]:
        """
        Calcula trailing stop baseado em ATR
        
        O stop segue o preço mantendo distância de X * ATR
        """
        try:
            symbol = position['symbol']
            pos_type = position['type']  # 0=BUY, 1=SELL
            current_sl = position.get('sl', 0)
            entry_price = position['price_open']
            
            # Calcular ATR se não fornecido
            if atr_value is None:
                atr_value = self.calculate_atr(symbol)
            
            if atr_value <= 0:
                return None
            
            # Distância do trailing
            trail_distance = atr_value * self.atr_multiplier
            
            # Calcular novo SL
            if pos_type == 0:  # BUY
                new_sl = current_price - trail_distance
                
                # Só move se novo SL é maior que o atual
                if current_sl > 0 and new_sl <= current_sl:
                    return None
                
                # Não mover abaixo do preço de entrada
                if new_sl < entry_price:
                    return None
                    
            else:  # SELL
                new_sl = current_price + trail_distance
                
                # Só move se novo SL é menor que o atual
                if current_sl > 0 and new_sl >= current_sl:
                    return None
                
                # Não mover acima do preço de entrada
                if new_sl > entry_price:
                    return None
            
            return new_sl
            
        except Exception as e:
            logger.error(f"Erro no trailing ATR: {e}")
            return None
    
    def calculate_trailing_chandelier(
        self,
        position: Dict,
        current_price: float,
        lookback: int = 22
    ) -> Optional[float]:
        """
        Chandelier Exit
        
        BUY: SL = Highest High - ATR * multiplier
        SELL: SL = Lowest Low + ATR * multiplier
        """
        try:
            symbol = position['symbol']
            pos_type = position['type']
            current_sl = position.get('sl', 0)
            entry_price = position['price_open']
            
            # Obter dados
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, lookback)
            if rates is None or len(rates) < lookback:
                return None
            
            # ATR
            atr = self.calculate_atr(symbol)
            if atr <= 0:
                return None
            
            if pos_type == 0:  # BUY
                # Highest high do período
                highest_high = max(r['high'] for r in rates)
                new_sl = highest_high - (atr * self.atr_multiplier)
                
                # Validações
                if current_sl > 0 and new_sl <= current_sl:
                    return None
                if new_sl < entry_price:
                    return None
                    
            else:  # SELL
                # Lowest low do período
                lowest_low = min(r['low'] for r in rates)
                new_sl = lowest_low + (atr * self.atr_multiplier)
                
                # Validações
                if current_sl > 0 and new_sl >= current_sl:
                    return None
                if new_sl > entry_price:
                    return None
            
            return new_sl
            
        except Exception as e:
            logger.error(f"Erro no Chandelier: {e}")
            return None
    
    def calculate_trailing_structure(
        self,
        position: Dict,
        current_price: float
    ) -> Optional[float]:
        """
        Structure-based Trailing
        
        Move o stop para abaixo/acima do último swing point
        """
        try:
            symbol = position['symbol']
            pos_type = position['type']
            current_sl = position.get('sl', 0)
            entry_price = position['price_open']
            
            # Obter swing points
            swings = self.get_swing_points(symbol)
            
            # Obter info do símbolo
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return None
            
            # Buffer abaixo/acima do swing
            buffer = symbol_info.point * 50  # 5 pips
            
            if pos_type == 0:  # BUY
                # Usar último swing low como referência
                swing_lows = [sl for sl in swings['lows'] if sl < current_price]
                
                if not swing_lows:
                    return None
                
                # Pegar o swing low mais alto (mais próximo do preço)
                new_sl = max(swing_lows) - buffer
                
                # Validações
                if current_sl > 0 and new_sl <= current_sl:
                    return None
                if new_sl < entry_price:
                    return None
                    
            else:  # SELL
                # Usar último swing high como referência
                swing_highs = [sh for sh in swings['highs'] if sh > current_price]
                
                if not swing_highs:
                    return None
                
                # Pegar o swing high mais baixo (mais próximo do preço)
                new_sl = min(swing_highs) + buffer
                
                # Validações
                if current_sl > 0 and new_sl >= current_sl:
                    return None
                if new_sl > entry_price:
                    return None
            
            return new_sl
            
        except Exception as e:
            logger.error(f"Erro no Structure trailing: {e}")
            return None
    
    def calculate_trailing_parabolic(
        self,
        position: Dict,
        current_price: float
    ) -> Optional[float]:
        """
        Parabolic SAR-style Trailing
        
        Acelera o trailing conforme a posição vai a favor
        """
        try:
            ticket = position['ticket']
            symbol = position['symbol']
            pos_type = position['type']
            current_sl = position.get('sl', 0)
            entry_price = position['price_open']
            
            # Inicializar estado se necessário
            if ticket not in self._position_states:
                self._position_states[ticket] = {
                    'af': 0.02,  # Acceleration Factor
                    'af_max': 0.20,
                    'af_step': 0.02,
                    'extreme_point': current_price,
                    'sar': current_sl if current_sl > 0 else entry_price,
                }
            
            state = self._position_states[ticket]
            
            if pos_type == 0:  # BUY
                # Atualizar extreme point (highest)
                if current_price > state['extreme_point']:
                    state['extreme_point'] = current_price
                    state['af'] = min(state['af'] + state['af_step'], state['af_max'])
                
                # Calcular novo SAR
                new_sar = state['sar'] + state['af'] * (state['extreme_point'] - state['sar'])
                
                # SAR nunca pode estar acima do preço atual
                if new_sar >= current_price:
                    new_sar = current_price - (current_price * 0.001)  # 0.1% abaixo
                
                # Validações
                if current_sl > 0 and new_sar <= current_sl:
                    return None
                if new_sar < entry_price:
                    return None
                
                state['sar'] = new_sar
                return new_sar
                
            else:  # SELL
                # Atualizar extreme point (lowest)
                if current_price < state['extreme_point']:
                    state['extreme_point'] = current_price
                    state['af'] = min(state['af'] + state['af_step'], state['af_max'])
                
                # Calcular novo SAR
                new_sar = state['sar'] - state['af'] * (state['sar'] - state['extreme_point'])
                
                # SAR nunca pode estar abaixo do preço atual
                if new_sar <= current_price:
                    new_sar = current_price + (current_price * 0.001)  # 0.1% acima
                
                # Validações
                if current_sl > 0 and new_sar >= current_sl:
                    return None
                if new_sar > entry_price:
                    return None
                
                state['sar'] = new_sar
                return new_sar
                
        except Exception as e:
            logger.error(f"Erro no Parabolic trailing: {e}")
            return None
    
    def should_move_to_breakeven(
        self,
        position: Dict,
        current_price: float
    ) -> Tuple[bool, Optional[float]]:
        """
        Verifica se deve mover para break-even
        
        Returns:
            Tuple (should_move, new_sl_price)
        """
        try:
            pos_type = position['type']
            entry_price = position['price_open']
            current_sl = position.get('sl', 0)
            symbol = position['symbol']
            
            # Obter info do símbolo
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return False, None
            
            point = symbol_info.point
            
            # Calcular pip value
            if "JPY" in symbol:
                pip_value = point * 100
            else:
                pip_value = point * 10
            
            trigger_distance = self.breakeven_trigger_pips * pip_value
            offset_distance = self.breakeven_offset_pips * pip_value
            
            if pos_type == 0:  # BUY
                profit_distance = current_price - entry_price
                
                # Já em lucro suficiente?
                if profit_distance >= trigger_distance:
                    # SL ainda está abaixo do BE?
                    be_price = entry_price + offset_distance
                    if current_sl < be_price:
                        return True, be_price
                        
            else:  # SELL
                profit_distance = entry_price - current_price
                
                # Já em lucro suficiente?
                if profit_distance >= trigger_distance:
                    # SL ainda está acima do BE?
                    be_price = entry_price - offset_distance
                    if current_sl > be_price or current_sl == 0:
                        return True, be_price
            
            return False, None
            
        except Exception as e:
            logger.error(f"Erro ao verificar break-even: {e}")
            return False, None
    
    def calculate_partial_close_levels(
        self,
        position: Dict,
        current_price: float
    ) -> List[Dict[str, Any]]:
        """
        Calcula níveis para fechamento parcial
        
        Returns:
            Lista de níveis com volume a fechar
        """
        try:
            pos_type = position['type']
            entry_price = position['price_open']
            volume = position['volume']
            tp_price = position.get('tp', 0)
            
            if tp_price == 0:
                return []
            
            levels = []
            
            # Distância total até TP
            if pos_type == 0:  # BUY
                total_distance = tp_price - entry_price
            else:  # SELL
                total_distance = entry_price - tp_price
            
            if total_distance <= 0:
                return []
            
            # Níveis de partial close
            partial_levels = [
                (0.5, 0.33),   # 50% do caminho = fechar 33%
                (0.75, 0.33),  # 75% do caminho = fechar mais 33%
            ]
            
            for progress_pct, close_pct in partial_levels:
                if pos_type == 0:  # BUY
                    trigger_price = entry_price + (total_distance * progress_pct)
                    if current_price >= trigger_price:
                        levels.append({
                            "trigger_price": trigger_price,
                            "close_percent": close_pct,
                            "close_volume": round(volume * close_pct, 2),
                        })
                else:  # SELL
                    trigger_price = entry_price - (total_distance * progress_pct)
                    if current_price <= trigger_price:
                        levels.append({
                            "trigger_price": trigger_price,
                            "close_percent": close_pct,
                            "close_volume": round(volume * close_pct, 2),
                        })
            
            return levels
            
        except Exception as e:
            logger.error(f"Erro ao calcular partial close: {e}")
            return []
    
    def get_trailing_update(
        self,
        position: Dict,
        current_price: float,
        method: Optional[TrailingMethod] = None
    ) -> Dict[str, Any]:
        """
        Obtém atualização de trailing stop para uma posição
        
        Args:
            position: Dados da posição
            current_price: Preço atual
            method: Método de trailing (usa default se None)
            
        Returns:
            Dict com ação recomendada e novo SL
        """
        try:
            method = method or self.default_method
            ticket = position['ticket']
            current_sl = position.get('sl', 0)
            
            result = {
                "ticket": ticket,
                "action": "none",
                "current_sl": current_sl,
                "new_sl": None,
                "method": method.value,
            }
            
            # 1. Verificar break-even primeiro
            should_be, be_price = self.should_move_to_breakeven(position, current_price)
            if should_be and be_price:
                result["action"] = "move_to_breakeven"
                result["new_sl"] = be_price
                return result
            
            # 2. Calcular trailing baseado no método
            new_sl = None
            
            if method == TrailingMethod.ATR:
                new_sl = self.calculate_trailing_atr(position, current_price)
                
            elif method == TrailingMethod.CHANDELIER:
                new_sl = self.calculate_trailing_chandelier(position, current_price)
                
            elif method == TrailingMethod.STRUCTURE:
                new_sl = self.calculate_trailing_structure(position, current_price)
                
            elif method == TrailingMethod.PARABOLIC:
                new_sl = self.calculate_trailing_parabolic(position, current_price)
            
            if new_sl is not None:
                result["action"] = "trail"
                result["new_sl"] = new_sl
            
            # 3. Verificar partial close
            partials = self.calculate_partial_close_levels(position, current_price)
            if partials:
                result["partial_close"] = partials
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao obter trailing update: {e}")
            return {"action": "error", "error": str(e)}
    
    def cleanup_position_state(self, ticket: int):
        """Remove estado de posição fechada"""
        if ticket in self._position_states:
            del self._position_states[ticket]


# Singleton
_trailing_manager: Optional[TrailingStopManager] = None


def get_trailing_manager(
    mt5_connector,
    config: Optional[Dict] = None
) -> TrailingStopManager:
    """Obtém instância singleton do Trailing Manager"""
    global _trailing_manager
    if _trailing_manager is None:
        _trailing_manager = TrailingStopManager(mt5_connector, config)
    return _trailing_manager


# Exemplo de uso:
"""
from core.trailing_stop_manager import get_trailing_manager, TrailingMethod

trailing = get_trailing_manager(mt5_connector, config)

# Para cada posição aberta
for position in positions:
    update = trailing.get_trailing_update(
        position,
        current_price,
        method=TrailingMethod.ATR
    )
    
    if update["action"] == "move_to_breakeven":
        mt5.modify_position(position['ticket'], sl=update["new_sl"])
        logger.info(f"#{position['ticket']} movido para Break-Even")
    
    elif update["action"] == "trail":
        mt5.modify_position(position['ticket'], sl=update["new_sl"])
        logger.info(f"#{position['ticket']} trailing: SL -> {update['new_sl']}")
    
    if "partial_close" in update:
        for level in update["partial_close"]:
            mt5.close_position_partial(position['ticket'], level["close_volume"])
"""
