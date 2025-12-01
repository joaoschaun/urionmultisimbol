# -*- coding: utf-8 -*-
"""
ML Training Pipeline
====================
Pipeline automatizado para treinamento de modelos de ML.

Funcionalidades:
- Auto-retraining baseado em performance
- Walk-forward validation
- Feature selection automatica
- Hyperparameter optimization com Optuna
- Model versioning
- A/B testing de modelos
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import threading
import time
import pickle
import json
from pathlib import Path
import hashlib

# Lazy loading globals
optuna = None
xgb = None
TimeSeriesSplit = None
StandardScaler = None
accuracy_score = None
precision_score = None
recall_score = None
f1_score = None

_optuna_loaded = False
_sklearn_loaded = False
_xgboost_loaded = False

def _load_optuna():
    global optuna, _optuna_loaded
    if _optuna_loaded: return optuna is not None
    _optuna_loaded = True
    try:
        import optuna as op
        optuna = op
        return True
    except ImportError:
        return False

def _load_sklearn():
    global TimeSeriesSplit, StandardScaler, accuracy_score, precision_score, recall_score, f1_score, _sklearn_loaded
    if _sklearn_loaded: return TimeSeriesSplit is not None
    _sklearn_loaded = True
    try:
        from sklearn.model_selection import TimeSeriesSplit as TSS
        from sklearn.preprocessing import StandardScaler as SS
        from sklearn.metrics import accuracy_score as acc, precision_score as prec, recall_score as rec, f1_score as f1
        TimeSeriesSplit, StandardScaler, accuracy_score, precision_score, recall_score, f1_score = TSS, SS, acc, prec, rec, f1
        return True
    except ImportError:
        return False

def _load_xgboost():
    global xgb, _xgboost_loaded
    if _xgboost_loaded: return xgb is not None
    _xgboost_loaded = True
    try:
        import xgboost as xg
        xgb = xg
        return True
    except ImportError:
        return False

# Compatibility checkers
def is_optuna_available(): return _load_optuna()
def is_sklearn_available(): return _load_sklearn()
def is_xgboost_available(): return _load_xgboost()


class ModelType(Enum):
    """Tipos de modelo suportados"""
    XGBOOST = "xgboost"
    RANDOM_FOREST = "random_forest"
    LSTM = "lstm"
    ENSEMBLE = "ensemble"


class TrainingStatus(Enum):
    """Status do treinamento"""
    IDLE = "idle"
    COLLECTING_DATA = "collecting_data"
    TRAINING = "training"
    VALIDATING = "validating"
    OPTIMIZING = "optimizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ModelMetrics:
    """Metricas de um modelo"""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    profit_factor: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    validation_date: datetime


@dataclass
class ModelVersion:
    """Versao de um modelo"""
    version: str
    model_type: ModelType
    created_at: datetime
    metrics: ModelMetrics
    hyperparameters: Dict
    feature_importance: Dict
    is_active: bool = False
    file_path: str = ""


@dataclass
class TrainingConfig:
    """Configuracao de treinamento"""
    model_type: ModelType
    features: List[str]
    target: str
    lookback_days: int = 90
    validation_split: float = 0.2
    n_trials: int = 50  # Optuna trials
    early_stopping_rounds: int = 10
    min_trades_for_retraining: int = 100


class MLTrainingPipeline:
    """
    Pipeline de Treinamento de Machine Learning
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.ml_config = config.get('ml_training', {})
        
        # Diretorios
        self.models_dir = Path(self.ml_config.get('models_dir', 'models'))
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuracoes
        self.auto_retrain_interval = self.ml_config.get('auto_retrain_hours', 24)
        self.min_accuracy_threshold = self.ml_config.get('min_accuracy', 0.55)
        self.performance_decay_threshold = self.ml_config.get('decay_threshold', 0.1)
        
        # Estado
        self.status = TrainingStatus.IDLE
        self._current_model: Optional[Any] = None
        self._model_versions: Dict[str, ModelVersion] = {}
        self._scaler: Optional[Any] = None
        
        # Threading
        self._training_thread = None
        self._running = False
        self._lock = threading.Lock()
        
        # Historico de trades para validacao
        self._trade_history: List[Dict] = []
        
        logger.info("MLTrainingPipeline inicializado")
    
    def add_trade_result(self, trade: Dict):
        """Adiciona resultado de trade para aprendizado"""
        with self._lock:
            self._trade_history.append({
                **trade,
                'timestamp': datetime.now()
            })
            
            # Limitar tamanho do historico
            if len(self._trade_history) > 10000:
                self._trade_history = self._trade_history[-10000:]
    
    def prepare_features(self, df: pd.DataFrame, feature_columns: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """Prepara features para treinamento"""
        if not is_sklearn_available():
            logger.error("sklearn nao disponivel")
            return np.array([]), np.array([])
        
        # Remover NaNs
        df_clean = df.dropna(subset=feature_columns)
        
        X = df_clean[feature_columns].values
        
        # Target: 1 se preco subiu, 0 se caiu
        if 'target' in df_clean.columns:
            y = df_clean['target'].values
        else:
            # Criar target baseado em movimento de preco
            y = (df_clean['close'].shift(-1) > df_clean['close']).astype(int).values[:-1]
            X = X[:-1]
        
        return X, y
    
    def train_xgboost(self, X_train: np.ndarray, y_train: np.ndarray,
                     X_val: np.ndarray, y_val: np.ndarray,
                     hyperparams: Dict = None) -> Tuple[Any, ModelMetrics]:
        """Treina modelo XGBoost"""
        if not is_xgboost_available():
            logger.error("XGBoost nao disponivel")
            return None, None
        
        default_params = {
            'max_depth': 6,
            'learning_rate': 0.1,
            'n_estimators': 100,
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'use_label_encoder': False,
            'verbosity': 0
        }
        
        params = {**default_params, **(hyperparams or {})}
        
        model = xgb.XGBClassifier(**params)
        
        # Treinar com early stopping
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Avaliar
        y_pred = model.predict(X_val)
        
        metrics = ModelMetrics(
            accuracy=accuracy_score(y_val, y_pred),
            precision=precision_score(y_val, y_pred, zero_division=0),
            recall=recall_score(y_val, y_pred, zero_division=0),
            f1_score=f1_score(y_val, y_pred, zero_division=0),
            profit_factor=0.0,  # Calcular depois com backtesting
            sharpe_ratio=0.0,
            win_rate=accuracy_score(y_val, y_pred),
            total_trades=len(y_val),
            validation_date=datetime.now()
        )
        
        return model, metrics
    
    def optimize_hyperparameters(self, X: np.ndarray, y: np.ndarray,
                                model_type: ModelType, n_trials: int = 50) -> Dict:
        """Otimiza hyperparametros usando Optuna"""
        if not is_optuna_available():
            logger.warning("Optuna nao disponivel, usando parametros padrao")
            return {}
        
        if not is_sklearn_available():
            return {}
        
        def objective(trial):
            # Split temporal
            tscv = TimeSeriesSplit(n_splits=3)
            scores = []
            
            for train_idx, val_idx in tscv.split(X):
                X_train, X_val = X[train_idx], X[val_idx]
                y_train, y_val = y[train_idx], y[val_idx]
                
                if model_type == ModelType.XGBOOST and is_xgboost_available():
                    params = {
                        'max_depth': trial.suggest_int('max_depth', 3, 10),
                        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                        'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                        'gamma': trial.suggest_float('gamma', 0, 1),
                        'reg_alpha': trial.suggest_float('reg_alpha', 0, 1),
                        'reg_lambda': trial.suggest_float('reg_lambda', 0, 1),
                    }
                    
                    model = xgb.XGBClassifier(**params, objective='binary:logistic', 
                                            use_label_encoder=False, verbosity=0)
                    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
                    y_pred = model.predict(X_val)
                    score = accuracy_score(y_val, y_pred)
                else:
                    score = 0.5
                
                scores.append(score)
            
            return np.mean(scores)
        
        # Executar otimizacao
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
        
        logger.info(f"Melhor accuracy: {study.best_value:.4f}")
        
        return study.best_params
    
    def walk_forward_validation(self, df: pd.DataFrame, feature_columns: List[str],
                               n_splits: int = 5) -> List[ModelMetrics]:
        """
        Walk-forward validation - simula treinamento em tempo real
        """
        if not is_sklearn_available():
            return []
        
        X, y = self.prepare_features(df, feature_columns)
        
        if len(X) == 0:
            return []
        
        # Split temporal
        tscv = TimeSeriesSplit(n_splits=n_splits)
        
        results = []
        
        for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
            logger.info(f"Walk-forward fold {fold + 1}/{n_splits}")
            
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            # Treinar modelo neste fold
            model, metrics = self.train_xgboost(
                X_train, y_train,
                X_test, y_test
            )
            
            if metrics:
                results.append(metrics)
                logger.info(f"Fold {fold + 1}: Accuracy={metrics.accuracy:.4f}")
        
        return results
    
    def train_model(self, df: pd.DataFrame, config: TrainingConfig,
                   optimize: bool = True) -> Optional[ModelVersion]:
        """
        Treina um novo modelo
        """
        self.status = TrainingStatus.TRAINING
        
        try:
            X, y = self.prepare_features(df, config.features)
            
            if len(X) < 100:
                logger.error(f"Dados insuficientes: {len(X)} amostras")
                self.status = TrainingStatus.FAILED
                return None
            
            # Split
            split_idx = int(len(X) * (1 - config.validation_split))
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
            
            # Normalizar
            if SKLEARN_AVAILABLE:
                self._scaler = StandardScaler()
                X_train = self._scaler.fit_transform(X_train)
                X_val = self._scaler.transform(X_val)
            
            # Otimizar hyperparametros
            hyperparams = {}
            if optimize and OPTUNA_AVAILABLE:
                self.status = TrainingStatus.OPTIMIZING
                hyperparams = self.optimize_hyperparameters(
                    X_train, y_train,
                    config.model_type,
                    config.n_trials
                )
            
            # Treinar modelo final
            self.status = TrainingStatus.TRAINING
            
            if config.model_type == ModelType.XGBOOST:
                model, metrics = self.train_xgboost(
                    X_train, y_train,
                    X_val, y_val,
                    hyperparams
                )
            else:
                logger.error(f"Tipo de modelo nao suportado: {config.model_type}")
                self.status = TrainingStatus.FAILED
                return None
            
            if model is None:
                self.status = TrainingStatus.FAILED
                return None
            
            # Validar
            self.status = TrainingStatus.VALIDATING
            
            if metrics.accuracy < self.min_accuracy_threshold:
                logger.warning(f"Accuracy {metrics.accuracy:.4f} abaixo do threshold {self.min_accuracy_threshold}")
            
            # Criar versao
            version_hash = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
            version_id = f"{config.model_type.value}_{version_hash}"
            
            # Feature importance
            feature_importance = {}
            if hasattr(model, 'feature_importances_'):
                for i, importance in enumerate(model.feature_importances_):
                    if i < len(config.features):
                        feature_importance[config.features[i]] = float(importance)
            
            # Salvar modelo
            model_path = self.models_dir / f"{version_id}.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump({
                    'model': model,
                    'scaler': self._scaler,
                    'features': config.features,
                    'hyperparams': hyperparams
                }, f)
            
            version = ModelVersion(
                version=version_id,
                model_type=config.model_type,
                created_at=datetime.now(),
                metrics=metrics,
                hyperparameters=hyperparams,
                feature_importance=feature_importance,
                is_active=True,
                file_path=str(model_path)
            )
            
            # Registrar versao
            with self._lock:
                # Desativar versao anterior
                for v in self._model_versions.values():
                    v.is_active = False
                
                self._model_versions[version_id] = version
                self._current_model = model
            
            self.status = TrainingStatus.COMPLETED
            
            logger.info(f"Modelo treinado: {version_id}, Accuracy: {metrics.accuracy:.4f}")
            
            return version
            
        except Exception as e:
            logger.error(f"Erro no treinamento: {e}")
            self.status = TrainingStatus.FAILED
            return None
    
    def load_model(self, version_id: str) -> bool:
        """Carrega um modelo especifico"""
        try:
            if version_id not in self._model_versions:
                logger.error(f"Versao nao encontrada: {version_id}")
                return False
            
            version = self._model_versions[version_id]
            
            with open(version.file_path, 'rb') as f:
                data = pickle.load(f)
            
            self._current_model = data['model']
            self._scaler = data['scaler']
            
            # Atualizar status ativo
            with self._lock:
                for v in self._model_versions.values():
                    v.is_active = False
                version.is_active = True
            
            logger.info(f"Modelo carregado: {version_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            return False
    
    def predict(self, features: np.ndarray) -> Tuple[int, float]:
        """
        Faz predicao com o modelo atual
        Retorna: (classe, probabilidade)
        """
        if self._current_model is None:
            logger.warning("Nenhum modelo carregado")
            return 0, 0.5
        
        try:
            # Normalizar
            if self._scaler is not None:
                features = self._scaler.transform(features.reshape(1, -1))
            else:
                features = features.reshape(1, -1)
            
            # Predicao
            prediction = self._current_model.predict(features)[0]
            
            # Probabilidade
            if hasattr(self._current_model, 'predict_proba'):
                proba = self._current_model.predict_proba(features)[0]
                confidence = max(proba)
            else:
                confidence = 0.5
            
            return int(prediction), float(confidence)
            
        except Exception as e:
            logger.error(f"Erro na predicao: {e}")
            return 0, 0.5
    
    def should_retrain(self) -> Tuple[bool, str]:
        """Verifica se deve retreinar o modelo"""
        if not self._model_versions:
            return True, "Nenhum modelo treinado"
        
        # Verificar modelo ativo
        active_version = None
        for v in self._model_versions.values():
            if v.is_active:
                active_version = v
                break
        
        if active_version is None:
            return True, "Nenhum modelo ativo"
        
        # Verificar idade do modelo
        hours_since_training = (datetime.now() - active_version.created_at).total_seconds() / 3600
        if hours_since_training > self.auto_retrain_interval:
            return True, f"Modelo com {hours_since_training:.1f} horas"
        
        # Verificar performance recente
        recent_trades = [t for t in self._trade_history 
                        if t['timestamp'] > datetime.now() - timedelta(hours=24)]
        
        if len(recent_trades) >= 20:
            wins = len([t for t in recent_trades if t.get('profit', 0) > 0])
            recent_win_rate = wins / len(recent_trades)
            
            if recent_win_rate < active_version.metrics.accuracy - self.performance_decay_threshold:
                return True, f"Performance degradou: {recent_win_rate:.2%} vs {active_version.metrics.accuracy:.2%}"
        
        return False, "Modelo OK"
    
    def get_model_summary(self) -> Dict:
        """Retorna resumo dos modelos"""
        versions = []
        active_version = None
        
        for v in self._model_versions.values():
            versions.append({
                'version': v.version,
                'type': v.model_type.value,
                'created': v.created_at.isoformat(),
                'accuracy': v.metrics.accuracy,
                'is_active': v.is_active
            })
            if v.is_active:
                active_version = v
        
        return {
            'total_versions': len(versions),
            'active_version': active_version.version if active_version else None,
            'status': self.status.value,
            'versions': versions,
            'trade_history_size': len(self._trade_history)
        }


# Singleton
_pipeline_instance = None

def get_ml_training_pipeline(config: Dict = None) -> MLTrainingPipeline:
    """Retorna instancia singleton"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = MLTrainingPipeline(config or {})
    return _pipeline_instance
