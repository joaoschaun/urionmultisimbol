# -*- coding: utf-8 -*-
"""
Transformer Price Predictor
===========================
Modelo Transformer para previsão de séries temporais de preços.

Usa arquitetura Encoder-only baseada em:
- Temporal Fusion Transformer (TFT) simplificado
- Positional Encoding para sequências temporais
- Multi-head Self-Attention para capturar padrões longos

Autor: Urion Trading Bot
Versão: 2.0
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from loguru import logger
import threading
import pickle
from pathlib import Path
import json

# Lazy loading
torch = None
nn = None
_loaded = False
_lock = threading.Lock()


def _load_torch():
    """Carrega PyTorch sob demanda"""
    global torch, nn, _loaded
    
    with _lock:
        if _loaded:
            return torch is not None
        
        _loaded = True
        
        try:
            import torch as th
            import torch.nn as tnn
            torch = th
            nn = tnn
            logger.info("PyTorch carregado para TransformerPredictor")
            return True
        except ImportError:
            logger.warning(
                "PyTorch não disponível. "
                "Instale com: pip install torch"
            )
            return False


class PredictionType(Enum):
    """Tipos de previsão"""
    DIRECTION = "direction"  # UP/DOWN/NEUTRAL
    PRICE = "price"          # Preço exato
    RETURNS = "returns"      # Retornos percentuais


@dataclass
class TransformerConfig:
    """Configuração do modelo Transformer"""
    # Arquitetura
    d_model: int = 64           # Dimensão do modelo
    n_heads: int = 4            # Número de attention heads
    n_encoder_layers: int = 3   # Número de camadas encoder
    d_ff: int = 256             # Dimensão da feedforward
    dropout: float = 0.1        # Dropout rate
    
    # Entrada/Saída
    seq_length: int = 60        # Tamanho da sequência de entrada
    n_features: int = 5         # OHLCV = 5 features
    forecast_horizon: int = 5   # Quantos passos prever
    
    # Treinamento
    batch_size: int = 32
    learning_rate: float = 0.001
    epochs: int = 100
    early_stopping_patience: int = 10


class PositionalEncoding:
    """Positional Encoding para séries temporais"""
    
    def __init__(self, d_model: int, max_len: int = 500):
        self.d_model = d_model
        self.max_len = max_len
        self._encoding = None
    
    def get_encoding(self, seq_len: int):
        """Gera encoding posicional"""
        if not _load_torch():
            return None
        
        if self._encoding is None or seq_len > self._encoding.size(0):
            position = torch.arange(self.max_len).unsqueeze(1)
            div_term = torch.exp(
                torch.arange(0, self.d_model, 2) * 
                (-np.log(10000.0) / self.d_model)
            )
            
            pe = torch.zeros(self.max_len, self.d_model)
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            
            self._encoding = pe
        
        return self._encoding[:seq_len]


class TransformerPricePredictor:
    """
    Modelo Transformer para previsão de preços
    
    Arquitetura:
    1. Input Embedding: Linear para projetar features
    2. Positional Encoding: Informação temporal
    3. Transformer Encoder: Multi-head attention + FFN
    4. Output Head: Linear para previsão
    
    Vantagens sobre LSTM:
    - Captura dependências de longo prazo melhor
    - Paralelizável (mais rápido)
    - Attention mostra quais candles são importantes
    """
    
    def __init__(self, config: TransformerConfig = None):
        """
        Inicializa o predictor
        
        Args:
            config: Configuração do modelo
        """
        self.config = config or TransformerConfig()
        
        # Modelo
        self._model = None
        self._optimizer = None
        self._criterion = None
        self._device = None
        
        # Normalizadores
        self._feature_mean = None
        self._feature_std = None
        
        # Histórico
        self._training_history: List[Dict] = []
        self._is_trained = False
        
        # Cache de predições
        self._prediction_cache: Dict[str, Dict] = {}
        self._cache_timeout = timedelta(minutes=5)
        
        # Diretório de modelos
        self.model_dir = Path("models/transformer")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"TransformerPredictor inicializado | "
            f"d_model={self.config.d_model}, "
            f"heads={self.config.n_heads}, "
            f"layers={self.config.n_encoder_layers}"
        )
    
    def _build_model(self):
        """Constrói modelo PyTorch"""
        if not _load_torch():
            return False
        
        try:
            # Device
            self._device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
            
            # Construir modelo como módulo customizado
            self._model = self._create_transformer_model()
            self._model = self._model.to(self._device)
            
            # Optimizer e Loss
            self._optimizer = torch.optim.Adam(
                self._model.parameters(),
                lr=self.config.learning_rate
            )
            self._criterion = nn.MSELoss()
            
            # Positional Encoding
            self._pos_encoder = PositionalEncoding(
                self.config.d_model,
                self.config.seq_length + 100
            )
            
            logger.info(f"Modelo construído em {self._device}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao construir modelo: {e}")
            return False
    
    def _create_transformer_model(self):
        """Cria o modelo Transformer"""
        
        class TransformerModel(nn.Module):
            def __init__(self, config: TransformerConfig):
                super().__init__()
                
                self.config = config
                
                # Input embedding
                self.input_embedding = nn.Linear(
                    config.n_features, 
                    config.d_model
                )
                
                # Positional encoding (será adicionado externamente)
                self.pos_dropout = nn.Dropout(config.dropout)
                
                # Transformer Encoder
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=config.d_model,
                    nhead=config.n_heads,
                    dim_feedforward=config.d_ff,
                    dropout=config.dropout,
                    batch_first=True
                )
                
                self.transformer_encoder = nn.TransformerEncoder(
                    encoder_layer,
                    num_layers=config.n_encoder_layers
                )
                
                # Output heads
                # 1. Direction (classificação: up, down, neutral)
                self.direction_head = nn.Sequential(
                    nn.Linear(config.d_model, config.d_model // 2),
                    nn.ReLU(),
                    nn.Dropout(config.dropout),
                    nn.Linear(config.d_model // 2, 3)  # 3 classes
                )
                
                # 2. Magnitude (regressão: quanto vai mover)
                self.magnitude_head = nn.Sequential(
                    nn.Linear(config.d_model, config.d_model // 2),
                    nn.ReLU(),
                    nn.Dropout(config.dropout),
                    nn.Linear(config.d_model // 2, config.forecast_horizon)
                )
                
                # 3. Volatility (regressão: volatilidade esperada)
                self.volatility_head = nn.Sequential(
                    nn.Linear(config.d_model, config.d_model // 2),
                    nn.ReLU(),
                    nn.Dropout(config.dropout),
                    nn.Linear(config.d_model // 2, config.forecast_horizon)
                )
            
            def forward(self, x, pos_encoding=None):
                # x shape: (batch, seq_len, n_features)
                
                # Embedding
                x = self.input_embedding(x)  # (batch, seq_len, d_model)
                
                # Add positional encoding
                if pos_encoding is not None:
                    x = x + pos_encoding.unsqueeze(0)
                
                x = self.pos_dropout(x)
                
                # Transformer encoding
                encoded = self.transformer_encoder(x)  # (batch, seq_len, d_model)
                
                # Usar último token para previsão
                last_token = encoded[:, -1, :]  # (batch, d_model)
                
                # Outputs
                direction_logits = self.direction_head(last_token)
                magnitude = self.magnitude_head(last_token)
                volatility = self.volatility_head(last_token)
                
                return {
                    'direction_logits': direction_logits,
                    'magnitude': magnitude,
                    'volatility': torch.abs(volatility)  # Volatilidade sempre positiva
                }
        
        return TransformerModel(self.config)
    
    def prepare_data(self, 
                     ohlcv_data: np.ndarray,
                     create_labels: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Prepara dados para treinamento/inferência
        
        Args:
            ohlcv_data: Array com [open, high, low, close, volume]
            create_labels: Se True, cria labels para treinamento
            
        Returns:
            (X, y) se create_labels, senão (X, None)
        """
        if len(ohlcv_data) < self.config.seq_length + self.config.forecast_horizon:
            logger.warning("Dados insuficientes para preparação")
            return None, None
        
        # Normalizar
        if self._feature_mean is None:
            self._feature_mean = np.mean(ohlcv_data, axis=0)
            self._feature_std = np.std(ohlcv_data, axis=0)
            self._feature_std[self._feature_std == 0] = 1  # Evitar divisão por zero
        
        normalized = (ohlcv_data - self._feature_mean) / self._feature_std
        
        # Criar sequências
        X = []
        y_direction = []
        y_magnitude = []
        y_volatility = []
        
        for i in range(len(normalized) - self.config.seq_length - self.config.forecast_horizon + 1):
            # Sequência de entrada
            seq = normalized[i:i + self.config.seq_length]
            X.append(seq)
            
            if create_labels:
                # Labels futuras
                future_start = i + self.config.seq_length
                future_end = future_start + self.config.forecast_horizon
                future = ohlcv_data[future_start:future_end, 3]  # Close prices
                current = ohlcv_data[future_start - 1, 3]
                
                # Direção
                total_change = (future[-1] - current) / current * 100
                if total_change > 0.1:
                    direction = 0  # UP
                elif total_change < -0.1:
                    direction = 1  # DOWN
                else:
                    direction = 2  # NEUTRAL
                
                # Magnitude (retornos)
                returns = np.diff(future, prepend=current) / current * 100
                
                # Volatilidade
                volatility = np.std(returns)
                
                y_direction.append(direction)
                y_magnitude.append(returns)
                y_volatility.append([volatility] * self.config.forecast_horizon)
        
        X = np.array(X)
        
        if create_labels:
            y = {
                'direction': np.array(y_direction),
                'magnitude': np.array(y_magnitude),
                'volatility': np.array(y_volatility)
            }
            return X, y
        
        return X, None
    
    def train(self, 
              ohlcv_data: np.ndarray,
              validation_split: float = 0.2) -> Dict:
        """
        Treina o modelo
        
        Args:
            ohlcv_data: Dados OHLCV
            validation_split: Proporção para validação
            
        Returns:
            Histórico de treinamento
        """
        if not _load_torch():
            return {'error': 'PyTorch não disponível'}
        
        if self._model is None:
            if not self._build_model():
                return {'error': 'Falha ao construir modelo'}
        
        logger.info("Iniciando treinamento do Transformer...")
        
        # Preparar dados
        X, y = self.prepare_data(ohlcv_data, create_labels=True)
        
        if X is None:
            return {'error': 'Dados insuficientes'}
        
        # Split train/val
        split_idx = int(len(X) * (1 - validation_split))
        
        X_train = torch.FloatTensor(X[:split_idx]).to(self._device)
        X_val = torch.FloatTensor(X[split_idx:]).to(self._device)
        
        y_train_dir = torch.LongTensor(y['direction'][:split_idx]).to(self._device)
        y_train_mag = torch.FloatTensor(y['magnitude'][:split_idx]).to(self._device)
        
        y_val_dir = torch.LongTensor(y['direction'][split_idx:]).to(self._device)
        y_val_mag = torch.FloatTensor(y['magnitude'][split_idx:]).to(self._device)
        
        # Positional encoding
        pos_enc = self._pos_encoder.get_encoding(self.config.seq_length)
        pos_enc = pos_enc.to(self._device)
        
        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        history = {'train_loss': [], 'val_loss': [], 'val_accuracy': []}
        
        criterion_ce = nn.CrossEntropyLoss()
        criterion_mse = nn.MSELoss()
        
        for epoch in range(self.config.epochs):
            self._model.train()
            
            # Mini-batches
            n_batches = len(X_train) // self.config.batch_size
            epoch_loss = 0
            
            for i in range(n_batches):
                start = i * self.config.batch_size
                end = start + self.config.batch_size
                
                batch_x = X_train[start:end]
                batch_y_dir = y_train_dir[start:end]
                batch_y_mag = y_train_mag[start:end]
                
                self._optimizer.zero_grad()
                
                outputs = self._model(batch_x, pos_enc)
                
                # Loss combinada
                loss_dir = criterion_ce(outputs['direction_logits'], batch_y_dir)
                loss_mag = criterion_mse(outputs['magnitude'], batch_y_mag)
                
                loss = loss_dir + 0.5 * loss_mag
                
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self._model.parameters(), 1.0)
                self._optimizer.step()
                
                epoch_loss += loss.item()
            
            avg_train_loss = epoch_loss / max(n_batches, 1)
            
            # Validação
            self._model.eval()
            with torch.no_grad():
                val_outputs = self._model(X_val, pos_enc)
                
                val_loss_dir = criterion_ce(val_outputs['direction_logits'], y_val_dir)
                val_loss_mag = criterion_mse(val_outputs['magnitude'], y_val_mag)
                val_loss = val_loss_dir + 0.5 * val_loss_mag
                
                # Accuracy da direção
                predictions = torch.argmax(val_outputs['direction_logits'], dim=1)
                accuracy = (predictions == y_val_dir).float().mean().item()
            
            history['train_loss'].append(avg_train_loss)
            history['val_loss'].append(val_loss.item())
            history['val_accuracy'].append(accuracy)
            
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # Salvar melhor modelo
                self._save_checkpoint('best')
            else:
                patience_counter += 1
            
            if patience_counter >= self.config.early_stopping_patience:
                logger.info(f"Early stopping no epoch {epoch + 1}")
                break
            
            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch + 1}/{self.config.epochs} | "
                    f"Train Loss: {avg_train_loss:.4f} | "
                    f"Val Loss: {val_loss.item():.4f} | "
                    f"Val Acc: {accuracy:.2%}"
                )
        
        # Carregar melhor modelo
        self._load_checkpoint('best')
        self._is_trained = True
        self._training_history = history
        
        final_accuracy = history['val_accuracy'][-1]
        logger.success(
            f"Treinamento concluído | "
            f"Epochs: {len(history['train_loss'])} | "
            f"Best Val Acc: {max(history['val_accuracy']):.2%}"
        )
        
        return {
            'epochs': len(history['train_loss']),
            'final_train_loss': history['train_loss'][-1],
            'final_val_loss': history['val_loss'][-1],
            'final_accuracy': final_accuracy,
            'best_accuracy': max(history['val_accuracy'])
        }
    
    def predict(self, ohlcv_data: np.ndarray) -> Dict:
        """
        Faz previsão para os próximos candles
        
        Args:
            ohlcv_data: Últimos N candles (OHLCV)
            
        Returns:
            Dict com previsões
        """
        if not _load_torch():
            return {'error': 'PyTorch não disponível'}
        
        if self._model is None or not self._is_trained:
            logger.warning("Modelo não treinado")
            return {'error': 'Modelo não treinado'}
        
        try:
            # Preparar dados
            if len(ohlcv_data) < self.config.seq_length:
                return {'error': 'Dados insuficientes'}
            
            # Usar últimos seq_length candles
            data = ohlcv_data[-self.config.seq_length:]
            
            # Normalizar
            if self._feature_mean is not None:
                data = (data - self._feature_mean) / self._feature_std
            
            # Converter para tensor
            x = torch.FloatTensor(data).unsqueeze(0).to(self._device)
            
            # Positional encoding
            pos_enc = self._pos_encoder.get_encoding(self.config.seq_length)
            pos_enc = pos_enc.to(self._device)
            
            # Inferência
            self._model.eval()
            with torch.no_grad():
                outputs = self._model(x, pos_enc)
            
            # Processar outputs
            direction_probs = torch.softmax(outputs['direction_logits'], dim=1)
            direction_probs = direction_probs.cpu().numpy()[0]
            
            predicted_direction_idx = np.argmax(direction_probs)
            direction_map = {0: 'UP', 1: 'DOWN', 2: 'NEUTRAL'}
            predicted_direction = direction_map[predicted_direction_idx]
            
            magnitude = outputs['magnitude'].cpu().numpy()[0]
            volatility = outputs['volatility'].cpu().numpy()[0]
            
            # Desnormalizar magnitude (era em % de retorno)
            current_price = ohlcv_data[-1, 3]  # Último close
            
            # Preços previstos
            predicted_prices = []
            price = current_price
            for ret in magnitude:
                price = price * (1 + ret / 100)
                predicted_prices.append(price)
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'current_price': current_price,
                'direction': predicted_direction,
                'direction_confidence': float(direction_probs[predicted_direction_idx]),
                'direction_probabilities': {
                    'UP': float(direction_probs[0]),
                    'DOWN': float(direction_probs[1]),
                    'NEUTRAL': float(direction_probs[2])
                },
                'predicted_returns': magnitude.tolist(),
                'predicted_prices': predicted_prices,
                'expected_volatility': float(np.mean(volatility)),
                'forecast_horizon': self.config.forecast_horizon
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Erro na previsão: {e}")
            return {'error': str(e)}
    
    def get_attention_weights(self, ohlcv_data: np.ndarray) -> Optional[np.ndarray]:
        """
        Retorna attention weights para interpretabilidade
        
        Args:
            ohlcv_data: Dados de entrada
            
        Returns:
            Attention weights ou None
        """
        # Nota: Para extrair attention weights, precisaria
        # modificar o modelo. Por ora retorna None.
        return None
    
    def _save_checkpoint(self, name: str):
        """Salva checkpoint do modelo"""
        if self._model is None:
            return
        
        path = self.model_dir / f"transformer_{name}.pt"
        
        torch.save({
            'model_state_dict': self._model.state_dict(),
            'optimizer_state_dict': self._optimizer.state_dict(),
            'config': self.config.__dict__,
            'feature_mean': self._feature_mean,
            'feature_std': self._feature_std,
            'is_trained': self._is_trained
        }, path)
        
        logger.debug(f"Checkpoint salvo: {path}")
    
    def _load_checkpoint(self, name: str) -> bool:
        """Carrega checkpoint do modelo"""
        path = self.model_dir / f"transformer_{name}.pt"
        
        if not path.exists():
            return False
        
        try:
            checkpoint = torch.load(path, map_location=self._device)
            
            self._model.load_state_dict(checkpoint['model_state_dict'])
            self._optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            self._feature_mean = checkpoint.get('feature_mean')
            self._feature_std = checkpoint.get('feature_std')
            self._is_trained = checkpoint.get('is_trained', True)
            
            logger.debug(f"Checkpoint carregado: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao carregar checkpoint: {e}")
            return False
    
    def save(self, path: str = None):
        """Salva modelo completo"""
        self._save_checkpoint(path or 'latest')
    
    def load(self, path: str = None) -> bool:
        """Carrega modelo salvo"""
        if self._model is None:
            self._build_model()
        return self._load_checkpoint(path or 'latest')
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do modelo"""
        return {
            'is_trained': self._is_trained,
            'device': str(self._device) if self._device else 'N/A',
            'config': self.config.__dict__,
            'training_history_length': len(self._training_history),
            'model_params': sum(
                p.numel() for p in self._model.parameters()
            ) if self._model else 0
        }


# Singleton
_predictor: Optional[TransformerPricePredictor] = None


def get_transformer_predictor(config: TransformerConfig = None) -> TransformerPricePredictor:
    """Retorna instância singleton"""
    global _predictor
    if _predictor is None:
        _predictor = TransformerPricePredictor(config)
    return _predictor


# Exemplo de uso
if __name__ == "__main__":
    logger.add(lambda msg: print(msg), level="INFO")
    
    # Criar predictor
    config = TransformerConfig(
        seq_length=30,
        n_features=5,
        forecast_horizon=5,
        epochs=50
    )
    
    predictor = get_transformer_predictor(config)
    
    # Gerar dados sintéticos para teste
    np.random.seed(42)
    n_samples = 500
    
    # Simular preço com tendência + ruído
    trend = np.linspace(1800, 1900, n_samples)
    noise = np.random.normal(0, 10, n_samples)
    close = trend + noise
    
    # OHLCV
    high = close + np.abs(np.random.normal(5, 2, n_samples))
    low = close - np.abs(np.random.normal(5, 2, n_samples))
    open_p = close + np.random.normal(0, 3, n_samples)
    volume = np.random.uniform(1000, 5000, n_samples)
    
    ohlcv = np.column_stack([open_p, high, low, close, volume])
    
    print("\n=== Treinando Transformer ===\n")
    
    # Treinar
    history = predictor.train(ohlcv, validation_split=0.2)
    print(f"\nResultado: {history}")
    
    # Prever
    print("\n=== Fazendo Previsão ===\n")
    prediction = predictor.predict(ohlcv[-60:])
    
    print(f"Direção: {prediction.get('direction')} "
          f"(confiança: {prediction.get('direction_confidence', 0):.2%})")
    print(f"Preço atual: {prediction.get('current_price', 0):.2f}")
    print(f"Preços previstos: {[f'{p:.2f}' for p in prediction.get('predicted_prices', [])]}")
