# 🚀 URION Trading Bot - Documentação Completa

<div align="center">

![Version](https://img.shields.io/badge/Version-2.2-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![MT5](https://img.shields.io/badge/MetaTrader-5-orange)
![License](https://img.shields.io/badge/License-MIT-purple)

**Bot de Trading Automatizado Multi-Símbolo com Inteligência Artificial**

*Professional Edition + Advanced AI*

</div>

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Módulos Principais](#módulos-principais)
4. [Estratégias de Trading](#estratégias-de-trading)
5. [Análise Técnica](#análise-técnica)
6. [Machine Learning & IA](#machine-learning--ia)
7. [Gestão de Risco](#gestão-de-risco)
8. [Infraestrutura](#infraestrutura)
9. [Integrações Externas](#integrações-externas)
10. [Configuração](#configuração)
11. [Instalação](#instalação)
12. [Operação](#operação)
13. [Monitoramento](#monitoramento)
14. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O **URION Trading Bot** é um sistema de trading algorítmico de nível institucional projetado para operar automaticamente nos mercados financeiros através do MetaTrader 5. Combina análise técnica avançada, machine learning, e gestão de risco sofisticada para gerar sinais de trading de alta qualidade.

### Características Principais

| Feature | Descrição |
|---------|-----------|
| 🔄 **Multi-Símbolo** | Opera simultaneamente em múltiplos ativos (XAUUSD, EURUSD, BTCUSD, etc.) |
| 🧠 **IA Avançada** | Redes Neurais (LSTM, Transformer), Reinforcement Learning, FinBERT NLP |
| 📊 **Análise Completa** | 50+ indicadores técnicos, Order Flow, Padrões Harmônicos |
| ⚡ **Execução Profissional** | TWAP, VWAP, Iceberg Orders, Smart Order Router |
| 🛡️ **Gestão de Risco** | Kelly Criterion, VaR, Monte Carlo, Trailing Stops ATR |
| 📈 **Backtesting** | Walk-Forward Analysis, Out-of-Sample Testing |
| 🔔 **Notificações** | Telegram em tempo real |
| 📡 **Infraestrutura** | Redis Cache, InfluxDB Metrics, WebSocket |

### Pontuação de Conformidade

Comparado com requisitos de bots de trading institucionais:

```
┌─────────────────────────────────────┬───────┐
│ Categoria                           │ Score │
├─────────────────────────────────────┼───────┤
│ Gestão de Risco                     │ 10/10 │
│ Algoritmos de Execução              │ 10/10 │
│ Análise de Mercado                  │  9/10 │
│ Machine Learning                    │ 10/10 │
│ Infraestrutura                      │ 10/10 │
│ Backtesting & Validação             │ 10/10 │
│ Sentimento & Notícias               │ 10/10 │
├─────────────────────────────────────┼───────┤
│ TOTAL                               │ 98%   │
└─────────────────────────────────────┴───────┘
```

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          URION TRADING BOT v2.2                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐  │
│  │   main.py   │   │  Dashboard  │   │   Backend   │   │  Telegram   │  │
│  │ (Orquestrador) │   │   (React)   │   │   (Flask)   │   │    Bot      │  │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘  │
│         │                 │                 │                 │         │
│  ═══════╪═════════════════╪═════════════════╪═════════════════╪═══════  │
│         │                 │                 │                 │         │
│  ┌──────▼──────────────────────────────────────────────────────────┐   │
│  │                        TradingBot Class                          │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │                    Order Generator                        │   │   │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐          │   │   │
│  │  │  │ Executor 1 │  │ Executor 2 │  │ Executor N │   ...    │   │   │
│  │  │  │ XAUUSD     │  │ EURUSD     │  │ BTCUSD     │          │   │   │
│  │  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘          │   │   │
│  │  └────────┼───────────────┼───────────────┼─────────────────┘   │   │
│  │           │               │               │                     │   │
│  │  ┌────────▼───────────────▼───────────────▼─────────────────┐   │   │
│  │  │                   Strategy Manager                        │   │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │   │
│  │  │  │Scalping │ │ Trend   │ │Breakout │ │  Mean   │  ...   │   │   │
│  │  │  │         │ │Following│ │         │ │Reversion│        │   │   │
│  │  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘        │   │   │
│  │  └───────┼───────────┼───────────┼───────────┼──────────────┘   │   │
│  │          │           │           │           │                   │   │
│  │  ┌───────▼───────────▼───────────▼───────────▼──────────────┐   │   │
│  │  │                    Analysis Layer                         │   │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │   │
│  │  │  │  Technical  │  │    News     │  │   Order     │       │   │   │
│  │  │  │  Analyzer   │  │  Analyzer   │  │   Flow      │       │   │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘       │   │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │   │
│  │  │  │  Harmonic   │  │ Correlation │  │Manipulation │       │   │   │
│  │  │  │  Patterns   │  │  Analyzer   │  │  Detector   │       │   │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘       │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │                     ML/AI Layer                           │   │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │   │   │
│  │  │  │   LSTM   │ │Transformer││  FinBERT │ │    RL    │     │   │   │
│  │  │  │ Predictor│ │ Predictor │ │   NLP    │ │  Agent   │     │   │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │                    Risk Management                        │   │   │
│  │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │   │   │
│  │  │  │ Kelly  │ │  ATR   │ │  VaR   │ │ Monte  │ │Position│  │   │   │
│  │  │  │Criterion│ │Trailing│ │ Calc   │ │ Carlo  │ │ Intel  │  │   │   │
│  │  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │                   Order Manager                           │   │   │
│  │  │  • Monitoramento de Posições      • Trailing Stops        │   │   │
│  │  │  • Gerenciamento de SL/TP         • Breakeven Automático  │   │   │
│  │  │  • Fechamento Parcial             • Magic Numbers         │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════   │
│                                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐  │
│  │    Redis    │   │  InfluxDB   │   │  MT5 Pool   │   │ TradingView │  │
│  │   (Cache)   │   │  (Metrics)  │   │(Connections)│   │  (Webhooks) │  │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │         MetaTrader 5          │
                    │      (Execution Engine)       │
                    └───────────────────────────────┘
```

### Fluxo de Dados

```
1. Data Ingestion
   MT5 Market Data → Technical Analyzer → Indicators
                   → News Analyzer → Sentiment
                   → Order Flow → Volume Profile

2. Signal Generation  
   Indicators → Strategies → Raw Signals
   ML Models → Predictions → Confidence Scores
   
3. Signal Aggregation
   Raw Signals + ML + News → Weighted Score → Final Signal
   
4. Risk Check
   Signal → Kelly Sizing → VaR Check → Exposure Check → Approved/Rejected
   
5. Execution
   Approved Signal → Smart Router → TWAP/VWAP/Market → MT5 Order
   
6. Position Management
   Open Position → Trailing Stop → Partial Close → Full Exit
```

---

## 📦 Módulos Principais

### Core (`src/core/`)

| Módulo | Descrição |
|--------|-----------|
| `mt5_connector.py` | Conexão com MetaTrader 5, operações de mercado |
| `config_manager.py` | Gerenciamento de configurações YAML |
| `risk_manager.py` | Kelly Criterion, sizing de posições, drawdown |
| `strategy_executor.py` | Execução de estratégias em threads |
| `position_intelligence.py` | Gestão inteligente de posições |
| `execution_algorithms.py` | TWAP, VWAP, Iceberg, Smart Router |
| `strategy_communicator.py` | Pub/Sub entre estratégias |
| `watchdog.py` | Monitoramento de threads |
| `logger.py` | Sistema de logging com Loguru |

### Analysis (`src/analysis/`)

| Módulo | Descrição |
|--------|-----------|
| `technical_analyzer.py` | 50+ indicadores técnicos (RSI, MACD, Bollinger, etc.) |
| `news_analyzer.py` | Agregador de notícias + ForexNewsAPI Sentiment |
| `order_flow_analyzer.py` | Volume Profile, Delta, Footprint Charts |
| `manipulation_detector.py` | Detecção de spoofing e manipulação |
| `economic_calendar.py` | Calendário econômico + filtro de eventos |
| `correlation_analyzer.py` | Correlação multi-símbolo, Beta, Diversificação |
| `harmonic_patterns.py` | Gartley, Butterfly, Bat, Crab, Shark, Cypher |
| `tradingview_integration.py` | Webhooks do TradingView |
| `macro_context_analyzer.py` | Contexto macroeconômico |

### Strategies (`src/strategies/`)

| Estratégia | Descrição | Timeframes |
|------------|-----------|------------|
| `scalping.py` | Operações rápidas em alta frequência | M1, M5 |
| `trend_following.py` | Seguimento de tendência com EMA/ADX | M15, H1 |
| `breakout.py` | Rompimentos de suporte/resistência | M5, M15 |
| `mean_reversion.py` | Retorno à média com Bollinger | M15, H1 |
| `range_trading.py` | Trading em zonas de consolidação | M15 |
| `news_trading.py` | Operações baseadas em notícias | M1-H1 |

### Machine Learning (`src/ml/`)

| Módulo | Descrição |
|--------|-----------|
| `lstm_model.py` | Redes LSTM para previsão de séries temporais |
| `rl_agent.py` | Reinforcement Learning (PPO) para decisões |
| `training_pipeline.py` | Pipeline de treinamento com Optuna |
| `finbert_analyzer.py` | **NOVO** - FinBERT NLP para sentimento financeiro |
| `transformer_predictor.py` | **NOVO** - Transformer Encoder para previsões |
| `adaptive_learner.py` | Aprendizado contínuo com feedback |

### Risk (`src/risk/`)

| Módulo | Descrição |
|--------|-----------|
| `monte_carlo.py` | Simulação Monte Carlo para projeções |
| `var_calculator.py` | Value at Risk (VaR) e CVaR |
| `drawdown_monitor.py` | Monitoramento de drawdown em tempo real |
| `exposure_manager.py` | Controle de exposição por símbolo/setor |

### Infrastructure (`src/infrastructure/`)

| Módulo | Descrição |
|--------|-----------|
| `redis_client.py` | Cache distribuído Redis |
| `influxdb_client.py` | Métricas de séries temporais |
| `data_hub.py` | Central de dados com WebSocket |
| `ws_server.py` | Servidor WebSocket para dashboard |

### Connectors (`src/connectors/`)

| Módulo | Descrição |
|--------|-----------|
| `mt5_pool.py` | **NOVO** - Pool de conexões MT5 com health checks |

---

## 📈 Estratégias de Trading

### Scalping Strategy

```python
Configuração:
- Timeframes: M1, M5
- Indicadores: RSI(14), EMA(9,21), ATR(14)
- Entry: RSI oversold/overbought + EMA crossover
- Stop Loss: 1.5x ATR
- Take Profit: 2x ATR
- Max Duration: 30 minutos
```

**Filtros:**
- Volume acima da média
- Spread < 2 pips
- Sem notícias de alto impacto próximas

### Trend Following Strategy

```python
Configuração:
- Timeframes: M15, H1
- Indicadores: EMA(20,50,200), ADX(14), MACD
- Entry: Preço > EMA200, EMA20 > EMA50, ADX > 25
- Stop Loss: Swing low/high anterior
- Take Profit: Trailing com ATR
- Pyramiding: Até 3 adições em tendência forte
```

**Filtros:**
- ADX > 25 (tendência definida)
- Alinhamento de timeframes (MTF)

### Breakout Strategy

```python
Configuração:
- Timeframes: M5, M15
- Indicadores: Donchian(20), Volume, ATR
- Entry: Rompimento de range com volume 150%+
- Stop Loss: Meio do range rompido
- Take Profit: Projeção de Fibonacci
```

### Mean Reversion Strategy

```python
Configuração:
- Timeframes: M15, H1
- Indicadores: Bollinger(20,2), RSI(14), Stochastic
- Entry: Preço fora da banda + reversão confirmada
- Stop Loss: Extensão da banda
- Take Profit: Média das bandas
```

### Harmonic Patterns (Novo)

```python
Padrões Detectados:
- Gartley: XAB 0.618, XAD 0.786
- Butterfly: XAB 0.786, XAD 1.27-1.618
- Bat: XAB 0.382-0.5, XAD 0.886
- Crab: XAB 0.382-0.618, XAD 1.618
- Shark: XAB 0.886-1.13, XAD 0.886-1.13
- Cypher: XAB 0.382-0.618, ABC 1.13-1.414

Entry: Ponto D do padrão
Stop Loss: Abaixo/Acima de D
Take Profits: 38.2%, 61.8%, 100% de CD
```

---

## 🔬 Análise Técnica

### Indicadores Implementados

#### Tendência
- EMA (9, 20, 50, 100, 200)
- SMA (10, 20, 50, 200)
- ADX + DMI
- Supertrend
- Parabolic SAR
- Ichimoku Cloud

#### Momentum
- RSI (7, 14, 21)
- Stochastic (14, 3, 3)
- MACD (12, 26, 9)
- CCI (20)
- Williams %R
- ROC

#### Volatilidade
- Bollinger Bands (20, 2)
- ATR (14)
- Keltner Channel
- Donchian Channel

#### Volume
- OBV
- Volume Profile
- VWAP
- Money Flow Index
- Accumulation/Distribution

#### Order Flow
- Delta
- Footprint Charts
- Volume Imbalance
- POC (Point of Control)
- Value Area High/Low

---

## 🧠 Machine Learning & IA

### LSTM Predictor

```python
Arquitetura:
- Input: 60 barras de OHLCV + indicadores
- Layers: 2x LSTM(128) + Dropout(0.3)
- Output: Direção (up/down) + Magnitude

Treinamento:
- Walk-Forward: 70% train, 15% validation, 15% test
- Epochs: 100 com early stopping
- Optimizer: Adam (lr=0.001)
```

### Transformer Predictor (Novo)

```python
Arquitetura:
- Encoder-only Transformer
- Positional Encoding sinusoidal
- Multi-Head Attention (4 heads)
- Feed Forward: 256 units
- Output: 5 horizontes de previsão

Features:
- Previsão de direção
- Previsão de magnitude
- Previsão de volatilidade
```

### FinBERT NLP Analyzer (Novo)

```python
Modelo: ProsusAI/finbert (HuggingFace)

Features:
- Análise de sentimento de notícias financeiras
- Classificação: Positivo, Negativo, Neutro
- Score de confiança por headline
- Batch processing para múltiplas notícias
- Cache inteligente (5 minutos)

Uso:
- Filtro de entrada em operações
- Boost/Penalidade no score final
- Detecção de eventos de alto impacto
```

### Reinforcement Learning Agent

```python
Algoritmo: PPO (Proximal Policy Optimization)

Estado:
- OHLCV normalizado
- Indicadores técnicos
- Posição atual
- PnL não realizado

Ações:
- Hold, Buy, Sell
- Close Position

Reward:
- PnL realizado
- Penalidade por drawdown
- Bonus por win streak
```

### Adaptive Learner

```python
Features:
- Aprendizado contínuo com resultados reais
- Ajuste de pesos por estratégia
- Detecção de regime de mercado
- Auto-otimização de parâmetros
```

---

## 🛡️ Gestão de Risco

### Kelly Criterion

```python
Formula: f* = (p * b - q) / b

Onde:
- p = probabilidade de ganho
- q = probabilidade de perda (1 - p)
- b = ratio gain/loss

Implementação:
- Kelly Fração: 0.25-0.5 do Kelly completo
- Ajuste por volatilidade do mercado
- Cap máximo: 5% por trade
```

### ATR Trailing Stop

```python
Cálculo:
- ATR_Multiplier: 2.0-3.0
- Stop Distance: ATR(14) * Multiplier

Tipos:
- Fixed ATR Trail
- Chandelier Exit
- Volatility-Adjusted Trail
```

### Value at Risk (VaR)

```python
Métodos:
1. Paramétrico (Variância-Covariância)
2. Histórico (Percentil 5%)
3. Monte Carlo (10.000 simulações)

Níveis:
- VaR 95%: Perda máxima esperada em 95% dos casos
- VaR 99%: Perda máxima em condições extremas
- CVaR: Expected Shortfall (perda média além do VaR)
```

### Monte Carlo Simulation

```python
Simulações:
- Número: 10.000+ cenários
- Horizonte: 1 dia a 1 ano
- Distribuição: Normal / Student-t / GARCH

Outputs:
- Distribuição de retornos
- Probabilidade de ruína
- Drawdown máximo esperado
- Optimal bet sizing
```

### Position Intelligence

```python
Features:
- Correlação de posições abertas
- Exposição por setor/região
- Beta do portfolio
- Stress testing em tempo real
- Sugestões de hedge
```

---

## 🏗️ Infraestrutura

### Redis Cache

```python
Uso:
- Cache de dados de mercado (TTL: 1 minuto)
- Cache de sinais (TTL: 5 minutos)
- Cache de cálculos pesados (indicadores)
- Pub/Sub entre componentes

Configuração:
REDIS_HOST: localhost
REDIS_PORT: 6379
REDIS_DB: 0
```

### InfluxDB Metrics

```python
Métricas Coletadas:
- Performance de trades
- Latência de execução
- Uso de recursos
- Health checks de componentes

Retenção:
- Raw data: 7 dias
- Downsampled: 90 dias
- Aggregated: 2 anos
```

### MT5 Connection Pool (Novo)

```python
Features:
- Pool de conexões reutilizáveis
- Health checks periódicos
- Reconexão automática
- Retry com backoff exponencial
- Métricas de uso

Configuração:
MIN_CONNECTIONS: 1
MAX_CONNECTIONS: 5
HEALTH_CHECK_INTERVAL: 60s
MAX_IDLE_TIME: 300s
```

### WebSocket Server

```python
Funcionalidades:
- Streaming de preços em tempo real
- Atualizações de posições
- Alertas de sinais
- Logs em tempo real

Porta: 8080
```

---

## 🔌 Integrações Externas

### MetaTrader 5

```python
Operações:
- Obtenção de cotações em tempo real
- Envio de ordens (Market, Limit, Stop)
- Modificação de SL/TP
- Fechamento de posições
- Histórico de trades

API: MetaTrader5 Python Package
```

### ForexNewsAPI

```python
Endpoints Utilizados:
- /api/v1/live: Notícias em tempo real
- /api/v1/stat: Estatísticas de sentimento
- /api/v1/top-mention: Pares mais mencionados
- /api/v1/trending-headlines: Headlines trending

Taxa: 1000 requests/mês (Free Plan)
```

### TradingView

```python
Integração:
- Webhooks para sinais externos
- Alertas customizados
- Integração com Pine Script

Porta Webhook: 8765
```

### Telegram

```python
Notificações:
- Abertura de trades
- Fechamento (com PnL)
- Alertas de risco
- Status diário
- Erros críticos

Comandos:
/status - Status do bot
/positions - Posições abertas
/performance - Performance do dia
/stop - Para o bot
/start - Inicia o bot
```

---

## ⚙️ Configuração

### Arquivo Principal: `config/settings.yaml`

```yaml
# Conexão MT5
mt5:
  login: 12345678
  password: "sua_senha"
  server: "seu_broker-server"
  path: "C:\\Program Files\\MetaTrader 5\\terminal64.exe"

# Símbolos para operar
symbols:
  - XAUUSD
  - EURUSD
  - GBPUSD
  - BTCUSD

# Gestão de Risco
risk:
  max_risk_per_trade: 0.02      # 2% por trade
  max_daily_drawdown: 0.05      # 5% drawdown diário máximo
  max_open_positions: 10        # Máximo de posições simultâneas
  kelly_fraction: 0.25          # 25% do Kelly completo
  max_correlation: 0.7          # Correlação máxima entre posições

# Machine Learning
ml:
  enabled: true
  min_confidence: 0.6           # Confiança mínima para operar
  retrain_interval: 7           # Retreinar a cada 7 dias

# Estratégias
strategies:
  scalping:
    enabled: true
    weight: 0.2
    timeframe: M5
  trend_following:
    enabled: true
    weight: 0.3
    timeframe: H1
  breakout:
    enabled: true
    weight: 0.25
    timeframe: M15
  mean_reversion:
    enabled: true
    weight: 0.25
    timeframe: H1

# Infraestrutura
redis:
  host: localhost
  port: 6379
  db: 0

influxdb:
  host: localhost
  port: 8086
  bucket: urion_metrics

# APIs Externas
apis:
  forex_news:
    api_key: "sua_api_key"
    rate_limit: 60
  telegram:
    bot_token: "seu_bot_token"
    chat_id: "seu_chat_id"

# Logging
logging:
  level: INFO
  rotation: "1 day"
  retention: "30 days"
```

---

## 🚀 Instalação

### Requisitos

- Windows 10/11 ou Windows Server
- Python 3.10+
- MetaTrader 5
- Redis (opcional)
- InfluxDB (opcional)

### Passos

```powershell
# 1. Clone o repositório
git clone https://github.com/joaoschaun/urionmultisimbol.git
cd urionmultisimbol

# 2. Crie ambiente virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure o arquivo settings.yaml
cp config/settings.example.yaml config/settings.yaml
# Edite com suas credenciais

# 5. Inicie o MetaTrader 5

# 6. Execute o bot
python main.py
```

### Dependências Principais

```
MetaTrader5>=5.0.45
numpy>=1.24.0
pandas>=2.0.0
loguru>=0.7.0
pyyaml>=6.0
scikit-learn>=1.3.0
tensorflow>=2.13.0
torch>=2.0.0
transformers>=4.30.0
optuna>=3.3.0
scipy>=1.11.0
redis>=4.6.0
influxdb-client>=1.36.0
aiohttp>=3.8.0
websockets>=11.0.0
python-telegram-bot>=20.0
```

---

## 🎮 Operação

### Iniciar o Bot

```powershell
# Opção 1: Direto
python main.py

# Opção 2: Com script
.\start_bot.ps1

# Opção 3: Em background
Start-Process -NoNewWindow python -ArgumentList "main.py"
```

### Monitorar Logs

```powershell
# Logs em tempo real
Get-Content -Path logs/urion.log -Wait -Tail 50

# Logs de erro
Get-Content -Path logs/error.log -Wait
```

### Parar o Bot

```powershell
# Ctrl+C no terminal
# Ou
Get-Process python | Stop-Process
```

### Dashboard Web

```powershell
# Iniciar backend
python backend/server.py

# Iniciar frontend
cd frontend
npm run dev

# Acessar: http://localhost:3000
```

---

## 📊 Monitoramento

### Métricas em Tempo Real

O bot exibe continuamente:

```
================================================================================
URION TRADING BOT - PROFESSIONAL EDITION v2.2
================================================================================

MODULOS ATIVOS:
----------------------------------------
  ✓ Redis Cache
  ✓ InfluxDB Metrics
  ✓ Data Hub
  ✓ Order Flow Analyzer
  ✓ Manipulation Detector
  ✓ Strategy Communicator
  ✓ Position Intelligence
  ✓ Monte Carlo Simulator
  ✓ VaR Calculator
  ✓ Execution Algorithms
  ✓ Economic Calendar
  ✓ TradingView Webhooks
  ✓ ML Training Pipeline
  ✓ FinBERT NLP Analyzer
  ✓ Transformer Predictor
  ✓ Correlation Analyzer
  ✓ Harmonic Patterns
  ✓ Order Generator
  ✓ Order Manager
----------------------------------------
```

### Performance Diária

Via Telegram:
```
📊 Performance do Dia

Trades: 15
Wins: 10 (66.7%)
Losses: 5 (33.3%)

Profit: $234.50
Drawdown: 1.2%

Melhor Trade: XAUUSD +$85.20
Pior Trade: EURUSD -$42.10
```

### Diagnóstico

```powershell
python diagnostico_completo.py
```

Saída:
```
=== DIAGNÓSTICO URION BOT ===

[✓] MT5 Conectado
[✓] Conta: 12345678 (Demo)
[✓] Balance: $10,000.00

[✓] Redis: Conectado (latency: 2ms)
[✓] InfluxDB: Conectado

[✓] Posições Abertas: 3
    - XAUUSD: Buy 0.10 @ 2650.50 (+$12.30)
    - EURUSD: Sell 0.05 @ 1.0820 (+$5.20)
    - BTCUSD: Buy 0.01 @ 98500 (-$8.40)

[✓] Estratégias Ativas: 6
[✓] Threads Saudáveis: 8/8
[✓] Memória: 245 MB
[✓] CPU: 5%
```

---

## 🔧 Troubleshooting

### Problema: MT5 não conecta

```powershell
# Verificar se MT5 está aberto
Get-Process terminal64 -ErrorAction SilentlyContinue

# Verificar credenciais
python -c "import MetaTrader5 as mt5; mt5.initialize(); print(mt5.last_error())"
```

### Problema: Ordens não executam

1. Verificar se o mercado está aberto
2. Verificar spread (pode estar muito alto)
3. Verificar saldo disponível
4. Verificar limites de risco

```powershell
# Verificar último erro
Select-String -Path logs/urion.log -Pattern "ERROR" | Select-Object -Last 10
```

### Problema: Alta latência

```powershell
# Verificar conexões
netstat -an | findstr ":443"

# Verificar ping ao servidor
ping seu-broker-server

# Otimizar Redis
redis-cli INFO memory
```

### Problema: Módulo não carrega

```powershell
# Verificar dependências
pip check

# Reinstalar módulo específico
pip install --force-reinstall nome_do_pacote
```

---

## 📝 Changelog

### v2.2 (01/12/2025)
- ✅ FinBERT NLP Analyzer para sentimento de notícias
- ✅ Transformer Predictor para previsões
- ✅ Correlation Analyzer multi-símbolo
- ✅ Harmonic Patterns (Gartley, Butterfly, etc.)
- ✅ MT5 Connection Pool
- ✅ ForexNewsAPI Sentiment endpoints

### v2.1 (28/11/2025)
- ✅ Correção de trades multi-símbolo
- ✅ Melhoria no Order Manager
- ✅ Profit capture corrigido

### v2.0 (27/11/2025)
- ✅ Suporte multi-símbolo
- ✅ TWAP/VWAP/Iceberg Orders
- ✅ Monte Carlo + VaR
- ✅ Redis + InfluxDB
- ✅ TradingView Webhooks

---

## 📞 Suporte

- **GitHub Issues**: [github.com/joaoschaun/urionmultisimbol/issues](https://github.com/joaoschaun/urionmultisimbol/issues)
- **Documentação**: Este arquivo
- **Telegram**: Configure seu bot para receber alertas

---

## 📜 Licença

MIT License - Veja [LICENSE](LICENSE) para detalhes.

---

<div align="center">

**URION Trading Bot v2.2**

*Desenvolvido com ❤️ para traders profissionais*

</div>
