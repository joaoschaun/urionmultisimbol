# -*- coding: utf-8 -*-
"""
LSTM PRICE PREDICTOR - URION 2.0 ELITE
=======================================
Rede Neural LSTM para Previsão de Preços e Direção

Funcionalidades:
1. Previsão de direção (up/down) para próximas N barras
2. Previsão de magnitude do movimento
3. Confiança da previsão baseada em histórico
4. Suporte a múltiplos timeframes

Arquitetura:
- Input: Sequência de features (lookback períodos)
- LSTM layers com dropout para evitar overfitting
- Dense layers para classificação/regressão
- Output: Probabilidade de direção + magnitude esperada

Autor: Urion Trading Bot
Versão: 2.0 Elite
"""

import asyncio
import pickle
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import numpy as np
import pandas as pd
from loguru import logger

# TensorFlow/Keras imports
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.models import Sequential, load_model, Model
    from tensorflow.keras.layers import (
        LSTM, Dense, Dropout, BatchNormalization, 
        Input, Bidirectional, Attention, Concatenate
    )
    from tensorflow.keras.callbacks import (
        EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
    )
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.regularizers import l2
    
    # Configurar GPU se disponível
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        logger.info(f"🖥️ GPU disponível: {len(gpus)} device(s)")
    
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("TensorFlow não disponível - instale com: pip install tensorflow")

try:
    from sklearn.preprocessing import MinMaxScaler, StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class PredictionDirection(Enum):
    """Direção prevista"""
    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


@dataclass
class LSTMPrediction:
    """Resultado da previsão LSTM"""
    direction: PredictionDirection
    direction_probability: float      # Probabilidade da direção (0-1)
    expected_move_pips: float         # Movimento esperado em pips
    confidence: float                 # Confiança do modelo (0-1)
    volatility_forecast: float        # Volatilidade esperada
    
    # Previsões por horizonte
    predictions_by_horizon: Dict[int, float] = field(default_factory=dict)
    
    # Metadados
    model_version: str = "1.0"
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            'direction': self.direction.value,
            'direction_probability': self.direction_probability,
            'expected_move_pips': self.expected_move_pips,
            'confidence': self.confidence,
            'volatility_forecast': self.volatility_forecast,
            'predictions_by_horizon': self.predictions_by_horizon
        }


@dataclass
class ModelMetrics:
    """Métricas do modelo"""
    accuracy: float
    precision: float
    recall: float
    mse: float
    mae: float
    directional_accuracy: float
    train_samples: int
    val_samples: int
    epochs_trained: int
    best_epoch: int
    training_time_seconds: float
    
    def to_dict(self) -> dict:
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'mse': self.mse,
            'mae': self.mae,
            'directional_accuracy': self.directional_accuracy,
            'train_samples': self.train_samples,
            'val_samples': self.val_samples,
            'epochs_trained': self.epochs_trained,
            'best_epoch': self.best_epoch,
            'training_time_seconds': self.training_time_seconds
        }


class LSTMPricePredictor:
    """
    Preditor de Preços usando LSTM
    
    Arquitetura do modelo:
    1. Input: (batch, lookback, features)
    2. Bidirectional LSTM layers
    3. Attention mechanism
    4. Dense layers com regularização
    5. Output dual: direção (classification) + magnitude (regression)
    
    Features de entrada:
    - OHLCV normalizados
    - Indicadores técnicos
    - Features de tempo
    - Contexto macro (opcional)
    """
    
    def __init__(self, config: dict = None, data_dir: str = "data/ml/lstm"):
        """
        Args:
            config: Configurações do modelo
            data_dir: Diretório para salvar modelos
        """
        self.config = config or {}
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Parâmetros do modelo
        self.lookback = self.config.get('lookback', 60)  # 60 barras de histórico
        self.forecast_horizon = self.config.get('forecast_horizon', 5)  # Prever 5 barras à frente
        self.n_features = self.config.get('n_features', 20)  # Features de entrada
        
        # Arquitetura
        self.lstm_units = self.config.get('lstm_units', [128, 64])
        self.dense_units = self.config.get('dense_units', [32, 16])
        self.dropout_rate = self.config.get('dropout_rate', 0.3)
        self.learning_rate = self.config.get('learning_rate', 0.001)
        
        # Treinamento
        self.batch_size = self.config.get('batch_size', 32)
        self.epochs = self.config.get('epochs', 100)
        self.min_training_samples = self.config.get('min_training_samples', 1000)
        self.validation_split = self.config.get('validation_split', 0.2)
        
        # Modelos por símbolo
        self._models: Dict[str, keras.Model] = {}
        self._scalers: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, ModelMetrics] = {}
        self._last_training: Dict[str, datetime] = {}
        
        # Dados de treinamento
        self._training_data: Dict[str, List[np.ndarray]] = {}
        
        # Carregar modelos existentes
        self._load_models()
        
        logger.info(f"🧠 LSTMPricePredictor inicializado (lookback={self.lookback}, horizon={self.forecast_horizon})")
        
        if not TENSORFLOW_AVAILABLE:
            logger.error("❌ TensorFlow não disponível - LSTM desabilitado")
    
    def _get_model_path(self, symbol: str) -> Path:
        """Caminho do arquivo do modelo"""
        return self.data_dir / f"lstm_model_{symbol}.keras"
    
    def _get_scaler_path(self, symbol: str) -> Path:
        """Caminho do arquivo do scaler"""
        return self.data_dir / f"lstm_scaler_{symbol}.pkl"
    
    def _load_models(self) -> None:
        """Carrega modelos salvos"""
        if not TENSORFLOW_AVAILABLE:
            return
        
        try:
            for model_file in self.data_dir.glob("lstm_model_*.keras"):
                symbol = model_file.stem.replace("lstm_model_", "")
                
                try:
                    self._models[symbol] = load_model(model_file)
                    
                    # Carregar scaler
                    scaler_path = self._get_scaler_path(symbol)
                    if scaler_path.exists():
                        with open(scaler_path, 'rb') as f:
                            self._scalers[symbol] = pickle.load(f)
                    
                    # Carregar métricas
                    metrics_path = self.data_dir / f"lstm_metrics_{symbol}.json"
                    if metrics_path.exists():
                        with open(metrics_path, 'r') as f:
                            data = json.load(f)
                            self._metrics[symbol] = ModelMetrics(**data)
                    
                    logger.info(f"📦 Modelo LSTM carregado: {symbol}")
                    
                except Exception as e:
                    logger.warning(f"Erro ao carregar modelo {symbol}: {e}")
                    
        except Exception as e:
            logger.error(f"Erro ao carregar modelos: {e}")
    
    def _build_model(self, n_features: int) -> keras.Model:
        """
        Constrói arquitetura do modelo LSTM
        
        Args:
            n_features: Número de features de entrada
            
        Returns:
            Modelo Keras compilado
        """
        # Input layer
        inputs = Input(shape=(self.lookback, n_features))
        
        # Primeira camada LSTM Bidirecional
        x = Bidirectional(LSTM(
            self.lstm_units[0],
            return_sequences=True,
            kernel_regularizer=l2(0.01)
        ))(inputs)
        x = BatchNormalization()(x)
        x = Dropout(self.dropout_rate)(x)
        
        # Segunda camada LSTM
        if len(self.lstm_units) > 1:
            x = Bidirectional(LSTM(
                self.lstm_units[1],
                return_sequences=False,
                kernel_regularizer=l2(0.01)
            ))(x)
            x = BatchNormalization()(x)
            x = Dropout(self.dropout_rate)(x)
        
        # Dense layers
        for units in self.dense_units:
            x = Dense(units, activation='relu', kernel_regularizer=l2(0.01))(x)
            x = Dropout(self.dropout_rate / 2)(x)
        
        # Output dual: direção (3 classes) + magnitude
        # Direção: down, neutral, up
        direction_output = Dense(3, activation='softmax', name='direction')(x)
        
        # Magnitude: valor contínuo
        magnitude_output = Dense(1, activation='linear', name='magnitude')(x)
        
        # Volatilidade: valor positivo
        volatility_output = Dense(1, activation='relu', name='volatility')(x)
        
        # Criar modelo
        model = Model(
            inputs=inputs,
            outputs=[direction_output, magnitude_output, volatility_output]
        )
        
        # Compilar
        model.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss={
                'direction': 'categorical_crossentropy',
                'magnitude': 'mse',
                'volatility': 'mse'
            },
            loss_weights={
                'direction': 1.0,
                'magnitude': 0.5,
                'volatility': 0.3
            },
            metrics={
                'direction': 'accuracy',
                'magnitude': 'mae',
                'volatility': 'mae'
            }
        )
        
        return model
    
    def _prepare_features(
        self,
        df: pd.DataFrame,
        symbol: str = None
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Prepara features para o modelo
        
        Args:
            df: DataFrame com OHLCV
            symbol: Símbolo para usar scaler existente
            
        Returns:
            Tuple (features_array, scaler_dict)
        """
        features = pd.DataFrame()
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        open_ = df['open'].values
        volume = df['volume'].values if 'volume' in df.columns else np.ones(len(close))
        
        # === PRICE FEATURES ===
        # Returns
        features['returns'] = pd.Series(close).pct_change()
        features['returns_2'] = pd.Series(close).pct_change(2)
        features['returns_5'] = pd.Series(close).pct_change(5)
        features['returns_10'] = pd.Series(close).pct_change(10)
        
        # Normalized OHLC
        features['close_norm'] = (close - close.mean()) / (close.std() + 1e-8)
        features['high_low_range'] = (high - low) / (close + 1e-8)
        features['close_position'] = (close - low) / (high - low + 1e-8)
        
        # === TECHNICAL INDICATORS ===
        # RSI
        delta = pd.Series(close).diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / (avg_loss + 1e-8)
        features['rsi'] = 100 - (100 / (1 + rs))
        features['rsi'] = features['rsi'] / 100  # Normalizar 0-1
        
        # MACD
        ema_12 = pd.Series(close).ewm(span=12).mean()
        ema_26 = pd.Series(close).ewm(span=26).mean()
        features['macd'] = (ema_12 - ema_26) / (close + 1e-8)
        features['macd_signal'] = features['macd'].ewm(span=9).mean()
        features['macd_hist'] = features['macd'] - features['macd_signal']
        
        # Bollinger Bands position
        sma_20 = pd.Series(close).rolling(20).mean()
        std_20 = pd.Series(close).rolling(20).std()
        features['bb_position'] = (close - sma_20) / (2 * std_20 + 1e-8)
        features['bb_width'] = (4 * std_20) / (sma_20 + 1e-8)
        
        # ATR
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - np.roll(close, 1)),
                np.abs(low - np.roll(close, 1))
            )
        )
        features['atr'] = pd.Series(tr).rolling(14).mean() / (close + 1e-8)
        
        # Volume
        features['volume_norm'] = volume / (pd.Series(volume).rolling(20).mean() + 1e-8)
        
        # === TIME FEATURES ===
        if isinstance(df.index, pd.DatetimeIndex):
            features['hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
            features['hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
            features['day_of_week'] = df.index.dayofweek / 4
        else:
            features['hour_sin'] = 0
            features['hour_cos'] = 1
            features['day_of_week'] = 0.5
        
        # === MOMENTUM ===
        features['momentum'] = pd.Series(close).pct_change(10)
        features['roc'] = pd.Series(close).pct_change(12)
        
        # Preencher NaN
        features = features.fillna(method='bfill').fillna(0)
        
        # Converter para array
        feature_array = features.values
        
        # Normalizar
        if symbol and symbol in self._scalers:
            scaler = self._scalers[symbol]['feature_scaler']
            feature_array = scaler.transform(feature_array)
            return feature_array, None
        else:
            scaler = MinMaxScaler(feature_range=(-1, 1))
            feature_array = scaler.fit_transform(feature_array)
            return feature_array, {'feature_scaler': scaler}
    
    def _create_sequences(
        self,
        features: np.ndarray,
        targets: np.ndarray = None
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Cria sequências para LSTM
        
        Args:
            features: Array de features (n_samples, n_features)
            targets: Array de targets (opcional)
            
        Returns:
            Tuple (X_sequences, y_sequences)
        """
        X = []
        y = [] if targets is not None else None
        
        for i in range(len(features) - self.lookback - self.forecast_horizon + 1):
            X.append(features[i:i + self.lookback])
            
            if targets is not None:
                # Target: retorno futuro
                y.append(targets[i + self.lookback:i + self.lookback + self.forecast_horizon])
        
        X = np.array(X)
        
        if y is not None:
            y = np.array(y)
            return X, y
        
        return X, None
    
    def _prepare_targets(
        self,
        df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepara targets para treinamento
        
        Args:
            df: DataFrame com OHLCV
            
        Returns:
            Tuple (direction_labels, magnitude, volatility)
        """
        close = df['close'].values
        
        # Retorno futuro
        future_returns = np.zeros((len(close), self.forecast_horizon))
        for h in range(self.forecast_horizon):
            future_returns[:, h] = np.roll(close, -(h + 1)) / close - 1
        
        # Média de retorno futuro
        avg_future_return = future_returns.mean(axis=1)
        
        # Direção (3 classes)
        # 0 = down (< -0.1%), 1 = neutral (-0.1% a 0.1%), 2 = up (> 0.1%)
        threshold = 0.001  # 0.1%
        direction = np.ones(len(close), dtype=int)  # Default neutral
        direction[avg_future_return < -threshold] = 0  # Down
        direction[avg_future_return > threshold] = 2  # Up
        
        # One-hot encoding
        direction_onehot = np.zeros((len(close), 3))
        for i, d in enumerate(direction):
            direction_onehot[i, d] = 1
        
        # Magnitude (retorno absoluto médio)
        magnitude = np.abs(avg_future_return) * 10000  # Em pips (para XAUUSD aproximado)
        
        # Volatilidade (std dos retornos futuros)
        volatility = future_returns.std(axis=1) * 10000
        
        return direction_onehot, magnitude, volatility
    
    async def train(
        self,
        symbol: str,
        df: pd.DataFrame,
        force: bool = False
    ) -> Optional[ModelMetrics]:
        """
        Treina modelo LSTM para um símbolo
        
        Args:
            symbol: Símbolo a treinar
            df: DataFrame com dados históricos
            force: Forçar treinamento
            
        Returns:
            ModelMetrics ou None se falhar
        """
        if not TENSORFLOW_AVAILABLE:
            logger.error("TensorFlow não disponível")
            return None
        
        if len(df) < self.min_training_samples + self.lookback + self.forecast_horizon:
            logger.warning(f"Dados insuficientes para treinar {symbol}")
            return None
        
        start_time = datetime.now()
        
        try:
            logger.info(f"🔄 Treinando LSTM para {symbol}...")
            
            # Preparar features
            features, scaler_dict = self._prepare_features(df)
            
            # Preparar targets
            direction_labels, magnitude, volatility = self._prepare_targets(df)
            
            # Criar sequências
            X, _ = self._create_sequences(features)
            
            # Ajustar targets para tamanho correto
            n_samples = len(X)
            y_direction = direction_labels[self.lookback:self.lookback + n_samples]
            y_magnitude = magnitude[self.lookback:self.lookback + n_samples]
            y_volatility = volatility[self.lookback:self.lookback + n_samples]
            
            # Split treino/validação
            indices = np.arange(n_samples)
            train_idx, val_idx = train_test_split(
                indices, 
                test_size=self.validation_split,
                shuffle=False  # Manter ordem temporal
            )
            
            X_train, X_val = X[train_idx], X[val_idx]
            y_dir_train, y_dir_val = y_direction[train_idx], y_direction[val_idx]
            y_mag_train, y_mag_val = y_magnitude[train_idx], y_magnitude[val_idx]
            y_vol_train, y_vol_val = y_volatility[train_idx], y_volatility[val_idx]
            
            # Construir modelo
            n_features = X.shape[2]
            model = self._build_model(n_features)
            
            # Callbacks
            callbacks = [
                EarlyStopping(
                    monitor='val_loss',
                    patience=15,
                    restore_best_weights=True
                ),
                ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=5,
                    min_lr=1e-6
                ),
                ModelCheckpoint(
                    str(self._get_model_path(symbol)),
                    monitor='val_loss',
                    save_best_only=True
                )
            ]
            
            # Treinar
            history = model.fit(
                X_train,
                {
                    'direction': y_dir_train,
                    'magnitude': y_mag_train,
                    'volatility': y_vol_train
                },
                validation_data=(
                    X_val,
                    {
                        'direction': y_dir_val,
                        'magnitude': y_mag_val,
                        'volatility': y_vol_val
                    }
                ),
                epochs=self.epochs,
                batch_size=self.batch_size,
                callbacks=callbacks,
                verbose=0
            )
            
            # Avaliar
            val_predictions = model.predict(X_val, verbose=0)
            
            # Direção accuracy
            pred_direction = np.argmax(val_predictions[0], axis=1)
            true_direction = np.argmax(y_dir_val, axis=1)
            directional_accuracy = np.mean(pred_direction == true_direction)
            
            # Métricas
            training_time = (datetime.now() - start_time).total_seconds()
            
            metrics = ModelMetrics(
                accuracy=directional_accuracy,
                precision=0.0,  # Calcular se necessário
                recall=0.0,
                mse=float(np.mean((val_predictions[1].flatten() - y_mag_val) ** 2)),
                mae=float(np.mean(np.abs(val_predictions[1].flatten() - y_mag_val))),
                directional_accuracy=directional_accuracy,
                train_samples=len(X_train),
                val_samples=len(X_val),
                epochs_trained=len(history.history['loss']),
                best_epoch=np.argmin(history.history['val_loss']) + 1,
                training_time_seconds=training_time
            )
            
            # Salvar
            self._models[symbol] = model
            self._scalers[symbol] = scaler_dict
            self._metrics[symbol] = metrics
            self._last_training[symbol] = datetime.now()
            
            # Salvar scaler
            with open(self._get_scaler_path(symbol), 'wb') as f:
                pickle.dump(scaler_dict, f)
            
            # Salvar métricas
            metrics_path = self.data_dir / f"lstm_metrics_{symbol}.json"
            with open(metrics_path, 'w') as f:
                json.dump(metrics.to_dict(), f, indent=2)
            
            logger.success(f"""
✅ LSTM treinado para {symbol}:
   Directional Accuracy: {metrics.directional_accuracy:.2%}
   MAE (magnitude): {metrics.mae:.2f} pips
   Epochs: {metrics.epochs_trained} (best: {metrics.best_epoch})
   Training Time: {metrics.training_time_seconds:.1f}s
            """)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Erro ao treinar LSTM {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def predict(
        self,
        symbol: str,
        df: pd.DataFrame
    ) -> LSTMPrediction:
        """
        Faz previsão para um símbolo
        
        Args:
            symbol: Símbolo
            df: DataFrame com dados recentes (mínimo lookback barras)
            
        Returns:
            LSTMPrediction
        """
        start_time = datetime.now()
        
        if not TENSORFLOW_AVAILABLE or symbol not in self._models:
            return self._default_prediction()
        
        try:
            # Verificar dados suficientes
            if len(df) < self.lookback:
                logger.warning(f"Dados insuficientes para previsão ({len(df)} < {self.lookback})")
                return self._default_prediction()
            
            # Preparar features
            features, _ = self._prepare_features(df, symbol)
            
            # Criar sequência
            X = features[-self.lookback:].reshape(1, self.lookback, -1)
            
            # Prever
            predictions = self._models[symbol].predict(X, verbose=0)
            
            # Extrair resultados
            direction_probs = predictions[0][0]  # [down, neutral, up]
            magnitude = float(predictions[1][0][0])
            volatility = float(predictions[2][0][0])
            
            # Determinar direção
            direction_idx = np.argmax(direction_probs)
            direction_prob = float(direction_probs[direction_idx])
            
            # Mapear para enum
            if direction_idx == 0:  # Down
                if direction_prob > 0.7:
                    direction = PredictionDirection.STRONG_DOWN
                else:
                    direction = PredictionDirection.DOWN
                expected_move = -magnitude
            elif direction_idx == 2:  # Up
                if direction_prob > 0.7:
                    direction = PredictionDirection.STRONG_UP
                else:
                    direction = PredictionDirection.UP
                expected_move = magnitude
            else:  # Neutral
                direction = PredictionDirection.NEUTRAL
                expected_move = 0
            
            # Calcular confiança
            # Baseado na diferença entre top 2 probabilidades
            sorted_probs = np.sort(direction_probs)[::-1]
            confidence = float(sorted_probs[0] - sorted_probs[1])
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return LSTMPrediction(
                direction=direction,
                direction_probability=direction_prob,
                expected_move_pips=expected_move,
                confidence=confidence,
                volatility_forecast=volatility,
                predictions_by_horizon={self.forecast_horizon: expected_move},
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Erro na previsão LSTM: {e}")
            return self._default_prediction()
    
    def _default_prediction(self) -> LSTMPrediction:
        """Retorna previsão padrão"""
        return LSTMPrediction(
            direction=PredictionDirection.NEUTRAL,
            direction_probability=0.33,
            expected_move_pips=0.0,
            confidence=0.0,
            volatility_forecast=0.0
        )
    
    def get_trade_signal(
        self,
        prediction: LSTMPrediction,
        min_confidence: float = 0.3,
        min_move_pips: float = 5.0
    ) -> Tuple[Optional[str], float]:
        """
        Converte previsão em sinal de trade
        
        Args:
            prediction: Resultado da previsão
            min_confidence: Confiança mínima
            min_move_pips: Movimento mínimo esperado
            
        Returns:
            Tuple (direction ou None, strength)
        """
        if prediction.confidence < min_confidence:
            return None, 0.0
        
        if abs(prediction.expected_move_pips) < min_move_pips:
            return None, 0.0
        
        if prediction.direction in [PredictionDirection.STRONG_UP, PredictionDirection.UP]:
            strength = prediction.direction_probability * prediction.confidence
            return "buy", strength
        elif prediction.direction in [PredictionDirection.STRONG_DOWN, PredictionDirection.DOWN]:
            strength = prediction.direction_probability * prediction.confidence
            return "sell", strength
        
        return None, 0.0
    
    def get_model_stats(self, symbol: str = None) -> Dict[str, Any]:
        """Retorna estatísticas dos modelos"""
        if symbol and symbol in self._models:
            metrics = self._metrics.get(symbol)
            return {
                symbol: {
                    'trained': True,
                    'metrics': metrics.to_dict() if metrics else None,
                    'last_training': self._last_training.get(symbol, 'never')
                }
            }
        
        stats = {}
        for sym in self._models.keys():
            metrics = self._metrics.get(sym)
            stats[sym] = {
                'trained': True,
                'metrics': metrics.to_dict() if metrics else None,
                'last_training': self._last_training.get(sym, 'never')
            }
        
        return stats
    
    async def get_summary(self) -> str:
        """Retorna resumo dos modelos"""
        lines = [
            "🧠 === LSTM PRICE PREDICTOR ===",
            f"\n📦 Modelos treinados: {len(self._models)}",
            f"📊 Lookback: {self.lookback} barras",
            f"🎯 Horizon: {self.forecast_horizon} barras"
        ]
        
        for symbol, model in self._models.items():
            metrics = self._metrics.get(symbol)
            if metrics:
                lines.append(f"\n📈 {symbol}:")
                lines.append(f"   Directional Accuracy: {metrics.directional_accuracy:.2%}")
                lines.append(f"   MAE: {metrics.mae:.2f} pips")
                lines.append(f"   Training Samples: {metrics.train_samples}")
        
        if not self._models:
            lines.append("\n⚠️ Nenhum modelo treinado")
            lines.append(f"   Mínimo de {self.min_training_samples} amostras necessário")
        
        return "\n".join(lines)


# =======================
# EXEMPLO DE USO
# =======================

async def example_usage():
    """Exemplo de uso do LSTMPricePredictor"""
    
    if not TENSORFLOW_AVAILABLE:
        print("❌ TensorFlow não disponível")
        return
    
    # Configuração
    config = {
        'lookback': 60,
        'forecast_horizon': 5,
        'lstm_units': [64, 32],
        'dense_units': [16],
        'dropout_rate': 0.3,
        'epochs': 10,  # Reduzido para demo
        'min_training_samples': 500
    }
    
    # Criar predictor
    predictor = LSTMPricePredictor(config)
    
    # Criar dados simulados
    np.random.seed(42)
    n = 2000
    
    dates = pd.date_range(end=datetime.now(), periods=n, freq='H')
    close = 2000 + np.cumsum(np.random.randn(n) * 5)
    
    df = pd.DataFrame({
        'open': close + np.random.randn(n) * 3,
        'high': close + np.random.rand(n) * 10,
        'low': close - np.random.rand(n) * 10,
        'close': close,
        'volume': np.random.randint(1000, 10000, n)
    }, index=dates)
    
    # Treinar
    print("🔄 Treinando modelo LSTM...")
    metrics = await predictor.train('XAUUSD', df)
    
    if metrics:
        print(f"\n✅ Modelo treinado!")
        print(f"   Accuracy: {metrics.directional_accuracy:.2%}")
    
    # Prever
    print("\n🎯 Fazendo previsão...")
    prediction = await predictor.predict('XAUUSD', df.tail(100))
    
    print(f"\n📊 Previsão:")
    print(f"   Direção: {prediction.direction.value}")
    print(f"   Probabilidade: {prediction.direction_probability:.2%}")
    print(f"   Movimento esperado: {prediction.expected_move_pips:.1f} pips")
    print(f"   Confiança: {prediction.confidence:.2%}")
    
    # Sinal de trade
    signal, strength = predictor.get_trade_signal(prediction)
    print(f"\n🚦 Sinal: {signal or 'Nenhum'} (força: {strength:.2%})")


if __name__ == "__main__":
    asyncio.run(example_usage())
