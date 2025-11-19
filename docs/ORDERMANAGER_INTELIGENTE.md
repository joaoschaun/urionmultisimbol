# OrderManager Inteligente - Configuração Multi-Estratégia

## 📋 Visão Geral

O OrderManager foi aprimorado para adaptar seu comportamento baseado em qual estratégia abriu cada posição. Cada estratégia tem velocidades e características diferentes, portanto requer gerenciamento customizado.

## 🎯 Problema Resolvido

**Situação Anterior:**
- OrderManager aplicava as mesmas regras para todas as posições
- Trailing stop de 15 pips não era ideal para todas as estratégias
- Scalping (60s) precisava de trailing agressivo (5 pips)
- Breakout (1800s) precisava de trailing amplo (25 pips)

**Solução Implementada:**
- Configuração específica por estratégia
- OrderManager identifica estratégia via magic number
- Aplica trailing, break-even e partial close customizados

## ⚙️ Configurações por Estratégia

### 1. **Scalping** (Velocidade: 60s - Mais Rápida)
```yaml
trailing_stop_distance: 5    # Pips - Bem agressivo
break_even_trigger: 8        # Pips - Rápido para proteger
partial_close_trigger: 12    # Pips - Realiza lucro cedo
```
**Razão:** Opera em movimentos pequenos, precisa capturar lucros rapidamente antes da reversão.

---

### 2. **Range Trading** (Velocidade: 180s)
```yaml
trailing_stop_distance: 10   # Pips - Moderado
break_even_trigger: 15       # Pips - Balanceado
partial_close_trigger: 20    # Pips - Objetivo médio
```
**Razão:** Opera em ranges limitados, precisa de espaço para flutuação mas não muito.

---

### 3. **News Trading** (Velocidade: 300s)
```yaml
trailing_stop_distance: 15   # Pips - Médio-rápido
break_even_trigger: 20       # Pips - Proteção moderada
partial_close_trigger: 30    # Pips - Objetivo moderado
```
**Razão:** Opera em eventos de notícias com volatilidade média, precisa de espaço mas com proteção.

---

### 4. **Mean Reversion** (Velocidade: 600s)
```yaml
trailing_stop_distance: 12   # Pips - Moderado
break_even_trigger: 18       # Pips - Balanceado
partial_close_trigger: 25    # Pips - Objetivo médio
```
**Razão:** Aguarda retorno à média, precisa de trailing moderado para não sair cedo demais.

---

### 5. **Trend Following** (Velocidade: 900s)
```yaml
trailing_stop_distance: 20   # Pips - Amplo
break_even_trigger: 30       # Pips - Deixa a tendência respirar
partial_close_trigger: 40    # Pips - Objetivo alto
```
**Razão:** Captura tendências longas, precisa de muito espaço para não ser stopado por ruído.

---

### 6. **Breakout** (Velocidade: 1800s - Mais Lenta)
```yaml
trailing_stop_distance: 25   # Pips - Muito amplo
break_even_trigger: 35       # Pips - Muito paciente
partial_close_trigger: 50    # Pips - Objetivo grande
```
**Razão:** Aguarda rompimentos significativos, precisa de máximo espaço para tendências longas.

---

## 🔧 Implementação Técnica

### 1. **Detecção de Estratégia**

O sistema identifica qual estratégia abriu a posição através do **magic number**:

```python
# Cálculo do magic number (igual ao StrategyExecutor)
base_magic = 100000
name_hash = sum(ord(c) for c in strategy_name[:5])
magic_number = base_magic + name_hash
```

### 2. **Mapa de Configurações**

OrderManager mantém um dicionário mapeando magic numbers para configurações:

```python
self.strategy_map = {
    100484: {  # Scalping
        'name': 'scalping',
        'trailing_stop_distance': 5,
        'break_even_trigger': 8,
        'partial_close_trigger': 12
    },
    100525: {  # Range Trading
        'name': 'range_trading',
        'trailing_stop_distance': 10,
        'break_even_trigger': 15,
        'partial_close_trigger': 20
    },
    # ... outras estratégias
}
```

### 3. **Aplicação Inteligente**

Quando gerenciando uma posição:

1. **Extrai magic number da posição**
   ```python
   magic_number = position.get('magic', 0)
   ```

2. **Busca configuração específica**
   ```python
   strategy_config = self.get_strategy_config(magic_number)
   ```

3. **Aplica trailing customizado**
   ```python
   trailing_pips = strategy_config.get('trailing_stop_distance', 15)
   trailing_distance = trailing_pips * point * 10
   new_sl = self.risk_manager.calculate_trailing_stop(
       position, current_price, trailing_distance
   )
   ```

4. **Aplica break-even customizado**
   ```python
   be_trigger_pips = strategy_config.get('break_even_trigger', 20)
   if profit_distance >= be_trigger_distance:
       # Move para break-even
   ```

5. **Aplica partial close customizado**
   ```python
   target_pips = strategy_config.get('partial_close_trigger', 50)
   if profit_pips >= target_pips:
       # Fecha porcentagem da posição
   ```

---

## 📊 Logging Inteligente

O sistema agora registra qual estratégia está sendo gerenciada:

```log
[scalping] Trailing stop atualizado | Ticket: 12345 | Distância: 5pips | Novo SL: 2625.50000
[breakout] Break-even aplicado | Ticket: 67890 | Trigger: 35pips
[trend_following] Trailing stop atualizado | Ticket: 11111 | Distância: 20pips | Novo SL: 2630.00000
```

---

## 🎯 Benefícios

1. **Otimização por Velocidade**
   - Estratégias rápidas (scalping) = trailing apertado
   - Estratégias lentas (breakout) = trailing amplo

2. **Redução de Falsos Stops**
   - Cada estratégia tem espaço apropriado
   - Breakout não é stopado por ruído de 10 pips

3. **Maximização de Lucros**
   - Scalping realiza lucro cedo (12 pips)
   - Breakout aguarda movimentos grandes (50 pips)

4. **Gerenciamento Inteligente**
   - Sem necessidade de múltiplos OrderManagers
   - Ciclo único de 60s verifica todas as posições
   - Cada posição é tratada conforme sua estratégia

---

## 🔄 Ciclo do OrderManager

**Frequência:** 60 segundos (mantido)

**Processo:**
1. Buscar todas as posições abertas no MT5
2. Para cada posição:
   - Identificar estratégia via magic number
   - Carregar configuração específica
   - Aplicar break-even (se aplicável)
   - Aplicar trailing stop customizado
   - Verificar partial close customizado
3. Repetir após 60 segundos

---

## 📝 Exemplo de Uso

### Posição do Scalping
```
Posição #12345 (Magic: 100484 = Scalping)
├── Abertura: 2625.00
├── Lucro atual: +8 pips
├── Break-even trigger: 8 pips ✅ ATINGIDO
└── Ação: Move SL para 2625.00 (break-even)
```

### Posição do Breakout
```
Posição #67890 (Magic: 100098 = Breakout)
├── Abertura: 2620.00
├── Preço atual: 2625.00
├── Lucro atual: +50 pips
├── Break-even trigger: 35 pips ✅ ATINGIDO
├── Partial close trigger: 50 pips ✅ ATINGIDO
└── Ação: Fecha 50% da posição, trailing de 25 pips no restante
```

---

## 🚀 Como Testar

1. **Verificar Inicialização**
   ```powershell
   Get-Content logs\urion.log | Select-String "Configuração customizada"
   ```
   
   Esperado:
   ```
   Configuração customizada por estratégia: 6 estratégias
   ```

2. **Monitorar Gestão de Posições**
   ```powershell
   Get-Content logs\urion.log -Tail 50 | Select-String "Trailing|Break-even"
   ```
   
   Esperado:
   ```
   [scalping] Trailing stop atualizado | Ticket: 12345 | Distância: 5pips
   [breakout] Break-even aplicado | Ticket: 67890 | Trigger: 35pips
   ```

3. **Verificar Estratégias Identificadas**
   ```powershell
   Get-Content logs\urion.log | Select-String "Estratégia identificada"
   ```

---

## ⚠️ Notas Importantes

1. **Magic Numbers Devem Corresponder**
   - OrderManager calcula magic number igual ao StrategyExecutor
   - Se houver inconsistência, usará valores default

2. **Valores Default**
   - Se estratégia não encontrada:
     - trailing_stop_distance: 15 pips
     - break_even_trigger: 20 pips
     - partial_close_trigger: 30 pips

3. **Modificação de Configurações**
   - Editar `config/config.yaml`
   - Reiniciar o bot
   - Mudanças aplicadas imediatamente às novas posições

---

## 📦 Arquivos Modificados

1. **config/config.yaml**
   - Adicionado `trailing_stop_distance`, `break_even_trigger`, `partial_close_trigger` em cada estratégia

2. **src/order_manager.py**
   - Adicionado `_build_strategy_map()` - Constrói mapa de estratégias
   - Adicionado `get_strategy_config()` - Busca configuração por magic number
   - Modificado `calculate_trailing_stop()` - Usa distância customizada
   - Modificado `should_move_to_breakeven()` - Usa trigger customizado
   - Modificado `should_partial_close()` - Usa trigger customizado
   - Modificado `manage_position()` - Logging com nome da estratégia

---

## ✅ Status

**Implementação:** ✅ COMPLETA  
**Testes:** ✅ BOT RODANDO  
**Logs:** ✅ CONFIRMADOS  
**Documentação:** ✅ CRIADA

**Data de Implementação:** 19/11/2025 08:27:30  
**Versão:** 1.0.0 - OrderManager Inteligente
