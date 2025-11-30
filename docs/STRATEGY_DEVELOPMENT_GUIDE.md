# 📖 Guia de Desenvolvimento de Estratégias

Este guia explica como criar novas estratégias de trading para o Urion Bot.

## 📋 Índice

1. [Estrutura de uma Estratégia](#estrutura-de-uma-estratégia)
2. [Criando uma Nova Estratégia](#criando-uma-nova-estratégia)
3. [Sinais de Trading](#sinais-de-trading)
4. [Backtesting](#backtesting)
5. [Otimização](#otimização)
6. [Integração com o Bot](#integração-com-o-bot)

---

## 🏗️ Estrutura de uma Estratégia

Toda estratégia deve herdar da classe base `BaseStrategy`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pandas as pd

@dataclass
class Signal:
    """Representa um sinal de trading"""
    direction: str  # 'buy', 'sell', 'hold'
    confidence: float  # 0.0 a 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy_name: str
    reason: str
    metadata: dict = None

class BaseStrategy(ABC):
    """Classe base para todas as estratégias"""
    
    def __init__(self, config: dict):
        self.config = config
        self.name = self.__class__.__name__
        
    @abstractmethod
    def analyze(self, data: pd.DataFrame) -> Optional[Signal]:
        """Analisa dados e retorna sinal se houver"""
        pass
    
    @abstractmethod
    def validate_entry(self, data: pd.DataFrame, signal: Signal) -> bool:
        """Valida se a entrada ainda é válida"""
        pass
    
    def get_stop_loss(self, data: pd.DataFrame, direction: str) -> float:
        """Calcula stop loss baseado na estratégia"""
        pass
    
    def get_take_profit(self, data: pd.DataFrame, direction: str) -> float:
        """Calcula take profit baseado na estratégia"""
        pass
```

---

## 🛠️ Criando uma Nova Estratégia

### Exemplo: Estratégia de Cruzamento de Médias

```python
# src/strategies/ema_crossover.py

import pandas as pd
import numpy as np
from typing import Optional
from dataclasses import dataclass

@dataclass
class Signal:
    direction: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy_name: str
    reason: str
    metadata: dict = None

class EMACrossoverStrategy:
    """
    Estratégia de Cruzamento de EMAs
    
    - Compra quando EMA rápida cruza acima da EMA lenta
    - Vende quando EMA rápida cruza abaixo da EMA lenta
    - Confirma com ADX e volume
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.name = "EMA_Crossover"
        
        # Parâmetros
        self.ema_fast = self.config.get('ema_fast', 9)
        self.ema_slow = self.config.get('ema_slow', 21)
        self.ema_trend = self.config.get('ema_trend', 50)
        self.adx_threshold = self.config.get('adx_threshold', 25)
        self.min_confidence = self.config.get('min_confidence', 0.6)
        self.atr_sl_mult = self.config.get('atr_sl_mult', 1.5)
        self.atr_tp_mult = self.config.get('atr_tp_mult', 3.0)
        
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores necessários"""
        df = data.copy()
        
        # EMAs
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        df['ema_trend'] = df['close'].ewm(span=self.ema_trend, adjust=False).mean()
        
        # ATR para SL/TP
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=14).mean()
        
        # ADX
        df['adx'] = self._calculate_adx(df)
        
        # Cruzamentos
        df['cross_up'] = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift() <= df['ema_slow'].shift())
        df['cross_down'] = (df['ema_fast'] < df['ema_slow']) & (df['ema_fast'].shift() >= df['ema_slow'].shift())
        
        return df
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula ADX"""
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        plus_dm[(plus_dm > 0) & (plus_dm <= minus_dm)] = 0
        minus_dm[(minus_dm > 0) & (minus_dm <= plus_dm)] = 0
        
        tr = pd.concat([
            df['high'] - df['low'],
            abs(df['high'] - df['close'].shift()),
            abs(df['low'] - df['close'].shift())
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        
        return adx
    
    def analyze(self, data: pd.DataFrame) -> Optional[Signal]:
        """Analisa dados e retorna sinal se houver"""
        if len(data) < self.ema_trend + 10:
            return None
            
        df = self.calculate_indicators(data)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Verifica força da tendência
        if last['adx'] < self.adx_threshold:
            return None
        
        confidence = 0.0
        direction = 'hold'
        reason = ""
        
        # Sinal de compra
        if last['cross_up']:
            direction = 'buy'
            confidence = 0.5
            reason = f"EMA{self.ema_fast} cruzou acima EMA{self.ema_slow}"
            
            # Bonus: acima da EMA de tendência
            if last['close'] > last['ema_trend']:
                confidence += 0.2
                reason += " | Acima EMA tendência"
            
            # Bonus: ADX forte
            if last['adx'] > 30:
                confidence += 0.15
                reason += f" | ADX forte ({last['adx']:.1f})"
            
            # Bonus: cruzamento com momentum
            if last['ema_fast'] - last['ema_slow'] > prev['ema_fast'] - prev['ema_slow']:
                confidence += 0.1
                reason += " | Momentum crescente"
                
        # Sinal de venda
        elif last['cross_down']:
            direction = 'sell'
            confidence = 0.5
            reason = f"EMA{self.ema_fast} cruzou abaixo EMA{self.ema_slow}"
            
            # Bonus: abaixo da EMA de tendência
            if last['close'] < last['ema_trend']:
                confidence += 0.2
                reason += " | Abaixo EMA tendência"
            
            # Bonus: ADX forte
            if last['adx'] > 30:
                confidence += 0.15
                reason += f" | ADX forte ({last['adx']:.1f})"
                
        else:
            return None
        
        # Retorna apenas se confiança mínima
        if confidence < self.min_confidence:
            return None
        
        # Calcula SL e TP
        atr = last['atr']
        entry_price = last['close']
        
        if direction == 'buy':
            stop_loss = entry_price - (atr * self.atr_sl_mult)
            take_profit = entry_price + (atr * self.atr_tp_mult)
        else:
            stop_loss = entry_price + (atr * self.atr_sl_mult)
            take_profit = entry_price - (atr * self.atr_tp_mult)
        
        return Signal(
            direction=direction,
            confidence=min(confidence, 1.0),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_name=self.name,
            reason=reason,
            metadata={
                'ema_fast': last['ema_fast'],
                'ema_slow': last['ema_slow'],
                'adx': last['adx'],
                'atr': atr
            }
        )
    
    def validate_entry(self, data: pd.DataFrame, signal: Signal) -> bool:
        """Valida se a entrada ainda é válida"""
        df = self.calculate_indicators(data)
        last = df.iloc[-1]
        
        # Para compra, EMA rápida deve estar acima da lenta
        if signal.direction == 'buy':
            return last['ema_fast'] > last['ema_slow']
        
        # Para venda, EMA rápida deve estar abaixo da lenta
        return last['ema_fast'] < last['ema_slow']
```

---

## 📊 Sinais de Trading

### Estrutura do Sinal

```python
@dataclass
class Signal:
    direction: str      # 'buy', 'sell', 'hold'
    confidence: float   # 0.0 a 1.0 (confiança no sinal)
    entry_price: float  # Preço de entrada sugerido
    stop_loss: float    # Stop loss
    take_profit: float  # Take profit
    strategy_name: str  # Nome da estratégia
    reason: str         # Motivo do sinal
    metadata: dict      # Dados adicionais
```

### Níveis de Confiança

| Confiança | Descrição | Ação |
|-----------|-----------|------|
| < 0.5 | Fraco | Ignorar |
| 0.5 - 0.6 | Moderado | Considerar |
| 0.6 - 0.75 | Bom | Executar com cautela |
| 0.75 - 0.9 | Forte | Executar |
| > 0.9 | Excelente | Executar com confiança |

### Calculando Confiança

```python
def calculate_confidence(self, factors: dict) -> float:
    """
    Calcula confiança baseado em múltiplos fatores
    """
    base = 0.3  # Confiança base
    
    # Fatores positivos
    if factors.get('trend_aligned'):
        base += 0.2
    if factors.get('strong_momentum'):
        base += 0.15
    if factors.get('volume_confirmation'):
        base += 0.1
    if factors.get('support_resistance'):
        base += 0.15
    if factors.get('no_divergence'):
        base += 0.1
        
    # Fatores negativos
    if factors.get('near_news'):
        base -= 0.1
    if factors.get('wide_spread'):
        base -= 0.05
    if factors.get('low_volatility'):
        base -= 0.1
        
    return max(0.0, min(1.0, base))
```

---

## 🧪 Backtesting

### Testando sua Estratégia

```python
from src.backtesting.engine import BacktestEngine
from src.backtesting.data_manager import HistoricalDataManager

# Carregar dados
data_manager = HistoricalDataManager()
data = data_manager.load_data(
    symbol='XAUUSD',
    timeframe='H1',
    start_date='2024-01-01',
    end_date='2024-06-30'
)

# Criar estratégia
strategy = EMACrossoverStrategy({
    'ema_fast': 9,
    'ema_slow': 21,
    'adx_threshold': 25
})

# Configurar backtest
engine = BacktestEngine(
    initial_capital=10000,
    commission=0.0001,  # 1 pip
    slippage=0.0001     # 1 pip
)

# Executar
results = engine.run(strategy, data)

# Analisar resultados
print(f"Total trades: {results['total_trades']}")
print(f"Win rate: {results['win_rate']:.2%}")
print(f"Profit factor: {results['profit_factor']:.2f}")
print(f"Max drawdown: {results['max_drawdown']:.2%}")
print(f"Sharpe ratio: {results['sharpe_ratio']:.2f}")
print(f"SQN: {results['sqn']:.2f}")
```

### Métricas Importantes

| Métrica | Bom | Excelente |
|---------|-----|-----------|
| Win Rate | > 50% | > 60% |
| Profit Factor | > 1.5 | > 2.0 |
| Max Drawdown | < 20% | < 10% |
| Sharpe Ratio | > 1.0 | > 2.0 |
| SQN | > 2.0 | > 3.0 |

---

## ⚡ Otimização

### Definindo Espaço de Parâmetros

```python
from src.backtesting.optimizer import StrategyOptimizer

# Definir parâmetros a otimizar
param_space = {
    'ema_fast': (5, 20),      # Range de valores
    'ema_slow': (15, 50),
    'adx_threshold': (20, 35),
    'atr_sl_mult': (1.0, 2.5),
    'atr_tp_mult': (2.0, 4.0)
}

# Criar otimizador
optimizer = StrategyOptimizer(
    strategy_class=EMACrossoverStrategy,
    data=historical_data,
    metric='sharpe_ratio'  # Métrica a maximizar
)

# Otimizar
best_params = optimizer.optimize(
    param_space,
    n_trials=100
)

print(f"Melhores parâmetros: {best_params}")
```

### Walk-Forward Analysis

```python
# Walk-forward para evitar overfitting
wf_results = optimizer.walk_forward(
    data=full_data,
    train_size=0.6,
    test_size=0.2,
    n_splits=5
)

# Verifica se performance é consistente
for i, split in enumerate(wf_results['splits']):
    print(f"Split {i+1}: Train Sharpe={split['train_sharpe']:.2f}, "
          f"Test Sharpe={split['test_sharpe']:.2f}")
```

---

## 🔌 Integração com o Bot

### Registrando a Estratégia

```python
# src/strategies/__init__.py

from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .ema_crossover import EMACrossoverStrategy  # Nova estratégia

AVAILABLE_STRATEGIES = {
    'trend_following': TrendFollowingStrategy,
    'mean_reversion': MeanReversionStrategy,
    'breakout': BreakoutStrategy,
    'ema_crossover': EMACrossoverStrategy,  # Registrar
}
```

### Configurando no config.yaml

```yaml
strategies:
  ema_crossover:
    enabled: true
    timeframes: [H1, H4]
    symbols: [XAUUSD, EURUSD]
    params:
      ema_fast: 9
      ema_slow: 21
      adx_threshold: 25
      atr_sl_mult: 1.5
      atr_tp_mult: 3.0
    risk:
      max_risk_per_trade: 0.02
      max_positions: 2
```

### Testando em Demo

```bash
# Execute em modo demo primeiro
python main.py --mode demo --strategy ema_crossover
```

---

## 📋 Checklist de Qualidade

Antes de colocar sua estratégia em produção:

- [ ] Backtest com pelo menos 1 ano de dados
- [ ] Walk-forward analysis com 5+ splits
- [ ] Profit factor > 1.5 em todos os splits
- [ ] Max drawdown < 15% em todos os splits
- [ ] Win rate consistente (variação < 10%)
- [ ] Sharpe ratio > 1.0
- [ ] Testado em múltiplos símbolos
- [ ] Testado em diferentes condições de mercado
- [ ] Stop loss e take profit definidos
- [ ] Tratamento de erros implementado
- [ ] Logs detalhados para debugging

---

## 🎯 Dicas para Boas Estratégias

### 1. Simplicidade
```python
# ✅ Bom: Lógica clara e simples
if ema_fast > ema_slow and adx > 25:
    return Signal(direction='buy', ...)

# ❌ Ruim: Muito complexo
if (ema_fast > ema_slow and adx > 25 and rsi < 70 and 
    macd > 0 and bb_position < 0.8 and volume > avg_volume * 1.2 and ...):
    return Signal(direction='buy', ...)
```

### 2. Gestão de Risco
```python
# Sempre defina SL/TP
def calculate_sl_tp(self, entry: float, direction: str, atr: float):
    if direction == 'buy':
        sl = entry - (atr * 1.5)  # 1.5x ATR
        tp = entry + (atr * 3.0)  # 3x ATR = R:R 1:2
    else:
        sl = entry + (atr * 1.5)
        tp = entry - (atr * 3.0)
    return sl, tp
```

### 3. Evite Overfitting
```python
# ✅ Bom: Poucos parâmetros robustos
class RobustStrategy:
    def __init__(self, config):
        self.ema_period = config.get('ema_period', 20)  # 1 parâmetro
        
# ❌ Ruim: Muitos parâmetros específicos
class OverfittedStrategy:
    def __init__(self, config):
        self.ema1 = config.get('ema1', 7)
        self.ema2 = config.get('ema2', 13)
        self.ema3 = config.get('ema3', 21)
        self.rsi_buy = config.get('rsi_buy', 32)  # Muito específico
        self.rsi_sell = config.get('rsi_sell', 68)
        # ... 10+ parâmetros
```

### 4. Log Decisões
```python
import logging

logger = logging.getLogger(__name__)

def analyze(self, data):
    logger.debug(f"Analisando {len(data)} barras")
    
    if signal:
        logger.info(f"Sinal {signal.direction} gerado: {signal.reason}")
        logger.debug(f"Confiança: {signal.confidence:.2f}")
        logger.debug(f"SL: {signal.stop_loss}, TP: {signal.take_profit}")
    
    return signal
```

---

## 📚 Recursos Adicionais

- [Backtesting Engine](../src/backtesting/engine.py)
- [Optimizer](../src/backtesting/optimizer.py)
- [Market Regime Detector](../src/analysis/market_regime.py)
- [Advanced Metrics](../src/core/advanced_metrics.py)

---

**Boa sorte criando suas estratégias!** 🚀
