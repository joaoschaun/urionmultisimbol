# 🏗️ Arquitetura do Sistema Urion

## Visão Geral

O **Urion Trading Bot** é um sistema de trading automatizado institucional composto por múltiplos módulos independentes que trabalham em conjunto para executar operações no mercado XAUUSD.

## Componentes Principais

### 1. Core System (`src/core/`)
✅ **Implementado**

- **MT5Connector**: Gerencia conexão com MetaTrader 5
  - Conexão automática e reconexão
  - Execução de ordens
  - Gerenciamento de posições
  - Coleta de dados históricos

- **ConfigManager**: Gerenciamento de configurações
  - Carregamento de YAML
  - Variáveis de ambiente
  - Configuração dinâmica

- **Logger**: Sistema de logs estruturado
  - Logs rotativos
  - Múltiplos níveis
  - Separação de erros

### 2. Order Generator (`src/order_generator.py`)
⏳ **A implementar**

Responsável por gerar sinais de trading:
- Análise de mercado em ciclos de 5 minutos
- Integração com análise técnica
- Integração com análise de notícias
- Validação de horários de trading
- Validação multi-confirmação
- Geração de ordens com SL/TP

### 3. Order Manager (`src/order_manager.py`)
⏳ **A implementar**

Gerencia posições abertas:
- Monitoramento contínuo (1 minuto)
- Trailing stop dinâmico
- Proteção de lucros
- Redução de perdas
- Break-even automático
- Fechamento parcial

### 4. Technical Analysis (`src/analysis/technical.py`)
⏳ **A implementar**

Análise técnica multi-timeframe:
- **Indicadores de Tendência**: EMA, SMA, MACD, ADX
- **Indicadores de Momentum**: RSI, Stochastic, CCI
- **Indicadores de Volatilidade**: Bollinger Bands, ATR, Keltner
- **Indicadores de Volume**: Volume, OBV, MFI
- **Padrões de Candlestick**: Doji, Hammer, Engulfing, etc.
- Análise multi-timeframe (M1, M5, M15, M30, H1, H4, D1)

### 5. News Analyzer (`src/analysis/news_analyzer.py`)
⏳ **A implementar**

Análise de notícias e sentimento:
- Integração com 3 APIs de notícias
- Análise de sentimento com NLP
- Detecção de eventos de alto impacto
- Previsão de reação do mercado
- Calendário econômico

### 6. Strategy System (`src/strategies/`)
⏳ **A implementar**

Múltiplas estratégias de trading:

- **Trend Following**: Segue tendências fortes
- **Mean Reversion**: Opera reversões à média
- **Breakout**: Detecta e opera rompimentos
- **News Trading**: Opera baseado em notícias

### 7. Risk Manager (`src/risk_manager.py`)
⏳ **A implementar**

Gerenciamento de risco:
- Position sizing dinâmico
- Cálculo de stop loss/take profit
- Controle de drawdown
- Limite de trades diários
- Proteção de capital

### 8. Machine Learning (`src/ml/`)
⏳ **A implementar**

Sistema de aprendizagem:
- Feature engineering
- Treinamento de modelos (XGBoost, LSTM)
- Predição de probabilidade de sucesso
- Otimização contínua
- Backtesting

### 9. Database Layer
⏳ **A implementar**

Persistência de dados:
- PostgreSQL para dados estruturados
- Redis para cache
- Armazenamento de trades
- Histórico de sinais
- Métricas de performance

## Fluxo de Operação

```
┌─────────────────────────────────────────────────────────┐
│                    URION TRADING BOT                     │
└─────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  News Analyzer   │         │ Technical Analysis│
│  - ForexNews API │         │  - Multi-timeframe│
│  - Finazon API   │────────▶│  - Indicadores    │
│  - FinModeling   │         │  - Padrões        │
└──────────────────┘         └──────────────────┘
         │                            │
         │                            │
         ▼                            ▼
┌────────────────────────────────────────────┐
│        ORDER GENERATOR (5min cycles)        │
│  1. Analisa notícias + sentimento           │
│  2. Analisa indicadores técnicos            │
│  3. Aplica estratégias ativas               │
│  4. Valida horários de trading              │
│  5. Calcula SL/TP baseado em ATR           │
│  6. Gera ordem se força >= threshold        │
└────────────────────────────────────────────┘
         │
         │ Sinal de Trading
         ▼
┌────────────────────────────────────────────┐
│          RISK MANAGER                       │
│  - Valida exposição total                   │
│  - Calcula position size                    │
│  - Verifica drawdown                        │
│  - Aprova ou rejeita ordem                  │
└────────────────────────────────────────────┘
         │
         │ Ordem aprovada
         ▼
┌────────────────────────────────────────────┐
│        MT5 CONNECTOR                        │
│  - Executa ordem no MT5                     │
│  - Registra no database                     │
│  - Notifica via Telegram                    │
└────────────────────────────────────────────┘
         │
         │ Ordem executada
         ▼
┌────────────────────────────────────────────┐
│      ORDER MANAGER (1min cycles)            │
│  1. Monitora posições abertas               │
│  2. Atualiza análise técnica                │
│  3. Aplica trailing stop                    │
│  4. Move para break-even                    │
│  5. Fecha parcialmente se atingir target    │
│  6. Fecha totalmente se SL ou TP            │
└────────────────────────────────────────────┘
         │
         │ Posição fechada
         ▼
┌────────────────────────────────────────────┐
│       MACHINE LEARNING                      │
│  - Registra resultado do trade              │
│  - Atualiza features                        │
│  - Retreina modelo periodicamente           │
│  - Melhora predições futuras                │
└────────────────────────────────────────────┘
```

## Horários de Operação

- **Segunda a Sexta**: 18:30 - 16:30 UTC
- **Pausa diária**: 16:30 - 18:30 UTC (fechamento do mercado)
- **Final de semana**: Sexta 16:30 - Domingo 18:30 UTC

**Evitar trading**: 15 minutos antes e depois de notícias de alto impacto

## Estratégias de Trading

### 1. Trend Following
- Detecta tendências com ADX > 25
- Usa EMAs para confirmação
- Entra na direção da tendência
- SL atrás do último swing
- TP = 2x SL

### 2. Mean Reversion
- Detecta sobrecompra/sobrevenda (RSI > 70 ou < 30)
- Usa Bollinger Bands para confirmação
- Entra na reversão
- SL na banda oposta
- TP na média móvel

### 3. Breakout
- Identifica suporte/resistência
- Espera rompimento com volume
- Entra após confirmação
- SL abaixo do suporte/acima da resistência
- TP = distância do canal

### 4. News Trading
- Analisa sentimento de notícias
- Prevê direção com ML
- Entra antes ou após notícia
- SL apertado
- TP rápido

## Gerenciamento de Risco

### Regras Fundamentais
- **Risco por trade**: Máximo 2% do capital
- **Drawdown máximo**: 15% (para trading)
- **Perda diária máxima**: 5% do capital
- **Máximo de trades por dia**: 10
- **Máximo de posições simultâneas**: 3

### Position Sizing
```python
risk_amount = account_balance * risk_per_trade
sl_distance = entry_price - stop_loss
lot_size = risk_amount / (sl_distance * contract_size)
```

### Stop Loss Dinâmico
- Baseado em ATR (Average True Range)
- Mínimo: 20 pips
- Ajustado conforme volatilidade

### Take Profit
- Risk/Reward mínimo: 1:2
- Fechamento parcial em 50% e 75% do TP
- Trailing stop após 60% do TP

## Machine Learning

### Features
- Variação de preço
- RSI, MACD, Bollinger position
- ATR (volatilidade)
- Volume
- Hora do dia / Dia da semana
- Sentimento de notícias

### Target
- Trade lucrativo (1) ou não (0)

### Modelos
- **XGBoost**: Decisões rápidas
- **LSTM**: Séries temporais
- **Ensemble**: Combinação dos dois

### Retreinamento
- Diariamente com novos dados
- Mínimo 1000 amostras
- Validação 80/10/10

## Notificações Telegram

### Mensagens Automáticas
- 🚀 Início do bot
- 📊 Sinais de trading
- ✅ Ordens executadas
- 💚/❌ Ordens fechadas
- ⚠️ Alertas importantes
- ❌ Erros críticos
- 📈 Resumo diário

### Comandos
- `/status` - Status do bot
- `/balance` - Saldo da conta
- `/positions` - Posições abertas
- `/stats` - Estatísticas
- `/start` - Iniciar bot
- `/stop` - Parar bot

## Próximos Passos de Implementação

### Fase 1: Módulos Essenciais
1. ✅ Core system (MT5, Config, Logger)
2. ⏳ Risk Manager
3. ⏳ Order Generator (básico)
4. ⏳ Order Manager (básico)
5. ⏳ Telegram notifications

### Fase 2: Análise
6. ⏳ Technical Analysis (indicadores básicos)
7. ⏳ News Analyzer (integração APIs)
8. ⏳ Sentiment Analysis

### Fase 3: Estratégias
9. ⏳ Trend Following Strategy
10. ⏳ Mean Reversion Strategy
11. ⏳ Breakout Strategy
12. ⏳ News Trading Strategy

### Fase 4: Inteligência
13. ⏳ Feature Engineering
14. ⏳ Model Training
15. ⏳ Prediction System
16. ⏳ Backtesting Engine

### Fase 5: Produção
17. ⏳ Database integration
18. ⏳ Monitoring & Metrics
19. ⏳ Testing suite
20. ⏳ Documentation

## Melhorias Sugeridas

### Adicionais Recomendados

1. **Dashboard Web**
   - Interface para monitoramento em tempo real
   - Gráficos de performance
   - Controle manual de operações

2. **Order Flow Analysis**
   - Análise de volume por nível de preço
   - Detecção de grandes ordens
   - Footprint charts

3. **Multi-Symbol Support**
   - Expandir para outros pares (EURUSD, GBPUSD, etc.)
   - Correlação entre pares
   - Hedging automático

4. **Sentiment Analysis Avançado**
   - Análise de redes sociais (Twitter, Reddit)
   - Índice de medo/ganância
   - Posicionamento de COT

5. **Adaptive Learning**
   - Detecção de mudança de regime de mercado
   - Ajuste automático de parâmetros
   - A/B testing de estratégias

6. **Advanced Risk Management**
   - Portfolio optimization
   - Correlação entre trades
   - VAR (Value at Risk)

7. **API REST**
   - Controle externo do bot
   - Integração com outros sistemas
   - Mobile app

8. **Redundância**
   - Múltiplos servidores
   - Failover automático
   - Backup em tempo real

## Segurança

### Credenciais
- Nunca commitar .env
- Rotacionar tokens regularmente
- Usar secrets management (ex: HashiCorp Vault)

### Operação
- Iniciar com conta demo
- Testes extensivos antes de produção
- Limites de perda rigorosos
- Monitoramento 24/7

### Auditoria
- Logs de todas as operações
- Rastreabilidade completa
- Alertas de anomalias

## Performance Esperada

### Métricas Alvo
- **Win Rate**: > 55%
- **Profit Factor**: > 1.5
- **Sharpe Ratio**: > 1.2
- **Max Drawdown**: < 15%
- **Avg Trade Duration**: 2-6 horas

### Benchmarking
- Comparação com buy & hold
- Comparação com índices
- Análise de consistência

---

**Status**: 🟡 Em desenvolvimento ativo
**Versão**: 0.1.0-alpha
**Última atualização**: 18 de novembro de 2025
