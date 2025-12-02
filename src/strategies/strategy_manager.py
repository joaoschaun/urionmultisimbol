"""
Gerenciador de Estratégias
Coordena múltiplas estratégias e combina sinais
🔥 CORRIGIDO: Suporte multi-símbolo - cada instância opera um símbolo específico
🧠 v2.0: Integração com Market Context para comunicação entre timeframes
"""

from typing import Dict, List, Optional
from loguru import logger

from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .news_trading import NewsTradingStrategy
from .scalping import ScalpingStrategy
from .range_trading import RangeTradingStrategy
from .catamilho import CatamilhoStrategy

# Import do Market Context (comunicação entre timeframes)
try:
    from ..analysis.market_context import MarketContextAnalyzer, MarketDirection, MarketRegime
    from ..analysis.market_regime_detector import MarketRegimeDetector, get_regime_detector
    MARKET_CONTEXT_AVAILABLE = True
except ImportError:
    MARKET_CONTEXT_AVAILABLE = False
    logger.warning("⚠️ Market Context não disponível - estratégias operam independentes")


class StrategyManager:
    """
    Gerencia múltiplas estratégias de trading para um símbolo específico
    🔥 Cada símbolo deve ter sua própria instância de StrategyManager
    🧠 v2.0: Consulta Market Context antes de permitir sinais
    """
    
    def __init__(self, config: Dict, symbol: str = None, technical_analyzer = None):
        """
        Inicializa gerenciador com estratégias configuradas
        
        Args:
            config: Configurações do sistema
            symbol: Símbolo para operar (ex: EURUSD, XAUUSD)
            technical_analyzer: TechnicalAnalyzer para Market Context
        """
        self.config = config
        self.strategies_config = config.get('strategies', {})
        # 🔥 MULTI-SÍMBOLO: Guardar símbolo no manager
        self.symbol = symbol if symbol else 'XAUUSD'
        
        # 🧠 Market Context para comunicação entre timeframes
        self.market_context: Optional[MarketContextAnalyzer] = None
        self.regime_detector: Optional[MarketRegimeDetector] = None
        
        if MARKET_CONTEXT_AVAILABLE:
            if technical_analyzer:
                self.market_context = MarketContextAnalyzer(
                    technical_analyzer, config, self.symbol
                )
            self.regime_detector = get_regime_detector(config)
            logger.info(f"🧠 Market Context habilitado para {self.symbol}")
        
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
        
        # 7. Catamilho (Scalping M1 Ultra-Ativo)
        catamilho_config = self.strategies_config.get('catamilho', {})
        if catamilho_config.get('enabled', False):  # Desabilitado por padrão (alta frequência)
            # 🌽 Catamilho só opera em pares com spread baixo
            catamilho_symbols = catamilho_config.get('symbols', ['EURUSD', 'GBPUSD', 'USDJPY'])
            if self.symbol in catamilho_symbols:
                self.strategies['catamilho'] = CatamilhoStrategy(catamilho_config, symbol=self.symbol)
                logger.info(f"🌽 Estratégia Catamilho carregada para {self.symbol}")
            else:
                logger.debug(f"🌽 Catamilho não habilitada para {self.symbol} (só {catamilho_symbols})")
        
        logger.info(f"StrategyManager inicializado: {len(self.strategies)} estratégias para {self.symbol}")
    
    def set_technical_analyzer(self, technical_analyzer):
        """
        Define o TechnicalAnalyzer para Market Context (se não foi passado no init)
        """
        if MARKET_CONTEXT_AVAILABLE and technical_analyzer and not self.market_context:
            self.market_context = MarketContextAnalyzer(
                technical_analyzer, self.config, self.symbol
            )
            logger.info(f"🧠 Market Context configurado para {self.symbol}")
    
    def analyze_all(self, technical_analysis: Dict,
                   news_analysis: Optional[Dict] = None) -> List[Dict]:
        """
        Executa todas as estratégias ativas
        
        🧠 v2.0: FILTRA sinais baseado no Market Context (timeframes maiores)
        
        Args:
            technical_analysis: Análise técnica completa
            news_analysis: Análise de notícias
            
        Returns:
            Lista de sinais de todas as estratégias (filtrados pelo contexto)
        """
        signals = []
        
        # 🧠 Obter contexto de mercado
        market_context = None
        allowed_directions = ['BUY', 'SELL']  # Default: ambas direções
        recommended_strategies = []
        risk_multiplier = 1.0
        
        if self.market_context:
            market_context = self.market_context.get_context()
            if market_context:
                allowed_directions = market_context.allowed_directions
                recommended_strategies = market_context.recommended_strategies
                risk_multiplier = market_context.risk_multiplier
                
                logger.debug(
                    f"🧠 [{self.symbol}] Contexto: "
                    f"Direções={allowed_directions}, "
                    f"Regime={market_context.regime.value}, "
                    f"Risk={risk_multiplier:.2f}"
                )
                
                # Se não há direções permitidas, não operar
                if not allowed_directions:
                    logger.info(f"🧠 [{self.symbol}] Mercado indeciso - aguardando direção")
                    return []
        
        for name, strategy in self.strategies.items():
            try:
                if not strategy.is_enabled():
                    continue
                
                # 🧠 Verificar se estratégia é recomendada para o regime atual
                if market_context and recommended_strategies:
                    if name not in recommended_strategies:
                        logger.debug(
                            f"🧠 [{name}] Não recomendada para regime "
                            f"{market_context.regime.value} - pulando"
                        )
                        continue
                
                signal = strategy.analyze(technical_analysis, news_analysis)
                
                if signal and signal.get('action') in ['BUY', 'SELL']:
                    action = signal['action']
                    
                    # 🧠 FILTRO PRINCIPAL: Verificar se direção é permitida
                    if action not in allowed_directions:
                        logger.info(
                            f"🧠 [{name}] Sinal {action} BLOQUEADO - "
                            f"Contexto permite apenas {allowed_directions}"
                        )
                        continue
                    
                    # 🧠 Ajustar confiança baseado no alinhamento com contexto
                    if market_context:
                        original_confidence = signal.get('confidence', 0.5)
                        
                        # Bonus se estratégia é recomendada
                        if name in recommended_strategies:
                            signal['confidence'] = min(original_confidence * 1.1, 1.0)
                        
                        # Aplicar multiplicador de risco
                        signal['risk_multiplier'] = risk_multiplier
                        
                        # Adicionar info do contexto
                        signal['market_context'] = {
                            'regime': market_context.regime.value,
                            'macro_direction': market_context.macro_direction.name,
                            'risk_multiplier': risk_multiplier
                        }
                    
                    signals.append(signal)
                    logger.debug(
                        f"✅ {name}: {action} "
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
    
    # =========================================
    # 🧠 MÉTODOS DO MARKET CONTEXT
    # =========================================
    
    def get_market_context(self):
        """Retorna o contexto de mercado atual"""
        if self.market_context:
            return self.market_context.get_context()
        return None
    
    def get_market_regime(self) -> str:
        """Retorna o regime de mercado atual"""
        if self.market_context:
            return self.market_context.get_regime()
        return 'UNKNOWN'
    
    def get_macro_bias(self) -> str:
        """Retorna o viés macro (BULLISH/BEARISH/NEUTRAL)"""
        if self.market_context:
            return self.market_context.get_macro_bias()
        return 'NEUTRAL'
    
    def can_trade_direction(self, direction: str) -> bool:
        """Verifica se uma direção específica é permitida"""
        if self.market_context:
            return self.market_context.can_trade(direction)
        return True  # Default: permitir
    
    def get_risk_adjustment(self) -> float:
        """Retorna o multiplicador de risco baseado no contexto"""
        if self.market_context:
            return self.market_context.get_risk_adjustment()
        return 1.0
