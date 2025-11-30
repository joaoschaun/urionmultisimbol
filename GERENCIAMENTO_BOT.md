# 🚀 GERENCIAMENTO PROFISSIONAL DO BOT

## 📊 **PROBLEMAS RESOLVIDOS**

### ❌ **Antes:**
- Múltiplos processos Python zumbis após encerramento
- Sem controle de instância única
- Sem restart automático
- ~32 threads rodando simultaneamente

### ✅ **Agora:**
- **ProcessManager**: Garante instância única com PID file
- **Supervisor**: Restart automático em caso de falha
- **Cleanup automático**: Remove processos zumbis
- **Shutdown gracioso**: Para todas threads corretamente

---

## 🎯 **ARQUITETURA DE THREADS**

### **Por Símbolo (XAUUSD, EURUSD, GBPUSD, USDJPY):**
```
├── 6 Estratégias (cada uma em 1 thread)
│   ├── trend_following
│   ├── mean_reversion
│   ├── breakout
│   ├── news_trading
│   ├── scalping
│   └── range_trading
└── 1 OrderManager (1 thread)

Total por símbolo: 7 threads
```

### **Threads Compartilhadas:**
```
├── 1 NewsNotifier
├── 1 AutoBackup
├── 1 Schedule
├── 1 Watchdog
└── 1 Main Thread

Total global: 5 threads
```

### **TOTAL: 4 símbolos × 7 + 5 = 33 threads**

---

## 🛠️ **COMO USAR**

### **1. Iniciar o Bot (Modo Normal)**
```powershell
cd c:\Users\Administrator\Desktop\urion
.\venv\Scripts\python.exe src\main.py
```

### **2. Forçar Restart (Mata instância anterior)**
```powershell
.\venv\Scripts\python.exe src\main.py --force
```

### **3. Iniciar com Supervisor (Restart Automático)**
```powershell
# Recomendado para produção
.\venv\Scripts\python.exe supervisor.py
```

**Configurações do Supervisor:**
- **Max falhas consecutivas**: 5 em 5 minutos
- **Delay entre restarts**: 10 segundos
- **Log**: `logs/supervisor.log`

### **4. Verificar se está Rodando**
```powershell
# Verificar PID file
Get-Content urion_bot.pid

# Listar processos Python
Get-Process python | Select-Object Id, CPU, StartTime
```

### **5. Parar o Bot**
```powershell
# Ctrl+C no terminal (shutdown gracioso)
# ou
taskkill /PID <pid> /T  # Usar PID do urion_bot.pid
```

---

## 🔍 **MONITORAMENTO**

### **Verificar Status do Processo**
O bot agora loga informações do processo na inicialização:
```
📊 Processo: PID 12345, 33 threads, 245.3 MB RAM
```

### **Arquivos de Controle**
- **`urion_bot.pid`**: PID da instância atual
- **`logs/urion.log`**: Log principal do bot
- **`logs/supervisor.log`**: Log do supervisor (se usado)

### **Prometheus Metrics**
```
http://localhost:8000/metrics
```

---

## 🚨 **RESOLUÇÃO DE PROBLEMAS**

### **Erro: "urion_bot já está rodando"**
**Solução 1** - Use `--force`:
```powershell
.\venv\Scripts\python.exe src\main.py --force
```

**Solução 2** - Mate manualmente:
```powershell
$pid = Get-Content urion_bot.pid
Stop-Process -Id $pid -Force
Remove-Item urion_bot.pid
```

### **Processos Zumbis Persistentes**
```powershell
# Matar TODOS processos Python (⚠️ CUIDADO!)
taskkill /F /IM python.exe

# Remover PID file
Remove-Item urion_bot.pid -ErrorAction SilentlyContinue
```

### **Bot Para Sozinho**
- Verificar `logs/urion.log` para erros
- Usar **supervisor.py** para restart automático
- Verificar se há exceções não tratadas

---

## 📈 **MELHORIAS IMPLEMENTADAS**

### **1. ProcessManager** (`src/core/process_manager.py`)
- ✅ PID file para controle de instância
- ✅ Detecção de processos zumbis
- ✅ Kill gracioso de instâncias antigas
- ✅ Handlers de sinais (SIGINT, SIGTERM, SIGBREAK)
- ✅ Informações do processo (CPU, RAM, threads)

### **2. Supervisor** (`supervisor.py`)
- ✅ Restart automático em falhas
- ✅ Limitador de tentativas (5 em 5 min)
- ✅ Delay configurável entre restarts
- ✅ Log dedicado de supervisão
- ✅ Proteção contra loops infinitos

### **3. Main.py Atualizado**
- ✅ Integração com ProcessManager
- ✅ Flag `--force` para forçar restart
- ✅ Cleanup de zumbis na inicialização
- ✅ Shutdown handler centralizado
- ✅ Logging de informações do processo

---

## 🎯 **MELHORES PRÁTICAS**

### **Desenvolvimento/Teste**
```powershell
# Iniciar direto (sem supervisor)
.\venv\Scripts\python.exe src\main.py

# Parar com Ctrl+C
```

### **Produção**
```powershell
# Usar supervisor para alta disponibilidade
.\venv\Scripts\python.exe supervisor.py

# Logs em logs/supervisor.log e logs/urion.log
```

### **Deploy/Atualização**
```powershell
# 1. Parar bot atual (Ctrl+C ou kill PID)
# 2. Atualizar código
# 3. Forçar restart limpo
.\venv\Scripts\python.exe src\main.py --force
```

---

## 📝 **CHECKLIST PÓS-SHUTDOWN**

Após parar o bot, sempre verificar:
```powershell
# 1. Nenhum processo Python rodando
Get-Process python -ErrorAction SilentlyContinue

# 2. PID file removido
Test-Path urion_bot.pid

# 3. Sem conexões MT5 abertas (verificar no terminal MT5)
```

---

## 🔧 **CONFIGURAÇÕES AVANÇADAS**

### **Ajustar Limites do Supervisor** (supervisor.py)
```python
# Linha 18-20
self.max_consecutive_failures = 5    # Máximo de falhas
self.failure_window = 300            # Janela de tempo (segundos)
self.restart_delay = 10              # Delay entre restarts
```

### **Timeout do ProcessManager** (src/core/process_manager.py)
```python
# Linha 95
process.wait(timeout=10)  # Tempo para shutdown gracioso
```

---

## 📊 **ESTATÍSTICAS**

**Antes vs Depois:**
| Métrica | Antes | Depois |
|---------|-------|--------|
| Processos Zumbis | Sim | Não |
| Instância Única | Não | Sim |
| Restart Automático | Não | Sim |
| Cleanup Gracioso | Não | Sim |
| PID Tracking | Não | Sim |
| Signal Handling | Parcial | Completo |

---

## 🎉 **RESULTADO FINAL**

✅ Bot profissional com gerenciamento robusto de processos
✅ Instância única garantida
✅ Restart automático confiável
✅ Cleanup completo de recursos
✅ Monitoramento e logging aprimorados
✅ Fácil deploy e manutenção
