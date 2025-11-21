# 🚨 PLANO DE CORREÇÃO CRÍTICA DO BOT

## PROBLEMAS IDENTIFICADOS

### 1. Bot operando 100% em SELL (contra tendência de alta)
- Últimos 30 trades: TODOS SELL
- Preço subiu 4040 → 4087 (+47pts = +1.15%)
- Prejuízo estimado: ~20% da banca

### 2. Range Trading mal configurado
- Vendendo na resistência DEPOIS da subida
- Sem aguardar retorno ao suporte
- Ignorando contexto de timeframes maiores

### 3. Sem filtro de tendência primária
- Operando range em M5 sem ver H1/H4
- Vendendo em tendência de alta confirmada

### 4. Confiança muito baixa (52.5%)
- Aceitando sinais fracos demais
- Mínimo deve ser 60-65%

### 5. Sem controle de drawdown
- Continua abrindo posições perdendo dinheiro

## CORREÇÕES PRIORITÁRIAS

### URGENTE: Parar o bot
```bash
Get-Process python | Stop-Process -Force
```

### CRÍTICO 1: Adicionar filtro de tendência primária
**Arquivo:** `src/strategies/range_trading.py`

Adicionar verificação de EMA 50/200 em M15:
- Se EMA50 > EMA200: Tendência de ALTA → Só BUY no suporte
- Se EMA50 < EMA200: Tendência de BAIXA → Só SELL na resistência
- Se EMAs próximas: Pode operar range normal

### CRÍTICO 2: Aumentar confiança mínima
**Arquivo:** `config/config.yaml`

```yaml
strategies:
  range_trading:
    min_confidence: 0.65  # Era 0.50 → Aumentar para 65%
```

### CRÍTICO 3: Adicionar limite de drawdown
**Arquivo:** `src/core/risk_manager.py`

Adicionar verificação antes de abrir posição:
```python
def can_open_position():
    # Calcular drawdown diário
    daily_pnl = get_daily_profit()
    if daily_pnl < -100:  # -$100 por dia
        return False, "daily_loss_limit_reached"
```

### CRÍTICO 4: Filtro de mercado unidirecional
**Arquivo:** `src/core/strategy_executor.py`

Adicionar análise de "market_bias":
```python
# Se últimos 5 trades foram SELL e todos perderam
# → Inverter lógica ou PAUSAR

# Se preço subiu >0.5% nas últimas 2 horas
# → Não vender, só comprar em pullback
```

### IMPORTANTE 5: Melhorar lógica Range Trading
**Arquivo:** `src/strategies/range_trading.py`

SELL só se:
- Preço tocou banda superior (resistência)
- RSI > 65 (não 55-65)
- Stoch > 80 (não 70)
- **E preço estava ABAIXO há menos de 1 hora** (não vender depois de alta forte)

BUY só se:
- Preço tocou banda inferior (suporte)
- RSI < 35 (não 35-45)
- Stoch < 20 (não 30)
- **E preço estava ACIMA há menos de 1 hora**

### IMPORTANTE 6: Log detalhado de decisões
Adicionar logging completo:
```python
logger.warning(f"RANGE SELL rejected: price rallied {price_change_1h:.1f}% in last hour")
logger.info(f"Market bias: {bias} (EMA50: {ema50}, EMA200: {ema200})")
```

## VALIDAÇÃO PÓS-CORREÇÃO

1. Backtest em dados históricos (últimas 2 semanas)
2. Verificar se detecta tendências corretamente
3. Testar em conta demo por 24h
4. Monitorar que NÃO abra 10 trades seguidos na mesma direção

## MÉTRICAS DE SUCESSO

- Win rate > 50%
- Max 2 trades consecutivos na mesma direção perdendo
- Drawdown máximo < 5% por dia
- Mix saudável de BUY/SELL (40-60% cada)

## TIMELINE

1. **AGORA**: Parar bot
2. **Próxima 1h**: Implementar filtros críticos (1, 2, 3)
3. **Próximas 2h**: Melhorar lógica range (5)
4. **Hoje**: Testar em demo
5. **Amanhã**: Liberar para produção SE validado

---

**NOTA**: Bot está perdendo dinheiro sistematicamente. DEVE ser parado imediatamente até correções serem aplicadas.
