# 🔌 Análise de APIs para Trading - Urion Bot

## 📊 APIs Atualmente Integradas

| API | Tipo | Uso Atual | Status |
|-----|------|-----------|--------|
| **ForexNewsAPI** | Notícias | Notícias gerais de Forex | ✅ Ativo |
| **Finazon** | Dados de Mercado | Tickers de Forex/Gold | ✅ Ativo |
| **Finnhub** | Notícias + Dados | Notícias de Forex + Sentiment | ✅ Ativo |
| **Financial Modeling Prep** | Calendário Econômico | Eventos econômicos | ✅ Ativo |
| **TwelveData** | Dados OHLCV | Cotações históricas | ⚠️ Configurado, não usado |

---

## 🚀 APIs Recomendadas para Integrar

### 1. 📈 **Alpha Vantage** (GRATUITA)
**Prioridade: ALTA**

```
URL: https://www.alphavantage.co/
Limite: 5 chamadas/min (gratuito), 75 chamadas/dia
```

**Dados Disponíveis:**
- Cotações em tempo real para Forex (XAUUSD)
- Indicadores técnicos calculados (RSI, MACD, SMA, EMA, etc.)
- Dados intraday (1min, 5min, 15min, 30min, 60min)
- Sentimento de mercado

**Por que integrar:**
- Indicadores técnicos prontos → reduz cálculo local
- Backup para dados do MT5
- Validação cruzada de sinais

---

### 2. 📰 **NewsAPI.org** (GRATUITA)
**Prioridade: ALTA**

```
URL: https://newsapi.org/
Limite: 100 requests/dia (gratuito), 1000/dia (developer)
```

**Dados Disponíveis:**
- Notícias globais de 80.000+ fontes
- Busca por palavras-chave (gold, inflation, fed, etc.)
- Headlines em tempo real
- Filtro por país, fonte, idioma

**Por que integrar:**
- Cobertura mais ampla que ForexNewsAPI
- Notícias de fontes mainstream (Reuters, Bloomberg, CNN)
- Detectar eventos geopolíticos que afetam ouro

---

### 3. 🏦 **FRED (Federal Reserve)** (GRATUITA)
**Prioridade: ALTA**

```
URL: https://fred.stlouisfed.org/
API: https://api.stlouisfed.org/fred/
Limite: Ilimitado
```

**Dados Disponíveis:**
- Taxa de juros do Fed (FEDFUNDS)
- Inflação (CPI, PCE)
- Emprego (NFP, Unemployment)
- PIB e indicadores macro
- Treasury Yields (10Y, 2Y)
- Índice do Dólar (DXY)

**Por que integrar:**
- Dados oficiais do Fed → máxima confiabilidade
- Correlação direta com preço do ouro
- Prever movimentos antes de announcements

---

### 4. 📊 **Trading Economics** (PAGA, vale o investimento)
**Prioridade: MÉDIA-ALTA**

```
URL: https://tradingeconomics.com/
Preço: $49/mês (básico)
```

**Dados Disponíveis:**
- Calendário econômico global
- Previsões de indicadores
- Dados históricos de 196 países
- Alertas de eventos

**Por que integrar:**
- Melhor calendário econômico disponível
- Previsões de consenso vs actual
- Histórico de surpresas (beat/miss)

---

### 5. 💹 **Quandl/Nasdaq Data Link** (GRATUITA para alguns datasets)
**Prioridade: MÉDIA**

```
URL: https://data.nasdaq.com/
Limite: 300 requests/10 segundos
```

**Dados Disponíveis:**
- CFTC Commitments of Traders (COT) → posições de grandes players
- COMEX Gold futures
- ETF holdings (GLD, IAU)
- Dados de volatilidade

**Por que integrar:**
- COT data → ver o que instituições estão fazendo
- Detectar acumulação/distribuição institucional
- Muito valioso para prever reversões

---

### 6. 🌐 **World Gold Council** (GRATUITA)
**Prioridade: MÉDIA**

```
URL: https://www.gold.org/goldhub/data
```

**Dados Disponíveis:**
- Demanda/oferta global de ouro
- Compras de bancos centrais
- ETF flows
- Produção de mineração

**Por que integrar:**
- Dados fundamentais únicos
- Prever tendências de longo prazo
- Alertas de compras de bancos centrais

---

### 7. 😊 **Twitter/X API** (PAGA)
**Prioridade: MÉDIA**

```
URL: https://developer.twitter.com/
Preço: $100/mês (Basic)
```

**Dados Disponíveis:**
- Sentiment de mercado em tempo real
- Tweets de influenciadores financeiros
- Trending topics sobre ouro/economia

**Por que integrar:**
- Sentiment em tempo real
- Detectar FUD/FOMO antes do mercado reagir
- Acompanhar contas importantes (Fed officials, analistas)

---

### 8. 📉 **VIX/Fear & Greed** (GRATUITAS)
**Prioridade: ALTA**

```
CBOE VIX: via Alpha Vantage ou Yahoo Finance
CNN Fear & Greed: https://production.dataviz.cnn.io/index/fearandgreed/graphdata
```

**Dados Disponíveis:**
- VIX (Índice de Volatilidade)
- Fear & Greed Index
- Market momentum
- Safe haven demand

**Por que integrar:**
- VIX alto → ouro sobe (safe haven)
- Fear extremo → possível reversão
- Correlação inversa com risk-on assets

---

### 9. 🔢 **Economic Calendar - Investing.com** (GRATUITA)
**Prioridade: MÉDIA**

```
Scraping: https://www.investing.com/economic-calendar/
```

**Dados Disponíveis:**
- Calendário econômico mais completo
- Impacto esperado (1-3 bulls)
- Previsão vs Anterior vs Atual
- Histórico de volatilidade por evento

**Por que integrar:**
- Backup para FMP
- Dados mais detalhados sobre impacto
- Filtro por moeda/país

---

### 10. 📊 **TradingView Webhooks** (GRATUITA com limitações)
**Prioridade: BAIXA**

```
Configurar alertas no TradingView → Webhook para Urion
```

**Dados Disponíveis:**
- Alertas de indicadores customizados
- Cruzamentos de médias
- Rompimentos de suporte/resistência

**Por que integrar:**
- Usar indicadores customizados do TradingView
- Comunidade de scripts prontos
- Validação externa de sinais

---

## 🎯 Priorização de Implementação

### Fase 1 - Essencial (Esta Semana)
1. **Alpha Vantage** - Indicadores técnicos prontos
2. **FRED** - Dados macro do Fed
3. **VIX/Fear & Greed** - Sentiment de mercado

### Fase 2 - Importante (Próxima Semana)
4. **NewsAPI.org** - Mais cobertura de notícias
5. **Quandl COT** - Posições institucionais

### Fase 3 - Complementar (Próximo Mês)
6. **World Gold Council** - Dados fundamentais
7. **Trading Economics** - Calendário premium
8. **Twitter API** - Sentiment social

---

## 💻 Código de Integração

### Alpha Vantage
```python
import requests

class AlphaVantageAPI:
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def get_forex_rate(self, from_currency: str = "XAU", to_currency: str = "USD"):
        """Cotação em tempo real"""
        params = {
            'function': 'CURRENCY_EXCHANGE_RATE',
            'from_currency': from_currency,
            'to_currency': to_currency,
            'apikey': self.api_key
        }
        response = requests.get(self.BASE_URL, params=params)
        return response.json()
    
    def get_rsi(self, symbol: str = "XAUUSD", interval: str = "60min", period: int = 14):
        """RSI calculado pela API"""
        params = {
            'function': 'RSI',
            'symbol': symbol,
            'interval': interval,
            'time_period': period,
            'series_type': 'close',
            'apikey': self.api_key
        }
        response = requests.get(self.BASE_URL, params=params)
        return response.json()
    
    def get_macd(self, symbol: str = "XAUUSD", interval: str = "60min"):
        """MACD calculado pela API"""
        params = {
            'function': 'MACD',
            'symbol': symbol,
            'interval': interval,
            'series_type': 'close',
            'apikey': self.api_key
        }
        response = requests.get(self.BASE_URL, params=params)
        return response.json()
```

### FRED API
```python
import requests

class FREDAPI:
    BASE_URL = "https://api.stlouisfed.org/fred"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def get_series(self, series_id: str, limit: int = 10):
        """Busca série de dados"""
        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'file_type': 'json',
            'limit': limit,
            'sort_order': 'desc'
        }
        response = requests.get(f"{self.BASE_URL}/series/observations", params=params)
        return response.json()
    
    def get_fed_funds_rate(self):
        """Taxa de juros do Fed"""
        return self.get_series('FEDFUNDS')
    
    def get_cpi(self):
        """Inflação (CPI)"""
        return self.get_series('CPIAUCSL')
    
    def get_treasury_10y(self):
        """Treasury 10 anos"""
        return self.get_series('DGS10')
    
    def get_dxy(self):
        """Índice do Dólar"""
        return self.get_series('DTWEXBGS')
```

### Fear & Greed Index
```python
import requests

class FearGreedAPI:
    URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    
    def get_current(self) -> dict:
        """Retorna Fear & Greed atual"""
        try:
            response = requests.get(self.URL, timeout=10)
            data = response.json()
            
            score = data.get('fear_and_greed', {}).get('score', 50)
            rating = data.get('fear_and_greed', {}).get('rating', 'Neutral')
            
            return {
                'score': score,
                'rating': rating,
                'interpretation': self._interpret(score)
            }
        except:
            return {'score': 50, 'rating': 'Neutral', 'interpretation': 'neutral'}
    
    def _interpret(self, score: int) -> str:
        if score <= 25:
            return 'extreme_fear'  # Ouro pode subir (safe haven)
        elif score <= 45:
            return 'fear'
        elif score <= 55:
            return 'neutral'
        elif score <= 75:
            return 'greed'
        else:
            return 'extreme_greed'  # Risk-on, ouro pode cair
```

---

## 📋 Configuração Sugerida

Adicionar ao `config.yaml`:

```yaml
apis:
  # Existentes
  forexnews_api_key: "sua_key"
  finazon_api_key: "sua_key"
  fmp_api_key: "sua_key"
  finnhub_api_key: "sua_key"
  twelvedata_api_key: "sua_key"
  
  # Novas
  alphavantage_api_key: ""  # Obter em: https://www.alphavantage.co/support/#api-key
  fred_api_key: ""          # Obter em: https://fred.stlouisfed.org/docs/api/api_key.html
  newsapi_api_key: ""       # Obter em: https://newsapi.org/register
  quandl_api_key: ""        # Obter em: https://data.nasdaq.com/sign-up

  # Configurações
  api_timeout: 10
  api_retry_count: 3
  cache_duration_minutes: 5
```

---

## 📊 Impacto Esperado

| API | Melhoria Esperada |
|-----|-------------------|
| Alpha Vantage | +5-10% precisão indicadores |
| FRED | +10-15% em trades macro |
| Fear & Greed | +5% em timing de entrada |
| COT Data | +15-20% em trades de reversão |
| NewsAPI | +10% cobertura de eventos |

**Impacto Total Estimado: +15-25% na taxa de acerto**

---

## 🔑 Onde Obter API Keys (Gratuitas)

1. **Alpha Vantage**: https://www.alphavantage.co/support/#api-key
2. **FRED**: https://fred.stlouisfed.org/docs/api/api_key.html
3. **NewsAPI**: https://newsapi.org/register
4. **Quandl**: https://data.nasdaq.com/sign-up

Todas essas APIs oferecem planos gratuitos suficientes para um bot de trading!
