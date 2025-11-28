# 📋 CONFIGURAÇÃO ATUAL DAS ESTRATÉGIAS

**Atualizado:** 21/11/2025 13:05  
**Status:** Conta DEMO (tratada como REAL)  
**Versão:** Com correções de distanciamento e scalping

---

## 🎯 VISÃO GERAL

### Ciclos Independentes e Simultâneos: ✅ SIM

Cada estratégia opera em **thread própria** com análise independente:

```
┌─────────────────────┐
│  Order Generator    │
│   (Multi-Thread)    │
└─────────┬───────────┘
          │
    ┌─────┴─────────────────────────────────┐
    │                                       │
    ▼                                       ▼
[Trend Following Thread]            [Scalping Thread]
  Ciclo: 10 min                      Ciclo: 2 min
  Max: 2 posições                    Max: 1 posição
    │                                       │
    ▼                                       ▼
[Mean Reversion Thread]             [Range Trading Thread]
  Ciclo: 10 min                      Ciclo: 5 min
  Max: 2 posições                    Max: 1 posição
    │                                       │
    ▼                                       ▼
[Breakout Thread]                   [News Trading Thread]
  Ciclo: 30 min                      Ciclo: 5 min
  Max: 2 posições                    Max: 2 posições
```

---

## 📊 TABELA DE CONFIGURAÇÕES

| # | Estratégia | Enabled | Timeframe | Ciclo (s) | Max Pos | Min Conf | Características |
|---|------------|---------|-----------|-----------|---------|----------|-----------------|
| 1 | **Trend Following** | ✅ | H1 | 600 (10min) | 2 | 70% | EMA12/26, ADX>25, Stop dinâmico 25 pips |
| 2 | **Mean Reversion** | ✅ | M15 | 600 (10min) | 2 | 70% | Bollinger, RSI 30/70, Stop 15 pips |
| 3 | **Breakout** | ✅ | M30 | 1800 (30min) | 2 | 75% | Suporte/Resistência, Volume 1.5x, Stop 30 pips |
| 4 | **News Trading** | ✅ | - | 300 (5min) | 2 | 80% | Alto impacto, Sentiment>70%, Stop 20 pips |
| 5 | **Scalping** | ✅ | M5 | 120 (2min) | 1 | 60% | RSI 35-65, MACD, Stoch, Stop 4 pips |
| 6 | **Range Trading** | ✅ | M5 | 300 (5min) | 1 | 70% | ADX<25, H1 filter, Stop 18 pips |

**Total Max Simultâneo:** 4 posições (limite global)

---

## 🛡️ SISTEMA DE PROTEÇÃO

### 1. **Limites Gerais**
- ✅ Max posições globais: **4** (reduzido de 6)
- ✅ Max drawdown diário: **8%** (stop total)
- ✅ Max loss diário: **5%** (pausa)
- ✅ Risk por trade: **2%** da conta

### 2. **Proteção Contra Perdas Consecutivas**
- ✅ Após **3 perdas** consecutivas → **Pausa de 60 minutos**
- ✅ Reset automático ao ganhar
- ✅ Log: "🛑 PAUSA ATIVADA! 3 perdas consecutivas"

### 3. **Proteção Multi-Timeframe (Range Trading)**
- ✅ Verifica tendência H1 antes de operar
- ✅ Se H1 ADX>15 e trend_strength>0.6 → **BLOQUEIA** operação
- ✅ Se H1 em alta → penaliza SELL (-20%)
- ✅ Se H1 em baixa → penaliza BUY (-20%)

### 4. **🆕 DISTANCIAMENTO MÍNIMO ENTRE ORDENS**
- ✅ **20 pips** mínimo entre ordens da mesma estratégia
- ✅ Impede duplicação de exposição (ex: SELL @ 4087.50 e 4087.55)
- ✅ Valida via `magic_number` (cada estratégia tem o seu)
- ✅ Log: "Ordem muito próxima de posição existente - X pips < 20 pips mínimo"

### 5. **Alerta de Travamento Direcional**
- ✅ Se 8+ dos últimos 10 trades forem mesma direção → **ALERTA**
- ✅ Log: "⚠️ ALERTA: 8/10 últimos trades são BUY/SELL - Bot pode estar travado!"

---

## 🔧 CORREÇÕES APLICADAS (21/11/2025)

### A. **Scalping - Critérios Relaxados**

**ANTES (impossível gerar sinais):**
```yaml
cycle_seconds: 60
max_positions: 2
min_confidence: 0.65
rsi_min: 40
rsi_max: 60
min_momentum: 0.0002
```

**DEPOIS (mais realista):**
```yaml
cycle_seconds: 120      # 2min (menos agressivo)
max_positions: 1        # Apenas 1 por vez
min_confidence: 0.60    # 65% → 60% (menos restritivo)
rsi_min: 35            # 40 → 35 (faixa mais ampla)
rsi_max: 65            # 60 → 65 (faixa mais ampla)
min_momentum: 0.00015  # 0.0002 → 0.00015 (menos restritivo)
```

**Impacto:** Scalping agora pode gerar sinais em condições normais de mercado.

---

### B. **Distanciamento Mínimo Implementado**

**Novo método em `risk_manager.py`:**
```python
def check_position_spacing(
    symbol, magic_number, proposed_entry, min_distance_pips=20.0
):
    # Busca posições existentes da mesma estratégia
    # Calcula distância em pips
    # Bloqueia se < 20 pips
```

**Fluxo:**
1. Estratégia gera sinal (ex: SELL @ 4087.50)
2. `strategy_executor` chama `risk_manager.can_open_position()`
3. Risk Manager verifica:
   - ✅ Pausa ativa? (perdas consecutivas)
   - ✅ **Distância de outras posições da mesma estratégia?**
   - ✅ Max posições?
   - ✅ Drawdown?
4. Se tudo OK → Executa ordem

---

### C. **Max Posições Reduzido**

```yaml
max_open_positions: 4  # Era 6
```

**Justificativa:**
- 4 posições × 0.01 lote × ~$100 loss potencial = **-$400 máximo** (8% de $5000)
- Alinhado com limite de drawdown de 8%
- Mais conservador para fase de testes DEMO

---

## 📈 COMO VALIDAR SE ESTÁ FUNCIONANDO

### 1. **Verificar Scalping Gerando Sinais**
```powershell
Get-Content "logs\urion.log" -Tail 100 | Select-String "Scalping: (BUY|SELL)"
```
**Esperado:** Ver sinais de scalping com confiança 60-85%

### 2. **Verificar Distanciamento**
```powershell
Get-Content "logs\urion.log" -Tail 100 | Select-String "muito próxima|distance"
```
**Esperado:** Se bot tentar abrir ordem < 20 pips, ver rejeição

### 3. **Verificar Proteção de Perdas**
```powershell
Get-Content "logs\urion.log" | Select-String "Perda consecutiva|PAUSA ATIVADA"
```
**Esperado:** Após 3 perdas, ver "🛑 PAUSA ATIVADA! 3 perdas consecutivas"

### 4. **Verificar Distribuição de Estratégias**
```powershell
python ver_trades.py
```
**Esperado:** Ver trades de múltiplas estratégias (não só Range Trading)

---

## ⚠️ RISCOS RESIDUAIS (MONITORAR)

### 1. **Scalping ainda pode ser ineficaz**
- Critérios relaxados, mas ainda precisa de 3-4 confirmações
- Target: 8 pips / Stop: 4 pips = R:R 2:1 (bom, mas precisa acertar >50%)
- **Ação:** Monitorar win rate de Scalping após 20 trades

### 2. **4 posições simultâneas = alta exposição**
- Se todas abrirem em momento desfavorável = -$400
- **Ação:** Verificar se drawdown de 8% é atingido frequentemente

### 3. **Range Trading ainda domina frequência**
- Ciclo: 5min (300s) vs Trend Following 10min (600s)
- **Ação:** Se Range Trading continuar dominando (>50% trades), reduzir cycle_seconds para 600s

### 4. **News Trading com critério 80%**
- Muito restritivo, pode nunca gerar sinais
- **Ação:** Monitorar. Se 0 sinais em 1 semana, considerar reduzir para 70%

---

## ✅ CHECKLIST PRÉ-VALIDAÇÃO CONCLUÍDO

| Item | Status | Detalhe |
|------|--------|---------|
| ✅ Ciclos independentes | **OK** | Cada estratégia em thread própria |
| ✅ Max posições por estratégia | **OK** | 1-2 dependendo da estratégia |
| ✅ Max posições global | **OK** | 4 (reduzido de 6) |
| ✅ Proteção perdas consecutivas | **OK** | Pausa após 3 perdas |
| ✅ Filtro multi-timeframe | **OK** | Range Trading com H1 |
| ✅ **Distanciamento mínimo** | **✅ IMPLEMENTADO** | 20 pips entre ordens mesma estratégia |
| ✅ **Scalping funcional** | **✅ CORRIGIDO** | Critérios relaxados |

---

## 🎯 PRÓXIMOS PASSOS

1. **Monitorar por 2 horas** no DEMO
2. **Validar:**
   - Scalping gera sinais? (esperar 2-3 sinais)
   - Distanciamento bloqueia ordens próximas? (testar intencionalmente)
   - Proteção de perdas ativa? (se ocorrerem 3 perdas)
   - Distribuição equilibrada? (ver trades de 3+ estratégias)
3. **Ajustes finos** conforme resultados
4. **Liberar para conta REAL** somente após validação completa

---

**Bot atualmente rodando com essas configurações!** 🚀

