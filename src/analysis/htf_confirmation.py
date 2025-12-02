"""
Higher Timeframe Confirmation System
=====================================
Sistema centralizado para confirmar sinais de TF menor com TF maior.

HIERARQUIA:
- D1 → Tendência macro (semanas)
- H4 → Tendência intermediária (dias)
- H1 → Tendência curta (horas)
- M15 → Momentum (minutos)
- M5 → Entrada precisa (scalping)

USO:
```python
from analysis.htf_confirmation import HTFConfirmation

htf = HTFConfirmation(config)
result = htf.confirm_signal(
    signal_direction='BUY',
    signal_timeframe='M5',
    technical_analysis=ta_data
)

if result.is_confirmed:
    # Executar trade
    adjusted_confidence = result.adjusted_confidence
    adjusted_sl = result.adjusted_sl
```
"""

from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from loguru import logger


class ConfirmationLevel(Enum):
    """Níveis de confirmação"""
    STRONG = "STRONG"           # Todos TFs alinhados
    MODERATE = "MODERATE"       # TF principal + 1 confirmam
    WEAK = "WEAK"              # Apenas TF principal confirma
    CONFLICTING = "CONFLICTING" # TFs em conflito
    NO_DATA = "NO_DATA"        # Dados insuficientes


@dataclass
class ConfirmationResult:
    """Resultado da confirmação de Higher Timeframe"""
    is_confirmed: bool
    level: ConfirmationLevel
    signal_direction: str  # 'BUY' ou 'SELL'
    
    # Análise por timeframe
    d1_direction: str
    h4_direction: str
    h1_direction: str
    m15_direction: str
    
    # Strengths
    d1_strength: float
    h4_strength: float
    h1_strength: float
    m15_strength: float
    
    # Ajustes recomendados
    adjusted_confidence: float  # Confiança ajustada
    risk_multiplier: float      # Multiplicador de risco
    recommended_sl_multiplier: float  # Ajuste de SL
    recommended_tp_multiplier: float  # Ajuste de TP
    
    # Info adicional
    aligned_timeframes: List[str]
    conflicting_timeframes: List[str]
    reason: str
    timestamp: datetime


class HTFConfirmation:
    """
    Sistema de Confirmação de Higher Timeframe
    
    Este é o "árbitro" que decide se um sinal de TF menor
    pode ser executado baseado na direção dos TFs maiores.
    """
    
    # Hierarquia de timeframes (maior para menor)
    TIMEFRAME_HIERARCHY = ['D1', 'H4', 'H1', 'M15', 'M5', 'M1']
    
    # Pesos por timeframe (quanto maior, mais importante)
    TIMEFRAME_WEIGHTS = {
        'D1': 1.0,
        'H4': 0.8,
        'H1': 0.6,
        'M15': 0.4,
        'M5': 0.2,
        'M1': 0.1
    }
    
    # Quantos TFs acima devem confirmar
    CONFIRMATION_REQUIREMENTS = {
        'M1': ['M5', 'M15'],      # M1 precisa de M5 e M15
        'M5': ['M15', 'H1'],      # M5 precisa de M15 e H1
        'M15': ['H1', 'H4'],      # M15 precisa de H1 e H4
        'H1': ['H4', 'D1'],       # H1 precisa de H4 e D1
        'H4': ['D1'],             # H4 precisa de D1
        'D1': []                  # D1 não precisa de confirmação
    }
    
    def __init__(self, config: Dict = None):
        """
        Args:
            config: Configurações opcionais
        """
        self.config = config or {}
        
        # Configurações
        self.strict_mode = self.config.get('strict_mode', True)
        self.min_confirmation_strength = self.config.get('min_strength', 0.4)
        
        logger.info("🎯 HTFConfirmation inicializado")
    
    def confirm_signal(
        self,
        signal_direction: str,
        signal_timeframe: str,
        technical_analysis: Dict,
        signal_confidence: float = 0.5
    ) -> ConfirmationResult:
        """
        Confirma um sinal de um timeframe menor com timeframes maiores.
        
        Args:
            signal_direction: 'BUY' ou 'SELL'
            signal_timeframe: Timeframe do sinal (ex: 'M5')
            technical_analysis: Dados de análise técnica multi-TF
            signal_confidence: Confiança original do sinal
            
        Returns:
            ConfirmationResult com análise completa
        """
        try:
            # Obter direções de todos os timeframes
            directions = {}
            strengths = {}
            
            for tf in self.TIMEFRAME_HIERARCHY:
                direction, strength = self._get_timeframe_direction(
                    technical_analysis, tf
                )
                directions[tf] = direction
                strengths[tf] = strength
            
            # Verificar timeframes de confirmação necessários
            required_tfs = self.CONFIRMATION_REQUIREMENTS.get(
                signal_timeframe, ['H1', 'H4']
            )
            
            # Analisar alinhamento
            aligned = []
            conflicting = []
            
            # Converter 'BUY' para 'BULLISH' e 'SELL' para 'BEARISH'
            expected_direction = 'BULLISH' if signal_direction == 'BUY' else 'BEARISH'
            opposite_direction = 'BEARISH' if signal_direction == 'BUY' else 'BULLISH'
            
            for tf in required_tfs:
                tf_direction = directions.get(tf, 'NEUTRAL')
                
                # Verificar se alinhado (BULLISH ou WEAK_BULLISH para BUY)
                if expected_direction in tf_direction:
                    aligned.append(tf)
                elif opposite_direction in tf_direction:
                    conflicting.append(tf)
            
            # Determinar nível de confirmação
            level = self._determine_confirmation_level(
                signal_direction, aligned, conflicting, required_tfs, strengths
            )
            
            # Determinar se confirma
            is_confirmed = level in [
                ConfirmationLevel.STRONG, 
                ConfirmationLevel.MODERATE
            ]
            
            if self.strict_mode and level == ConfirmationLevel.WEAK:
                is_confirmed = False
            
            # Calcular ajustes
            adjusted_confidence = self._calculate_adjusted_confidence(
                signal_confidence, level, aligned, strengths
            )
            
            risk_multiplier = self._calculate_risk_multiplier(level, strengths)
            sl_multiplier, tp_multiplier = self._calculate_sl_tp_multipliers(
                level, aligned, conflicting
            )
            
            # Gerar razão
            reason = self._generate_reason(
                signal_direction, level, aligned, conflicting
            )
            
            return ConfirmationResult(
                is_confirmed=is_confirmed,
                level=level,
                signal_direction=signal_direction,
                d1_direction=directions.get('D1', 'NEUTRAL'),
                h4_direction=directions.get('H4', 'NEUTRAL'),
                h1_direction=directions.get('H1', 'NEUTRAL'),
                m15_direction=directions.get('M15', 'NEUTRAL'),
                d1_strength=strengths.get('D1', 0.0),
                h4_strength=strengths.get('H4', 0.0),
                h1_strength=strengths.get('H1', 0.0),
                m15_strength=strengths.get('M15', 0.0),
                adjusted_confidence=adjusted_confidence,
                risk_multiplier=risk_multiplier,
                recommended_sl_multiplier=sl_multiplier,
                recommended_tp_multiplier=tp_multiplier,
                aligned_timeframes=aligned,
                conflicting_timeframes=conflicting,
                reason=reason,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Erro ao confirmar sinal: {e}")
            return self._create_default_result(signal_direction)
    
    def _get_timeframe_direction(
        self, 
        technical_analysis: Dict, 
        timeframe: str
    ) -> Tuple[str, float]:
        """Obtém direção e força de um timeframe"""
        
        if timeframe not in technical_analysis:
            return 'NEUTRAL', 0.0
        
        tf_data = technical_analysis[timeframe]
        
        try:
            # Extrair indicadores
            macd_data = tf_data.get('macd', {})
            ema_data = tf_data.get('ema', {})
            adx_data = tf_data.get('adx', {})
            rsi = tf_data.get('rsi', 50)
            current_price = tf_data.get('current_price', 0)
            
            macd_hist = macd_data.get('histogram', 0) if isinstance(macd_data, dict) else 0
            macd_line = macd_data.get('macd', 0) if isinstance(macd_data, dict) else 0
            macd_signal = macd_data.get('signal', 0) if isinstance(macd_data, dict) else 0
            
            ema_9 = ema_data.get('ema_9', 0) if isinstance(ema_data, dict) else 0
            ema_21 = ema_data.get('ema_21', 0) if isinstance(ema_data, dict) else 0
            ema_50 = ema_data.get('ema_50', 0) if isinstance(ema_data, dict) else 0
            
            adx = adx_data.get('adx', 0) if isinstance(adx_data, dict) else 0
            di_plus = adx_data.get('di_plus', 0) if isinstance(adx_data, dict) else 0
            di_minus = adx_data.get('di_minus', 0) if isinstance(adx_data, dict) else 0
            
            # Scoring
            bullish = 0
            bearish = 0
            
            # MACD
            if macd_line > macd_signal and macd_hist > 0:
                bullish += 3
            elif macd_line < macd_signal and macd_hist < 0:
                bearish += 3
            
            # EMA Alignment
            if ema_9 > ema_21 > ema_50:
                bullish += 3
            elif ema_9 < ema_21 < ema_50:
                bearish += 3
            
            # Price position
            if current_price > 0 and ema_21 > 0:
                if current_price > ema_21:
                    bullish += 2
                else:
                    bearish += 2
            
            # ADX
            if adx > 20:
                if di_plus > di_minus:
                    bullish += 2
                else:
                    bearish += 2
            
            # RSI
            if rsi > 55:
                bullish += 1
            elif rsi < 45:
                bearish += 1
            
            # Determinar
            max_score = 11
            threshold = 4
            
            if bullish > bearish and bullish >= threshold:
                return 'BULLISH' if bullish >= 6 else 'WEAK_BULLISH', bullish / max_score
            elif bearish > bullish and bearish >= threshold:
                return 'BEARISH' if bearish >= 6 else 'WEAK_BEARISH', bearish / max_score
            else:
                return 'NEUTRAL', 0.0
                
        except Exception as e:
            return 'NEUTRAL', 0.0
    
    def _determine_confirmation_level(
        self,
        signal_direction: str,
        aligned: List[str],
        conflicting: List[str],
        required: List[str],
        strengths: Dict[str, float]
    ) -> ConfirmationLevel:
        """Determina o nível de confirmação"""
        
        if not required:
            return ConfirmationLevel.STRONG
        
        if conflicting:
            return ConfirmationLevel.CONFLICTING
        
        aligned_count = len(aligned)
        required_count = len(required)
        
        if aligned_count == required_count:
            # Verificar força
            avg_strength = sum(strengths.get(tf, 0) for tf in aligned) / aligned_count
            if avg_strength >= 0.6:
                return ConfirmationLevel.STRONG
            else:
                return ConfirmationLevel.MODERATE
        
        elif aligned_count >= 1:
            return ConfirmationLevel.MODERATE if aligned_count > 1 else ConfirmationLevel.WEAK
        
        else:
            return ConfirmationLevel.NO_DATA
    
    def _calculate_adjusted_confidence(
        self,
        original: float,
        level: ConfirmationLevel,
        aligned: List[str],
        strengths: Dict[str, float]
    ) -> float:
        """Calcula confiança ajustada"""
        
        multipliers = {
            ConfirmationLevel.STRONG: 1.2,
            ConfirmationLevel.MODERATE: 1.0,
            ConfirmationLevel.WEAK: 0.8,
            ConfirmationLevel.CONFLICTING: 0.5,
            ConfirmationLevel.NO_DATA: 0.7
        }
        
        base = original * multipliers.get(level, 1.0)
        
        # Bonus por TFs alinhados fortes
        for tf in aligned:
            if strengths.get(tf, 0) >= 0.7:
                base += 0.05
        
        return min(max(base, 0.0), 1.0)
    
    def _calculate_risk_multiplier(
        self,
        level: ConfirmationLevel,
        strengths: Dict[str, float]
    ) -> float:
        """Calcula multiplicador de risco"""
        
        multipliers = {
            ConfirmationLevel.STRONG: 1.2,
            ConfirmationLevel.MODERATE: 1.0,
            ConfirmationLevel.WEAK: 0.7,
            ConfirmationLevel.CONFLICTING: 0.3,
            ConfirmationLevel.NO_DATA: 0.5
        }
        
        return multipliers.get(level, 1.0)
    
    def _calculate_sl_tp_multipliers(
        self,
        level: ConfirmationLevel,
        aligned: List[str],
        conflicting: List[str]
    ) -> Tuple[float, float]:
        """Calcula multiplicadores de SL/TP"""
        
        if level == ConfirmationLevel.STRONG:
            return 1.0, 1.3  # SL normal, TP maior
        elif level == ConfirmationLevel.MODERATE:
            return 1.0, 1.0  # Normal
        elif level == ConfirmationLevel.WEAK:
            return 1.2, 0.8  # SL maior, TP menor
        elif level == ConfirmationLevel.CONFLICTING:
            return 1.5, 0.5  # SL muito maior, TP muito menor
        else:
            return 1.2, 0.8
    
    def _generate_reason(
        self,
        direction: str,
        level: ConfirmationLevel,
        aligned: List[str],
        conflicting: List[str]
    ) -> str:
        """Gera descrição da confirmação"""
        
        if level == ConfirmationLevel.STRONG:
            return f"{direction} confirmado por {', '.join(aligned)} (FORTE)"
        elif level == ConfirmationLevel.MODERATE:
            return f"{direction} confirmado parcialmente por {', '.join(aligned)}"
        elif level == ConfirmationLevel.WEAK:
            return f"{direction} com confirmação fraca"
        elif level == ConfirmationLevel.CONFLICTING:
            return f"{direction} em CONFLITO com {', '.join(conflicting)}"
        else:
            return f"{direction} sem dados suficientes para confirmar"
    
    def _create_default_result(self, direction: str) -> ConfirmationResult:
        """Cria resultado padrão em caso de erro"""
        return ConfirmationResult(
            is_confirmed=False,
            level=ConfirmationLevel.NO_DATA,
            signal_direction=direction,
            d1_direction='NEUTRAL',
            h4_direction='NEUTRAL',
            h1_direction='NEUTRAL',
            m15_direction='NEUTRAL',
            d1_strength=0.0,
            h4_strength=0.0,
            h1_strength=0.0,
            m15_strength=0.0,
            adjusted_confidence=0.3,
            risk_multiplier=0.5,
            recommended_sl_multiplier=1.5,
            recommended_tp_multiplier=0.5,
            aligned_timeframes=[],
            conflicting_timeframes=[],
            reason='Erro ao processar confirmação',
            timestamp=datetime.now()
        )
    
    # =========================================
    # MÉTODOS SIMPLIFICADOS
    # =========================================
    
    def is_aligned(
        self, 
        direction: str, 
        technical_analysis: Dict,
        min_timeframes: int = 2
    ) -> bool:
        """
        Verifica rapidamente se direção está alinhada com TFs maiores.
        
        Args:
            direction: 'BUY' ou 'SELL'
            technical_analysis: Dados de análise
            min_timeframes: Mínimo de TFs alinhados
            
        Returns:
            True se alinhado, False caso contrário
        """
        aligned_count = 0
        
        for tf in ['D1', 'H4', 'H1']:
            tf_dir, strength = self._get_timeframe_direction(technical_analysis, tf)
            
            if direction == 'BUY' and tf_dir in ['BULLISH', 'WEAK_BULLISH']:
                aligned_count += 1
            elif direction == 'SELL' and tf_dir in ['BEARISH', 'WEAK_BEARISH']:
                aligned_count += 1
        
        return aligned_count >= min_timeframes
    
    def get_macro_direction(self, technical_analysis: Dict) -> str:
        """
        Retorna a direção macro (D1 + H4 combinados).
        
        Returns:
            'BULLISH', 'BEARISH', ou 'NEUTRAL'
        """
        d1_dir, d1_str = self._get_timeframe_direction(technical_analysis, 'D1')
        h4_dir, h4_str = self._get_timeframe_direction(technical_analysis, 'H4')
        
        # Se ambos alinhados
        if d1_dir in ['BULLISH', 'WEAK_BULLISH'] and h4_dir in ['BULLISH', 'WEAK_BULLISH']:
            return 'BULLISH'
        elif d1_dir in ['BEARISH', 'WEAK_BEARISH'] and h4_dir in ['BEARISH', 'WEAK_BEARISH']:
            return 'BEARISH'
        
        # Se apenas um define
        if d1_dir not in ['NEUTRAL'] and d1_str > 0.6:
            return 'BULLISH' if 'BULLISH' in d1_dir else 'BEARISH'
        
        return 'NEUTRAL'


# =========================================
# SINGLETON
# =========================================

_htf_confirmation: Optional[HTFConfirmation] = None


def get_htf_confirmation(config: Dict = None) -> HTFConfirmation:
    """Factory function para obter singleton"""
    global _htf_confirmation
    if _htf_confirmation is None:
        _htf_confirmation = HTFConfirmation(config)
    return _htf_confirmation
