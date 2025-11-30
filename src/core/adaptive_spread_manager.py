"""
Adaptive Spread Manager
Ajusta estratégias dinamicamente baseado nas condições de spread
Filosofia: O mercado sempre oferece oportunidades, basta adaptar-se!
"""
from loguru import logger
from typing import Dict, Any, Optional
import MetaTrader5 as mt5


class AdaptiveSpreadManager:
    """
    Gerencia adaptação de parâmetros baseado no spread atual
    
    Níveis de Spread:
    - NORMAL (0-3 pips): Operação padrão
    - ALTO (3-8 pips): Alvos maiores, stops ajustados
    - EXTREMO (8-15 pips): Estratégias específicas, apenas oportunidades claras
    - PROIBITIVO (>15 pips): Apenas scalping ultra-rápido ou aguardar
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Thresholds de spread (em pips)
        self.NORMAL_MAX = 3.0
        self.ALTO_MAX = 8.0
        self.EXTREMO_MAX = 15.0
        
        # Multiplicadores para alvos (TP)
        self.TP_MULTIPLIERS = {
            'normal': 1.0,      # 100% do TP original
            'alto': 1.5,        # 150% - compensar spread
            'extremo': 2.0,     # 200% - compensar + lucro
            'proibitivo': 3.0   # 300% - apenas grandes movimentos
        }
        
        # Multiplicadores para stops (SL)
        self.SL_MULTIPLIERS = {
            'normal': 1.0,      # 100% do SL original
            'alto': 1.2,        # 120% - evitar stop prematuro
            'extremo': 1.5,     # 150% - dar espaço para volatilidade
            'proibitivo': 2.0   # 200% - movimentos extremos
        }
        
        # Ajuste de confiança mínima (mais seletivo em spreads altos)
        self.CONFIDENCE_ADJUSTMENTS = {
            'normal': 0.0,      # Sem ajuste
            'alto': 0.10,       # +10% de confiança exigida
            'extremo': 0.20,    # +20% de confiança exigida
            'proibitivo': 0.30  # +30% - apenas sinais muito fortes
        }
        
        logger.info("🎯 Adaptive Spread Manager inicializado")
        logger.info(f"   Normal: 0-{self.NORMAL_MAX} pips")
        logger.info(f"   Alto: {self.NORMAL_MAX}-{self.ALTO_MAX} pips → TP×{self.TP_MULTIPLIERS['alto']}, SL×{self.SL_MULTIPLIERS['alto']}")
        logger.info(f"   Extremo: {self.ALTO_MAX}-{self.EXTREMO_MAX} pips → TP×{self.TP_MULTIPLIERS['extremo']}, SL×{self.SL_MULTIPLIERS['extremo']}")
        logger.info(f"   Proibitivo: >{self.EXTREMO_MAX} pips → TP×{self.TP_MULTIPLIERS['proibitivo']}, SL×{self.SL_MULTIPLIERS['proibitivo']}")
    
    def classify_spread(self, spread_pips: float) -> str:
        """
        Classifica o spread atual
        
        Args:
            spread_pips: Spread em pips
            
        Returns:
            'normal', 'alto', 'extremo' ou 'proibitivo'
        """
        if spread_pips <= self.NORMAL_MAX:
            return 'normal'
        elif spread_pips <= self.ALTO_MAX:
            return 'alto'
        elif spread_pips <= self.EXTREMO_MAX:
            return 'extremo'
        else:
            return 'proibitivo'
    
    def get_adapted_parameters(
        self,
        strategy_name: str,
        spread_pips: float,
        original_sl: float,
        original_tp: float,
        entry_price: float,
        position_type: int,
        confidence: float
    ) -> Dict[str, Any]:
        """
        Retorna parâmetros adaptados ao spread atual
        
        Args:
            strategy_name: Nome da estratégia
            spread_pips: Spread atual em pips
            original_sl: Stop loss original
            original_tp: Take profit original
            entry_price: Preço de entrada
            position_type: 0=BUY, 1=SELL
            confidence: Confiança do sinal (0-1)
            
        Returns:
            Dict com parâmetros adaptados e metadados
        """
        spread_level = self.classify_spread(spread_pips)
        
        # Multiplicadores para este nível
        tp_mult = self.TP_MULTIPLIERS[spread_level]
        sl_mult = self.SL_MULTIPLIERS[spread_level]
        conf_adj = self.CONFIDENCE_ADJUSTMENTS[spread_level]
        
        # Calcular distâncias originais
        if position_type == 0:  # BUY
            sl_distance = entry_price - original_sl
            tp_distance = original_tp - entry_price
        else:  # SELL
            sl_distance = original_sl - entry_price
            tp_distance = entry_price - original_tp
        
        # Aplicar multiplicadores
        new_sl_distance = sl_distance * sl_mult
        new_tp_distance = tp_distance * tp_mult
        
        # Calcular novos níveis
        if position_type == 0:  # BUY
            adapted_sl = entry_price - new_sl_distance
            adapted_tp = entry_price + new_tp_distance
        else:  # SELL
            adapted_sl = entry_price + new_sl_distance
            adapted_tp = entry_price - new_tp_distance
        
        # Confiança ajustada
        adjusted_confidence = confidence + conf_adj
        should_trade = adjusted_confidence >= 0.0 and adjusted_confidence <= 1.0
        
        result = {
            'spread_level': spread_level,
            'spread_pips': spread_pips,
            'original_sl': original_sl,
            'original_tp': original_tp,
            'adapted_sl': adapted_sl,
            'adapted_tp': adapted_tp,
            'sl_multiplier': sl_mult,
            'tp_multiplier': tp_mult,
            'original_sl_pips': sl_distance * 10000,  # Assumindo 4 casas decimais
            'adapted_sl_pips': new_sl_distance * 10000,
            'original_tp_pips': tp_distance * 10000,
            'adapted_tp_pips': new_tp_distance * 10000,
            'confidence_adjustment': conf_adj,
            'original_confidence': confidence,
            'adjusted_confidence': min(1.0, adjusted_confidence),
            'should_trade': should_trade and spread_level != 'proibitivo',
            'recommendation': self._get_recommendation(spread_level, strategy_name, confidence + conf_adj)
        }
        
        logger.debug(
            f"🎯 [{strategy_name}] Adaptação | Spread: {spread_pips:.1f} pips ({spread_level.upper()}) | "
            f"SL: {original_sl:.5f} → {adapted_sl:.5f} (×{sl_mult}) | "
            f"TP: {original_tp:.5f} → {adapted_tp:.5f} (×{tp_mult}) | "
            f"Confiança: {confidence:.0%} → {min(1.0, adjusted_confidence):.0%}"
        )
        
        return result
    
    def _get_recommendation(self, spread_level: str, strategy_name: str, adjusted_confidence: float) -> str:
        """Retorna recomendação de ação"""
        if spread_level == 'proibitivo':
            return "⛔ AGUARDAR - Spread proibitivo, apenas oportunidades extremas"
        
        if spread_level == 'extremo':
            if adjusted_confidence >= 0.80:
                return "⚡ OPERAR COM CAUTELA - Alta confiança em spread extremo = oportunidade"
            return "⚠️ EVITAR - Spread extremo, confiança insuficiente"
        
        if spread_level == 'alto':
            if adjusted_confidence >= 0.70:
                return "✅ OPERAR - Spread alto compensado por TP maior"
            return "⚠️ SELETIVO - Apenas sinais de alta confiança"
        
        return "✅ OPERAÇÃO NORMAL - Condições ideais"
    
    def should_modify_position(self, spread_pips: float) -> tuple[bool, str]:
        """
        Verifica se deve modificar posição dado o spread atual
        
        Returns:
            (should_modify, reason)
        """
        spread_level = self.classify_spread(spread_pips)
        
        if spread_level == 'proibitivo':
            # Em spread proibitivo, apenas modifica se for URGENTE (SL mental atingido)
            return False, f"⛔ Spread proibitivo ({spread_pips:.1f} pips) - aguardando normalização"
        
        if spread_level == 'extremo':
            # Em spread extremo, aceita mas com reservas
            return True, f"⚡ Spread extremo ({spread_pips:.1f} pips) - modificando com cautela"
        
        if spread_level == 'alto':
            # Spread alto é normal, modifica normalmente
            return True, f"✅ Spread alto ({spread_pips:.1f} pips) - modificação permitida"
        
        # Spread normal
        return True, f"✅ Spread normal ({spread_pips:.1f} pips)"
    
    def get_spread_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Obtém informações de spread do símbolo
        
        Returns:
            Dict com spread_pips, spread_level, etc.
        """
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return None
            
            spread_pips = symbol_info.spread / 10  # MT5 retorna em points (0.1 pip)
            spread_level = self.classify_spread(spread_pips)
            
            return {
                'symbol': symbol,
                'spread_points': symbol_info.spread,
                'spread_pips': spread_pips,
                'spread_level': spread_level,
                'bid': symbol_info.bid,
                'ask': symbol_info.ask,
                'point': symbol_info.point
            }
        except Exception as e:
            logger.error(f"Erro ao obter spread para {symbol}: {e}")
            return None
