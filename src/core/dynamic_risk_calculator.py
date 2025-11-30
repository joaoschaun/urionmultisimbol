"""
Dynamic Risk Calculator
Calcula SL/TP dinâmico baseado em ATR e condições de mercado

Features:
- ATR-based stop loss
- Multi-timeframe ATR
- Volatility-adjusted position sizing
- Risk/Reward otimizado
"""
import MetaTrader5 as mt5
import numpy as np
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
from loguru import logger


class DynamicRiskCalculator:
    """
    Calculador de risco dinâmico baseado em ATR
    
    ATR (Average True Range) mede volatilidade:
    - Alta volatilidade → ATR alto → Stops mais largos
    - Baixa volatilidade → ATR baixo → Stops mais apertados
    """
    
    # Multiplicadores ATR por estratégia
    STRATEGY_ATR_MULTIPLIERS = {
        # Estratégia: (SL_multiplier, TP_multiplier)
        "scalping": (1.0, 1.5),           # Stop apertado, TP 1.5x
        "range_trading": (1.5, 2.0),      # Moderado
        "mean_reversion": (1.5, 2.5),     # Moderado, TP maior
        "trend_following": (2.5, 4.0),    # Largo, deixa correr
        "breakout": (2.0, 3.0),           # Breakout precisa de espaço
        "news_trading": (2.5, 3.5),       # Volatilidade alta
    }
    
    # Multiplicadores por símbolo (ajuste fino)
    SYMBOL_ADJUSTMENTS = {
        "XAUUSD": 1.0,    # Ouro: padrão
        "EURUSD": 0.8,    # EUR: menos volátil
        "GBPUSD": 1.1,    # GBP: mais volátil
        "USDJPY": 0.9,    # JPY: menos volátil
    }
    
    # Multiplicadores por sessão
    SESSION_ADJUSTMENTS = {
        "excellent": 1.0,   # London/NY overlap
        "good": 1.0,        # London ou NY
        "moderate": 1.2,    # Tokyo
        "poor": 1.5,        # Sydney
    }
    
    def __init__(self, mt5_connector, config: Optional[Dict] = None):
        """
        Inicializa o calculador
        
        Args:
            mt5_connector: Instância do MT5Connector
            config: Configuração opcional
        """
        self.mt5 = mt5_connector
        self.config = config or {}
        
        # Cache de ATR
        self._atr_cache: Dict[str, Tuple[float, datetime]] = {}
        self._cache_duration_seconds = 60  # Atualizar ATR a cada minuto
        
        # Configurações
        risk_config = self.config.get('risk', {})
        self.min_rr_ratio = risk_config.get('min_risk_reward', 1.5)
        self.max_sl_pips = risk_config.get('max_stop_loss_pips', 50)
        self.min_sl_pips = risk_config.get('min_stop_loss_pips', 5)
        
        logger.info(
            f"📊 Dynamic Risk Calculator inicializado | "
            f"Min R:R = 1:{self.min_rr_ratio}"
        )
    
    def calculate_atr(
        self,
        symbol: str,
        timeframe: int = mt5.TIMEFRAME_H1,
        period: int = 14
    ) -> Optional[float]:
        """
        Calcula ATR (Average True Range)
        
        ATR = Média dos True Ranges dos últimos N períodos
        True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
        
        Args:
            symbol: Símbolo (ex: XAUUSD)
            timeframe: Timeframe do MT5
            period: Período do ATR (default: 14)
            
        Returns:
            Valor do ATR ou None se erro
        """
        try:
            # Verificar cache
            cache_key = f"{symbol}_{timeframe}_{period}"
            if cache_key in self._atr_cache:
                cached_atr, cached_time = self._atr_cache[cache_key]
                age = (datetime.now() - cached_time).total_seconds()
                if age < self._cache_duration_seconds:
                    return cached_atr
            
            # Obter dados históricos
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 10)
            
            if rates is None or len(rates) < period:
                logger.warning(f"Dados insuficientes para ATR de {symbol}")
                return None
            
            # Calcular True Range para cada candle
            true_ranges = []
            for i in range(1, len(rates)):
                high = rates[i]['high']
                low = rates[i]['low']
                prev_close = rates[i-1]['close']
                
                # True Range = max(H-L, |H-PC|, |L-PC|)
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)
            
            # ATR = Média dos True Ranges
            atr = np.mean(true_ranges[-period:])
            
            # Atualizar cache
            self._atr_cache[cache_key] = (atr, datetime.now())
            
            return atr
            
        except Exception as e:
            logger.error(f"Erro ao calcular ATR: {e}")
            return None
    
    def calculate_multi_timeframe_atr(
        self,
        symbol: str,
        period: int = 14
    ) -> Dict[str, float]:
        """
        Calcula ATR em múltiplos timeframes
        
        Returns:
            Dict com ATR por timeframe
        """
        timeframes = {
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
        }
        
        result = {}
        for name, tf in timeframes.items():
            atr = self.calculate_atr(symbol, tf, period)
            if atr:
                result[name] = atr
        
        return result
    
    def atr_to_pips(
        self,
        symbol: str,
        atr_value: float
    ) -> float:
        """
        Converte valor ATR para pips
        
        Args:
            symbol: Símbolo
            atr_value: Valor do ATR
            
        Returns:
            ATR em pips
        """
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return 0.0
            
            # XAUUSD: 1 pip = 0.1, point = 0.01
            # EURUSD: 1 pip = 0.0001, point = 0.00001
            point = symbol_info.point
            
            # Para a maioria dos pares: pip = point * 10
            # Para JPY: pip = point * 100
            if "JPY" in symbol:
                pip_value = point * 100
            else:
                pip_value = point * 10
            
            return atr_value / pip_value
            
        except Exception as e:
            logger.error(f"Erro ao converter ATR para pips: {e}")
            return 0.0
    
    def calculate_dynamic_stops(
        self,
        symbol: str,
        order_type: str,
        entry_price: float,
        strategy_name: str,
        session_quality: str = "good",
        custom_rr_ratio: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calcula SL/TP dinâmico baseado em ATR
        
        Args:
            symbol: Símbolo (ex: XAUUSD)
            order_type: 'BUY' ou 'SELL'
            entry_price: Preço de entrada
            strategy_name: Nome da estratégia
            session_quality: Qualidade da sessão (excellent/good/moderate/poor)
            custom_rr_ratio: Ratio R:R customizado (opcional)
            
        Returns:
            Dict com sl_price, tp_price, sl_pips, tp_pips, atr_info
        """
        try:
            # 1. Obter informações do símbolo
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Símbolo {symbol} não encontrado")
                return self._get_fallback_stops(symbol, order_type, entry_price)
            
            point = symbol_info.point
            digits = symbol_info.digits
            
            # 2. Calcular ATR multi-timeframe
            atr_data = self.calculate_multi_timeframe_atr(symbol)
            
            if not atr_data:
                logger.warning(f"ATR indisponível para {symbol}, usando fallback")
                return self._get_fallback_stops(symbol, order_type, entry_price)
            
            # 3. Usar ATR do H1 como referência principal (mais estável)
            primary_atr = atr_data.get("H1") or atr_data.get("M15") or list(atr_data.values())[0]
            
            # 4. Obter multiplicadores da estratégia
            strategy_key = strategy_name.lower().replace(" ", "_")
            sl_mult, tp_mult = self.STRATEGY_ATR_MULTIPLIERS.get(
                strategy_key,
                (2.0, 3.0)  # Default
            )
            
            # 5. Aplicar ajuste do símbolo
            symbol_adj = self.SYMBOL_ADJUSTMENTS.get(symbol, 1.0)
            
            # 6. Aplicar ajuste da sessão
            session_adj = self.SESSION_ADJUSTMENTS.get(session_quality, 1.0)
            
            # 7. Calcular distâncias
            sl_distance = primary_atr * sl_mult * symbol_adj * session_adj
            
            # 8. Calcular R:R ratio
            rr_ratio = custom_rr_ratio or self.min_rr_ratio
            tp_distance = sl_distance * rr_ratio
            
            # 9. Converter para pips
            sl_pips = self.atr_to_pips(symbol, sl_distance)
            tp_pips = self.atr_to_pips(symbol, tp_distance)
            
            # 10. Aplicar limites
            sl_pips = max(self.min_sl_pips, min(sl_pips, self.max_sl_pips))
            
            # Recalcular distância após limites
            if "JPY" in symbol:
                pip_value = point * 100
            else:
                pip_value = point * 10
            
            sl_distance = sl_pips * pip_value
            tp_distance = sl_distance * rr_ratio
            tp_pips = self.atr_to_pips(symbol, tp_distance)
            
            # 11. Calcular preços finais
            if order_type == "BUY":
                sl_price = entry_price - sl_distance
                tp_price = entry_price + tp_distance
            else:  # SELL
                sl_price = entry_price + sl_distance
                tp_price = entry_price - tp_distance
            
            # Arredondar para dígitos corretos
            sl_price = round(sl_price, digits)
            tp_price = round(tp_price, digits)
            
            # 12. Log detalhado
            logger.info(
                f"📊 Dynamic Stops [{symbol}] | "
                f"ATR(H1): {primary_atr:.5f} | "
                f"Strategy: {strategy_name} ({sl_mult}x/{tp_mult}x) | "
                f"Session: {session_quality} ({session_adj}x) | "
                f"SL: {sl_pips:.1f} pips @ {sl_price:.5f} | "
                f"TP: {tp_pips:.1f} pips @ {tp_price:.5f} | "
                f"R:R = 1:{rr_ratio}"
            )
            
            return {
                "sl_price": sl_price,
                "tp_price": tp_price,
                "sl_pips": round(sl_pips, 1),
                "tp_pips": round(tp_pips, 1),
                "sl_distance": sl_distance,
                "tp_distance": tp_distance,
                "risk_reward_ratio": rr_ratio,
                "atr_info": {
                    "primary_atr": primary_atr,
                    "all_timeframes": atr_data,
                    "strategy_multiplier": sl_mult,
                    "symbol_adjustment": symbol_adj,
                    "session_adjustment": session_adj,
                },
                "method": "atr_dynamic",
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular stops dinâmicos: {e}")
            return self._get_fallback_stops(symbol, order_type, entry_price)
    
    def _get_fallback_stops(
        self,
        symbol: str,
        order_type: str,
        entry_price: float
    ) -> Dict[str, Any]:
        """
        Retorna stops fixos como fallback
        """
        try:
            symbol_info = mt5.symbol_info(symbol)
            point = symbol_info.point if symbol_info else 0.01
            digits = symbol_info.digits if symbol_info else 2
            
            # Stops fixos conservadores
            sl_pips = 20
            tp_pips = 40
            
            if "JPY" in symbol:
                pip_value = point * 100
            else:
                pip_value = point * 10
            
            sl_distance = sl_pips * pip_value
            tp_distance = tp_pips * pip_value
            
            if order_type == "BUY":
                sl_price = entry_price - sl_distance
                tp_price = entry_price + tp_distance
            else:
                sl_price = entry_price + sl_distance
                tp_price = entry_price - tp_distance
            
            logger.warning(
                f"⚠️ Usando stops fallback: SL={sl_pips} pips, TP={tp_pips} pips"
            )
            
            return {
                "sl_price": round(sl_price, digits),
                "tp_price": round(tp_price, digits),
                "sl_pips": sl_pips,
                "tp_pips": tp_pips,
                "sl_distance": sl_distance,
                "tp_distance": tp_distance,
                "risk_reward_ratio": 2.0,
                "method": "fallback_fixed",
            }
            
        except Exception as e:
            logger.error(f"Erro no fallback: {e}")
            return {}
    
    def calculate_position_size_atr(
        self,
        symbol: str,
        account_balance: float,
        risk_percent: float,
        sl_pips: float
    ) -> float:
        """
        Calcula tamanho da posição baseado em risco e ATR
        
        Args:
            symbol: Símbolo
            account_balance: Saldo da conta
            risk_percent: Percentual de risco (ex: 0.02 = 2%)
            sl_pips: Stop loss em pips
            
        Returns:
            Tamanho da posição em lotes
        """
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return 0.01
            
            # Valor em risco
            risk_amount = account_balance * risk_percent
            
            # Valor do pip por lote
            contract_size = symbol_info.trade_contract_size
            point = symbol_info.point
            
            if "JPY" in symbol:
                pip_value_per_lot = contract_size * point * 100
            else:
                pip_value_per_lot = contract_size * point * 10
            
            # Tamanho da posição
            if sl_pips > 0 and pip_value_per_lot > 0:
                lot_size = risk_amount / (sl_pips * pip_value_per_lot)
            else:
                lot_size = 0.01
            
            # Aplicar limites
            lot_step = symbol_info.volume_step
            lot_size = round(lot_size / lot_step) * lot_step
            lot_size = max(symbol_info.volume_min, min(lot_size, symbol_info.volume_max))
            
            # Limite de config
            max_lot = self.config.get('trading', {}).get('max_lot_size', 1.0)
            lot_size = min(lot_size, max_lot)
            
            logger.debug(
                f"Position sizing: Balance=${account_balance:.2f}, "
                f"Risk={risk_percent*100}%, SL={sl_pips} pips → {lot_size} lots"
            )
            
            return lot_size
            
        except Exception as e:
            logger.error(f"Erro no position sizing: {e}")
            return 0.01
    
    def get_volatility_state(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Analisa estado atual de volatilidade
        
        Returns:
            Dict com estado de volatilidade e recomendações
        """
        try:
            # ATR em múltiplos timeframes
            atr_data = self.calculate_multi_timeframe_atr(symbol)
            
            if not atr_data:
                return {"state": "unknown", "message": "ATR indisponível"}
            
            # Comparar ATR curto prazo (M5) vs longo prazo (H4)
            atr_m5 = atr_data.get("M5", 0)
            atr_h1 = atr_data.get("H1", 0)
            atr_h4 = atr_data.get("H4", 0)
            
            if not atr_h1:
                return {"state": "unknown", "message": "ATR H1 indisponível"}
            
            # Ratio de volatilidade
            short_term_ratio = atr_m5 / atr_h1 if atr_h1 > 0 else 1.0
            
            # Classificar estado
            if short_term_ratio > 1.5:
                state = "high"
                recommendation = "Volatilidade ALTA - aumentar stops, reduzir posição"
                sl_adjustment = 1.3
            elif short_term_ratio > 1.2:
                state = "elevated"
                recommendation = "Volatilidade ELEVADA - cautela recomendada"
                sl_adjustment = 1.1
            elif short_term_ratio < 0.7:
                state = "low"
                recommendation = "Volatilidade BAIXA - mercado quieto"
                sl_adjustment = 0.9
            else:
                state = "normal"
                recommendation = "Volatilidade NORMAL - condições padrão"
                sl_adjustment = 1.0
            
            # Converter para pips
            atr_pips = {
                tf: self.atr_to_pips(symbol, atr)
                for tf, atr in atr_data.items()
            }
            
            return {
                "state": state,
                "recommendation": recommendation,
                "sl_adjustment": sl_adjustment,
                "short_term_ratio": round(short_term_ratio, 2),
                "atr_values": atr_data,
                "atr_pips": atr_pips,
            }
            
        except Exception as e:
            logger.error(f"Erro ao analisar volatilidade: {e}")
            return {"state": "unknown", "message": str(e)}


# Singleton
_risk_calculator: Optional[DynamicRiskCalculator] = None


def get_dynamic_risk_calculator(
    mt5_connector,
    config: Optional[Dict] = None
) -> DynamicRiskCalculator:
    """Obtém instância singleton do calculador"""
    global _risk_calculator
    if _risk_calculator is None:
        _risk_calculator = DynamicRiskCalculator(mt5_connector, config)
    return _risk_calculator


# Exemplo de uso:
"""
from core.dynamic_risk_calculator import get_dynamic_risk_calculator

calc = get_dynamic_risk_calculator(mt5_connector, config)

# Calcular stops dinâmicos
stops = calc.calculate_dynamic_stops(
    symbol="XAUUSD",
    order_type="BUY",
    entry_price=2650.50,
    strategy_name="scalping",
    session_quality="excellent"
)

print(f"SL: {stops['sl_price']} ({stops['sl_pips']} pips)")
print(f"TP: {stops['tp_price']} ({stops['tp_pips']} pips)")
print(f"R:R = 1:{stops['risk_reward_ratio']}")

# Verificar volatilidade
vol_state = calc.get_volatility_state("XAUUSD")
print(f"Volatilidade: {vol_state['state']} - {vol_state['recommendation']}")
"""
