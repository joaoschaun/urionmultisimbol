# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [2.0.0] - 2025-11-27

### Adicionado

#### 🌍 Multi-Symbol Support
- Suporte para 4 símbolos simultâneos (XAUUSD, EURUSD, GBPUSD, USDJPY)
- `SymbolManager` para gerenciamento centralizado
- `SymbolContext` individual para cada símbolo
- Execução paralela independente por símbolo

#### 🧠 Machine Learning
- `StrategyLearner` - Sistema de aprendizagem automática
- Análise de performance histórica por estratégia
- Auto-ajuste de parâmetros (min_confidence)
- Identificação e salvamento de padrões vencedores
- Ranking automático de estratégias
- Persistência de dados de aprendizagem em JSON

#### 📊 Análise Avançada
- `MacroContextAnalyzer` - Análise de contexto macro-econômico
- `SmartMoneyDetector` - Detecção de movimentos institucionais
- `MarketConditionAnalyzer` - Análise de condições de mercado
- Análise multi-timeframe (6 timeframes: M1, M5, M15, H1, H4, D1)

#### 📱 Notificações
- `NewsNotifier` com tradução automática para português
- Monitoramento de notícias em tempo real
- Integração com múltiplas APIs (Finnhub, ForexNews, FMP)
- Notificações Telegram em português

#### 📈 Relatórios
- Relatórios diários detalhados
- Relatórios semanais com ranking de estratégias
- Relatórios mensais com projeções
- Todos com explicações em português

#### 🕐 Market Hours
- `ForexMarketHours` - Gestão de horário 24/5 sem feriados para Forex
- `MarketHoursManager` - Gestão de horário 23/5 para XAUUSD
- Remoção de verificação de feriados US para XAUUSD (opera em todos os feriados)
- `MarketHolidays` - Sistema de gerenciamento de feriados

#### 🔄 Operacional
- Auto-backup diário do database
- Sistema de watchdog para monitorar threads
- Auto-recovery em caso de falhas
- Launcher profissional (`start.ps1`)

### Modificado

#### ⚙️ Core Systems
- `strategy_executor.py` - Integração com StrategyLearner
- `order_manager.py` - Melhorias no fechamento de posições
- `risk_manager.py` - Ajustes de gestão de risco
- `mt5_connector.py` - Melhorias na conexão e estabilidade

#### 🎯 Estratégias
- Todas as 6 estratégias atualizadas para usar aprendizagem
- Melhor integração com análise multi-timeframe
- Ajustes de parâmetros baseados em dados históricos

#### 📊 Database
- Nova estrutura de tabelas para suportar multi-símbolo
- Índices otimizados para consultas rápidas
- Sistema de backup automático

### Corrigido

- Bug no cálculo de profit em fechamentos parciais
- Erro de TypeError no NewsNotifier (conversão string→int)
- Problemas com cache Python bloqueando atualizações
- Verificação incorreta de feriados para XAUUSD
- Erros de conexão MT5 em reconexões

### Documentação

- README.md completamente reformulado
- Documentação profissional adicionada
- Guia de instalação atualizado
- Troubleshooting expandido
- Roadmap de futuras versões

---

## [1.0.0] - 2025-11-20

### Versão Inicial

- Sistema básico de trading para XAUUSD
- 6 estratégias implementadas
- Integração com MT5
- Bot Telegram básico
- Gestão de risco fundamental
