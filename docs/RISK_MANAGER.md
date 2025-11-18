# 🛡️ Risk Manager

## Visão Geral

O **Risk Manager** é o módulo mais crítico do sistema Urion. Ele protege o capital através de cálculos precisos e validações rigorosas antes de cada operação.

## Funcionalidades

### 1. Position Sizing
Calcula o tamanho ideal da posição baseado em:
- Percentual de risco (padrão 2%)
- Distância do stop loss
- Saldo da conta
- Tamanho do contrato

```python
lot_size = risk_manager.calculate_position_size(
    symbol='XAUUSD',
    entry_price=1950.00,
    stop_loss=1945.00,
    risk_percent=0.02
)
```

### 2. Stop Loss Calculation
Calcula stop loss baseado em:
- ATR (Average True Range)
- Pips fixos
- Volatilidade do mercado

```python
stop_loss = risk_manager.calculate_stop_loss(
    symbol='XAUUSD',
    order_type='BUY',
    entry_price=1950.00,
    atr_value=5.0,
    atr_multiplier=1.5
)
```

### 3. Take Profit Calculation
Calcula take profit com risk/reward ratio:

```python
take_profit = risk_manager.calculate_take_profit(
    entry_price=1950.00,
    stop_loss=1945.00,
    risk_reward_ratio=2.0  # 1:2
)
```

### 4. Position Validation
Valida se pode abrir nova posição verificando:
- ✅ Limite de trades diários
- ✅ Número máximo de posições abertas
- ✅ Perda diária máxima
- ✅ Drawdown atual
- ✅ Margem disponível
- ✅ Spread do símbolo

```python
validation = risk_manager.can_open_position(
    symbol='XAUUSD',
    order_type='BUY',
    lot_size=0.01
)

if validation['allowed']:
    # Pode abrir posição
else:
    # Bloqueado: validation['reason']
```

### 5. Trailing Stop
Calcula trailing stop dinâmico:

```python
new_sl = risk_manager.calculate_trailing_stop(
    position=position,
    current_price=1955.00,
    trailing_distance=15  # pips
)
```

### 6. Break-Even
Verifica se deve mover para break-even:

```python
should_move = risk_manager.should_move_to_breakeven(
    position=position,
    current_price=1951.50
)
```

### 7. Risk Statistics
Obtém estatísticas de risco em tempo real:

```python
stats = risk_manager.get_risk_stats()
print(f"Balance: ${stats['balance']}")
print(f"Drawdown: {stats['current_drawdown_percent']}%")
print(f"Can Trade: {stats['can_trade']}")
```

## Configuração

Configure os parâmetros em `config/config.yaml`:

```yaml
risk:
  max_risk_per_trade: 0.02      # 2% por trade
  max_drawdown: 0.15             # 15% drawdown máximo
  max_daily_loss: 0.05           # 5% perda diária máxima
  stop_loss_pips: 20             # SL padrão em pips
  take_profit_multiplier: 2.0    # R:R de 1:2
  trailing_stop_distance: 15     # Trailing stop em pips
  break_even_enabled: true
  break_even_trigger: 15         # Trigger em pips

trading:
  max_open_positions: 3  # CRÍTICO: Limite de posições simultâneas
  spread_threshold: 30
```

## Exemplo de Uso

```python
from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager
from src.risk_manager import RiskManager

# Inicializar
config = ConfigManager('config/config.yaml')
mt5 = MT5Connector(config.get_all())
mt5.connect()

risk_manager = RiskManager(config.get_all(), mt5)

# Calcular trade
entry = 1950.00
sl = risk_manager.calculate_stop_loss('XAUUSD', 'BUY', entry)
tp = risk_manager.calculate_take_profit(entry, sl, 2.0)
lot_size = risk_manager.calculate_position_size('XAUUSD', entry, sl)

# Validar
validation = risk_manager.can_open_position('XAUUSD', 'BUY', lot_size)

if validation['allowed']:
    # Executar ordem
    mt5.place_order('XAUUSD', 'BUY', lot_size, sl, tp)
```

## Proteções Implementadas

### 1. Posições Simultâneas (CRÍTICO)
**Sempre ativo** - Limita número de posições abertas simultaneamente (padrão: 3).
Esta é a proteção mais importante para evitar overexposure.

### 2. Perda Diária Máxima
Para de operar se perda diária atingir limite (padrão 5%).

### 3. Drawdown Máximo
Monitora drawdown e bloqueia trading se exceder limite (padrão 15%).

### 4. Position Sizing Automático
Calcula tamanho baseado em risco fixo (padrão 2% por trade).

### 5. Validação de Margem
Verifica margem disponível antes de abrir posição.

### 6. Controle de Spread
Bloqueia trading se spread estiver muito alto.

### 7. Trailing Stop Automático
Protege lucros movendo SL conforme preço favorável.

### 8. Break-Even Automático
Move SL para entrada após atingir lucro mínimo.

## Testes

Execute os testes:

```bash
pytest tests/test_risk_manager.py -v
```

## Demo

Execute o exemplo:

```bash
python examples/risk_manager_demo.py
```

## Métricas Monitoradas

- **Balance**: Saldo da conta
- **Equity**: Patrimônio atual
- **Drawdown**: Queda do pico
- **Daily P/L**: Lucro/perda do dia
- **Daily Trades**: Trades executados hoje
- **Margin Level**: Nível de margem
- **Free Margin**: Margem livre

## Alertas

O Risk Manager registra alertas quando:
- ⚠️ Drawdown se aproxima do limite
- ⚠️ Perda diária se aproxima do limite
- ⚠️ Número de trades se aproxima do limite
- ⚠️ Margem livre está baixa
- ❌ Qualquer limite é atingido

## Boas Práticas

1. **Nunca desabilite o Risk Manager**
2. **Comece com risco baixo (1-2%)**
3. **Monitore drawdown diariamente**
4. **Ajuste parâmetros gradualmente**
5. **Teste extensivamente em demo**
6. **Revise estatísticas semanalmente**

## Fórmulas

### Position Size
```
risk_amount = balance × risk_percent
lot_size = risk_amount / (sl_distance × contract_size)
```

### Drawdown
```
drawdown = (peak_balance - current_balance) / peak_balance
```

### Risk/Reward
```
reward = risk × risk_reward_ratio
tp_distance = sl_distance × risk_reward_ratio
```

## Status

✅ **Implementado e testado**

---

**Prioridade**: ⭐⭐⭐⭐⭐ CRÍTICO  
**Status**: ✅ Completo  
**Testes**: ✅ 20 testes passando  
**Documentação**: ✅ Completa
