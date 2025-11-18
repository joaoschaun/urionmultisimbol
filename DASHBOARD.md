# 📊 Dashboard de Performance de Estratégias

Sistema completo de tracking e análise de performance das estratégias de trading.

## 🎯 Funcionalidades

### 1. Tracking Automático
- ✅ Salva automaticamente cada trade executado
- ✅ Registra estratégia, preço, SL, TP, confidence
- ✅ Atualiza resultado quando trade é fechado
- ✅ Calcula estatísticas em tempo real

### 2. Banco de Dados SQLite
Três tabelas principais:

#### `strategy_trades`
- Todos os trades executados
- Dados de abertura e fechamento
- Lucro/perda individual
- Confidence do sinal
- Condições de mercado

#### `strategy_daily_stats`
- Estatísticas diárias por estratégia
- Win rate, profit factor
- Média de ganho/perda
- Total de trades

#### `strategy_weekly_ranking`
- Ranking semanal salvo
- Score calculado (0-100)
- Comparação histórica
- Status (ativo/desativado)

### 3. Dashboard Interativo
```bash
python dashboard.py
```

**Menu Principal:**
1. 📈 Ver Ranking Atual (7 dias)
2. 📊 Ver Ranking (30 dias)
3. 📅 Evolução Histórica (4 semanas)
4. 💾 Salvar Ranking Semanal
5. 🔄 Atualizar (Auto-refresh)
6. 🚪 Sair

### 4. Sistema de Pontuação

**Score (0-100 pontos):**
- Win Rate: até 40 pontos
- Profit Factor: até 30 pontos
- Lucro Líquido: até 20 pontos
- Confidence Média: até 10 pontos

**Classificação:**
- 🟢 70-100: Excelente
- 🟡 50-69: Bom
- 🟠 30-49: Regular
- 🔴 0-29: Fraco

## 📈 Como Usar

### Iniciar Tracking Automático
O tracking é automático! Quando o bot roda:
1. Cada ordem executada é salva
2. Ao fechar, resultado é atualizado
3. Estatísticas calculadas automaticamente

### Visualizar Dashboard
```bash
# Dashboard interativo
python dashboard.py

# Ver ranking atual
# Escolha opção 1

# Ver histórico
# Escolha opção 3

# Auto-refresh (atualiza a cada 30s)
# Escolha opção 5
```

### Análise Semanal
Recomendado: Todo domingo, execute:
```bash
python dashboard.py
# Escolha opção 4 para salvar ranking semanal
```

## 📊 Exemplo de Ranking

```
🏆 RANKING DE ESTRATÉGIAS
═══════════════════════════════════════════════════════════════
#  | Estratégia      | Score | Trades | Win%  | P.Factor | Lucro     | Status
───┼─────────────────┼───────┼────────┼───────┼──────────┼───────────┼────────────
1  | RangeTrading    | 78.5  | 15     | 66.7% | 2.3      | $125.50   | 🟢 Excelente
2  | Scalping        | 65.2  | 23     | 60.9% | 1.8      | $98.30    | 🟡 Bom
3  | MeanReversion   | 58.7  | 12     | 58.3% | 1.5      | $75.20    | 🟡 Bom
4  | TrendFollowing  | 45.3  | 8      | 50.0% | 1.2      | $35.10    | 🟠 Regular
5  | Breakout        | 38.1  | 6      | 50.0% | 1.0      | $12.50    | 🟠 Regular
6  | NewsTrading     | 25.8  | 4      | 25.0% | 0.6      | -$45.80   | 🔴 Fraco
```

## 🔍 Detalhes das Estratégias

Para cada estratégia no Top 3:
- Total de trades
- Trades ganhos/perdidos
- Win rate
- Profit factor
- Lucro líquido
- Média de ganho/perda
- Maior ganho/perda
- Confidence média

## 💡 Recomendações Automáticas

O dashboard gera recomendações:

### 🔴 Estratégias Fracas (Score < 30)
```
Considere DESATIVAR:
• NewsTrading (Score: 25.8)
```

### 🟢 Estratégias Excelentes (Score >= 70)
```
Mantenha ATIVAS:
• RangeTrading (Score: 78.5)
• Scalping (Score: 72.3)
```

### ⚠️ Baixa Atividade (< 5 trades)
```
Estratégias com poucos dados:
• Breakout (4 trades)
```

## 📅 Análise Histórica

Veja evolução semanal:
- Rank de cada estratégia
- Trades executados
- Win rate
- Lucro
- Score

Identifique:
- ✅ Estratégias consistentes
- ❌ Estratégias em queda
- 📈 Estratégias melhorando
- 📉 Estratégias piorando

## 🗄️ Localização dos Dados

```
urion/
├── data/
│   └── strategy_stats.db    # Banco SQLite
├── src/
│   └── database/
│       └── strategy_stats.py # Manager do database
└── dashboard.py              # Dashboard visual
```

## 🔧 Integração no Bot

### Strategy Executor
Salva automaticamente ao executar ordem:
```python
# Após place_order()
self.stats_db.save_trade({
    'strategy_name': self.strategy_name,
    'ticket': ticket,
    'symbol': self.symbol,
    'type': action,
    'volume': volume,
    'open_price': signal['price'],
    'sl': sl,
    'tp': tp,
    'signal_confidence': signal['confidence'] * 100
})
```

### Order Manager
Atualiza ao fechar posição:
```python
# Após close_position()
self.stats_db.update_trade_close(ticket, {
    'close_price': position['price_current'],
    'close_time': datetime.now(),
    'profit': position['profit']
})
```

## 📱 Comandos Rápidos

```bash
# Ver ranking atual (7 dias)
python -c "from src.database.strategy_stats import StrategyStatsDB; db = StrategyStatsDB(); [print(f'{s[\"rank\"]}. {s[\"strategy_name\"]}: {s[\"score\"]:.1f}') for s in db.get_all_strategies_ranking(7)]"

# Salvar ranking semanal
python -c "from src.database.strategy_stats import StrategyStatsDB; StrategyStatsDB().save_weekly_ranking(); print('✅ Ranking salvo!')"

# Ver stats de uma estratégia
python -c "from src.database.strategy_stats import StrategyStatsDB; import json; print(json.dumps(StrategyStatsDB().get_strategy_stats('RangeTrading', 7), indent=2))"
```

## 🎯 Fluxo de Uso Recomendado

### Diário:
1. Bot roda automaticamente
2. Trades salvos no database
3. Estatísticas atualizadas em tempo real

### Semanal (Domingo):
1. Abrir dashboard: `python dashboard.py`
2. Ver ranking completo (opção 1)
3. Salvar ranking semanal (opção 4)
4. Analisar recomendações
5. Desativar estratégias fracas no `config.yaml`

### Mensal:
1. Ver ranking 30 dias (opção 2)
2. Ver evolução histórica (opção 3)
3. Ajustar parâmetros das estratégias
4. Otimizar baseado em performance

## 🔄 Auto-Refresh

Modo ideal para monitoramento contínuo:
```bash
python dashboard.py
# Escolha opção 5
# Dashboard atualiza a cada 30 segundos
# Pressione Ctrl+C para sair
```

## 📊 Métricas Calculadas

- **Win Rate**: % de trades ganhos
- **Profit Factor**: Total ganho / Total perdido
- **Avg Win**: Média de ganho por trade ganho
- **Avg Loss**: Média de perda por trade perdido
- **Net Profit**: Lucro líquido total
- **Confidence**: Média de confiança dos sinais
- **Score**: Pontuação composta (0-100)

## 🎨 Interface do Dashboard

- 🏆 Ranking visual com cores
- 📊 Tabelas formatadas
- 🟢🟡🔴 Status por cor
- 📈 Estatísticas detalhadas
- 💡 Recomendações inteligentes
- 🔄 Auto-refresh opcional

## ⚠️ Observações

- Database criado automaticamente na primeira execução
- Dados persistem entre restarts do bot
- Backup recomendado do arquivo `strategy_stats.db`
- Análise requer mínimo 5 trades por estratégia
- Score é relativo ao período analisado

## 🚀 Próximos Passos

Após 1 semana de operação:
1. Analise ranking
2. Desative estratégias com score < 30
3. Aumente ciclo de estratégias fracas
4. Mantenha apenas Top 3-4 estratégias
5. Otimize parâmetros baseado em dados

---

**Dashboard criado para decisões baseadas em dados reais! 📊✨**
