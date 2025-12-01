# ⚠️ CHECKLIST CRÍTICO - PRÉ-PRODUÇÃO

## 🚨 STATUS ATUAL: NÃO PRONTO PARA DINHEIRO REAL

**Score Atual: ~85/100** (melhorado de 72/100)
**Score Mínimo para Produção: 95/100**

---

## ✅ O QUE FOI IMPLEMENTADO

### 🔒 Infraestrutura de Segurança

| Componente | Arquivo | Status |
|------------|---------|--------|
| State Manager | `src/core/state_manager.py` | ✅ Implementado |
| Disaster Recovery | `src/core/disaster_recovery.py` | ✅ Implementado |
| Circuit Breaker | `src/core/disaster_recovery.py` | ✅ Implementado |
| Backtest Robusto | `src/backtesting/backtest_engine.py` | ✅ Implementado |
| Paper Trading | `src/backtesting/paper_trading.py` | ✅ Implementado |
| ML Validator | `src/ml/ml_validator.py` | ✅ Implementado |
| Advanced Monitor | `src/monitoring/advanced_monitor.py` | ✅ Implementado |
| Unit Tests | `tests/test_core.py` | ✅ Implementado |

---

## 📋 CHECKLIST OBRIGATÓRIO ANTES DE OPERAR REAL

### 1️⃣ Backtesting (Crítico)
- [ ] Executar backtest com 5+ anos de dados
- [ ] Walk-forward analysis com 12+ folds
- [ ] Monte Carlo simulation (1000+ iterações)
- [ ] Profit factor > 1.5 em todos os períodos
- [ ] Max drawdown < 15% em todos os períodos
- [ ] Sharpe Ratio > 1.5 out-of-sample

### 2️⃣ Paper Trading (Obrigatório)
- [ ] Executar 90+ dias de paper trading
- [ ] Win rate > 55% consistente
- [ ] Verificar slippage real vs simulado
- [ ] Testar em diferentes condições de mercado
- [ ] Nenhum bug crítico detectado

### 3️⃣ Testes (Obrigatório)
- [ ] Rodar `pytest tests/ -v`
- [ ] Coverage > 80%
- [ ] Todos os testes passando
- [ ] Testes de integração OK
- [ ] Teste de stress completo

### 4️⃣ Recovery System (Crítico)
- [ ] Testar recovery após crash
- [ ] Testar recovery após perda de conexão
- [ ] Verificar sincronização com MT5
- [ ] Testar circuit breakers
- [ ] Validar checkpoints

### 5️⃣ Monitoramento (Importante)
- [ ] Dashboard funcionando
- [ ] Alertas de Telegram configurados
- [ ] Health checks ativos
- [ ] Logs estruturados
- [ ] Métricas Prometheus (opcional)

### 6️⃣ ML Models (Crítico)
- [ ] Validação cruzada temporal OK
- [ ] Sem data leakage detectado
- [ ] Overfitting score < 0.15
- [ ] Feature importance validada
- [ ] Re-treino agendado

---

## 🛑 QUANDO NÃO OPERAR

**PARE IMEDIATAMENTE SE:**
- Drawdown > 5% (diário) ou > 15% (total)
- Mais de 5 perdas consecutivas
- Latência de execução > 500ms
- Perda de conexão frequente
- Qualquer comportamento anômalo

---

## 📊 MÉTRICAS MÍNIMAS PARA PRODUÇÃO

| Métrica | Mínimo | Ideal |
|---------|--------|-------|
| Win Rate | 52% | 58%+ |
| Profit Factor | 1.3 | 1.8+ |
| Sharpe Ratio | 1.0 | 2.0+ |
| Max Drawdown | < 20% | < 10% |
| Recovery Factor | > 2 | > 4 |
| Calmar Ratio | > 1 | > 2 |

---

## 🔄 TIMELINE RECOMENDADA

```
Mês 1-2:    Implementação + Backtesting
Mês 3:      Walk-Forward + Otimização  
Mês 4-6:    Paper Trading REAL
Mês 7:      Análise de Resultados
Mês 8+:     Capital pequeno (~$1000)
Ano 2:      Escalar gradualmente
```

---

## 💰 CAPITAL INICIAL RECOMENDADO

**NUNCA comece com muito capital!**

| Fase | Capital | Risco/Trade |
|------|---------|-------------|
| Paper | $0 (simulado) | N/A |
| Micro | $500-1000 | 0.5% |
| Mini | $2000-5000 | 1% |
| Standard | $10000+ | 1-2% |

---

## 📞 SUPORTE DE EMERGÊNCIA

Em caso de comportamento anômalo:
1. **STOP imediato** - Desligar bot
2. **Fechar posições** manualmente se necessário
3. **Verificar logs** em `logs/`
4. **Analisar estado** em `data/state/`
5. **Não reiniciar** sem entender o problema

---

## ⚠️ DISCLAIMER

> Este software é fornecido "como está", sem garantias. Trading envolve riscos significativos e pode resultar em perda total do capital. Use por sua conta e risco. Recomendamos fortemente começar com paper trading e valores mínimos.

---

**Última atualização:** 2025-01-29
**Versão do Sistema:** 2.2
**Score de Prontidão:** 85/100
