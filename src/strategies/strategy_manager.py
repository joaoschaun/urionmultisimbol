"""
Gerenciador de Estratégias
Coordena múltiplas estratégias e combina sinais
🔥 CORRIGIDO: Suporte multi-símbolo - cada instância opera um símbolo específico
"""

from typing import Dict, List, Optional
from loguru import logger

from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .news_trading import NewsTradingStrategy
from .scalping import ScalpingStrategy
from .range_trading import RangeTradingStrategy


class StrategyManager:
    """
    Gerencia múltiplas estratégias de trading para um símbolo específico
    🔥 Cada símbolo deve ter sua própria instância de StrategyManager
    """
    
    def __init__(self, config: Dict, symbol: str = None):
        """
        Inicializa gerenciador com estratégias configuradas
        
        Args:
            config: Configurações do sistema
            symbol: Símbolo para operar (ex: EURUSD, XAUUSD)
        """
        self.config = config
        self.strategies_config = config.get('strategies', {})
        # 🔥 MULTI-SÍMBOLO: Guardar símbolo no manager
        self.symbol = symbol if symbol else 'XAUUSD'
        
        # Inicializar estratégias COM O SÍMBOLO
        self.strategies = {}
        
        # Trend Following
        if self.strategies_config.get('trend_following', {}).get('enabled', True):
            self.strategies['trend_following'] = TrendFollowingStrategy(
                self.strategies_config.get('trend_following', {}),
                symbol=self.symbol
            )
        
        # Mean Reversion
        if self.strategies_config.get('mean_reversion', {}).get('enabled', True):
            self.strategies['mean_reversion'] = MeanReversionStrategy(
                self.strategies_config.get('mean_reversion', {}),
                symbol=self.symbol
            )
        
        # Breakout
        if self.strategies_config.get('breakout', {}).get('enabled', True):
            self.strategies['breakout'] = BreakoutStrategy(
                self.strategies_config.get('breakout', {}),
                symbol=self.symbol
            )
        
        # News Trading
        if self.strategies_config.get('news_trading', {}).get('enabled', True):
            self.strategies['news_trading'] = NewsTradingStrategy(
                self.strategies_config.get('news_trading', {}),
                symbol=self.symbol
            )
        
        # 5. Scalping
        scalping_config = self.strategies_config.get('scalping', {})
        if scalping_config.get('enabled', True):
            self.strategies['scalping'] = ScalpingStrategy(scalping_config, symbol=self.symbol)
            logger.debug(f"Estratégia Scalping carregada para {self.symbol}")
        
        # 6. Range Trading
        range_config = self.strategies_config.get('range_trading', {})
        if range_config.get('enabled', True):
            self.strategies['range_trading'] = RangeTradingStrategy(range_config, symbol=self.symbol)
            logger.debug(f"Estratégia RangeTrading carregada para {self.symbol}")
        
        logger.info(f"StrategyManager inicializado: {len(self.strategies)} estratégias para {self.symbol}")
    
    def analyze_all(self, technical_analysis: Dict,
                   news_analysis: Optional[Dict] = None) -> List[Dict]:
        """
        Executa todas as estratégias ativas
        
        Args:
            technical_analysis: Análise técnica completa
            news_analysis: Análise de notícias
            
        Returns:
            Lista de sinais de todas as estratégias
        """
        signals = []
        
        for name, strategy in self.strategies.items():
            try:
                if not strategy.is_enabled():
                    continue
                
                signal = strategy.analyze(technical_analysis, news_analysis)
                
                if signal and signal.get('action') in ['BUY', 'SELL']:
                    signals.append(signal)
                    logger.debug(
                        f"{name}: {signal['action']} "
                        f"(confiança: {signal['confidence']:.2%})"
                    )
                    
            except Exception as e:
                logger.error(f"Erro ao executar estratégia {name}: {e}")
        
        return signals
    
    def get_best_signal(self, technical_analysis: Dict,
                       news_analysis: Optional[Dict] = None) -> Optional[Dict]:
        """
        Retorna melhor sinal entre todas as estratégias
        
        Args:
            technical_analysis: Análise técnica completa
            news_analysis: Análise de notícias
            
        Returns:
            Melhor sinal ou None
        """
        signals = self.analyze_all(technical_analysis, news_analysis)
        
        if not signals:
            logger.info("Nenhum sinal válido gerado pelas estratégias")
            return None
        
        # Ordenar por confiança
        signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        best_signal = signals[0]
        
        logger.info(
            f"Melhor sinal: {best_signal['strategy']} - "
            f"{best_signal['action']} (confiança: {best_signal['confidence']:.2%})"
        )
        
        return best_signal
    
    def get_consensus_signal(self, technical_analysis: Dict,
                            news_analysis: Optional[Dict] = None) -> Optional[Dict]:
        """
        Retorna sinal de consenso entre estratégias
        
        Args:
            technical_analysis: Análise técnica completa
            news_analysis: Análise de notícias
            
        Returns:
            Sinal de consenso ou None
        """
        signals = self.analyze_all(technical_analysis, news_analysis)
        
        if not signals:
            return None
        
        # Contar votos
        buy_votes = []
        sell_votes = []
        
        for signal in signals:
            action = signal.get('action')
            confidence = signal.get('confidence', 0)
            
            if action == 'BUY':
                buy_votes.append((signal['strategy'], confidence))
            elif action == 'SELL':
                sell_votes.append((signal['strategy'], confidence))
        
        # Calcular consenso
        total_strategies = len(signals)
        buy_count = len(buy_votes)
        sell_count = len(sell_votes)
        
        # Pelo menos 60% de acordo
        min_agreement = 0.6
        
        if buy_count / total_strategies >= min_agreement:
            # Consenso de compra
            avg_confidence = sum(c for _, c in buy_votes) / buy_count
            
            return {
                'strategy': 'Consensus',
                'action': 'BUY',
                'confidence': round(avg_confidence, 3),
                'reason': 'strategy_consensus',
                'details': {
                    'buy_votes': buy_count,
                    'sell_votes': sell_count,
                    'total': total_strategies,
                    'agreement': buy_count / total_strategies,
                    'strategies': [s for s, _ in buy_votes]
                }
            }
            
        elif sell_count / total_strategies >= min_agreement:
            # Consenso de venda
            avg_confidence = sum(c for _, c in sell_votes) / sell_count
            
            return {
                'strategy': 'Consensus',
                'action': 'SELL',
                'confidence': round(avg_confidence, 3),
                'reason': 'strategy_consensus',
                'details': {
                    'buy_votes': buy_count,
                    'sell_votes': sell_count,
                    'total': total_strategies,
                    'agreement': sell_count / total_strategies,
                    'strategies': [s for s, _ in sell_votes]
                }
            }
        
        else:
            # Sem consenso - retornar sinal de maior confiança
            logger.info(
                f"Sem consenso claro: {buy_count} BUY vs {sell_count} SELL"
            )
            return self.get_best_signal(technical_analysis, news_analysis)
    
    def get_strategy(self, name: str):
        """Retorna estratégia específica"""
        return self.strategies.get(name)
    
    def list_strategies(self) -> List[str]:
        """Lista todas as estratégias carregadas"""
        return list(self.strategies.keys())
    
    def enable_strategy(self, name: str):
        """Ativa uma estratégia"""
        if name in self.strategies:
            self.strategies[name].enabled = True
            logger.info(f"Estratégia {name} ativada")
    
    def disable_strategy(self, name: str):
        """Desativa uma estratégia"""
        if name in self.strategies:
            self.strategies[name].enabled = False
            logger.info(f"Estratégia {name} desativada")
