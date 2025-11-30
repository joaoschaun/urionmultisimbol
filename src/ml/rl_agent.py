# -*- coding: utf-8 -*-
"""
REINFORCEMENT LEARNING TRADING AGENT - URION 2.0 ELITE
=======================================================
Agente de Aprendizado por Reforço para Trading

Arquitetura: Deep Q-Network (DQN) com Double DQN e Prioritized Experience Replay

Estados:
- Features de mercado (50+)
- Posição atual (long/short/flat)
- P&L não realizado
- Tempo desde última ação

Ações:
- 0: Hold (manter posição)
- 1: Buy (abrir/aumentar long)
- 2: Sell (abrir/aumentar short)
- 3: Close (fechar posição)

Recompensas:
- P&L realizado
- Sharpe ratio incremental
- Penalidades por overtrading
- Bônus por consistência

Autor: Urion Trading Bot
Versão: 2.0 Elite
"""

import asyncio
import pickle
import json
import random
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import numpy as np
import pandas as pd
from loguru import logger

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.models import Sequential, load_model, clone_model
    from tensorflow.keras.layers import Dense, Dropout, BatchNormalization, Input
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.regularizers import l2
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("TensorFlow não disponível para RL Agent")


class Action(Enum):
    """Ações possíveis do agente"""
    HOLD = 0
    BUY = 1
    SELL = 2
    CLOSE = 3


class Position(Enum):
    """Estado da posição"""
    FLAT = 0
    LONG = 1
    SHORT = 2


@dataclass
class Experience:
    """Experiência para replay buffer"""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    priority: float = 1.0


@dataclass
class AgentDecision:
    """Decisão do agente"""
    action: Action
    confidence: float
    q_values: Dict[str, float]
    expected_reward: float
    reasoning: str
    
    def to_dict(self) -> dict:
        return {
            'action': self.action.value,
            'action_name': self.action.name,
            'confidence': self.confidence,
            'q_values': self.q_values,
            'expected_reward': self.expected_reward,
            'reasoning': self.reasoning
        }


@dataclass
class TrainingStats:
    """Estatísticas de treinamento"""
    episodes: int
    total_reward: float
    avg_reward: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    epsilon: float
    loss: float
    
    def to_dict(self) -> dict:
        return {
            'episodes': self.episodes,
            'total_reward': self.total_reward,
            'avg_reward': self.avg_reward,
            'win_rate': self.win_rate,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'epsilon': self.epsilon,
            'loss': self.loss
        }


class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay Buffer
    
    Prioriza experiências mais importantes (maior TD error)
    """
    
    def __init__(self, capacity: int = 100000, alpha: float = 0.6, beta: float = 0.4):
        """
        Args:
            capacity: Tamanho máximo do buffer
            alpha: Quanto prioridade afeta sampling (0 = uniforme, 1 = totalmente priorizado)
            beta: Correção de bias de importance sampling
        """
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = 0.001
        
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)
    
    def add(self, experience: Experience) -> None:
        """Adiciona experiência ao buffer"""
        max_priority = max(self.priorities) if self.priorities else 1.0
        self.buffer.append(experience)
        self.priorities.append(max_priority)
    
    def sample(self, batch_size: int) -> Tuple[List[Experience], np.ndarray, np.ndarray]:
        """
        Amostra batch de experiências
        
        Returns:
            Tuple (experiences, indices, weights)
        """
        if len(self.buffer) < batch_size:
            batch_size = len(self.buffer)
        
        # Calcular probabilidades
        priorities = np.array(self.priorities)
        probabilities = priorities ** self.alpha
        probabilities /= probabilities.sum()
        
        # Amostrar
        indices = np.random.choice(len(self.buffer), batch_size, replace=False, p=probabilities)
        
        # Importance sampling weights
        total = len(self.buffer)
        weights = (total * probabilities[indices]) ** (-self.beta)
        weights /= weights.max()
        
        # Incrementar beta
        self.beta = min(1.0, self.beta + self.beta_increment)
        
        experiences = [self.buffer[i] for i in indices]
        
        return experiences, indices, weights
    
    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray) -> None:
        """Atualiza prioridades baseado em TD errors"""
        for idx, td_error in zip(indices, td_errors):
            self.priorities[idx] = abs(td_error) + 1e-6
    
    def __len__(self) -> int:
        return len(self.buffer)


class RLTradingAgent:
    """
    Agente de Trading com Deep Reinforcement Learning
    
    Implementa Double DQN com Prioritized Experience Replay
    
    O agente aprende:
    1. Quando entrar em trades (timing)
    2. Qual direção (long/short)
    3. Quando sair (take profit / stop loss)
    4. Gerenciamento de risco implícito
    """
    
    def __init__(self, config: dict = None, data_dir: str = "data/ml/rl"):
        """
        Args:
            config: Configurações do agente
            data_dir: Diretório para salvar modelos
        """
        self.config = config or {}
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Dimensões
        self.state_size = self.config.get('state_size', 60)  # Features de estado
        self.action_size = 4  # HOLD, BUY, SELL, CLOSE
        
        # Hiperparâmetros DQN
        self.gamma = self.config.get('gamma', 0.99)  # Fator de desconto
        self.epsilon = self.config.get('epsilon', 1.0)  # Exploração inicial
        self.epsilon_min = self.config.get('epsilon_min', 0.01)
        self.epsilon_decay = self.config.get('epsilon_decay', 0.995)
        self.learning_rate = self.config.get('learning_rate', 0.0001)
        self.batch_size = self.config.get('batch_size', 64)
        self.target_update_freq = self.config.get('target_update_freq', 100)
        
        # Arquitetura
        self.hidden_layers = self.config.get('hidden_layers', [256, 128, 64])
        self.dropout_rate = self.config.get('dropout_rate', 0.2)
        
        # Replay Buffer
        self.buffer_size = self.config.get('buffer_size', 100000)
        self.replay_buffer = PrioritizedReplayBuffer(capacity=self.buffer_size)
        
        # Modelos
        self._models: Dict[str, keras.Model] = {}
        self._target_models: Dict[str, keras.Model] = {}
        self._training_stats: Dict[str, TrainingStats] = {}
        
        # Estado do agente
        self._position: Dict[str, Position] = {}
        self._entry_price: Dict[str, float] = {}
        self._steps_since_update: Dict[str, int] = {}
        
        # Carregar modelos
        self._load_models()
        
        logger.info(f"🤖 RLTradingAgent inicializado (state_size={self.state_size}, actions={self.action_size})")
        
        if not TENSORFLOW_AVAILABLE:
            logger.error("❌ TensorFlow não disponível - RL Agent desabilitado")
    
    def _get_model_path(self, symbol: str) -> Path:
        """Caminho do modelo"""
        return self.data_dir / f"rl_model_{symbol}.keras"
    
    def _get_target_model_path(self, symbol: str) -> Path:
        """Caminho do target model"""
        return self.data_dir / f"rl_target_{symbol}.keras"
    
    def _load_models(self) -> None:
        """Carrega modelos salvos"""
        if not TENSORFLOW_AVAILABLE:
            return
        
        try:
            for model_file in self.data_dir.glob("rl_model_*.keras"):
                symbol = model_file.stem.replace("rl_model_", "")
                
                try:
                    self._models[symbol] = load_model(model_file)
                    
                    target_path = self._get_target_model_path(symbol)
                    if target_path.exists():
                        self._target_models[symbol] = load_model(target_path)
                    else:
                        self._target_models[symbol] = clone_model(self._models[symbol])
                        self._target_models[symbol].set_weights(self._models[symbol].get_weights())
                    
                    self._position[symbol] = Position.FLAT
                    self._entry_price[symbol] = 0.0
                    self._steps_since_update[symbol] = 0
                    
                    logger.info(f"📦 RL Agent carregado: {symbol}")
                    
                except Exception as e:
                    logger.warning(f"Erro ao carregar RL model {symbol}: {e}")
                    
        except Exception as e:
            logger.error(f"Erro ao carregar modelos RL: {e}")
    
    def _build_model(self) -> keras.Model:
        """
        Constrói rede neural DQN
        
        Returns:
            Modelo Keras
        """
        model = Sequential()
        
        # Input layer
        model.add(Input(shape=(self.state_size,)))
        
        # Hidden layers
        for i, units in enumerate(self.hidden_layers):
            model.add(Dense(
                units,
                activation='relu',
                kernel_regularizer=l2(0.01),
                kernel_initializer='he_uniform'
            ))
            model.add(BatchNormalization())
            if i < len(self.hidden_layers) - 1:
                model.add(Dropout(self.dropout_rate))
        
        # Output layer (Q-values para cada ação)
        model.add(Dense(self.action_size, activation='linear'))
        
        model.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss='huber'  # Mais estável que MSE
        )
        
        return model
    
    def _get_or_create_model(self, symbol: str) -> keras.Model:
        """Obtém ou cria modelo para símbolo"""
        if symbol not in self._models:
            self._models[symbol] = self._build_model()
            self._target_models[symbol] = clone_model(self._models[symbol])
            self._target_models[symbol].set_weights(self._models[symbol].get_weights())
            self._position[symbol] = Position.FLAT
            self._entry_price[symbol] = 0.0
            self._steps_since_update[symbol] = 0
        
        return self._models[symbol]
    
    def prepare_state(
        self,
        features: np.ndarray,
        symbol: str,
        current_price: float,
        account_balance: float = 10000
    ) -> np.ndarray:
        """
        Prepara estado para o agente
        
        Args:
            features: Features de mercado
            symbol: Símbolo
            current_price: Preço atual
            account_balance: Saldo da conta
            
        Returns:
            Estado formatado
        """
        # Features de mercado (primeiras N)
        market_features = features[:self.state_size - 10]  # Reservar 10 para estado
        
        # Features de estado da posição
        position = self._position.get(symbol, Position.FLAT)
        entry_price = self._entry_price.get(symbol, 0.0)
        
        # One-hot da posição
        position_features = np.zeros(3)
        position_features[position.value] = 1.0
        
        # P&L não realizado
        if position == Position.LONG and entry_price > 0:
            unrealized_pnl = (current_price - entry_price) / entry_price
        elif position == Position.SHORT and entry_price > 0:
            unrealized_pnl = (entry_price - current_price) / entry_price
        else:
            unrealized_pnl = 0.0
        
        # Tempo na posição (normalizado)
        time_in_position = min(self._steps_since_update.get(symbol, 0) / 100, 1.0)
        
        # Combinar estado
        state_features = np.array([
            unrealized_pnl,
            time_in_position,
            account_balance / 10000,  # Normalizado
            0.0  # Placeholder
        ])
        
        # Concatenar
        full_state = np.concatenate([
            market_features[:self.state_size - 7],
            position_features,
            state_features
        ])
        
        # Garantir tamanho correto
        if len(full_state) < self.state_size:
            full_state = np.pad(full_state, (0, self.state_size - len(full_state)))
        elif len(full_state) > self.state_size:
            full_state = full_state[:self.state_size]
        
        return full_state
    
    def get_action(
        self,
        state: np.ndarray,
        symbol: str,
        training: bool = False
    ) -> Tuple[Action, np.ndarray]:
        """
        Seleciona ação usando política epsilon-greedy
        
        Args:
            state: Estado atual
            symbol: Símbolo
            training: Se está em modo de treinamento
            
        Returns:
            Tuple (Action, Q-values)
        """
        if not TENSORFLOW_AVAILABLE:
            return Action.HOLD, np.zeros(self.action_size)
        
        model = self._get_or_create_model(symbol)
        
        # Epsilon-greedy
        if training and random.random() < self.epsilon:
            action = Action(random.randint(0, self.action_size - 1))
            q_values = np.zeros(self.action_size)
        else:
            state_input = state.reshape(1, -1)
            q_values = model.predict(state_input, verbose=0)[0]
            action = Action(np.argmax(q_values))
        
        return action, q_values
    
    async def decide(
        self,
        features: np.ndarray,
        symbol: str,
        current_price: float,
        account_balance: float = 10000
    ) -> AgentDecision:
        """
        Toma decisão de trading
        
        Args:
            features: Features de mercado
            symbol: Símbolo
            current_price: Preço atual
            account_balance: Saldo da conta
            
        Returns:
            AgentDecision
        """
        # Preparar estado
        state = self.prepare_state(features, symbol, current_price, account_balance)
        
        # Obter ação
        action, q_values = self.get_action(state, symbol, training=False)
        
        # Calcular confiança
        q_softmax = np.exp(q_values) / np.sum(np.exp(q_values))
        confidence = float(q_softmax[action.value])
        
        # Q-values por ação
        q_dict = {
            'HOLD': float(q_values[0]),
            'BUY': float(q_values[1]),
            'SELL': float(q_values[2]),
            'CLOSE': float(q_values[3])
        }
        
        # Gerar reasoning
        position = self._position.get(symbol, Position.FLAT)
        reasoning = self._generate_reasoning(action, position, q_values)
        
        return AgentDecision(
            action=action,
            confidence=confidence,
            q_values=q_dict,
            expected_reward=float(q_values[action.value]),
            reasoning=reasoning
        )
    
    def _generate_reasoning(
        self,
        action: Action,
        position: Position,
        q_values: np.ndarray
    ) -> str:
        """Gera explicação da decisão"""
        max_q = np.max(q_values)
        min_q = np.min(q_values)
        q_range = max_q - min_q if max_q != min_q else 1
        
        strength = (q_values[action.value] - min_q) / q_range
        
        reasons = []
        
        if action == Action.HOLD:
            reasons.append("Manter posição atual")
            if position == Position.FLAT:
                reasons.append("Mercado sem direção clara")
            else:
                reasons.append("Posição ainda favorável")
                
        elif action == Action.BUY:
            reasons.append("Sinal de entrada LONG")
            if strength > 0.7:
                reasons.append("Alta convicção no movimento de alta")
            else:
                reasons.append("Oportunidade moderada de compra")
                
        elif action == Action.SELL:
            reasons.append("Sinal de entrada SHORT")
            if strength > 0.7:
                reasons.append("Alta convicção no movimento de baixa")
            else:
                reasons.append("Oportunidade moderada de venda")
                
        elif action == Action.CLOSE:
            reasons.append("Fechar posição")
            if position != Position.FLAT:
                reasons.append("Proteger P&L ou limitar perdas")
        
        return " | ".join(reasons)
    
    def calculate_reward(
        self,
        action: Action,
        symbol: str,
        current_price: float,
        next_price: float,
        transaction_cost: float = 0.0001
    ) -> float:
        """
        Calcula recompensa para a ação
        
        Args:
            action: Ação tomada
            symbol: Símbolo
            current_price: Preço atual
            next_price: Próximo preço
            transaction_cost: Custo de transação (spread + comissão)
            
        Returns:
            Recompensa
        """
        position = self._position.get(symbol, Position.FLAT)
        entry_price = self._entry_price.get(symbol, 0.0)
        
        reward = 0.0
        price_change = (next_price - current_price) / current_price
        
        # Atualizar posição baseado na ação
        if action == Action.BUY:
            if position == Position.FLAT:
                # Abrir long
                self._position[symbol] = Position.LONG
                self._entry_price[symbol] = current_price
                reward -= transaction_cost  # Custo de entrada
            elif position == Position.SHORT:
                # Fechar short e abrir long
                pnl = (entry_price - current_price) / entry_price
                reward += pnl - 2 * transaction_cost  # Realiza PnL
                self._position[symbol] = Position.LONG
                self._entry_price[symbol] = current_price
                
        elif action == Action.SELL:
            if position == Position.FLAT:
                # Abrir short
                self._position[symbol] = Position.SHORT
                self._entry_price[symbol] = current_price
                reward -= transaction_cost
            elif position == Position.LONG:
                # Fechar long e abrir short
                pnl = (current_price - entry_price) / entry_price
                reward += pnl - 2 * transaction_cost
                self._position[symbol] = Position.SHORT
                self._entry_price[symbol] = current_price
                
        elif action == Action.CLOSE:
            if position == Position.LONG:
                pnl = (current_price - entry_price) / entry_price
                reward += pnl - transaction_cost
                self._position[symbol] = Position.FLAT
                self._entry_price[symbol] = 0.0
            elif position == Position.SHORT:
                pnl = (entry_price - current_price) / entry_price
                reward += pnl - transaction_cost
                self._position[symbol] = Position.FLAT
                self._entry_price[symbol] = 0.0
                
        elif action == Action.HOLD:
            # Recompensa por P&L não realizado
            if position == Position.LONG:
                reward += price_change * 0.1  # Fração do movimento
            elif position == Position.SHORT:
                reward -= price_change * 0.1
            
            # Pequena penalidade por inação em oportunidades
            if abs(price_change) > 0.001:  # Movimento significativo
                reward -= 0.0001
        
        # Penalidade por overtrading
        if action in [Action.BUY, Action.SELL]:
            steps = self._steps_since_update.get(symbol, 0)
            if steps < 5:  # Trading muito frequente
                reward -= 0.0005
        
        # Atualizar contador
        if action != Action.HOLD:
            self._steps_since_update[symbol] = 0
        else:
            self._steps_since_update[symbol] = self._steps_since_update.get(symbol, 0) + 1
        
        return reward
    
    def store_experience(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ) -> None:
        """Armazena experiência no replay buffer"""
        experience = Experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done
        )
        self.replay_buffer.add(experience)
    
    def train_step(self, symbol: str) -> float:
        """
        Executa um passo de treinamento
        
        Returns:
            Loss do treinamento
        """
        if len(self.replay_buffer) < self.batch_size:
            return 0.0
        
        if not TENSORFLOW_AVAILABLE:
            return 0.0
        
        model = self._get_or_create_model(symbol)
        target_model = self._target_models[symbol]
        
        # Amostrar batch
        experiences, indices, weights = self.replay_buffer.sample(self.batch_size)
        
        # Preparar batch
        states = np.array([e.state for e in experiences])
        actions = np.array([e.action for e in experiences])
        rewards = np.array([e.reward for e in experiences])
        next_states = np.array([e.next_state for e in experiences])
        dones = np.array([e.done for e in experiences])
        
        # Double DQN: usar modelo principal para selecionar ação, target para avaliar
        next_q_values = model.predict(next_states, verbose=0)
        next_actions = np.argmax(next_q_values, axis=1)
        
        target_q_values = target_model.predict(next_states, verbose=0)
        target_q = target_q_values[np.arange(len(next_actions)), next_actions]
        
        # Calcular targets
        targets = rewards + self.gamma * target_q * (1 - dones)
        
        # Q-values atuais
        current_q = model.predict(states, verbose=0)
        
        # TD errors para prioridade
        td_errors = targets - current_q[np.arange(len(actions)), actions]
        
        # Atualizar Q-values
        current_q[np.arange(len(actions)), actions] = targets
        
        # Treinar
        loss = model.train_on_batch(states, current_q, sample_weight=weights)
        
        # Atualizar prioridades
        self.replay_buffer.update_priorities(indices, td_errors)
        
        # Atualizar target model periodicamente
        self._steps_since_update[symbol] = self._steps_since_update.get(symbol, 0) + 1
        if self._steps_since_update[symbol] % self.target_update_freq == 0:
            self._target_models[symbol].set_weights(model.get_weights())
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        return float(loss)
    
    async def train_episode(
        self,
        symbol: str,
        df: pd.DataFrame,
        feature_generator: Any = None
    ) -> Dict[str, float]:
        """
        Treina um episódio completo
        
        Args:
            symbol: Símbolo
            df: DataFrame com dados históricos
            feature_generator: Gerador de features
            
        Returns:
            Dict com métricas do episódio
        """
        if not TENSORFLOW_AVAILABLE:
            return {}
        
        # Reset posição
        self._position[symbol] = Position.FLAT
        self._entry_price[symbol] = 0.0
        
        total_reward = 0.0
        trades = 0
        wins = 0
        losses_list = []
        
        # Iterar sobre os dados
        for i in range(50, len(df) - 1):  # Skip primeiro período para features
            # Dados até este ponto
            current_data = df.iloc[max(0, i-100):i+1]
            
            # Gerar features (simplificado)
            features = self._simple_features(current_data)
            
            current_price = df['close'].iloc[i]
            next_price = df['close'].iloc[i + 1]
            
            # Preparar estado
            state = self.prepare_state(features, symbol, current_price)
            
            # Selecionar ação
            action, _ = self.get_action(state, symbol, training=True)
            
            # Calcular recompensa
            reward = self.calculate_reward(action, symbol, current_price, next_price)
            total_reward += reward
            
            # Próximo estado
            next_data = df.iloc[max(0, i-99):i+2]
            next_features = self._simple_features(next_data)
            next_state = self.prepare_state(next_features, symbol, next_price)
            
            # Armazenar experiência
            done = (i == len(df) - 2)
            self.store_experience(state, action.value, reward, next_state, done)
            
            # Treinar
            if len(self.replay_buffer) >= self.batch_size:
                self.train_step(symbol)
            
            # Estatísticas
            if action in [Action.CLOSE]:
                trades += 1
                if reward > 0:
                    wins += 1
            
            losses_list.append(reward)
        
        # Calcular métricas
        returns = np.array(losses_list)
        sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
        
        return {
            'total_reward': total_reward,
            'trades': trades,
            'win_rate': wins / max(trades, 1),
            'sharpe': sharpe,
            'epsilon': self.epsilon
        }
    
    def _simple_features(self, df: pd.DataFrame) -> np.ndarray:
        """Gera features simples para treinamento"""
        close = df['close'].values
        
        features = []
        
        # Returns
        for period in [1, 2, 5, 10, 20]:
            if len(close) > period:
                ret = (close[-1] - close[-period-1]) / close[-period-1]
            else:
                ret = 0
            features.append(ret)
        
        # Normalized price
        if len(close) > 20:
            features.append((close[-1] - np.mean(close[-20:])) / (np.std(close[-20:]) + 1e-8))
        else:
            features.append(0)
        
        # RSI simplificado
        if len(close) > 14:
            delta = np.diff(close[-15:])
            gain = np.mean(delta[delta > 0]) if len(delta[delta > 0]) > 0 else 0
            loss = -np.mean(delta[delta < 0]) if len(delta[delta < 0]) > 0 else 0
            rs = gain / (loss + 1e-8)
            rsi = 100 - (100 / (1 + rs))
            features.append(rsi / 100)
        else:
            features.append(0.5)
        
        # Volatility
        if len(close) > 20:
            features.append(np.std(np.diff(close[-20:])) / np.mean(close[-20:]))
        else:
            features.append(0)
        
        # Pad para state_size
        while len(features) < self.state_size - 7:
            features.append(0)
        
        return np.array(features[:self.state_size - 7])
    
    def save_model(self, symbol: str) -> None:
        """Salva modelo"""
        if symbol in self._models:
            self._models[symbol].save(self._get_model_path(symbol))
            self._target_models[symbol].save(self._get_target_model_path(symbol))
            logger.info(f"💾 RL Agent salvo: {symbol}")
    
    def get_model_stats(self, symbol: str = None) -> Dict[str, Any]:
        """Retorna estatísticas"""
        if symbol and symbol in self._models:
            return {
                symbol: {
                    'trained': True,
                    'position': self._position.get(symbol, Position.FLAT).name,
                    'epsilon': self.epsilon,
                    'buffer_size': len(self.replay_buffer)
                }
            }
        
        stats = {}
        for sym in self._models.keys():
            stats[sym] = {
                'trained': True,
                'position': self._position.get(sym, Position.FLAT).name,
                'epsilon': self.epsilon,
                'buffer_size': len(self.replay_buffer)
            }
        
        return stats
    
    async def get_summary(self) -> str:
        """Retorna resumo"""
        lines = [
            "🤖 === RL TRADING AGENT ===",
            f"\n📦 Modelos: {len(self._models)}",
            f"🎲 Epsilon: {self.epsilon:.4f}",
            f"💾 Buffer: {len(self.replay_buffer)} experiências"
        ]
        
        for symbol in self._models.keys():
            pos = self._position.get(symbol, Position.FLAT)
            lines.append(f"\n📈 {symbol}:")
            lines.append(f"   Posição: {pos.name}")
        
        return "\n".join(lines)


# =======================
# EXEMPLO DE USO
# =======================

async def example_usage():
    """Exemplo de uso do RLTradingAgent"""
    
    if not TENSORFLOW_AVAILABLE:
        print("❌ TensorFlow não disponível")
        return
    
    # Configuração
    config = {
        'state_size': 60,
        'hidden_layers': [128, 64],
        'learning_rate': 0.001,
        'epsilon': 0.5,
        'batch_size': 32
    }
    
    # Criar agente
    agent = RLTradingAgent(config)
    
    # Dados simulados
    np.random.seed(42)
    n = 1000
    
    dates = pd.date_range(end=datetime.now(), periods=n, freq='H')
    close = 2000 + np.cumsum(np.random.randn(n) * 5)
    
    df = pd.DataFrame({
        'open': close + np.random.randn(n) * 3,
        'high': close + np.random.rand(n) * 10,
        'low': close - np.random.rand(n) * 10,
        'close': close,
        'volume': np.random.randint(1000, 10000, n)
    }, index=dates)
    
    # Treinar episódio
    print("🔄 Treinando episódio...")
    metrics = await agent.train_episode('XAUUSD', df)
    
    print(f"\n📊 Métricas do episódio:")
    for key, value in metrics.items():
        print(f"   {key}: {value:.4f}")
    
    # Decisão
    features = np.random.randn(60)
    decision = await agent.decide(features, 'XAUUSD', 2050, 10000)
    
    print(f"\n🎯 Decisão:")
    print(f"   Ação: {decision.action.name}")
    print(f"   Confiança: {decision.confidence:.2%}")
    print(f"   Reasoning: {decision.reasoning}")
    
    # Resumo
    summary = await agent.get_summary()
    print(f"\n{summary}")


if __name__ == "__main__":
    asyncio.run(example_usage())
