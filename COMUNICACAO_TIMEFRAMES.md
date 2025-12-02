# 🧠 COMUNICAÇÃO ENTRE TIMEFRAMES - URION v2.1

## Implementação Concluída: 01/12/2025

---

## 🎯 CONCEITO PRINCIPAL

As estratégias agora **SE COMUNICAM** entre si através de uma hierarquia de timeframes:

```
┌─────────────────────────────────────────────────────────────┐
│                    HIERARQUIA DE TIMEFRAMES                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   D1  ────────────────▶  TENDÊNCIA MACRO (semanas)         │
│    │                     Define direção principal           │
│    │                                                        │
│    ▼                                                        │
│   H4  ────────────────▶  TENDÊNCIA INTERMEDIÁRIA (dias)    │
│    │                     Confirma D1                        │
│    │                                                        │
│    ▼                                                        │
│   H1  ────────────────▶  TENDÊNCIA CURTA (horas)           │
│    │                     Timing para TrendFollowing         │
│    │                     Filtro para Scalping               │
│    │                                                        │
│    ▼                                                        │
│   M5  ────────────────▶  ENTRADA PRECISA                   │
│                          Scalping executa aqui              │
│                          SÓ NA DIREÇÃO DO H1                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 ARQUIVOS CRIADOS

### 1. `src/analysis/market_context.py`
**Market Context Analyzer** - O cérebro central que:
- Analisa D1 + H4 para definir **direção macro**
- Determina **regime de mercado** (TRENDING vs RANGING)
- Define quais **direções são permitidas** (BUY/SELL)
- Recomenda quais **estratégias usar** para cada regime
- Calcula **multiplicador de risco** baseado no contexto

```python
# Exemplo de uso
context = market_context.get_context()
if 'BUY' in context.allowed_directions:
    # Pode fazer compra
if context.regime == MarketRegime.TRENDING_STRONG:
    # Usar TrendFollowing
```

### 2. `src/analysis/market_regime_detector.py`
**Market Regime Detector** - Detecta se mercado está:
- `STRONG_TREND_UP/DOWN` - Tendência forte (ADX > 35)
- `TREND_UP/DOWN` - Tendência moderada (ADX 25-35)
- `WEAK_TREND` - Tendência fraca
- `RANGING` - Mercado lateral (ADX < 25)
- `CONSOLIDATION` - Pré-breakout
- `HIGH_VOLATILITY` - Volatilidade extrema

```python
# Estratégias recomendadas por regime:
TRENDING → TrendFollowing, Scalping na direção
RANGING  → MeanReversion, RangeTrading
CONSOLIDATION → Breakout
```

### 3. `src/analysis/htf_confirmation.py`
**Higher Timeframe Confirmation System** - Valida sinais:
- Verifica se TFs maiores confirmam o sinal
- Retorna nível de confirmação (STRONG/MODERATE/WEAK/CONFLICTING)
- Ajusta confiança baseado no alinhamento
- Calcula ajustes de SL/TP

```python
result = htf.confirm_signal('BUY', 'M5', technical_analysis)
if result.is_confirmed:
    confidence = result.adjusted_confidence  # Maior se alinhado
```

---

## 📝 ARQUIVOS MODIFICADOS

### 1. `src/strategies/strategy_manager.py`
- Integrado com Market Context
- Filtra sinais automaticamente baseado na direção macro
- Só permite trades nas direções aprovadas pelo contexto
- Ajusta confiança dos sinais baseado no alinhamento

### 2. `src/strategies/scalping.py` (v2.1)
**Novas funcionalidades:**
- `require_h1_confirmation` - Obrigatório H1 confirmar direção
- `_get_h1_direction()` - Método que lê direção do H1
- Só gera sinais BUY se H1 é BULLISH
- Só gera sinais SELL se H1 é BEARISH
- Bonus de confiança quando alinhado com H1

### 3. `src/strategies/trend_following.py` (v2.1)
**Novas funcionalidades:**
- `require_d1_alignment` - D1 deve confirmar direção
- `require_h4_alignment` - H4 deve confirmar direção
- `_get_htf_direction()` - Lê direção de D1/H4
- Bloqueia BUY se D1+H4 são BEARISH
- Bloqueia SELL se D1+H4 são BULLISH
- Bonus de confiança quando macro alinhado

### 4. `src/order_generator.py`
- Passa TechnicalAnalyzer para StrategyManager
- Habilita Market Context automaticamente

---

## 🧪 TESTE

Execute o teste completo:
```powershell
cd c:\Users\Administrator\Desktop\urion
.\venv\Scripts\Activate.ps1
python test_htf_communication.py
```

---

## 🔄 FLUXO DE OPERAÇÃO

### Antes (v2.0):
```
Scalping M5: "MACD bearish → SELL!"
TrendFollowing H1: "ADX alto + MACD bullish → BUY!"
→ CONFLITO: Bot operava nas duas direções
→ Perdas por trades contra tendência
```

### Depois (v2.1):
```
1. Market Context analisa D1+H4:
   → D1: BULLISH (ADX=35, DI+ > DI-)
   → H4: BULLISH (EMAs alinhadas)
   → DIREÇÃO MACRO: BULLISH
   → DIREÇÕES PERMITIDAS: ['BUY']

2. Scalping M5 verifica H1:
   → H1: BULLISH
   → M5 sinal seria SELL
   → BLOQUEADO: "h1_conflict_SELL_vs_BUY"

3. TrendFollowing H1 verifica D1+H4:
   → Ambos BULLISH
   → H1 indica BUY
   → PERMITIDO: BUY com bonus de confiança

→ Bot só opera BUY (na direção macro)
→ Trades mais assertivos
```

---

## 📊 REGIMES E ESTRATÉGIAS

| Regime | ADX | Estratégias Recomendadas |
|--------|-----|--------------------------|
| TRENDING_STRONG | > 35 | TrendFollowing, Scalping |
| TRENDING_WEAK | 25-35 | TrendFollowing, Breakout |
| RANGING | < 25 | MeanReversion, RangeTrading |
| CONSOLIDATION | < 20 + BB squeeze | Breakout |
| HIGH_VOLATILITY | ATR > 2x média | Evitar ou Breakout |
| LOW_VOLATILITY | ATR < 0.5x média | Não operar |

---

## 🎛️ CONFIGURAÇÃO

No `config.yaml`:
```yaml
market_context:
  adx_strong: 35
  adx_trend: 25
  atr_high: 2.0
  atr_low: 0.5

strategies:
  scalping:
    require_h1_confirmation: true
    h1_trend_weight: 0.3
    
  trend_following:
    require_d1_alignment: true
    require_h4_alignment: true
```

---

## ✅ BENEFÍCIOS

1. **Menos trades contra tendência** - Scalping não vende em alta macro
2. **Maior win rate** - Só opera quando TFs alinhados
3. **Gestão de risco adaptativa** - Risco reduz em ranging/volatilidade
4. **Estratégias complementares** - Cada uma opera no regime ideal
5. **Menos conflitos** - Uma direção por vez

---

## 🚀 PRÓXIMOS PASSOS

1. Rodar backtest com nova lógica
2. Monitorar win rate por regime
3. Ajustar thresholds baseado em resultados
4. Adicionar logs detalhados de filtragem
