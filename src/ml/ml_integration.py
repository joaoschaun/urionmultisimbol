# -*- coding: utf-8 -*-
"""
ML INTEGRATION MANAGER - URION 2.0 ELITE
=========================================
Integração central de todos os módulos de Machine Learning

Conecta:
1. Feature Engineering (50+ features)
2. XGBoost Signal Predictor
3. Macro Context Analyzer
4. Strategy Degradation Detector
5. LSTM Price Predictor (ELITE)
6. Reinforcement Learning Agent (ELITE)
7. Ensemble Model Manager (ELITE)

Autor: Urion Trading Bot
Versão: 2.0 ELITE
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from loguru import logger

# Importacoes locais - Core
from ml.feature_engineering import AdvancedFeatureEngineer, FeatureSet
from ml.xgboost_predictor import XGBoostSignalPredictor, PredictionResult, SignalQuality
from core.macro_context import MacroContextAnalyzer, MacroContext
from core.strategy_degradation_detector import StrategyDegradationDetector, DegradationLevel

# Importacoes Elite (opcionais - usando lazy loading para performance)
LSTM_AVAILABLE = False
RL_AVAILABLE = False
ENSEMBLE_AVAILABLE = False
LSTMPricePredictor = None
LSTMPrediction = None
RLTradingAgent = None
EnsembleModelManager = None
EnsembleDecision = None


def _lazy_load_lstm():
    global LSTM_AVAILABLE, LSTMPricePredictor, LSTMPrediction
    if LSTMPricePredictor is not None:
        return LSTM_AVAILABLE
    try:
        from ml.lstm_predictor import LSTMPricePredictor as _LSTM, LSTMPrediction as _Pred
        LSTMPricePredictor = _LSTM
        LSTMPrediction = _Pred
        LSTM_AVAILABLE = True
        logger.info("LSTM Predictor carregado com sucesso")
    except ImportError as e:
        LSTM_AVAILABLE = False
        logger.warning(f"LSTM Predictor nao disponivel: {e}")
    return LSTM_AVAILABLE


def _lazy_load_rl():
    global RL_AVAILABLE, RLTradingAgent
    if RLTradingAgent is not None:
        return RL_AVAILABLE
    try:
        from ml.rl_agent import RLTradingAgent as _RL
        RLTradingAgent = _RL
        RL_AVAILABLE = True
        logger.info("RL Agent carregado com sucesso")
    except ImportError as e:
        RL_AVAILABLE = False
        logger.warning(f"RL Agent nao disponivel: {e}")
    return RL_AVAILABLE


def _lazy_load_ensemble():
    global ENSEMBLE_AVAILABLE, EnsembleModelManager, EnsembleDecision
    if EnsembleModelManager is not None:
        return ENSEMBLE_AVAILABLE
    try:
        from ml.ensemble_manager import EnsembleModelManager as _Ens, EnsembleDecision as _Dec
        EnsembleModelManager = _Ens
        EnsembleDecision = _Dec
        ENSEMBLE_AVAILABLE = True
        logger.info("Ensemble Manager carregado com sucesso")
    except ImportError as e:
        ENSEMBLE_AVAILABLE = False
        logger.warning(f"Ensemble Manager nao disponivel: {e}")
    return ENSEMBLE_AVAILABLE


@dataclass
class SignalEnhancement:
    """Resultado da análise ML completa de um sinal"""
    # Dados originais
    symbol: str
    strategy: str
    direction: str  # 'buy' ou 'sell'
    original_confidence: float
    
    # Features geradas
    features: Optional[FeatureSet] = None
    
    # Previsão XGBoost
    ml_prediction: Optional[PredictionResult] = None
    
    # Contexto Macro
    macro_context: Optional[MacroContext] = None
    macro_bias: float = 0.0
    macro_aligned: bool = True
    
    # Degradacao da estrategia
    degradation_level: DegradationLevel = DegradationLevel.HEALTHY
    
    # === ELITE MODELS ===
    # LSTM Prediction
    lstm_prediction: Optional[Any] = None  # LSTMPrediction
    lstm_direction: str = ""  # up, down, neutral
    lstm_confidence: float = 0.0
    
    # RL Agent
    rl_action: int = 0  # 0=hold, 1=buy, 2=sell
    rl_confidence: float = 0.0
    
    # Ensemble Decision
    ensemble_decision: Optional[Any] = None  # EnsembleDecision
    ensemble_consensus: str = ""  # strong_execute, execute, cautious, reduce, skip
    
    # Decisão final
    should_execute: bool = True
    adjusted_confidence: float = 0.0
    adjusted_lot_multiplier: float = 1.0
    rejection_reason: str = ""
    
    # Metadados
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    elite_mode: bool = False  # Se usou modelos elite
    
    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'strategy': self.strategy,
            'direction': self.direction,
            'original_confidence': self.original_confidence,
            'adjusted_confidence': self.adjusted_confidence,
            'should_execute': self.should_execute,
            'lot_multiplier': self.adjusted_lot_multiplier,
            'ml_quality': self.ml_prediction.signal_quality.value if self.ml_prediction else 'unknown',
            'ml_probability': self.ml_prediction.win_probability if self.ml_prediction else 0.5,
            'macro_bias': self.macro_bias,
            'macro_aligned': self.macro_aligned,
            'degradation': self.degradation_level.value,
            # Elite info
            'elite_mode': self.elite_mode,
            'lstm_direction': self.lstm_direction,
            'lstm_confidence': self.lstm_confidence,
            'rl_action': self.rl_action,
            'ensemble_consensus': self.ensemble_consensus,
            'rejection_reason': self.rejection_reason,
            'processing_time_ms': self.processing_time_ms
        }


class MLIntegrationManager:
    """
    Gerenciador Central de Integração ML - ELITE
    
    Processa sinais através de múltiplos módulos ML:
    
    === CORE MODULES ===
    1. Feature Engineering
       - Gera 50+ features dos dados de mercado
       
    2. XGBoost Predictor
       - Prevê probabilidade de sucesso do trade
       - Recomenda executar/reduzir/pular
       
    3. Macro Context
       - Analisa DXY, VIX para contexto
       - Verifica alinhamento com direção do trade
       
    4. Degradation Detector
       - Verifica se estratégia está em declínio
       - Ajusta parâmetros automaticamente
    
    === ELITE MODULES ===
    5. LSTM Price Predictor
       - Rede neural para previsão de preço
       - Previsão de direção e magnitude
       
    6. Reinforcement Learning Agent
       - Agente DQN que aprende estratégias ótimas
       - Decisões baseadas em experiência acumulada
       
    7. Ensemble Model Manager
       - Combina todos os modelos para decisao robusta
       - Votacao ponderada com pesos adaptativos
       
    Resultado: SignalEnhancement com decisao final
    """
    
    def __init__(self, config: dict = None, elite_mode: bool = True):
        """
        Args:
            config: Configuracao completa do bot
            elite_mode: Se True, usa modelos avancados (LSTM, RL, Ensemble)
        """
        self.config = config or {}
        
        # Lazy load Elite modules quando elite_mode solicitado
        if elite_mode:
            _lazy_load_lstm()
            _lazy_load_rl()
            _lazy_load_ensemble()
        
        self.elite_mode = elite_mode and (LSTM_AVAILABLE or RL_AVAILABLE or ENSEMBLE_AVAILABLE)
        
        # Configuracoes especificas
        ml_config = self.config.get('xgboost_predictor', {})
        macro_config = self.config.get('macro_context', {})
        feature_config = self.config.get('feature_engineering', {})
        degradation_config = self.config.get('degradation_detector', {})
        
        # Inicializar modulos CORE
        self.feature_engineer = AdvancedFeatureEngineer(feature_config)
        self.xgb_predictor = XGBoostSignalPredictor(
            config=ml_config,
            data_dir=ml_config.get('data_dir', 'data/ml')
        )
        self.macro_analyzer = MacroContextAnalyzer(macro_config)
        self.degradation_detector = StrategyDegradationDetector(degradation_config)
        
        # Inicializar modulos ELITE
        self.lstm_predictor = None
        self.rl_agent = None
        self.ensemble_manager = None
        
        if self.elite_mode:
            self._init_elite_modules()
        
        # Configuracoes de decisao
        self.min_ml_quality = SignalQuality.MODERATE
        self.use_macro_filter = self.config.get('macro_context', {}).get('enabled', True)
        self.macro_min_alignment = 0.3
        self.use_ensemble = self.elite_mode and ENSEMBLE_AVAILABLE
        
        # Estatisticas
        self._stats = {
            'signals_processed': 0,
            'signals_enhanced': 0,
            'signals_rejected': 0,
            'avg_processing_time_ms': 0,
            'elite_decisions': 0,
            'ensemble_agreements': 0
        }
        
        mode_str = "ELITE" if self.elite_mode else "STANDARD"
        logger.info(f"MLIntegrationManager inicializado em modo {mode_str}")
    
    def _init_elite_modules(self) -> None:
        """Inicializa modulos Elite (LSTM, RL, Ensemble)"""
        elite_config = self.config.get('elite', {})
        
        # LSTM Predictor
        if LSTM_AVAILABLE and LSTMPricePredictor is not None:
            try:
                lstm_config = elite_config.get('lstm', {})
                self.lstm_predictor = LSTMPricePredictor(
                    config=lstm_config,
                    data_dir=lstm_config.get('data_dir', 'data/ml/lstm')
                )
                logger.info("LSTM Predictor inicializado")
            except Exception as e:
                logger.error(f"Erro ao inicializar LSTM: {e}")
        
        # RL Agent
        if RL_AVAILABLE and RLTradingAgent is not None:
            try:
                rl_config = elite_config.get('rl_agent', {})
                self.rl_agent = RLTradingAgent(
                    config=rl_config,
                    data_dir=rl_config.get('data_dir', 'data/ml/rl')
                )
                logger.info("RL Agent inicializado")
            except Exception as e:
                logger.error(f"Erro ao inicializar RL Agent: {e}")
        
        # Ensemble Manager
        if ENSEMBLE_AVAILABLE and EnsembleModelManager is not None:
            try:
                ensemble_config = elite_config.get('ensemble', {})
                self.ensemble_manager = EnsembleModelManager(
                    config=ensemble_config,
                    xgboost_predictor=self.xgb_predictor,
                    lstm_predictor=self.lstm_predictor,
                    rl_agent=self.rl_agent,
                    macro_analyzer=self.macro_analyzer
                )
                logger.info("Ensemble Manager inicializado")
            except Exception as e:
                logger.error(f"Erro ao inicializar Ensemble: {e}")
    
    async def enhance_signal(
        self,
        symbol: str,
        strategy: str,
        direction: str,
        confidence: float,
        market_data: pd.DataFrame,
        additional_context: dict = None
    ) -> SignalEnhancement:
        """
        Processa sinal através de todos os módulos ML
        
        Args:
            symbol: Símbolo (XAUUSD, EURUSD, etc)
            strategy: Nome da estratégia
            direction: 'buy' ou 'sell'
            confidence: Confiança original (0-1)
            market_data: DataFrame com OHLCV
            additional_context: Contexto adicional
            
        Returns:
            SignalEnhancement com análise completa
        """
        start_time = datetime.now()
        
        enhancement = SignalEnhancement(
            symbol=symbol,
            strategy=strategy,
            direction=direction,
            original_confidence=confidence,
            adjusted_confidence=confidence,
            elite_mode=self.elite_mode
        )
        
        try:
            # === CORE PIPELINE ===
            
            # 1. GERAR FEATURES
            await self._generate_features(enhancement, market_data)
            
            # 2. OBTER CONTEXTO MACRO
            await self._analyze_macro_context(enhancement)
            
            # 3. PREVISÃO ML (XGBoost)
            await self._predict_signal_quality(enhancement)
            
            # 4. VERIFICAR DEGRADAÇÃO DA ESTRATÉGIA
            await self._check_strategy_degradation(enhancement, additional_context)
            
            # === ELITE PIPELINE ===
            if self.elite_mode:
                # 5. LSTM Price Prediction
                await self._predict_with_lstm(enhancement, market_data)
                
                # 6. RL Agent Decision
                await self._get_rl_decision(enhancement, market_data)
                
                # 7. ENSEMBLE Decision (combina todos)
                if self.use_ensemble:
                    await self._get_ensemble_decision(enhancement, market_data)
            
            # 8. TOMAR DECISÃO FINAL
            self._make_final_decision(enhancement)
            
            # Estatísticas
            self._stats['signals_processed'] += 1
            if enhancement.should_execute:
                self._stats['signals_enhanced'] += 1
            else:
                self._stats['signals_rejected'] += 1
            
            if self.elite_mode:
                self._stats['elite_decisions'] += 1
            
        except Exception as e:
            logger.error(f"Erro no enhance_signal: {e}")
            import traceback
            traceback.print_exc()
            # Em caso de erro, permitir execução com valores originais
            enhancement.should_execute = True
            enhancement.adjusted_confidence = confidence
            enhancement.rejection_reason = f"error: {str(e)}"
        
        # Calcular tempo de processamento
        enhancement.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Atualizar média
        n = self._stats['signals_processed']
        old_avg = self._stats['avg_processing_time_ms']
        self._stats['avg_processing_time_ms'] = old_avg + (enhancement.processing_time_ms - old_avg) / n
        
        return enhancement
    
    async def _generate_features(
        self,
        enhancement: SignalEnhancement,
        market_data: pd.DataFrame
    ) -> None:
        """Gera features usando Feature Engineer"""
        try:
            # Obter contexto macro para features
            macro_dict = None
            if enhancement.macro_context:
                macro_dict = enhancement.macro_context.to_dict()
            
            # Gerar features
            feature_set = await self.feature_engineer.generate_features(
                df=market_data,
                symbol=enhancement.symbol,
                macro_context=macro_dict
            )
            
            enhancement.features = feature_set
            
        except Exception as e:
            logger.warning(f"Erro ao gerar features: {e}")
    
    async def _analyze_macro_context(
        self,
        enhancement: SignalEnhancement
    ) -> None:
        """Analisa contexto macroeconômico"""
        if not self.use_macro_filter:
            return
        
        try:
            # Obter contexto
            context = await self.macro_analyzer.get_context()
            enhancement.macro_context = context
            
            # Obter bias para o símbolo
            bias, bias_desc = self.macro_analyzer.get_symbol_bias(enhancement.symbol)
            enhancement.macro_bias = bias
            
            # Verificar alinhamento com direção
            if enhancement.direction.lower() == 'buy':
                # Para compra, queremos bias positivo
                enhancement.macro_aligned = bias >= -self.macro_min_alignment
            else:
                # Para venda, queremos bias negativo
                enhancement.macro_aligned = bias <= self.macro_min_alignment
            
            # Ajustar confiança baseado no macro
            adjusted = self.macro_analyzer.adjust_confidence(
                symbol=enhancement.symbol,
                direction=enhancement.direction,
                base_confidence=enhancement.adjusted_confidence
            )
            enhancement.adjusted_confidence = adjusted
            
        except Exception as e:
            logger.warning(f"Erro ao analisar macro: {e}")
    
    async def _predict_signal_quality(
        self,
        enhancement: SignalEnhancement
    ) -> None:
        """Usa XGBoost para prever qualidade do sinal"""
        if not enhancement.features:
            return
        
        try:
            # Fazer previsão
            prediction = await self.xgb_predictor.predict(
                features=enhancement.features.to_array(),
                feature_names=enhancement.features.feature_names,
                symbol=enhancement.symbol,
                strategy=enhancement.strategy
            )
            
            enhancement.ml_prediction = prediction
            
            # Ajustar confiança com ML
            if prediction.confidence > 0.3:  # Só se modelo tem confiança
                enhancement.adjusted_confidence = self.xgb_predictor.adjust_confidence(
                    prediction=prediction,
                    base_confidence=enhancement.adjusted_confidence
                )
            
            # Ajustar multiplicador de lote
            enhancement.adjusted_lot_multiplier = self.xgb_predictor.adjust_lot_size(
                prediction=prediction,
                base_lot=1.0  # Base multiplicador
            )
            
        except Exception as e:
            logger.warning(f"Erro na previsão ML: {e}")
    
    async def _check_strategy_degradation(
        self,
        enhancement: SignalEnhancement,
        context: dict = None
    ) -> None:
        """Verifica degradação da estratégia"""
        try:
            # Obter histórico de trades (do contexto ou placeholder)
            trades = context.get('recent_trades', []) if context else []
            
            if not trades:
                # Sem histórico, assumir OK
                enhancement.degradation_level = DegradationLevel.NONE
                return
            
            # Analisar degradação
            analysis = self.degradation_detector.analyze_strategy(
                strategy_name=enhancement.strategy,
                trades=trades
            )
            
            enhancement.degradation_level = analysis.level
            
            # Se degradação severa, ajustar multiplicador
            if analysis.level == DegradationLevel.SEVERE:
                enhancement.adjusted_lot_multiplier *= 0.5
                enhancement.adjusted_confidence *= 0.8
            elif analysis.level == DegradationLevel.CRITICAL:
                enhancement.adjusted_lot_multiplier *= 0.7
                enhancement.adjusted_confidence *= 0.9
                
        except Exception as e:
            logger.warning(f"Erro ao verificar degradação: {e}")
    
    # === ELITE METHODS ===
    
    async def _predict_with_lstm(
        self,
        enhancement: SignalEnhancement,
        market_data: pd.DataFrame
    ) -> None:
        """Previsão de preço usando LSTM"""
        if not self.lstm_predictor:
            return
        
        try:
            # Fazer previsão
            prediction = await self.lstm_predictor.predict(
                df=market_data,
                symbol=enhancement.symbol
            )
            
            if prediction:
                enhancement.lstm_prediction = prediction
                enhancement.lstm_direction = prediction.direction
                enhancement.lstm_confidence = prediction.confidence
                
                # Verificar alinhamento com sinal
                signal_dir = 'up' if enhancement.direction.lower() == 'buy' else 'down'
                
                if prediction.direction == signal_dir:
                    # LSTM confirma - boost confiança
                    enhancement.adjusted_confidence *= 1.0 + (prediction.confidence * 0.1)
                    enhancement.adjusted_confidence = min(enhancement.adjusted_confidence, 0.95)
                elif prediction.direction != 'neutral' and prediction.confidence > 0.6:
                    # LSTM contradiz fortemente - reduzir confiança
                    enhancement.adjusted_confidence *= 0.85
                    
        except Exception as e:
            logger.warning(f"Erro na previsão LSTM: {e}")
    
    async def _get_rl_decision(
        self,
        enhancement: SignalEnhancement,
        market_data: pd.DataFrame
    ) -> None:
        """Obtém decisão do agente RL"""
        if not self.rl_agent:
            return
        
        try:
            # Construir estado para o RL
            state = self.rl_agent.build_state(
                df=market_data,
                symbol=enhancement.symbol,
                current_position=0  # 0=sem posição
            )
            
            # Obter ação do agente
            action, confidence = await self.rl_agent.get_action(state, exploration=False)
            
            enhancement.rl_action = action
            enhancement.rl_confidence = confidence
            
            # Mapear ação para direção
            # 0=hold, 1=buy, 2=sell
            signal_action = 1 if enhancement.direction.lower() == 'buy' else 2
            
            if action == signal_action:
                # RL confirma - boost
                enhancement.adjusted_confidence *= 1.0 + (confidence * 0.08)
                enhancement.adjusted_confidence = min(enhancement.adjusted_confidence, 0.95)
            elif action == 0:
                # RL diz hold - reduzir levemente
                enhancement.adjusted_confidence *= 0.95
            elif confidence > 0.7:
                # RL contradiz fortemente
                enhancement.adjusted_confidence *= 0.80
                
        except Exception as e:
            logger.warning(f"Erro na decisão RL: {e}")
    
    async def _get_ensemble_decision(
        self,
        enhancement: SignalEnhancement,
        market_data: pd.DataFrame
    ) -> None:
        """Obtém decisão do ensemble de modelos"""
        if not self.ensemble_manager:
            return
        
        try:
            # Construir dados do sinal
            signal_data = {
                'direction': enhancement.direction,
                'confidence': enhancement.original_confidence,
                'strategy': enhancement.strategy,
                'features': enhancement.features
            }
            
            # Obter decisão ensemble
            decision = await self.ensemble_manager.get_ensemble_decision(
                symbol=enhancement.symbol,
                timeframe='M15',  # Default
                signal_data=signal_data,
                df=market_data
            )
            
            if decision:
                enhancement.ensemble_decision = decision
                enhancement.ensemble_consensus = decision.decision_type
                
                # Aplicar decisão do ensemble
                if decision.decision_type == 'strong_execute':
                    enhancement.adjusted_confidence = decision.final_confidence
                    enhancement.adjusted_lot_multiplier *= 1.2
                elif decision.decision_type == 'execute':
                    enhancement.adjusted_confidence = decision.final_confidence
                elif decision.decision_type == 'cautious':
                    enhancement.adjusted_confidence = decision.final_confidence * 0.9
                    enhancement.adjusted_lot_multiplier *= 0.8
                elif decision.decision_type == 'reduce':
                    enhancement.adjusted_confidence = decision.final_confidence * 0.8
                    enhancement.adjusted_lot_multiplier *= 0.6
                elif decision.decision_type == 'skip':
                    enhancement.should_execute = False
                    enhancement.rejection_reason = f"ensemble_skip:{decision.reasoning}"
                
                # Atualizar estatísticas se houve acordo
                if decision.model_agreement > 0.7:
                    self._stats['ensemble_agreements'] += 1
                    
        except Exception as e:
            logger.warning(f"Erro na decisão Ensemble: {e}")
    
    def _make_final_decision(self, enhancement: SignalEnhancement) -> None:
        """Toma decisão final sobre executar ou não"""
        reasons = []
        
        # Se Ensemble já decidiu skip, respeitar
        if enhancement.ensemble_consensus == 'skip':
            enhancement.should_execute = False
            return
        
        # 1. Verificar qualidade ML (XGBoost)
        if enhancement.ml_prediction:
            should_exec, reason = self.xgb_predictor.should_execute_trade(
                prediction=enhancement.ml_prediction,
                min_quality=self.min_ml_quality
            )
            
            if not should_exec:
                # Se não tem suporte Elite, bloquear
                if not self.elite_mode:
                    enhancement.should_execute = False
                    reasons.append(f"ml_{reason}")
                else:
                    # Se tem Elite, usar como aviso
                    reasons.append(f"ml_warn_{reason}")
        
        # 2. Verificar alinhamento macro
        if self.use_macro_filter and not enhancement.macro_aligned:
            filter_mode = self.config.get('macro_context', {}).get('auto_adjust', {}).get('filter_trades', False)
            
            if filter_mode:
                enhancement.should_execute = False
                reasons.append("macro_misaligned")
            else:
                enhancement.adjusted_lot_multiplier *= 0.7
                reasons.append("macro_warn_reduced")
        
        # 3. Verificar degradação
        if enhancement.degradation_level == DegradationLevel.SEVERE:
            enhancement.should_execute = False
            reasons.append("strategy_degraded_severe")
        
        # 4. Verificar LSTM (Elite)
        if self.elite_mode and enhancement.lstm_prediction:
            signal_dir = 'up' if enhancement.direction.lower() == 'buy' else 'down'
            if (enhancement.lstm_direction != 'neutral' and 
                enhancement.lstm_direction != signal_dir and 
                enhancement.lstm_confidence > 0.75):
                # LSTM contradiz fortemente
                if not enhancement.ensemble_decision:  # Sem ensemble para override
                    enhancement.should_execute = False
                    reasons.append("lstm_strong_contradiction")
                else:
                    reasons.append("lstm_warn_contradiction")
        
        # 5. Verificar RL Agent (Elite)
        if self.elite_mode and enhancement.rl_action is not None:
            signal_action = 1 if enhancement.direction.lower() == 'buy' else 2
            # Se RL diz ação oposta com alta confiança
            if (enhancement.rl_action != signal_action and 
                enhancement.rl_action != 0 and  # Não é hold
                enhancement.rl_confidence > 0.8):
                if not enhancement.ensemble_decision:
                    enhancement.should_execute = False
                    reasons.append("rl_strong_contradiction")
                else:
                    reasons.append("rl_warn_contradiction")
        
        # 6. Verificar confiança mínima
        min_confidence = self.config.get('order_generator', {}).get('min_signal_confidence', 0.6)
        if enhancement.adjusted_confidence < min_confidence:
            enhancement.should_execute = False
            reasons.append(f"confidence_below_{min_confidence:.0%}")
        
        # 7. Override final do Ensemble (Elite)
        if enhancement.ensemble_consensus in ['strong_execute', 'execute']:
            # Ensemble com alta confiança pode salvar trade
            if enhancement.ensemble_decision and enhancement.ensemble_decision.model_agreement > 0.8:
                if len(reasons) <= 2:  # Não muitos problemas
                    enhancement.should_execute = True
                    reasons = [f"ensemble_override:{enhancement.ensemble_consensus}"]
        
        # Definir razão de rejeição/avisos
        if reasons and not enhancement.should_execute:
            enhancement.rejection_reason = "|".join(reasons)
        elif reasons:
            enhancement.rejection_reason = f"warnings:{','.join(reasons)}"
    
    async def record_trade_outcome(
        self,
        symbol: str,
        strategy: str,
        features: FeatureSet,
        was_profitable: bool,
        profit_pips: float = 0
    ) -> None:
        """
        Registra resultado do trade para treinamento
        
        Args:
            symbol: Símbolo negociado
            strategy: Estratégia usada
            features: Features usadas na previsão
            was_profitable: Se trade foi lucrativo
            profit_pips: Lucro em pips
        """
        try:
            await self.xgb_predictor.add_training_sample(
                features=features.to_array(),
                feature_names=features.feature_names,
                symbol=symbol,
                strategy=strategy,
                was_profitable=was_profitable,
                profit_pips=profit_pips
            )
            
        except Exception as e:
            logger.error(f"Erro ao registrar outcome: {e}")
    
    async def retrain_models(self, force: bool = False) -> Dict[str, Any]:
        """
        Retreina todos os modelos
        
        Args:
            force: Forçar retreino mesmo com poucas amostras
            
        Returns:
            Dict com resultados do treinamento
        """
        results = {}
        
        stats = self.xgb_predictor.get_model_stats()
        
        for model_key in stats.keys():
            try:
                metrics = await self.xgb_predictor.train_model(model_key, force=force)
                results[model_key] = {
                    'success': metrics is not None,
                    'metrics': metrics.to_dict() if metrics else None
                }
            except Exception as e:
                results[model_key] = {
                    'success': False,
                    'error': str(e)
                }
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do integration manager"""
        return {
            'integration': self._stats.copy(),
            'xgboost': self.xgb_predictor.get_model_stats(),
            'degradation': {
                'strategies_monitored': len(self.degradation_detector._strategy_performance)
            }
        }
    
    async def get_summary(self) -> str:
        """Retorna resumo completo do sistema ML"""
        mode_str = "ELITE" if self.elite_mode else "STANDARD"
        lines = [
            f"🧠 === ML INTEGRATION MANAGER ({mode_str}) ===",
            "",
            f"📊 Sinais processados: {self._stats['signals_processed']}",
            f"✅ Sinais aprovados: {self._stats['signals_enhanced']}",
            f"❌ Sinais rejeitados: {self._stats['signals_rejected']}",
            f"⏱️ Tempo médio: {self._stats['avg_processing_time_ms']:.1f}ms"
        ]
        
        if self.elite_mode:
            lines.extend([
                "",
                "🏆 === ELITE MODULES ===",
                f"🤖 Decisões Elite: {self._stats['elite_decisions']}",
                f"🤝 Acordos Ensemble: {self._stats['ensemble_agreements']}",
                f"🧠 LSTM: {'✅ Ativo' if self.lstm_predictor else '❌ Inativo'}",
                f"🎮 RL Agent: {'✅ Ativo' if self.rl_agent else '❌ Inativo'}",
                f"⚖️ Ensemble: {'✅ Ativo' if self.ensemble_manager else '❌ Inativo'}"
            ])
        
        # XGBoost summary
        xgb_summary = await self.xgb_predictor.get_summary()
        lines.append("\n" + xgb_summary)
        
        # Macro summary
        macro_summary = await self.macro_analyzer.get_summary()
        lines.append("\n" + macro_summary)
        
        # Elite summaries
        if self.elite_mode:
            if self.lstm_predictor:
                try:
                    lstm_summary = self.lstm_predictor.get_summary()
                    lines.append("\n" + lstm_summary)
                except:
                    pass
            
            if self.rl_agent:
                try:
                    rl_summary = self.rl_agent.get_summary()
                    lines.append("\n" + rl_summary)
                except:
                    pass
            
            if self.ensemble_manager:
                try:
                    ensemble_summary = await self.ensemble_manager.get_summary()
                    lines.append("\n" + ensemble_summary)
                except:
                    pass
        
        return "\n".join(lines)
    
    async def train_elite_models(
        self,
        training_data: pd.DataFrame,
        labels: np.ndarray = None
    ) -> Dict[str, Any]:
        """
        Treina todos os modelos Elite
        
        Args:
            training_data: DataFrame com dados de treinamento
            labels: Labels para treinamento supervisionado
            
        Returns:
            Dict com resultados do treinamento
        """
        results = {}
        
        if not self.elite_mode:
            return {'error': 'Elite mode not enabled'}
        
        # Treinar LSTM
        if self.lstm_predictor:
            try:
                lstm_result = await self.lstm_predictor.train(training_data)
                results['lstm'] = lstm_result
                logger.info("✅ LSTM treinado com sucesso")
            except Exception as e:
                results['lstm'] = {'error': str(e)}
                logger.error(f"❌ Erro ao treinar LSTM: {e}")
        
        # Treinar RL (RL treina durante uso, mas pode ter pre-training)
        if self.rl_agent:
            try:
                rl_result = await self.rl_agent.pretrain(training_data)
                results['rl_agent'] = rl_result
                logger.info("✅ RL Agent pré-treinado")
            except Exception as e:
                results['rl_agent'] = {'error': str(e)}
                logger.error(f"❌ Erro ao pré-treinar RL: {e}")
        
        return results
    
    async def save_models(self, directory: str = 'data/ml') -> Dict[str, bool]:
        """Salva todos os modelos"""
        results = {}
        
        # Salvar XGBoost
        try:
            self.xgb_predictor.save_models(directory)
            results['xgboost'] = True
        except Exception as e:
            results['xgboost'] = False
            logger.error(f"Erro ao salvar XGBoost: {e}")
        
        # Salvar modelos Elite
        if self.elite_mode:
            if self.lstm_predictor:
                try:
                    self.lstm_predictor.save_model(f"{directory}/lstm")
                    results['lstm'] = True
                except Exception as e:
                    results['lstm'] = False
                    logger.error(f"Erro ao salvar LSTM: {e}")
            
            if self.rl_agent:
                try:
                    self.rl_agent.save(f"{directory}/rl")
                    results['rl_agent'] = True
                except Exception as e:
                    results['rl_agent'] = False
                    logger.error(f"Erro ao salvar RL Agent: {e}")
        
        return results
    
    async def load_models(self, directory: str = 'data/ml') -> Dict[str, bool]:
        """Carrega todos os modelos"""
        results = {}
        
        # Carregar XGBoost
        try:
            self.xgb_predictor.load_models(directory)
            results['xgboost'] = True
        except Exception as e:
            results['xgboost'] = False
            logger.warning(f"Erro ao carregar XGBoost: {e}")
        
        # Carregar modelos Elite
        if self.elite_mode:
            if self.lstm_predictor:
                try:
                    self.lstm_predictor.load_model(f"{directory}/lstm")
                    results['lstm'] = True
                except Exception as e:
                    results['lstm'] = False
                    logger.warning(f"Erro ao carregar LSTM: {e}")
            
            if self.rl_agent:
                try:
                    self.rl_agent.load(f"{directory}/rl")
                    results['rl_agent'] = True
                except Exception as e:
                    results['rl_agent'] = False
                    logger.warning(f"Erro ao carregar RL Agent: {e}")
        
        return results


# =======================
# SINGLETON E HELPERS
# =======================

_ml_manager: Optional[MLIntegrationManager] = None


def get_ml_manager(config: dict = None, elite_mode: bool = True) -> MLIntegrationManager:
    """
    Obtém instância singleton do ML Manager
    
    Args:
        config: Configuração (apenas usado na primeira chamada)
        elite_mode: Se True, usa modelos avançados
        
    Returns:
        MLIntegrationManager
    """
    global _ml_manager
    
    if _ml_manager is None:
        _ml_manager = MLIntegrationManager(config, elite_mode=elite_mode)
    
    return _ml_manager


def reset_ml_manager() -> None:
    """Reseta o singleton do ML Manager"""
    global _ml_manager
    _ml_manager = None


async def quick_enhance_signal(
    symbol: str,
    strategy: str,
    direction: str,
    confidence: float,
    market_data: pd.DataFrame,
    elite: bool = True
) -> SignalEnhancement:
    """
    Helper para processar sinal rapidamente
    
    Args:
        symbol: Símbolo
        strategy: Estratégia
        direction: 'buy' ou 'sell'
        confidence: Confiança original
        market_data: DataFrame OHLCV
        elite: Se usa modo Elite
        
    Returns:
        SignalEnhancement
    """
    manager = get_ml_manager(elite_mode=elite)
    return await manager.enhance_signal(
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        confidence=confidence,
        market_data=market_data
    )


# =======================
# EXEMPLO DE USO
# =======================

async def example_usage():
    """Exemplo de uso do MLIntegrationManager ELITE"""
    
    # Configuração
    config = {
        'xgboost_predictor': {
            'enabled': True,
            'min_training_samples': 50,
            'data_dir': 'data/ml'
        },
        'macro_context': {
            'enabled': True,
            'update_interval_minutes': 15
        },
        'order_generator': {
            'min_signal_confidence': 0.6
        },
        'elite': {
            'lstm': {
                'enabled': True,
                'sequence_length': 60,
                'data_dir': 'data/ml/lstm'
            },
            'rl_agent': {
                'enabled': True,
                'data_dir': 'data/ml/rl'
            },
            'ensemble': {
                'enabled': True,
                'min_agreement': 0.6
            }
        }
    }
    
    # Criar manager em modo ELITE
    manager = MLIntegrationManager(config, elite_mode=True)
    
    # Criar dados de mercado simulados
    np.random.seed(42)
    n = 300
    
    dates = pd.date_range(end=datetime.now(), periods=n, freq='H')
    close = 2000 + np.cumsum(np.random.randn(n) * 5)
    
    market_data = pd.DataFrame({
        'open': close + np.random.randn(n) * 3,
        'high': close + np.random.rand(n) * 10,
        'low': close - np.random.rand(n) * 10,
        'close': close,
        'volume': np.random.randint(1000, 10000, n)
    }, index=dates)
    
    # Processar sinal
    print("🔄 Processando sinal em modo ELITE...")
    
    enhancement = await manager.enhance_signal(
        symbol='XAUUSD',
        strategy='trend_following',
        direction='buy',
        confidence=0.75,
        market_data=market_data
    )
    
    print(f"\n📊 Resultado:")
    print(f"   🎯 Should Execute: {enhancement.should_execute}")
    print(f"   📈 Original Confidence: {enhancement.original_confidence:.2%}")
    print(f"   📊 Adjusted Confidence: {enhancement.adjusted_confidence:.2%}")
    print(f"   📦 Lot Multiplier: {enhancement.adjusted_lot_multiplier:.2f}")
    
    # Core results
    print(f"\n   === CORE ===")
    print(f"   🤖 XGBoost Quality: {enhancement.ml_prediction.signal_quality.value if enhancement.ml_prediction else 'N/A'}")
    print(f"   🌍 Macro Aligned: {enhancement.macro_aligned}")
    print(f"   📉 Degradation: {enhancement.degradation_level.value}")
    
    # Elite results
    if enhancement.elite_mode:
        print(f"\n   === ELITE ===")
        print(f"   🧠 LSTM Direction: {enhancement.lstm_direction or 'N/A'}")
        print(f"   🧠 LSTM Confidence: {enhancement.lstm_confidence:.2%}")
        print(f"   🎮 RL Action: {enhancement.rl_action} (0=hold, 1=buy, 2=sell)")
        print(f"   🎮 RL Confidence: {enhancement.rl_confidence:.2%}")
        print(f"   ⚖️ Ensemble Consensus: {enhancement.ensemble_consensus or 'N/A'}")
    
    print(f"\n   ❌ Rejection Reason: {enhancement.rejection_reason or 'None'}")
    print(f"   ⏱️ Processing Time: {enhancement.processing_time_ms:.1f}ms")
    
    # Resumo
    summary = await manager.get_summary()
    print(f"\n{summary}")


if __name__ == "__main__":
    asyncio.run(example_usage())
