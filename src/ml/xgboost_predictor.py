# -*- coding: utf-8 -*-
"""
XGBOOST SIGNAL PREDICTOR - URION 2.0
=====================================
Preditor de Qualidade de Sinais usando XGBoost

Funcionalidades:
1. Prevê probabilidade de sucesso do trade ANTES de executar
2. Filtra sinais de baixa qualidade
3. Ajusta confiança baseado na previsão
4. Auto-retreinamento com novos dados

Autor: Urion Trading Bot
Versão: 2.0
"""

import asyncio
import pickle
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from loguru import logger
from pathlib import Path

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost não disponível - instale com: pip install xgboost")

try:
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, 
        f1_score, roc_auc_score, classification_report
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("Scikit-learn não disponível - instale com: pip install scikit-learn")


class SignalQuality(Enum):
    """Qualidade do sinal prevista"""
    EXCELLENT = "excellent"    # >80% probabilidade de sucesso
    GOOD = "good"              # 60-80% probabilidade
    MODERATE = "moderate"      # 50-60% probabilidade
    POOR = "poor"              # 40-50% probabilidade
    AVOID = "avoid"            # <40% probabilidade


@dataclass
class PredictionResult:
    """Resultado da previsão do modelo"""
    signal_quality: SignalQuality
    win_probability: float      # Probabilidade de sucesso (0-1)
    confidence: float           # Confiança do modelo na previsão
    recommendation: str         # "execute", "reduce_size", "skip"
    feature_importance: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    
    def to_dict(self) -> dict:
        return {
            'signal_quality': self.signal_quality.value,
            'win_probability': self.win_probability,
            'confidence': self.confidence,
            'recommendation': self.recommendation,
            'explanation': self.explanation
        }


@dataclass
class TrainingMetrics:
    """Métricas de treinamento do modelo"""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    train_samples: int
    test_samples: int
    feature_importance: Dict[str, float]
    training_date: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'roc_auc': self.roc_auc,
            'train_samples': self.train_samples,
            'test_samples': self.test_samples,
            'training_date': self.training_date.isoformat()
        }


class XGBoostSignalPredictor:
    """
    Preditor de Qualidade de Sinais usando XGBoost
    
    O modelo aprende com trades históricos para prever:
    - Probabilidade de um sinal resultar em trade vencedor
    - Confiança da previsão
    - Recomendação (executar, reduzir, pular)
    
    Workflow:
    1. Estratégia gera sinal
    2. Feature Engineer gera 50+ features
    3. XGBoost prevê qualidade do sinal
    4. Se qualidade baixa, ajusta ou rejeita trade
    """
    
    # Limiares de qualidade
    QUALITY_THRESHOLDS = {
        'excellent': 0.80,
        'good': 0.60,
        'moderate': 0.50,
        'poor': 0.40
    }
    
    def __init__(self, config: dict = None, data_dir: str = "data/ml"):
        """
        Args:
            config: Configurações do preditor
            data_dir: Diretório para salvar modelos e dados
        """
        self.config = config or {}
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurações
        self.min_training_samples = self.config.get('min_training_samples', 100)
        self.retrain_interval_days = self.config.get('retrain_interval_days', 7)
        self.min_prediction_confidence = self.config.get('min_prediction_confidence', 0.6)
        
        # XGBoost parameters
        self.xgb_params = {
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'max_depth': self.config.get('max_depth', 6),
            'learning_rate': self.config.get('learning_rate', 0.1),
            'n_estimators': self.config.get('n_estimators', 100),
            'min_child_weight': self.config.get('min_child_weight', 1),
            'subsample': self.config.get('subsample', 0.8),
            'colsample_bytree': self.config.get('colsample_bytree', 0.8),
            'random_state': 42,
            'n_jobs': -1,
            'verbosity': 0
        }
        
        # Modelos por símbolo/estratégia
        self._models: Dict[str, xgb.XGBClassifier] = {}
        self._feature_names: List[str] = []
        self._training_metrics: Dict[str, TrainingMetrics] = {}
        self._last_training: Dict[str, datetime] = {}
        
        # Dados de treinamento
        self._training_data: Dict[str, pd.DataFrame] = {}
        
        # Carregar modelos existentes
        self._load_models()
        
        logger.info("🤖 XGBoostSignalPredictor inicializado")
        
        if not XGBOOST_AVAILABLE:
            logger.error("❌ XGBoost não disponível - predições desabilitadas")
        if not SKLEARN_AVAILABLE:
            logger.error("❌ Scikit-learn não disponível - treinamento desabilitado")
    
    def _get_model_key(self, symbol: str, strategy: str = None) -> str:
        """Gera chave única para modelo"""
        if strategy:
            return f"{symbol}_{strategy}"
        return symbol
    
    def _get_model_path(self, model_key: str) -> Path:
        """Caminho do arquivo do modelo"""
        return self.data_dir / f"xgb_model_{model_key}.pkl"
    
    def _get_data_path(self, model_key: str) -> Path:
        """Caminho do arquivo de dados de treinamento"""
        return self.data_dir / f"training_data_{model_key}.parquet"
    
    def _load_models(self) -> None:
        """Carrega modelos salvos"""
        try:
            for model_file in self.data_dir.glob("xgb_model_*.pkl"):
                model_key = model_file.stem.replace("xgb_model_", "")
                
                try:
                    with open(model_file, 'rb') as f:
                        data = pickle.load(f)
                        self._models[model_key] = data['model']
                        self._training_metrics[model_key] = data.get('metrics')
                        self._last_training[model_key] = data.get(
                            'training_date', 
                            datetime.now() - timedelta(days=30)
                        )
                        
                    logger.info(f"📦 Modelo carregado: {model_key}")
                except Exception as e:
                    logger.warning(f"Erro ao carregar modelo {model_key}: {e}")
                    
            # Carregar feature names
            feature_file = self.data_dir / "feature_names.json"
            if feature_file.exists():
                with open(feature_file, 'r') as f:
                    self._feature_names = json.load(f)
                    
        except Exception as e:
            logger.error(f"Erro ao carregar modelos: {e}")
    
    def _save_model(self, model_key: str) -> None:
        """Salva modelo em disco"""
        try:
            if model_key not in self._models:
                return
            
            model_path = self._get_model_path(model_key)
            
            data = {
                'model': self._models[model_key],
                'metrics': self._training_metrics.get(model_key),
                'training_date': self._last_training.get(model_key, datetime.now())
            }
            
            with open(model_path, 'wb') as f:
                pickle.dump(data, f)
            
            # Salvar feature names
            if self._feature_names:
                feature_file = self.data_dir / "feature_names.json"
                with open(feature_file, 'w') as f:
                    json.dump(self._feature_names, f)
            
            logger.info(f"💾 Modelo salvo: {model_key}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar modelo {model_key}: {e}")
    
    async def predict(
        self,
        features: np.ndarray,
        feature_names: List[str],
        symbol: str,
        strategy: str = None
    ) -> PredictionResult:
        """
        Prevê qualidade do sinal
        
        Args:
            features: Array de features (50+ valores)
            feature_names: Nomes das features
            symbol: Símbolo sendo negociado
            strategy: Estratégia que gerou o sinal (opcional)
            
        Returns:
            PredictionResult com qualidade e recomendação
        """
        if not XGBOOST_AVAILABLE:
            return self._default_prediction()
        
        model_key = self._get_model_key(symbol, strategy)
        
        # Verificar se temos modelo treinado
        if model_key not in self._models:
            # Tentar modelo genérico do símbolo
            model_key = symbol
            if model_key not in self._models:
                return self._default_prediction()
        
        try:
            model = self._models[model_key]
            
            # Garantir shape correto
            if features.ndim == 1:
                features = features.reshape(1, -1)
            
            # Previsão
            win_probability = float(model.predict_proba(features)[0][1])
            
            # Calcular confiança baseada em distância do threshold 0.5
            confidence = abs(win_probability - 0.5) * 2  # 0 a 1
            
            # Determinar qualidade
            signal_quality = self._get_quality_level(win_probability)
            
            # Recomendação
            recommendation = self._get_recommendation(win_probability, confidence)
            
            # Feature importance
            feature_importance = {}
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                for i, name in enumerate(feature_names[:len(importances)]):
                    if importances[i] > 0.01:  # Só features relevantes
                        feature_importance[name] = float(importances[i])
            
            # Explicação
            explanation = self._generate_explanation(
                win_probability, 
                signal_quality, 
                feature_importance
            )
            
            return PredictionResult(
                signal_quality=signal_quality,
                win_probability=win_probability,
                confidence=confidence,
                recommendation=recommendation,
                feature_importance=feature_importance,
                explanation=explanation
            )
            
        except Exception as e:
            logger.error(f"Erro na previsão: {e}")
            return self._default_prediction()
    
    def _default_prediction(self) -> PredictionResult:
        """Retorna previsão padrão quando modelo não disponível"""
        return PredictionResult(
            signal_quality=SignalQuality.MODERATE,
            win_probability=0.50,
            confidence=0.0,
            recommendation="execute",
            explanation="Modelo não disponível - usando valores padrão"
        )
    
    def _get_quality_level(self, probability: float) -> SignalQuality:
        """Determina nível de qualidade baseado na probabilidade"""
        if probability >= self.QUALITY_THRESHOLDS['excellent']:
            return SignalQuality.EXCELLENT
        elif probability >= self.QUALITY_THRESHOLDS['good']:
            return SignalQuality.GOOD
        elif probability >= self.QUALITY_THRESHOLDS['moderate']:
            return SignalQuality.MODERATE
        elif probability >= self.QUALITY_THRESHOLDS['poor']:
            return SignalQuality.POOR
        else:
            return SignalQuality.AVOID
    
    def _get_recommendation(
        self, 
        probability: float, 
        confidence: float
    ) -> str:
        """
        Gera recomendação baseada na previsão
        
        Returns:
            "execute" - Executar normalmente
            "reduce_size" - Executar com tamanho reduzido
            "skip" - Pular este sinal
        """
        if probability >= 0.70 and confidence >= 0.5:
            return "execute"
        elif probability >= 0.55:
            return "reduce_size"
        elif probability >= 0.45 and confidence < 0.3:
            return "execute"  # Modelo incerto, deixar estratégia decidir
        else:
            return "skip"
    
    def _generate_explanation(
        self,
        probability: float,
        quality: SignalQuality,
        feature_importance: Dict[str, float]
    ) -> str:
        """Gera explicação textual da previsão"""
        lines = []
        
        lines.append(f"Probabilidade de sucesso: {probability:.1%}")
        lines.append(f"Qualidade do sinal: {quality.value}")
        
        if feature_importance:
            top_features = sorted(
                feature_importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:3]
            
            if top_features:
                lines.append("Features mais relevantes:")
                for name, importance in top_features:
                    lines.append(f"  - {name}: {importance:.2%}")
        
        return "\n".join(lines)
    
    async def add_training_sample(
        self,
        features: np.ndarray,
        feature_names: List[str],
        symbol: str,
        strategy: str,
        was_profitable: bool,
        profit_pips: float = 0
    ) -> None:
        """
        Adiciona amostra para treinamento
        
        Args:
            features: Features do sinal
            feature_names: Nomes das features
            symbol: Símbolo
            strategy: Estratégia
            was_profitable: Se trade foi lucrativo
            profit_pips: Lucro em pips
        """
        model_key = self._get_model_key(symbol, strategy)
        
        # Armazenar feature names
        if not self._feature_names:
            self._feature_names = feature_names
        
        # Criar ou atualizar DataFrame
        if model_key not in self._training_data:
            self._training_data[model_key] = pd.DataFrame(
                columns=feature_names + ['target', 'profit_pips', 'timestamp']
            )
        
        # Adicionar amostra
        sample = dict(zip(feature_names, features.flatten()))
        sample['target'] = 1 if was_profitable else 0
        sample['profit_pips'] = profit_pips
        sample['timestamp'] = datetime.now()
        
        self._training_data[model_key] = pd.concat([
            self._training_data[model_key],
            pd.DataFrame([sample])
        ], ignore_index=True)
        
        # Salvar dados periodicamente
        if len(self._training_data[model_key]) % 50 == 0:
            await self._save_training_data(model_key)
        
        # Verificar se precisa retreinar
        await self._check_retrain(model_key)
    
    async def _save_training_data(self, model_key: str) -> None:
        """Salva dados de treinamento"""
        if model_key not in self._training_data:
            return
        
        try:
            data_path = self._get_data_path(model_key)
            self._training_data[model_key].to_parquet(data_path)
            logger.debug(f"📊 Dados salvos: {model_key} ({len(self._training_data[model_key])} amostras)")
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")
    
    async def _check_retrain(self, model_key: str) -> None:
        """Verifica se precisa retreinar modelo"""
        if model_key not in self._training_data:
            return
        
        n_samples = len(self._training_data[model_key])
        last_train = self._last_training.get(model_key)
        
        # Condições para retreinar
        needs_retrain = False
        
        # 1. Modelo não existe e temos amostras suficientes
        if model_key not in self._models and n_samples >= self.min_training_samples:
            needs_retrain = True
            logger.info(f"🔄 Primeiro treinamento: {model_key} ({n_samples} amostras)")
        
        # 2. Passou tempo suficiente desde último treino
        elif last_train:
            days_since = (datetime.now() - last_train).days
            if days_since >= self.retrain_interval_days and n_samples >= self.min_training_samples:
                needs_retrain = True
                logger.info(f"🔄 Retreinamento agendado: {model_key} ({days_since} dias)")
        
        if needs_retrain:
            await self.train_model(model_key)
    
    async def train_model(
        self,
        model_key: str,
        force: bool = False
    ) -> Optional[TrainingMetrics]:
        """
        Treina ou retreina modelo
        
        Args:
            model_key: Chave do modelo
            force: Forçar treinamento mesmo com poucas amostras
            
        Returns:
            TrainingMetrics ou None se falhar
        """
        if not XGBOOST_AVAILABLE or not SKLEARN_AVAILABLE:
            logger.error("XGBoost ou Scikit-learn não disponível")
            return None
        
        # Carregar dados de treinamento
        data = await self._load_training_data(model_key)
        
        if data is None or len(data) < self.min_training_samples:
            if not force:
                logger.warning(f"Dados insuficientes para treinar {model_key}: {len(data) if data is not None else 0}")
                return None
        
        try:
            # Preparar features e target
            feature_cols = [c for c in data.columns if c not in ['target', 'profit_pips', 'timestamp']]
            
            X = data[feature_cols].values
            y = data['target'].values
            
            # Verificar balanceamento
            pos_ratio = np.mean(y)
            logger.info(f"📊 Balanceamento: {pos_ratio:.1%} positivo, {1-pos_ratio:.1%} negativo")
            
            # Split treino/teste
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Ajustar peso para classes desbalanceadas
            scale_pos_weight = (1 - pos_ratio) / pos_ratio if pos_ratio > 0 else 1
            
            params = self.xgb_params.copy()
            params['scale_pos_weight'] = scale_pos_weight
            
            # Treinar modelo
            model = xgb.XGBClassifier(**params)
            
            # Early stopping
            model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False
            )
            
            # Avaliar
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]
            
            metrics = TrainingMetrics(
                accuracy=float(accuracy_score(y_test, y_pred)),
                precision=float(precision_score(y_test, y_pred, zero_division=0)),
                recall=float(recall_score(y_test, y_pred, zero_division=0)),
                f1_score=float(f1_score(y_test, y_pred, zero_division=0)),
                roc_auc=float(roc_auc_score(y_test, y_prob)),
                train_samples=len(X_train),
                test_samples=len(X_test),
                feature_importance=dict(zip(
                    feature_cols,
                    [float(x) for x in model.feature_importances_]
                ))
            )
            
            # Salvar modelo
            self._models[model_key] = model
            self._training_metrics[model_key] = metrics
            self._last_training[model_key] = datetime.now()
            self._save_model(model_key)
            
            logger.success(f"""
✅ Modelo treinado: {model_key}
   Accuracy: {metrics.accuracy:.2%}
   Precision: {metrics.precision:.2%}
   Recall: {metrics.recall:.2%}
   F1 Score: {metrics.f1_score:.2%}
   ROC AUC: {metrics.roc_auc:.2%}
            """)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Erro ao treinar modelo {model_key}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _load_training_data(self, model_key: str) -> Optional[pd.DataFrame]:
        """Carrega dados de treinamento do disco"""
        try:
            # Primeiro verificar memória
            if model_key in self._training_data and len(self._training_data[model_key]) > 0:
                return self._training_data[model_key]
            
            # Carregar do disco
            data_path = self._get_data_path(model_key)
            if data_path.exists():
                data = pd.read_parquet(data_path)
                self._training_data[model_key] = data
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {e}")
            return None
    
    def should_execute_trade(
        self,
        prediction: PredictionResult,
        min_quality: SignalQuality = SignalQuality.MODERATE
    ) -> Tuple[bool, str]:
        """
        Decide se deve executar trade baseado na previsão
        
        Args:
            prediction: Resultado da previsão
            min_quality: Qualidade mínima aceitável
            
        Returns:
            Tuple (should_execute, reason)
        """
        # Mapear qualidade para valor numérico
        quality_values = {
            SignalQuality.EXCELLENT: 5,
            SignalQuality.GOOD: 4,
            SignalQuality.MODERATE: 3,
            SignalQuality.POOR: 2,
            SignalQuality.AVOID: 1
        }
        
        pred_value = quality_values.get(prediction.signal_quality, 3)
        min_value = quality_values.get(min_quality, 3)
        
        if pred_value >= min_value:
            return True, f"quality_{prediction.signal_quality.value}"
        
        if prediction.recommendation == "skip":
            return False, "model_skip"
        
        if prediction.confidence < self.min_prediction_confidence:
            return True, "low_confidence_allow"  # Modelo incerto, deixar passar
        
        return False, f"below_min_quality_{min_quality.value}"
    
    def adjust_confidence(
        self,
        prediction: PredictionResult,
        base_confidence: float
    ) -> float:
        """
        Ajusta confiança do sinal baseado na previsão ML
        
        Args:
            prediction: Resultado da previsão
            base_confidence: Confiança original da estratégia
            
        Returns:
            Confiança ajustada
        """
        # Peso do modelo na decisão
        model_weight = min(prediction.confidence, 0.5)  # Max 50% de influência
        
        # Ajuste baseado na probabilidade
        prob_adjustment = (prediction.win_probability - 0.5) * model_weight
        
        # Aplicar ajuste
        adjusted = base_confidence + prob_adjustment
        
        # Clipar entre 0 e 1
        return float(np.clip(adjusted, 0.0, 1.0))
    
    def adjust_lot_size(
        self,
        prediction: PredictionResult,
        base_lot: float
    ) -> float:
        """
        Ajusta tamanho de lote baseado na previsão
        
        Args:
            prediction: Resultado da previsão
            base_lot: Lote base calculado
            
        Returns:
            Lote ajustado
        """
        # Multiplicadores por qualidade
        lot_multipliers = {
            SignalQuality.EXCELLENT: 1.2,    # +20%
            SignalQuality.GOOD: 1.0,         # Normal
            SignalQuality.MODERATE: 0.8,     # -20%
            SignalQuality.POOR: 0.5,         # -50%
            SignalQuality.AVOID: 0.0         # Não executar
        }
        
        multiplier = lot_multipliers.get(prediction.signal_quality, 1.0)
        
        # Ajustar pela confiança do modelo
        if prediction.confidence < 0.3:
            multiplier = 1.0  # Modelo incerto, usar tamanho normal
        
        return round(base_lot * multiplier, 2)
    
    def get_model_stats(self, model_key: str = None) -> Dict[str, Any]:
        """
        Retorna estatísticas dos modelos
        
        Args:
            model_key: Chave específica ou None para todos
            
        Returns:
            Dicionário com estatísticas
        """
        if model_key and model_key in self._models:
            metrics = self._training_metrics.get(model_key)
            return {
                model_key: {
                    'trained': True,
                    'metrics': metrics.to_dict() if metrics else None,
                    'last_training': self._last_training.get(model_key, 'never').isoformat() 
                        if isinstance(self._last_training.get(model_key), datetime) else 'never',
                    'training_samples': len(self._training_data.get(model_key, []))
                }
            }
        
        stats = {}
        for key in self._models.keys():
            metrics = self._training_metrics.get(key)
            stats[key] = {
                'trained': True,
                'metrics': metrics.to_dict() if metrics else None,
                'last_training': self._last_training.get(key, 'never').isoformat()
                    if isinstance(self._last_training.get(key), datetime) else 'never',
                'training_samples': len(self._training_data.get(key, []))
            }
        
        return stats
    
    async def get_summary(self) -> str:
        """Retorna resumo dos modelos"""
        lines = [
            "🤖 === XGBOOST SIGNAL PREDICTOR ===",
            f"\n📦 Modelos treinados: {len(self._models)}",
            f"📊 Feature names: {len(self._feature_names)}"
        ]
        
        for key, model in self._models.items():
            metrics = self._training_metrics.get(key)
            samples = len(self._training_data.get(key, []))
            
            if metrics:
                lines.append(f"\n📈 {key}:")
                lines.append(f"   Accuracy: {metrics.accuracy:.2%}")
                lines.append(f"   ROC AUC: {metrics.roc_auc:.2%}")
                lines.append(f"   Amostras: {samples}")
        
        if not self._models:
            lines.append("\n⚠️ Nenhum modelo treinado ainda")
            lines.append(f"   Mínimo de {self.min_training_samples} trades necessários")
        
        return "\n".join(lines)


# =======================
# EXEMPLO DE USO
# =======================

async def example_usage():
    """Exemplo de uso do XGBoostSignalPredictor"""
    
    # Configuração
    config = {
        'min_training_samples': 50,  # Reduzido para demo
        'retrain_interval_days': 7,
        'max_depth': 6,
        'learning_rate': 0.1,
        'n_estimators': 100
    }
    
    # Criar preditor
    predictor = XGBoostSignalPredictor(config)
    
    # Feature names de exemplo
    feature_names = [
        'returns_1bar', 'returns_5bar', 'rsi_14', 'macd_histogram',
        'bb_position', 'volume_ratio', 'atr_14', 'trend_strength',
        'session_quality', 'momentum_10'
    ]
    
    # Simular dados de treinamento
    print("📊 Gerando dados de treinamento simulados...")
    np.random.seed(42)
    
    for i in range(100):
        features = np.random.randn(len(feature_names))
        
        # Simular target correlacionado com algumas features
        prob = 1 / (1 + np.exp(-(features[2] * 0.5 + features[3] * 0.3 + features[7] * 0.4)))
        was_profitable = np.random.random() < prob
        
        await predictor.add_training_sample(
            features=features,
            feature_names=feature_names,
            symbol='XAUUSD',
            strategy='trend_following',
            was_profitable=was_profitable,
            profit_pips=np.random.randn() * 20
        )
    
    # Treinar modelo
    print("\n🔄 Treinando modelo...")
    metrics = await predictor.train_model('XAUUSD_trend_following', force=True)
    
    if metrics:
        print(f"\n✅ Modelo treinado com sucesso!")
        print(f"   Accuracy: {metrics.accuracy:.2%}")
        print(f"   ROC AUC: {metrics.roc_auc:.2%}")
    
    # Fazer previsão
    test_features = np.random.randn(len(feature_names))
    prediction = await predictor.predict(
        features=test_features,
        feature_names=feature_names,
        symbol='XAUUSD',
        strategy='trend_following'
    )
    
    print(f"\n🎯 Previsão:")
    print(f"   Qualidade: {prediction.signal_quality.value}")
    print(f"   Probabilidade: {prediction.win_probability:.2%}")
    print(f"   Confiança: {prediction.confidence:.2%}")
    print(f"   Recomendação: {prediction.recommendation}")
    
    # Resumo
    summary = await predictor.get_summary()
    print(f"\n{summary}")


if __name__ == "__main__":
    asyncio.run(example_usage())
