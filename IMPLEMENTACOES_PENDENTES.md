# URION TRADING BOT - IMPLEMENTAÇÕES NECESSÁRIAS

## Status Atual: 25/11/2025 04:03 AM

### ✅ CONCLUÍDO:
1. **Market Condition Analyzer** - Sistema inteligente de seleção de estratégias
   - Detecta 6 condições de mercado
   - Recomenda estratégias ideais automaticamente
   - Testado e funcionando

2. **Bug de Confidence** - Corrigido
   - Valores estavam corretos no banco (0.0-1.0)
   - Corrigido apenas visualização nos scripts

---

### 🔧 IMPLEMENTAÇÕES PENDENTES:

#### 1. **Integrar Market Analyzer no Bot** (CRÍTICO)
**Onde**: `src/order_generator.py` ou `src/strategies/strategy_manager.py`
**O que fazer**:
- Chamar `MarketConditionAnalyzer().analyze()` antes de gerar sinais
- Usar `get_strategy_priority()` para ajustar quais estratégias devem operar
- Desabilitar temporariamente estratégias com prioridade < 30%

**Código sugerido**:
```python
# No order_generator.py, antes do loop de estratégias:
from analysis.market_condition_analyzer import MarketConditionAnalyzer

analyzer = MarketConditionAnalyzer(self.symbol)
market_analysis = analyzer.analyze()
priorities = analyzer.get_strategy_priority(market_analysis)

# Filtrar estratégias com baixa prioridade
active_strategies = [
    strat for strat in strategies 
    if priorities.get(strat.name, 0.5) >= 0.3  # Mínimo 30% prioridade
]
```

---

#### 2. **Gestão Inteligente de Ordens por Estratégia** (CRÍTICO)
**Onde**: `src/order_manager.py`
**Problema atual**: Todas as estratégias usam MESMA gestão (trailing stop 15 pips, parcial 50%)

**O que implementar**:
```python
# Configurações ESPECÍFICAS por estratégia:

STRATEGY_CONFIGS = {
    'scalping': {
        'trailing_stop_distance': 5,    # 5 pips (mais agressivo)
        'partial_close_at': 0.3,        # 30% do TP
        'partial_close_volume': 0.5,    # Fecha 50%
        'breakeven_at': 0.2,            # Move SL para BE em 20% do TP
        'max_hold_time': 300,           # 5 minutos máximo
    },
    'range_trading': {
        'trailing_stop_distance': 10,   # 10 pips
        'partial_close_at': 0.5,
        'partial_close_volume': 0.5,
        'breakeven_at': 0.3,
        'max_hold_time': 3600,          # 1 hora
    },
    'trend_following': {
        'trailing_stop_distance': 20,   # 20 pips (deixa correr)
        'partial_close_at': 0.7,        # Aguarda mais
        'partial_close_volume': 0.3,    # Fecha menos
        'breakeven_at': 0.4,
        'max_hold_time': None,          # Sem limite
    },
    'breakout': {
        'trailing_stop_distance': 15,
        'partial_close_at': 0.6,
        'partial_close_volume': 0.4,
        'breakeven_at': 0.5,
        'max_hold_time': 7200,          # 2 horas
    },
    'mean_reversion': {
        'trailing_stop_distance': 8,
        'partial_close_at': 0.4,
        'partial_close_volume': 0.6,    # Fecha mais rápido
        'breakeven_at': 0.2,
        'max_hold_time': 1800,          # 30 minutos
    },
    'news_trading': {
        'trailing_stop_distance': 25,   # Volatilidade alta
        'partial_close_at': 0.5,
        'partial_close_volume': 0.5,
        'breakeven_at': 0.3,
        'max_hold_time': 900,           # 15 minutos
    },
}
```

**Implementação**:
1. Adicionar campo `strategy_name` nas posições monitoradas
2. Buscar config específica: `config = STRATEGY_CONFIGS.get(strategy_name, DEFAULT)`
3. Aplicar regras customizadas em `manage_position()`

---

#### 3. **Notificações Telegram - LOSS não está enviando** (CRÍTICO)
**Onde**: `src/monitoring/telegram_notifier.py` ou onde está implementado
**Problema**: Usuário não recebe notificações de trades perdedores

**Verificar**:
1. Método `send_trade_closed()` está sendo chamado para WINS e LOSSES?
2. Tem filtro que impede envio de LOSS?
3. Log mostra "Telegram message sent" para ambos?

**Solução**: Garantir que TODAS as atualizações de `update_trade_close()` disparem notificação:
```python
# Em order_manager.py, após close_data ser salvo:
if final_profit > 0:
    logger.success(f"✅ WIN: ${final_profit:.2f}")
    telegram_notifier.send_trade_closed(ticket, strategy, "WIN", final_profit)
elif final_profit < 0:
    logger.error(f"🔴 LOSS: ${final_profit:.2f}")
    telegram_notifier.send_trade_closed(ticket, strategy, "LOSS", final_profit)
else:
    logger.info(f"⚪ BREAK-EVEN: $0.00")
    telegram_notifier.send_trade_closed(ticket, strategy, "BE", 0)
```

---

#### 4. **Sistema de Relatórios Automáticos** (IMPORTANTE)
**O que criar**: 3 novos arquivos

**a) `src/reporting/daily_report.py`**
- Executar diariamente às 23:59
- Performance do dia por estratégia
- Win rate, profit, drawdown
- Melhores e piores trades
- Enviar por Telegram

**b) `src/reporting/weekly_report.py`**
- Executar domingo 23:59
- Comparativo semana vs semana anterior
- Ranking de estratégias
- Análise de tendências
- PDF + Telegram

**c) `src/reporting/monthly_report.py`**
- Executar último dia do mês 23:59
- Relatório completo mensal
- Gráficos de equity curve
- Performance acumulada
- PDF detalhado + Telegram

**Estrutura sugerida**:
```python
class DailyReport:
    def __init__(self, db_path, telegram_bot):
        ...
    
    def generate(self, date=None):
        # 1. Coletar trades do dia
        # 2. Calcular métricas por estratégia
        # 3. Identificar melhores/piores
        # 4. Formatar mensagem
        # 5. Enviar Telegram
        ...
    
    def schedule(self):
        # Agendar para 23:59 todo dia
        schedule.every().day.at("23:59").do(self.generate)
```

---

#### 5. **Verificação SL/TP Real** (VALIDAÇÃO)
**O que fazer**: Script para analisar últimos 50 trades e confirmar:
- SL está sendo aplicado em $50 do entry?
- TP está sendo aplicado em $150 do entry?
- Trailing stop está funcionando?
- Fechamento parcial está acontecendo?

**Script**: `verificar_sl_tp_reais.py`
```python
# Buscar últimos 50 trades no banco
# Para cada trade:
#   - Calcular SL esperado vs SL real
#   - Calcular TP esperado vs TP real
#   - Verificar se teve trailing (SL modificado)
#   - Verificar se teve parcial (volume reduzido)
# Relatório com discrepâncias
```

---

#### 6. **ML Learning Data - Não está criando** (IMPORTANTE)
**Onde**: `src/ml/strategy_learner.py`
**Problema**: Arquivo `data/ml_learning_data.json` não existe

**Verificar**:
1. Método `learn_from_trade()` está sendo chamado?
2. Tem permissão para criar arquivo?
3. Diretório `data/` existe?
4. Log mostra "Learning from trade"?

**Solução**:
1. Adicionar log verbose em StrategyLearner
2. Garantir que `learn_from_trade()` seja chamado em `update_trade_close()`
3. Criar `data/` se não existir
4. Salvar JSON após cada aprendizado

---

### 📋 ORDEM DE PRIORIDADE:

1. **URGENTE** - Notificações Telegram de LOSS
2. **URGENTE** - Integrar Market Analyzer no bot
3. **ALTA** - Gestão inteligente por estratégia
4. **ALTA** - Relatórios automáticos (começar pelo diário)
5. **MÉDIA** - ML Learning Data
6. **BAIXA** - Verificação SL/TP (validação)

---

### ⚙️ CONFIGURAÇÕES ADICIONAIS SUGERIDAS:

**Em `config/config.yaml`, adicionar**:
```yaml
market_analysis:
  enabled: true
  update_interval: 300  # 5 minutos
  min_priority_threshold: 0.3  # 30% mínimo para operar
  
reporting:
  daily_report:
    enabled: true
    time: "23:59"
    telegram: true
  weekly_report:
    enabled: true
    day: "sunday"
    time: "23:59"
    telegram: true
    pdf: true
  monthly_report:
    enabled: true
    time: "23:59"
    telegram: true
    pdf: true

telegram:
  send_wins: true
  send_losses: true  # ⚠️ VERIFICAR SE ESTÁ TRUE
  send_breakeven: true
  send_reports: true
```

---

### 🎯 RESULTADO ESPERADO APÓS IMPLEMENTAÇÕES:

1. **Bot seleciona estratégias automaticamente** baseado em condições
   - Range/Scalping em lateralização
   - Trend/Breakout em tendências
   - News em alta volatilidade

2. **Cada estratégia gerencia suas ordens de forma única**
   - Scalping: rápido, trailing agressivo
   - Trend Following: deixa correr, trailing largo
   - Range: médio prazo

3. **Usuário recebe notificações de TODOS os fechamentos**
   - WIN, LOSS e BREAK-EVEN
   - Via Telegram instantâneo

4. **Relatórios automáticos diários/semanais/mensais**
   - Performance detalhada
   - Rankings
   - Análises de melhoria

5. **Sistema aprende e ajusta confiança mínima**
   - ML learning data sendo criado
   - Estratégias ruins têm confiança aumentada
   - Estratégias boas mantêm confiança ideal

---

### 📝 PRÓXIMOS PASSOS IMEDIATOS:

1. Testar notificações Telegram manualmente
2. Integrar Market Analyzer (15 minutos)
3. Adicionar configs por estratégia (30 minutos)
4. Criar daily_report.py (1 hora)
5. Testar sistema completo
6. Colocar bot online

---

**Última atualização**: 25/11/2025 04:03 AM
**Desenvolvedor**: GitHub Copilot
**Status**: Aguardando aprovação para implementação
