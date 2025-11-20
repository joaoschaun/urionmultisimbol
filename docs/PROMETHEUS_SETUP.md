# 📊 Prometheus Monitoring Setup

## Visão Geral

O Urion Trading Bot exporta métricas no formato Prometheus para monitoramento completo em tempo real.

## Métricas Disponíveis

### 📈 Trades
- `urion_trades_total` - Total de trades executados (por estratégia, ação, símbolo)
- `urion_trades_profit_usd` - Lucro total em USD (por estratégia)
- `urion_trade_duration_minutes` - Duração dos trades em minutos

### 💼 Posições
- `urion_positions_open` - Número de posições abertas
- `urion_position_profit_usd` - Lucro/perda da posição

### 💰 Conta
- `urion_account_balance_usd` - Saldo da conta
- `urion_account_equity_usd` - Equity da conta
- `urion_account_margin_usd` - Margem utilizada
- `urion_account_margin_free_usd` - Margem livre
- `urion_account_profit_usd` - Lucro/perda total
- `urion_account_drawdown_percent` - Drawdown atual

### 🎯 Estratégias
- `urion_strategy_win_rate` - Taxa de acerto (0-1)
- `urion_strategy_confidence` - Confiança do sinal (0-100)
- `urion_strategy_signals_total` - Total de sinais gerados

### 🖥️ Sistema
- `urion_mt5_connected` - Status da conexão MT5
- `urion_bot_uptime_seconds` - Tempo de execução
- `urion_errors_total` - Total de erros
- `urion_order_execution_seconds` - Tempo de execução de ordens

### 🛡️ Risk Management
- `urion_risk_rejections_total` - Trades rejeitados
- `urion_spread_pips` - Spread atual

## Instalação e Configuração

### 1. Download Prometheus

```powershell
# Windows - Download do site oficial
# https://prometheus.io/download/
# Versão recomendada: prometheus-2.x.x.windows-amd64.zip

# Extrair para C:\prometheus
```

### 2. Configurar Prometheus

```powershell
# Copiar arquivo de configuração
Copy-Item config\prometheus.yml C:\prometheus\prometheus.yml
```

### 3. Iniciar Prometheus

```powershell
# PowerShell
cd C:\prometheus
.\prometheus.exe --config.file=prometheus.yml

# Acesse: http://localhost:9090
```

### 4. Iniciar Urion Bot

```powershell
# O bot iniciará o servidor de métricas na porta 8000
.\start_bot.ps1

# Métricas disponíveis em: http://localhost:8000/metrics
```

## Visualização de Métricas

### Prometheus UI (http://localhost:9090)

**Queries úteis:**

```promql
# Taxa de acerto por estratégia
urion_strategy_win_rate

# Posições abertas
urion_positions_open

# Lucro total
sum(urion_trades_profit_usd)

# Drawdown atual
urion_account_drawdown_percent

# Erros por componente
sum(urion_errors_total) by (component)

# Tempo médio de execução de ordens
histogram_quantile(0.95, urion_order_execution_seconds)
```

### Grafana Dashboard (opcional)

1. Instalar Grafana: https://grafana.com/grafana/download
2. Adicionar Prometheus como Data Source
3. Importar dashboard: `config/grafana_dashboard.json`

## Alertas

### Configuração de Alertas (alert_rules.yml)

```yaml
groups:
  - name: urion_alerts
    interval: 30s
    rules:
      # Drawdown alto
      - alert: HighDrawdown
        expr: urion_account_drawdown_percent > 5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Drawdown alto detectado"
          description: "Drawdown atual: {{ $value }}%"
      
      # MT5 desconectado
      - alert: MT5Disconnected
        expr: urion_mt5_connected == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "MT5 desconectado"
      
      # Muitos erros
      - alert: HighErrorRate
        expr: rate(urion_errors_total[5m]) > 0.5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Taxa de erros elevada"
```

## Integração com o Bot

O bot atualiza métricas automaticamente:

```python
from monitoring.prometheus_metrics import get_metrics

# Obter instância
metrics = get_metrics()

# Registrar trade
metrics.record_trade(
    strategy='TrendFollowing',
    action='BUY',
    symbol='XAUUSD',
    profit=50.0,
    duration_minutes=120
)

# Atualizar conta
metrics.update_account(account_info)

# Atualizar posições
metrics.update_positions(positions)
```

## Troubleshooting

### Porta 8000 já em uso

```powershell
# Alterar porta em src/monitoring/prometheus_metrics.py
PrometheusMetrics(port=8001)

# Atualizar config/prometheus.yml
targets: ['localhost:8001']
```

### Métricas não aparecem

```powershell
# Verificar servidor está rodando
Invoke-WebRequest http://localhost:8000/metrics

# Verificar logs do Prometheus
# Procurar por erros de scrape
```

### Grafana não conecta

```
# Data Source settings
URL: http://localhost:9090
Access: Browser
```

## Recursos Adicionais

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Cheat Sheet](https://promlabs.com/promql-cheat-sheet/)

---

**Próximos Passos:**
1. ✅ Métricas Prometheus implementadas
2. ⏭️ Dashboard Web com Flask (próximo TODO)
3. ⏭️ Alertas por Email/SMS
4. ⏭️ CI/CD com GitHub Actions
