# -*- coding: utf-8 -*-
"""
ENSEMBLE MODEL MANAGER - URION 2.0 ELITE
=========================================
Combina múltiplos modelos ML para decisão final robusta

Modelos combinados:
1. XGBoost Signal Predictor - Classificação de qualidade
2. LSTM Price Predictor - Previsão de direção e magnitude
3. RL Trading Agent - Otimização de timing e sizing

Métodos de ensemble:
- Voting (majoritário)
- Weighted Average (ponderado por performance)
- Stacking (meta-modelo)
- Confidence-based (por confiança individual)

Autor: Urion Trading Bot
Versão: 2.0 Elite
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from loguru import logger

# Importacoes locais
from ml.xgboost_predictor import XGBoostSignalPredictor, PredictionResult, SignalQuality
from ml.lstm_predictor import LSTMPricePredictor, LSTMPrediction, PredictionDirection
from ml.rl_agent import RLTradingAgent, AgentDecision, Action
from ml.feature_engineering import AdvancedFeatureEngineer, FeatureSet


class EnsembleMethod(Enum):
    """Método de ensemble"""
    VOTING = "voting"                # Votação majoritária
    WEIGHTED = "weighted"            # Média ponderada
    CONFIDENCE = "confidence"        # Baseado em confiança
    STACKING = "stacking"            # Meta-modelo
    DYNAMIC = "dynamic"              # Dinâmico por performance


class FinalSignal(Enum):
    """Sinal final do ensemble"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WEAK_BUY = "weak_buy"
    NEUTRAL = "neutral"
    WEAK_SELL = "weak_sell"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class ModelVote:
    """Voto de um modelo individual"""
    model_name: str
    signal: str                      # "buy", "sell", "neutral"
    confidence: float                # 0-1
    strength: float                  # -1 a 1
    weight: float                    # Peso do modelo
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnsembleDecision:
    """Decisão final do ensemble"""
    final_signal: FinalSignal
    direction: str                   # "buy", "sell", "hold"
    confidence: float                # Confiança combinada (0-1)
    strength: float                  # Força do sinal (-1 a 1)
    
    # Componentes
    votes: List[ModelVote] = field(default_factory=list)
    agreement_score: float = 0.0     # Concordância entre modelos (0-1)
    
    # Recomendações
    recommended_lot_multiplier: float = 1.0
    recommended_sl_multiplier: float = 1.0
    recommended_tp_multiplier: float = 1.0
    
    # Explicação
    reasoning: str = ""
    warnings: List[str] = field(default_factory=list)
    
    # Metadados
    ensemble_method: str = "weighted"
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'final_signal': self.final_signal.value,
            'direction': self.direction,
            'confidence': self.confidence,
            'strength': self.strength,
            'agreement_score': self.agreement_score,
            'lot_multiplier': self.recommended_lot_multiplier,
            'sl_multiplier': self.recommended_sl_multiplier,
            'tp_multiplier': self.recommended_tp_multiplier,
            'reasoning': self.reasoning,
            'warnings': self.warnings,
            'votes': [
                {
                    'model': v.model_name,
                    'signal': v.signal,
                    'confidence': v.confidence,
                    'strength': v.strength
                }
                for v in self.votes
            ]
        }


@dataclass
class ModelPerformance:
    """Performance histórica de um modelo"""
    model_name: str
    accuracy: float = 0.5
    precision: float = 0.5
    win_rate: float = 0.5
    profit_factor: float = 1.0
    sharpe_ratio: float = 0.0
    total_signals: int = 0
    correct_signals: int = 0
    last_update: datetime = field(default_factory=datetime.now)
    
    @property
    def weight(self) -> float:
        """Calcula peso baseado na performance"""
        if self.total_signals < 10:
            return 0.5  # Peso neutro para poucos dados
        
        # Combinar métricas
        weight = (
            self.accuracy * 0.3 +
            self.win_rate * 0.3 +
            min(self.profit_factor / 3, 1.0) * 0.2 +
            min(self.sharpe_ratio / 2 + 0.5, 1.0) * 0.2
        )
        
        return np.clip(weight, 0.1, 1.0)


class EnsembleModelManager:
    """
    Gerenciador de Ensemble de Modelos ML
    
    Combina previsões de múltiplos modelos para gerar
    sinal de trading mais robusto e confiável.
    
    Pipeline:
    1. Recebe sinal da estratégia
    2. Gera features (50+)
    3. Consulta cada modelo
    4. Combina previsões usando método configurado
    5. Retorna decisão final com ajustes
    """
    
    # Pesos base dos modelos
    BASE_WEIGHTS = {
        'xgboost': 0.35,      # Bom em classificação
        'lstm': 0.35,         # Bom em previsão temporal
        'rl_agent': 0.30      # Bom em timing
    }
    
    def __init__(self, config: dict = None):
        """
        Args:
            config: Configurações do ensemble
        """
        self.config = config or {}
        
        # Método de ensemble
        self.method = EnsembleMethod(
            self.config.get('method', 'weighted')
        )
        
        # Thresholds
        self.min_confidence = self.config.get('min_confidence', 0.5)
        self.min_agreement = self.config.get('min_agreement', 0.5)
        self.strong_signal_threshold = self.config.get('strong_threshold', 0.75)
        
        # Inicializar modelos
        xgb_config = self.config.get('xgboost', {})
        lstm_config = self.config.get('lstm', {})
        rl_config = self.config.get('rl_agent', {})
        feature_config = self.config.get('features', {})
        
        self.feature_engineer = AdvancedFeatureEngineer(feature_config)
        self.xgb_predictor = XGBoostSignalPredictor(xgb_config)
        self.lstm_predictor = LSTMPricePredictor(lstm_config)
        self.rl_agent = RLTradingAgent(rl_config)
        
        # Performance tracking
        self._model_performance: Dict[str, ModelPerformance] = {
            'xgboost': ModelPerformance(model_name='xgboost'),
            'lstm': ModelPerformance(model_name='lstm'),
            'rl_agent': ModelPerformance(model_name='rl_agent')
        }
        
        # Estatísticas
        self._stats = {
            'total_decisions': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'neutral_signals': 0,
            'avg_confidence': 0.0,
            'avg_agreement': 0.0
        }
        
        logger.info(f"🎯 EnsembleModelManager inicializado (method={self.method.value})")
    
    async def get_ensemble_decision(
        self,
        symbol: str,
        strategy: str,
        market_data: pd.DataFrame,
        current_price: float,
        account_balance: float = 10000,
        strategy_signal: str = None  # Sinal original da estratégia
    ) -> EnsembleDecision:
        """
        Obtém decisão do ensemble de modelos
        
        Args:
            symbol: Símbolo
            strategy: Nome da estratégia
            market_data: DataFrame com OHLCV
            current_price: Preço atual
            account_balance: Saldo da conta
            strategy_signal: Sinal original ("buy", "sell", None)
            
        Returns:
            EnsembleDecision
        """
        start_time = datetime.now()
        
        try:
            # 1. Gerar features
            features = await self.feature_engineer.generate_features(
                df=market_data,
                symbol=symbol
            )
            
            # 2. Coletar votos de cada modelo
            votes = await self._collect_votes(
                symbol=symbol,
                strategy=strategy,
                features=features,
                market_data=market_data,
                current_price=current_price,
                account_balance=account_balance
            )
            
            # 3. Combinar votos
            decision = self._combine_votes(votes, strategy_signal)
            
            # 4. Calcular ajustes de posição
            self._calculate_position_adjustments(decision)
            
            # 5. Gerar explicação
            decision.reasoning = self._generate_reasoning(decision, votes)
            
            # Metadados
            decision.ensemble_method = self.method.value
            decision.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Atualizar estatísticas
            self._update_stats(decision)
            
            return decision
            
        except Exception as e:
            logger.error(f"Erro no ensemble: {e}")
            import traceback
            traceback.print_exc()
            return self._default_decision()
    
    async def _collect_votes(
        self,
        symbol: str,
        strategy: str,
        features: FeatureSet,
        market_data: pd.DataFrame,
        current_price: float,
        account_balance: float
    ) -> List[ModelVote]:
        """Coleta votos de todos os modelos"""
        votes = []
        
        # 1. XGBoost
        try:
            xgb_vote = await self._get_xgb_vote(
                symbol, strategy, features
            )
            if xgb_vote:
                votes.append(xgb_vote)
        except Exception as e:
            logger.warning(f"Erro no XGBoost vote: {e}")
        
        # 2. LSTM
        try:
            lstm_vote = await self._get_lstm_vote(
                symbol, market_data
            )
            if lstm_vote:
                votes.append(lstm_vote)
        except Exception as e:
            logger.warning(f"Erro no LSTM vote: {e}")
        
        # 3. RL Agent
        try:
            rl_vote = await self._get_rl_vote(
                symbol, features.to_array(), current_price, account_balance
            )
            if rl_vote:
                votes.append(rl_vote)
        except Exception as e:
            logger.warning(f"Erro no RL vote: {e}")
        
        return votes
    
    async def _get_xgb_vote(
        self,
        symbol: str,
        strategy: str,
        features: FeatureSet
    ) -> Optional[ModelVote]:
        """Obtém voto do XGBoost"""
        prediction = await self.xgb_predictor.predict(
            features=features.to_array(),
            feature_names=features.feature_names,
            symbol=symbol,
            strategy=strategy
        )
        
        if prediction.confidence < 0.1:
            return None
        
        # Converter qualidade para sinal
        quality_to_signal = {
            SignalQuality.EXCELLENT: ("buy", 0.9),
            SignalQuality.GOOD: ("buy", 0.6),
            SignalQuality.MODERATE: ("neutral", 0.0),
            SignalQuality.POOR: ("sell", -0.4),
            SignalQuality.AVOID: ("sell", -0.8)
        }
        
        signal, strength = quality_to_signal.get(
            prediction.signal_quality, 
            ("neutral", 0.0)
        )
        
        # Ajustar pela probabilidade
        if prediction.win_probability > 0.6:
            signal = "buy"
            strength = prediction.win_probability
        elif prediction.win_probability < 0.4:
            signal = "sell"
            strength = -(1 - prediction.win_probability)
        
        # Peso dinâmico
        perf = self._model_performance['xgboost']
        weight = self.BASE_WEIGHTS['xgboost'] * perf.weight
        
        return ModelVote(
            model_name='xgboost',
            signal=signal,
            confidence=prediction.confidence,
            strength=strength,
            weight=weight,
            details={
                'win_probability': prediction.win_probability,
                'quality': prediction.signal_quality.value
            }
        )
    
    async def _get_lstm_vote(
        self,
        symbol: str,
        market_data: pd.DataFrame
    ) -> Optional[ModelVote]:
        """Obtém voto do LSTM"""
        prediction = await self.lstm_predictor.predict(symbol, market_data)
        
        if prediction.confidence < 0.1:
            return None
        
        # Converter direção para sinal
        direction_to_signal = {
            PredictionDirection.STRONG_UP: ("buy", 0.9),
            PredictionDirection.UP: ("buy", 0.5),
            PredictionDirection.NEUTRAL: ("neutral", 0.0),
            PredictionDirection.DOWN: ("sell", -0.5),
            PredictionDirection.STRONG_DOWN: ("sell", -0.9)
        }
        
        signal, strength = direction_to_signal.get(
            prediction.direction,
            ("neutral", 0.0)
        )
        
        # Ajustar força pela magnitude esperada
        if prediction.expected_move_pips > 10:
            strength *= 1.2
        elif prediction.expected_move_pips < 5:
            strength *= 0.8
        
        strength = np.clip(strength, -1, 1)
        
        # Peso dinâmico
        perf = self._model_performance['lstm']
        weight = self.BASE_WEIGHTS['lstm'] * perf.weight
        
        return ModelVote(
            model_name='lstm',
            signal=signal,
            confidence=prediction.confidence,
            strength=strength,
            weight=weight,
            details={
                'direction': prediction.direction.value,
                'expected_move': prediction.expected_move_pips,
                'volatility': prediction.volatility_forecast
            }
        )
    
    async def _get_rl_vote(
        self,
        symbol: str,
        features: np.ndarray,
        current_price: float,
        account_balance: float
    ) -> Optional[ModelVote]:
        """Obtém voto do RL Agent"""
        decision = await self.rl_agent.decide(
            features, symbol, current_price, account_balance
        )
        
        if decision.confidence < 0.1:
            return None
        
        # Converter ação para sinal
        action_to_signal = {
            Action.BUY: ("buy", 0.7),
            Action.SELL: ("sell", -0.7),
            Action.HOLD: ("neutral", 0.0),
            Action.CLOSE: ("neutral", 0.0)  # Close depende da posição
        }
        
        signal, strength = action_to_signal.get(
            decision.action,
            ("neutral", 0.0)
        )
        
        # Ajustar força pela confiança
        strength *= decision.confidence
        
        # Peso dinâmico
        perf = self._model_performance['rl_agent']
        weight = self.BASE_WEIGHTS['rl_agent'] * perf.weight
        
        return ModelVote(
            model_name='rl_agent',
            signal=signal,
            confidence=decision.confidence,
            strength=strength,
            weight=weight,
            details={
                'action': decision.action.name,
                'q_values': decision.q_values,
                'reasoning': decision.reasoning
            }
        )
    
    def _combine_votes(
        self,
        votes: List[ModelVote],
        strategy_signal: str = None
    ) -> EnsembleDecision:
        """
        Combina votos dos modelos
        
        Args:
            votes: Lista de votos
            strategy_signal: Sinal original da estratégia
            
        Returns:
            EnsembleDecision
        """
        if not votes:
            return self._default_decision()
        
        decision = EnsembleDecision(
            final_signal=FinalSignal.NEUTRAL,
            direction="hold",
            confidence=0.0,
            strength=0.0,
            votes=votes
        )
        
        # Calcular com base no método
        if self.method == EnsembleMethod.VOTING:
            self._voting_combine(decision)
        elif self.method == EnsembleMethod.WEIGHTED:
            self._weighted_combine(decision)
        elif self.method == EnsembleMethod.CONFIDENCE:
            self._confidence_combine(decision)
        elif self.method == EnsembleMethod.DYNAMIC:
            self._dynamic_combine(decision)
        else:
            self._weighted_combine(decision)  # Default
        
        # Calcular agreement
        decision.agreement_score = self._calculate_agreement(votes)
        
        # Considerar sinal da estratégia
        if strategy_signal:
            self._incorporate_strategy_signal(decision, strategy_signal)
        
        # Determinar sinal final
        decision.final_signal = self._determine_final_signal(
            decision.strength,
            decision.confidence
        )
        
        # Determinar direção
        if decision.strength > 0.1:
            decision.direction = "buy"
        elif decision.strength < -0.1:
            decision.direction = "sell"
        else:
            decision.direction = "hold"
        
        # Adicionar warnings
        if decision.agreement_score < self.min_agreement:
            decision.warnings.append(
                f"Baixa concordância entre modelos ({decision.agreement_score:.0%})"
            )
        
        if decision.confidence < self.min_confidence:
            decision.warnings.append(
                f"Confiança baixa ({decision.confidence:.0%})"
            )
        
        return decision
    
    def _voting_combine(self, decision: EnsembleDecision) -> None:
        """Combinação por votação majoritária"""
        buy_votes = sum(1 for v in decision.votes if v.signal == "buy")
        sell_votes = sum(1 for v in decision.votes if v.signal == "sell")
        total = len(decision.votes)
        
        if buy_votes > sell_votes:
            decision.strength = buy_votes / total
            decision.confidence = buy_votes / total
        elif sell_votes > buy_votes:
            decision.strength = -sell_votes / total
            decision.confidence = sell_votes / total
        else:
            decision.strength = 0
            decision.confidence = 0.5
    
    def _weighted_combine(self, decision: EnsembleDecision) -> None:
        """Combinação por média ponderada"""
        total_weight = sum(v.weight for v in decision.votes)
        
        if total_weight == 0:
            return
        
        # Strength ponderado
        weighted_strength = sum(v.strength * v.weight for v in decision.votes)
        decision.strength = weighted_strength / total_weight
        
        # Confidence ponderado
        weighted_confidence = sum(v.confidence * v.weight for v in decision.votes)
        decision.confidence = weighted_confidence / total_weight
    
    def _confidence_combine(self, decision: EnsembleDecision) -> None:
        """Combinação baseada em confiança"""
        # Usar apenas modelos com alta confiança
        high_conf_votes = [v for v in decision.votes if v.confidence > 0.5]
        
        if not high_conf_votes:
            self._weighted_combine(decision)
            return
        
        total_conf = sum(v.confidence for v in high_conf_votes)
        
        # Strength ponderado por confiança
        weighted_strength = sum(v.strength * v.confidence for v in high_conf_votes)
        decision.strength = weighted_strength / total_conf
        
        decision.confidence = total_conf / len(high_conf_votes)
    
    def _dynamic_combine(self, decision: EnsembleDecision) -> None:
        """Combinação dinâmica baseada em performance recente"""
        # Usar performance para ajustar pesos
        adjusted_votes = []
        
        for vote in decision.votes:
            perf = self._model_performance.get(vote.model_name)
            if perf:
                adjusted_weight = vote.weight * perf.weight
                adjusted_votes.append((vote, adjusted_weight))
            else:
                adjusted_votes.append((vote, vote.weight))
        
        total_weight = sum(w for _, w in adjusted_votes)
        
        if total_weight == 0:
            return
        
        # Calcular com pesos ajustados
        decision.strength = sum(
            v.strength * w for v, w in adjusted_votes
        ) / total_weight
        
        decision.confidence = sum(
            v.confidence * w for v, w in adjusted_votes
        ) / total_weight
    
    def _calculate_agreement(self, votes: List[ModelVote]) -> float:
        """Calcula concordância entre modelos"""
        if len(votes) < 2:
            return 1.0
        
        # Contar sinais
        signals = [v.signal for v in votes]
        buy_count = signals.count("buy")
        sell_count = signals.count("sell")
        neutral_count = signals.count("neutral")
        
        max_count = max(buy_count, sell_count, neutral_count)
        
        return max_count / len(votes)
    
    def _incorporate_strategy_signal(
        self,
        decision: EnsembleDecision,
        strategy_signal: str
    ) -> None:
        """Incorpora sinal da estratégia original"""
        # Verificar alinhamento
        if strategy_signal == "buy" and decision.strength > 0:
            decision.strength *= 1.1  # Boost se alinhado
            decision.confidence *= 1.05
        elif strategy_signal == "sell" and decision.strength < 0:
            decision.strength *= 1.1
            decision.confidence *= 1.05
        elif strategy_signal != decision.direction:
            decision.warnings.append(
                f"Sinal da estratégia ({strategy_signal}) diverge do ensemble"
            )
    
    def _determine_final_signal(
        self,
        strength: float,
        confidence: float
    ) -> FinalSignal:
        """Determina sinal final baseado em força e confiança"""
        combined = strength * confidence
        
        if combined > 0.7:
            return FinalSignal.STRONG_BUY
        elif combined > 0.4:
            return FinalSignal.BUY
        elif combined > 0.15:
            return FinalSignal.WEAK_BUY
        elif combined > -0.15:
            return FinalSignal.NEUTRAL
        elif combined > -0.4:
            return FinalSignal.WEAK_SELL
        elif combined > -0.7:
            return FinalSignal.SELL
        else:
            return FinalSignal.STRONG_SELL
    
    def _calculate_position_adjustments(
        self,
        decision: EnsembleDecision
    ) -> None:
        """Calcula ajustes de posição baseado na decisão"""
        # Lot multiplier baseado em confiança e agreement
        base_mult = decision.confidence * decision.agreement_score
        
        if decision.final_signal in [FinalSignal.STRONG_BUY, FinalSignal.STRONG_SELL]:
            decision.recommended_lot_multiplier = min(1.3, 1 + base_mult * 0.3)
        elif decision.final_signal in [FinalSignal.WEAK_BUY, FinalSignal.WEAK_SELL]:
            decision.recommended_lot_multiplier = max(0.5, base_mult)
        else:
            decision.recommended_lot_multiplier = 1.0
        
        # SL/TP baseado em volatilidade prevista pelo LSTM
        lstm_vote = next(
            (v for v in decision.votes if v.model_name == 'lstm'),
            None
        )
        
        if lstm_vote and 'volatility' in lstm_vote.details:
            vol = lstm_vote.details['volatility']
            if vol > 20:  # Alta volatilidade
                decision.recommended_sl_multiplier = 1.3
                decision.recommended_tp_multiplier = 1.5
            elif vol < 10:  # Baixa volatilidade
                decision.recommended_sl_multiplier = 0.8
                decision.recommended_tp_multiplier = 0.9
    
    def _generate_reasoning(
        self,
        decision: EnsembleDecision,
        votes: List[ModelVote]
    ) -> str:
        """Gera explicação da decisão"""
        lines = []
        
        lines.append(f"Sinal: {decision.final_signal.value}")
        lines.append(f"Confiança: {decision.confidence:.0%}")
        lines.append(f"Concordância: {decision.agreement_score:.0%}")
        
        lines.append("\nVotos:")
        for vote in votes:
            lines.append(
                f"  - {vote.model_name}: {vote.signal} "
                f"(conf: {vote.confidence:.0%}, força: {vote.strength:+.2f})"
            )
        
        if decision.warnings:
            lines.append("\n⚠️ Avisos:")
            for warn in decision.warnings:
                lines.append(f"  - {warn}")
        
        return "\n".join(lines)
    
    def _default_decision(self) -> EnsembleDecision:
        """Retorna decisão padrão"""
        return EnsembleDecision(
            final_signal=FinalSignal.NEUTRAL,
            direction="hold",
            confidence=0.0,
            strength=0.0,
            reasoning="Nenhum modelo disponível"
        )
    
    async def update_model_performance(
        self,
        model_name: str,
        was_correct: bool,
        profit_loss: float = 0
    ) -> None:
        """
        Atualiza performance de um modelo
        
        Args:
            model_name: Nome do modelo
            was_correct: Se a previsão estava correta
            profit_loss: P&L do trade
        """
        if model_name not in self._model_performance:
            return
        
        perf = self._model_performance[model_name]
        
        perf.total_signals += 1
        if was_correct:
            perf.correct_signals += 1
        
        # Atualizar métricas
        perf.accuracy = perf.correct_signals / perf.total_signals
        
        if was_correct and profit_loss > 0:
            perf.win_rate = (
                perf.win_rate * (perf.total_signals - 1) + 1
            ) / perf.total_signals
        
        perf.last_update = datetime.now()
    
    def _update_stats(self, decision: EnsembleDecision) -> None:
        """Atualiza estatísticas"""
        self._stats['total_decisions'] += 1
        
        if decision.direction == "buy":
            self._stats['buy_signals'] += 1
        elif decision.direction == "sell":
            self._stats['sell_signals'] += 1
        else:
            self._stats['neutral_signals'] += 1
        
        # Média móvel
        n = self._stats['total_decisions']
        old_conf = self._stats['avg_confidence']
        self._stats['avg_confidence'] = old_conf + (decision.confidence - old_conf) / n
        
        old_agree = self._stats['avg_agreement']
        self._stats['avg_agreement'] = old_agree + (decision.agreement_score - old_agree) / n
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas"""
        return {
            'ensemble': self._stats.copy(),
            'models': {
                name: {
                    'accuracy': perf.accuracy,
                    'win_rate': perf.win_rate,
                    'weight': perf.weight,
                    'total_signals': perf.total_signals
                }
                for name, perf in self._model_performance.items()
            }
        }
    
    async def get_summary(self) -> str:
        """Retorna resumo do ensemble"""
        lines = [
            "🎯 === ENSEMBLE MODEL MANAGER ===",
            f"\n📊 Método: {self.method.value}",
            f"📈 Decisões totais: {self._stats['total_decisions']}",
            f"🟢 Buy signals: {self._stats['buy_signals']}",
            f"🔴 Sell signals: {self._stats['sell_signals']}",
            f"⚪ Neutral: {self._stats['neutral_signals']}",
            f"💯 Confiança média: {self._stats['avg_confidence']:.0%}",
            f"🤝 Concordância média: {self._stats['avg_agreement']:.0%}",
            "\n📦 Performance dos Modelos:"
        ]
        
        for name, perf in self._model_performance.items():
            lines.append(f"  {name}:")
            lines.append(f"    Accuracy: {perf.accuracy:.0%}")
            lines.append(f"    Weight: {perf.weight:.2f}")
            lines.append(f"    Signals: {perf.total_signals}")
        
        return "\n".join(lines)


# =======================
# EXEMPLO DE USO
# =======================

async def example_usage():
    """Exemplo de uso do EnsembleModelManager"""
    
    config = {
        'method': 'weighted',
        'min_confidence': 0.5,
        'min_agreement': 0.5
    }
    
    manager = EnsembleModelManager(config)
    
    # Dados simulados
    np.random.seed(42)
    n = 200
    
    dates = pd.date_range(end=datetime.now(), periods=n, freq='H')
    close = 2000 + np.cumsum(np.random.randn(n) * 5)
    
    market_data = pd.DataFrame({
        'open': close + np.random.randn(n) * 3,
        'high': close + np.random.rand(n) * 10,
        'low': close - np.random.rand(n) * 10,
        'close': close,
        'volume': np.random.randint(1000, 10000, n)
    }, index=dates)
    
    # Obter decisão do ensemble
    decision = await manager.get_ensemble_decision(
        symbol='XAUUSD',
        strategy='trend_following',
        market_data=market_data,
        current_price=close[-1],
        account_balance=10000,
        strategy_signal='buy'
    )
    
    print(f"\n🎯 Decisão do Ensemble:")
    print(f"   Sinal: {decision.final_signal.value}")
    print(f"   Direção: {decision.direction}")
    print(f"   Confiança: {decision.confidence:.0%}")
    print(f"   Força: {decision.strength:+.2f}")
    print(f"   Concordância: {decision.agreement_score:.0%}")
    print(f"   Lot Multiplier: {decision.recommended_lot_multiplier:.2f}")
    
    if decision.warnings:
        print(f"\n⚠️ Warnings: {decision.warnings}")
    
    print(f"\n📝 Reasoning:\n{decision.reasoning}")
    
    # Resumo
    summary = await manager.get_summary()
    print(f"\n{summary}")


if __name__ == "__main__":
    asyncio.run(example_usage())
