"""
Classe base para estratégias de trading
Define interface comum para todas as estratégias
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from loguru import logger


class BaseStrategy(ABC):
    """
    Classe abstrata base para todas as estratégias
    """
    
    def __init__(self, name: str, config: Dict):
        """
        Inicializa a estratégia
        
        Args:
            name: Nome da estratégia
            config: Configurações da estratégia
        """
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.min_confidence = config.get('min_confidence', 0.6)
        
        logger.info(f"Estratégia {self.name} inicializada")
    
    @abstractmethod
    def analyze(self, technical_analysis: Dict, 
                news_analysis: Optional[Dict] = None) -> Dict:
        """
        Analisa o mercado e retorna sinal
        
        Args:
            technical_analysis: Análise técnica completa
            news_analysis: Análise de notícias (opcional)
            
        Returns:
            Dict com sinal e detalhes
        """
        pass
    
    def is_enabled(self) -> bool:
        """Verifica se estratégia está ativa"""
        return self.enabled
    
    def calculate_score(self, conditions: Dict[str, bool], 
                       weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calcula score baseado em condições
        
        Args:
            conditions: Dict com condições booleanas
            weights: Pesos opcionais para cada condição
            
        Returns:
            Score normalizado (0.0 a 1.0)
        """
        if not conditions:
            return 0.0
        
        if weights is None:
            # Peso igual para todas as condições
            weights = {k: 1.0 for k in conditions.keys()}
        
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0
        
        weighted_score = sum(
            weights.get(k, 1.0) for k, v in conditions.items() if v
        )
        
        return min(weighted_score / total_weight, 1.0)
    
    def validate_signal(self, signal: Dict) -> bool:
        """
        Valida se sinal atende critérios mínimos
        
        Args:
            signal: Sinal a validar
            
        Returns:
            True se válido
        """
        if not signal:
            return False
        
        action = signal.get('action')
        if action not in ['BUY', 'SELL']:
            return False
        
        confidence = signal.get('confidence', 0.0)
        if confidence < self.min_confidence:
            logger.debug(
                f"{self.name}: Confiança {confidence:.2%} abaixo do mínimo "
                f"{self.min_confidence:.2%}"
            )
            return False
        
        return True
    
    def create_signal(self, action: str, confidence: float, 
                     reason: str, details: Optional[Dict] = None) -> Dict:
        """
        Cria sinal padronizado
        
        Args:
            action: BUY, SELL ou HOLD
            confidence: Nível de confiança (0.0 a 1.0)
            reason: Razão do sinal
            details: Detalhes adicionais
            
        Returns:
            Dict com sinal completo com SL/TP
        """
        details = details or {}
        
        # Obter preço atual dos details ou da análise técnica
        current_price = details.get('current_price', 0)
        
        # Se não tem current_price nos details, tentar pegar da analysis
        if not current_price and 'analysis' in details:
            m5_data = details.get('analysis', {}).get('M5', {})
            current_price = m5_data.get('close', 0)
        
        # Calcular SL/TP baseado na ação
        sl = None
        tp = None
        
        if action == 'BUY' and current_price > 0:
            # Para BUY: SL abaixo, TP acima
            sl = current_price - (current_price * 0.005)  # 0.5% abaixo
            tp = current_price + (current_price * 0.015)  # 1.5% acima (R:R 1:3)
        elif action == 'SELL' and current_price > 0:
            # Para SELL: SL acima, TP abaixo
            sl = current_price + (current_price * 0.005)  # 0.5% acima
            tp = current_price - (current_price * 0.015)  # 1.5% abaixo (R:R 1:3)
        
        signal = {
            'strategy': self.name,
            'action': action,
            'confidence': round(confidence, 3),
            'reason': reason,
            'details': details,
            'price': current_price,
            'sl': round(sl, 2) if sl else None,
            'tp': round(tp, 2) if tp else None
        }
        
        return signal
    
    def __str__(self) -> str:
        return f"{self.name} (enabled={self.enabled})"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
