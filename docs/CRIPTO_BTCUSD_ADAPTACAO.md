# 🪙 Adaptação para BTCUSD (Criptomoedas)

## 📊 Diferenças Fundamentais: Forex vs Cripto

| Característica | Forex (EURUSD) | Cripto (BTCUSD) |
|----------------|----------------|-----------------|
| **Horário** | 24h (seg-sex) | 24h/7 (sem pausa) |
| **Feriados** | Sim (NY/Londres) | Não (mercado sempre aberto) |
| **Volatilidade** | 0.5-1.5% ao dia | 3-15% ao dia |
| **Spread** | 0.5-3 pips | 10-100 USD (0.01-0.1%) |
| **Liquidez** | Altíssima | Média-Alta (depende da corretora) |
| **Slippage** | Baixo (1-3 pips) | Alto (5-50 USD) |
| **Gaps** | Raros (só fim de semana) | Frequentes (24/7) |
| **Alavancagem** | 1:100 - 1:500 | 1:2 - 1:20 (regulado) |
| **Tamanho mínimo** | 0.01 lote (1k) | 0.001 BTC (varia) |

---

## 🔧 Mudanças Necessárias no Código

### **1. MarketHours (src/core/market_hours.py)**

Criar classe específica para cripto:

```python
class CryptoMarketHours:
    """Mercado 24/7 sem pausas"""
    
    def is_market_open(self, symbol: str) -> bool:
        # Cripto SEMPRE aberto
        return True
    
    def has_daily_pause(self) -> bool:
        # Cripto NÃO tem pausa diária
        return False
    
    def should_close_positions(self) -> bool:
        # Nunca fecha por horário (só por risco)
        return False
```

**Modificar `SymbolContext._build_symbol_config()`:**
```python
# Detectar tipo de ativo
if symbol.endswith('USD') and not symbol.startswith(('BTC', 'ETH')):
    # Forex/Commodities
    market_hours = MarketHoursManager(config)
elif symbol.startswith(('BTC', 'ETH', 'LTC')):
    # Cripto
    market_hours = CryptoMarketHours()
```

---

### **2. MarketHolidays (src/core/market_holidays.py)**

Cripto **ignora feriados**:

```python
class CryptoHolidays:
    """Criptomoedas não têm feriados"""
    
    def is_holiday(self, date=None) -> bool:
        return False  # Sempre operando
    
    def can_trade(self) -> bool:
        return True  # Sempre permitido
```

---

### **3. RiskManager (ajustes para volatilidade)**

Cripto precisa de **parâmetros mais conservadores**:

```python
# config.yaml (exemplo BTCUSD)
risk:
  crypto_multiplier: 0.5  # 🆕 Reduz risco em 50% para cripto
  max_risk_per_trade: 0.01  # 1% (cripto) vs 2% (forex)
  max_drawdown: 0.05  # 5% (cripto) vs 8% (forex)
  stop_loss_pips: 200  # 200 USD (cripto) vs 50 pips (forex)
  take_profit_pips: 400  # 400 USD (cripto)
```

**Modificar `RiskManager.calculate_position_size()`:**
```python
def calculate_position_size(self, symbol: str, ...) -> float:
    base_size = self._calculate_base_size(...)
    
    # 🆕 Ajustar para cripto
    if self._is_crypto(symbol):
        base_size *= self.crypto_multiplier
        base_size = max(base_size, self.min_crypto_size)
    
    return base_size

def _is_crypto(self, symbol: str) -> bool:
    return symbol.startswith(('BTC', 'ETH', 'LTC', 'XRP'))
```

---

### **4. Spread/Slippage Ajustados**

```yaml
# config.yaml
symbols:
  BTCUSD:
    enabled: true  # 🪙 CRIPTO: 24/7, alta volatilidade
    timeframes:
    - M5
    - M15
    - M30
    - H1
    - H4
    - D1
    default_lot_size: 0.01  # 0.01 BTC (~$900 em 2025)
    min_lot_size: 0.001     # 0.001 BTC (~$90)
    max_lot_size: 0.5       # 0.5 BTC (~$45k)
    max_open_positions: 4   # Menos posições (maior volatilidade)
    spread_threshold: 50    # 50 USD de spread máximo (0.05%)
    slippage: 20            # 20 USD de slippage esperado
```

---

### **5. Estratégias Adaptadas**

#### **Scalping (NÃO recomendado para cripto)**
```yaml
strategies:
  scalping:
    enabled: false  # ❌ DESATIVAR para BTCUSD (spread alto demais)
```

#### **Trend Following (RECOMENDADO)**
```yaml
strategies:
  trend_following:
    enabled: true  # ✅ Ideal para tendências fortes de cripto
    timeframe: H1  # H1 ou H4 (evitar M5/M15)
    min_confidence: 0.80  # Mais exigente (80% vs 75%)
    trailing_stop_distance: 100  # 100 USD (cripto) vs 25 pips (forex)
```

#### **Mean Reversion (CUIDADO)**
```yaml
strategies:
  mean_reversion:
    enabled: true
    bollinger_std: 3  # 3 desvios (cripto) vs 2 (forex)
    rsi_overbought: 80  # 80 (cripto) vs 70 (forex)
    rsi_oversold: 20    # 20 (cripto) vs 30 (forex)
```

#### **News Trading (MUITO EFETIVO)**
```yaml
strategies:
  news_trading:
    enabled: true  # ✅ Cripto reage fortemente a notícias
    min_sentiment_confidence: 0.8
    crypto_news_sources:
      - coindesk
      - cointelegraph
      - twitter_whales  # 🆕 Monitorar whales
```

---

## 🚀 Configuração Completa BTCUSD

```yaml
symbols:
  BTCUSD:
    enabled: true
    
    # Timeframes (evitar M1/M5 por spread alto)
    timeframes:
    - M15
    - M30
    - H1
    - H4
    - D1
    
    # Tamanhos de posição
    default_lot_size: 0.01   # 0.01 BTC = ~$900 (ajustar por capital)
    min_lot_size: 0.001      # 0.001 BTC = ~$90
    max_lot_size: 0.5        # 0.5 BTC = ~$45k
    
    # Limites de risco
    max_open_positions: 4    # Máximo 4 posições simultâneas
    spread_threshold: 50     # Spread máximo: 50 USD (0.05%)
    slippage: 20             # Slippage esperado: 20 USD
    
    # Stops específicos para cripto
    stop_loss_usd: 200       # 🆕 SL fixo em USD (não pips)
    take_profit_usd: 400     # 🆕 TP fixo em USD
    trailing_stop_usd: 100   # 🆕 Trailing em USD
    
    # Características únicas
    market_type: crypto      # 🆕 Identifica como cripto
    operates_24_7: true      # 🆕 Sem horários/feriados
    high_volatility: true    # 🆕 Ajusta parâmetros
```

---

## 📝 Checklist de Implementação

### **Fase 1: Preparação (1-2 horas)**
- [ ] Criar `CryptoMarketHours` class
- [ ] Criar `CryptoHolidays` class
- [ ] Adicionar `crypto_multiplier` no RiskManager
- [ ] Testar com BTCUSD desabilitado (só estrutura)

### **Fase 2: Adaptação (2-3 horas)**
- [ ] Modificar `SymbolContext` para detectar cripto
- [ ] Ajustar cálculo de `position_size` (USD vs pips)
- [ ] Implementar `stop_loss_usd`/`take_profit_usd`
- [ ] Desabilitar `scalping` para cripto

### **Fase 3: Testes (1-2 horas)**
- [ ] Testar BTCUSD em demo com `max_open_positions: 1`
- [ ] Validar spread/slippage reais da Pepperstone
- [ ] Comparar volatilidade BTCUSD vs XAUUSD
- [ ] Ajustar `default_lot_size` por capital disponível

### **Fase 4: Otimização (contínua)**
- [ ] Monitorar performance 7 dias
- [ ] Ajustar `trailing_stop_usd` por backtests
- [ ] Avaliar adicionar ETH, LTC, SOL
- [ ] Criar estratégias específicas para cripto

---

## ⚠️ AVISOS CRÍTICOS

### **1. Alavancagem Regulada**
```python
# Pepperstone limita cripto a 1:2 ou 1:5
if symbol.startswith('BTC'):
    max_leverage = 2  # 🚨 Muito menor que forex (1:500)
```

### **2. Spread MUITO Maior**
```python
# EURUSD: 0.5-2 pips (~$0.50-$2 por lote)
# BTCUSD: 10-50 USD (~$10-$50 por lote) 🚨

# Solução: Operar apenas H1/H4 (não M5/M15)
```

### **3. Gaps de Fim de Semana SÃO RAROS**
```python
# Forex: Fecha sexta 17:00, abre domingo 18:00 (gaps comuns)
# Cripto: Opera 24/7 (gaps apenas por exchange down) ✅
```

### **4. Liquidez Varia por Exchange**
```python
# Pepperstone: Liquidez boa (agregador de exchanges)
# Outros brokers: Podem ter liquidez ruim = slippage absurdo 🚨
```

---

## 🎯 Recomendações Finais

### **Símbolos Cripto por Prioridade:**
1. **BTCUSD** (Bitcoin) - Maior liquidez, menor spread
2. **ETHUSD** (Ethereum) - Segunda maior liquidez
3. **LTCUSD** (Litecoin) - Menor volatilidade
4. ⚠️ **Evitar altcoins** (XRP, ADA, etc) - Spread/slippage proibitivos

### **Estratégias Recomendadas:**
- ✅ **Trend Following** (H1/H4) - Ideal para tendências fortes
- ✅ **Breakout** (H1/D1) - Captura movimentos explosivos
- ✅ **News Trading** - Cripto reage muito a notícias
- ❌ **Scalping** - Spread mata a lucratividade
- ⚠️ **Range Trading** - Só em períodos de baixa volatilidade

### **Capital Mínimo Sugerido:**
```
BTCUSD com 0.01 lote (risco 1%):
- Capital mínimo: $5.000 USD
- Risco por trade: $50 USD (1%)
- Tamanho posição: 0.01 BTC (~$900)
- Stop Loss: 200 USD = 4% do capital ✅
```

---

## 📚 Recursos Adicionais

### **APIs de Dados Cripto:**
- **CoinGecko API** (gratuita) - Preços históricos
- **CryptoCompare** - Dados de mercado
- **Glassnode** (paga) - On-chain metrics

### **Fontes de Notícias:**
- CoinDesk, CoinTelegraph
- Twitter: @whale_alert (movimentações grandes)
- Reddit: r/CryptoCurrency

### **Backtest de Cripto:**
```python
# Baixar dados históricos do MT5
# BTCUSD: 2020-01-01 até hoje
# Timeframe: H1 (evitar M5 por spread)
# Testar estratégias em período de:
# - Bull market (2020-2021)
# - Bear market (2022)
# - Consolidação (2023-2024)
```

---

## 🔥 Exemplo de Configuração Inicial Conservadora

```yaml
symbols:
  BTCUSD:
    enabled: false  # ❌ DESABILITADO até testes completos
    
    # Configuração ULTRA CONSERVADORA para testes
    default_lot_size: 0.001   # 0.001 BTC = ~$90
    max_open_positions: 1     # Apenas 1 posição por vez
    spread_threshold: 30      # Spread máximo: 30 USD
    
    # Apenas 2 estratégias mais seguras
    allowed_strategies:
      - trend_following  # H4 apenas
      - breakout         # D1 apenas
```

---

**Próximo Passo:** Implementar `CryptoMarketHours` e testar com BTCUSD desabilitado primeiro. Depois de validar a estrutura, habilitar com `max_open_positions: 1` em conta demo.
