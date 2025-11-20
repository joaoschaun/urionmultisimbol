# 🤖 URION TRADING BOT - Estrutura Simplificada

## ✅ Bot 100% Funcional e Confiável

### 📁 Estrutura Principal

```
urion/
├── src/                    # Código principal do bot
│   ├── main.py            # Ponto de entrada
│   ├── order_generator.py # Gerador de ordens (estratégias)
│   ├── order_manager.py   # Gerenciador de posições
│   ├── core/              # Módulos principais
│   ├── strategies/        # 6 estratégias de trading
│   ├── analysis/          # Análise técnica e notícias
│   ├── ml/                # Machine Learning
│   └── database/          # Banco de dados SQLite
│
├── config/                # Configurações
│   └── config.yaml        # Configuração principal
│
├── scripts/               # Utilitários e testes
│   ├── monitor.py         # Monitor tempo real
│   ├── ver_aprendizagem.py # Status ML
│   └── test_*.py          # Scripts de teste
│
├── dashboard_web.py       # Dashboard web (Flask)
├── templates/             # Templates HTML
│   └── dashboard.html     # Interface do dashboard
│
└── logs/                  # Logs do sistema
    ├── urion.log          # Log principal
    └── error.log          # Apenas erros
```

### 🚀 Como Usar

#### 1. Iniciar o Bot
```powershell
python src/main.py
```

#### 2. Abrir Dashboard
```powershell
.\start_dashboard.ps1
# Acesse: http://localhost:5000
```

#### 3. Ver Status de Aprendizagem
```powershell
python scripts/ver_aprendizagem.py
```

#### 4. Monitor Tempo Real
```powershell
python scripts/monitor.py
```

### 🎯 Estratégias Ativas

1. **TrendFollowing** - Segue tendências (900s)
2. **MeanReversion** - Reversão à média (600s)
3. **Breakout** - Rompimento de suportes/resistências (1800s)
4. **NewsTrading** - Opera em notícias (300s)
5. **Scalping** - Operações rápidas (60s)
6. **RangeTrading** - Mercado lateral (180s)

### 📊 Dashboard Web

- **Auto-atualização**: A cada 5 segundos
- **Dados em tempo real**:
  - Balance e Equity
  - Posições abertas
  - Histórico de trades (24h)
  - Estatísticas (7 dias)
  - Performance por estratégia

### 🔧 Correções Aplicadas

✅ **3 Problemas Críticos Resolvidos:**
1. `place_order()` erro de parâmetro `price` - CORRIGIDO
2. "Invalid stops" no MT5 - CORRIGIDO (validação stops_level)
3. Thread FREEZE a cada 10 min - CORRIGIDO (try-except robusto)

✅ **Sistema de Logs:**
- Funciona corretamente (nível INFO)
- Rotação automática (10MB por arquivo)
- Compressão de logs antigos

✅ **Sistema de Aprendizagem:**
- Totalmente funcional
- Aprende a cada 20 trades
- Ajusta confiança automaticamente

### ⚙️ Configuração

Edite `config/config.yaml` para ajustar:
- Risk management (2% padrão)
- Estratégias (ciclos, confiança)
- Horários de operação
- Telegram, APIs, etc.

### 📝 Logs

```powershell
# Ver logs em tempo real
Get-Content logs\urion.log -Wait -Tail 50

# Ver apenas erros
Get-Content logs\error.log -Tail 20
```

### 🎯 Status Atual

- ✅ Bot operando 100% confiável
- ✅ Dashboard funcional
- ✅ 6 estratégias ativas
- ✅ Machine Learning integrado
- ✅ Telegram notificações
- ✅ Prometheus metrics (porta 8000)
- ✅ Sem erros críticos

### 📚 Commits Importantes

- `17dcda0` - Correções críticas (bot confiável)
- `bb2d698` - Dashboard funcional
- `7d75125` - Estrutura organizada
- `2323867` - Sistema de logs corrigido

---

**Bot desenvolvido por Virtus Investimentos**
**100% testado e aprovado** ✅
