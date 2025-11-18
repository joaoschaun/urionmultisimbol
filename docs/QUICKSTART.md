# 🚀 Guia de Início Rápido - Urion Trading Bot

## ✅ Status Atual do Projeto

### Implementado (30%)
- ✅ Estrutura de diretórios completa
- ✅ Sistema de configuração (YAML + .env)
- ✅ Conexão com MetaTrader 5
- ✅ Sistema de logging avançado
- ✅ Notificações via Telegram
- ✅ Docker Compose para serviços
- ✅ Documentação de arquitetura

### Em Desenvolvimento (0%)
- ⏳ Análise técnica multi-timeframe
- ⏳ Análise de notícias
- ⏳ Gerador de ordens
- ⏳ Gerenciador de ordens
- ⏳ Sistema de estratégias
- ⏳ Machine Learning
- ⏳ Gerenciamento de risco

## 📋 Próximos Passos Imediatos

### 1. Configurar Ambiente de Desenvolvimento

```powershell
# 1. Criar ambiente virtual
python -m venv venv
.\venv\Scripts\activate

# 2. Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt

# 3. Copiar e configurar .env
copy .env.example .env
# Edite o .env com suas credenciais

# 4. Iniciar serviços Docker
docker-compose up -d

# 5. Verificar serviços
docker-compose ps
```

### 2. Testar Conexão MT5

Crie um arquivo `test_connection.py`:

```python
from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager

config = ConfigManager('config/config.yaml')
mt5 = MT5Connector(config.get_all())

if mt5.connect():
    print("✅ Conexão MT5 estabelecida!")
    
    # Testar obter informações da conta
    account = mt5.get_account_info()
    print(f"Saldo: ${account['balance']}")
    print(f"Equity: ${account['equity']}")
    
    # Testar obter informações do símbolo
    symbol_info = mt5.get_symbol_info('XAUUSD')
    print(f"\nXAUUSD - Bid: {symbol_info['bid']}, Ask: {symbol_info['ask']}")
    
    mt5.disconnect()
else:
    print("❌ Falha na conexão MT5")
```

Execute:
```powershell
python test_connection.py
```

### 3. Testar Telegram Bot

Crie um arquivo `test_telegram.py`:

```python
import asyncio
from src.notifications.telegram_bot import TelegramNotifier
from src.core.config_manager import ConfigManager

async def test_telegram():
    config = ConfigManager('config/config.yaml')
    telegram = TelegramNotifier(config.get_all())
    
    # Enviar mensagem de teste
    await telegram.send_message("🧪 Teste de conexão Telegram!")
    print("✅ Mensagem enviada!")

asyncio.run(test_telegram())
```

Execute:
```powershell
python test_telegram.py
```

## 🔨 Implementações Prioritárias

### Fase 1: Risk Manager (Prioridade Alta)
**Arquivo**: `src/risk_manager.py`

O Risk Manager deve ser implementado primeiro pois é crítico para proteger o capital.

**Funcionalidades necessárias**:
- [ ] Calcular tamanho de posição baseado em % de risco
- [ ] Validar se nova ordem excede exposição máxima
- [ ] Calcular stop loss baseado em ATR
- [ ] Calcular take profit (risk/reward 1:2)
- [ ] Verificar drawdown atual
- [ ] Controlar número de trades diários

**Exemplo de uso**:
```python
risk_manager = RiskManager(config, mt5_connector)

# Calcular position size
lot_size = risk_manager.calculate_position_size(
    symbol='XAUUSD',
    entry_price=1950.00,
    stop_loss=1945.00,
    risk_percent=0.02  # 2%
)

# Validar se pode abrir ordem
can_trade = risk_manager.can_open_position(
    symbol='XAUUSD',
    order_type='BUY',
    lot_size=0.01
)
```

### Fase 2: Technical Analysis (Prioridade Alta)
**Arquivo**: `src/analysis/technical.py`

Análise técnica é a base para todas as estratégias.

**Funcionalidades necessárias**:
- [ ] Calcular indicadores (EMA, RSI, MACD, ATR, etc.)
- [ ] Análise multi-timeframe
- [ ] Detectar padrões de candlestick
- [ ] Identificar suporte/resistência
- [ ] Detectar tendências
- [ ] Calcular força de sinais

**Exemplo de uso**:
```python
technical = TechnicalAnalysis(mt5_connector)

# Obter análise completa
analysis = technical.analyze('XAUUSD', timeframes=['M5', 'M15', 'H1'])

print(f"Tendência: {analysis['trend']}")  # BULLISH, BEARISH, NEUTRAL
print(f"Força: {analysis['strength']}")   # 0.0 a 1.0
print(f"RSI: {analysis['indicators']['rsi']}")
print(f"MACD: {analysis['indicators']['macd']}")
```

### Fase 3: News Analyzer (Prioridade Média)
**Arquivo**: `src/analysis/news_analyzer.py`

Análise de notícias para evitar operar em momentos perigosos.

**Funcionalidades necessárias**:
- [ ] Integração com APIs de notícias
- [ ] Análise de sentimento (positivo/negativo/neutro)
- [ ] Detecção de eventos de alto impacto
- [ ] Calendário econômico
- [ ] Previsão de impacto no mercado

**Exemplo de uso**:
```python
news_analyzer = NewsAnalyzer(config)

# Verificar se há notícias importantes nas próximas horas
upcoming_news = news_analyzer.get_upcoming_news(hours=2)

# Obter sentimento do mercado
sentiment = news_analyzer.get_market_sentiment()
print(f"Sentimento: {sentiment['score']}")  # -1 a 1
print(f"Confiança: {sentiment['confidence']}")  # 0 a 1

# Verificar se pode operar agora
safe_to_trade = news_analyzer.is_safe_to_trade()
```

### Fase 4: Order Generator (Prioridade Alta)
**Arquivo**: `src/order_generator.py`

Módulo que gera sinais de trading.

**Funcionalidades necessárias**:
- [ ] Loop principal (5 minutos)
- [ ] Integrar análise técnica
- [ ] Integrar análise de notícias
- [ ] Aplicar estratégias ativas
- [ ] Validar horários de trading
- [ ] Gerar sinais com SL/TP
- [ ] Enviar para Risk Manager

**Exemplo de estrutura**:
```python
class OrderGenerator:
    async def start(self):
        while self.running:
            # 1. Verificar se pode operar
            if not self.can_trade():
                await asyncio.sleep(300)
                continue
            
            # 2. Obter análises
            technical = await self.get_technical_analysis()
            news = await self.get_news_analysis()
            
            # 3. Aplicar estratégias
            signals = await self.apply_strategies(technical, news)
            
            # 4. Validar e executar melhor sinal
            if signals:
                best_signal = max(signals, key=lambda x: x['strength'])
                if best_signal['strength'] >= self.min_signal_strength:
                    await self.execute_signal(best_signal)
            
            await asyncio.sleep(300)  # 5 minutos
```

### Fase 5: Order Manager (Prioridade Alta)
**Arquivo**: `src/order_manager.py`

Módulo que gerencia posições abertas.

**Funcionalidades necessárias**:
- [ ] Loop principal (1 minuto)
- [ ] Monitorar posições abertas
- [ ] Aplicar trailing stop
- [ ] Mover para break-even
- [ ] Fechamento parcial
- [ ] Redução de perdas
- [ ] Proteção de lucros

**Exemplo de estrutura**:
```python
class OrderManager:
    async def start(self):
        while self.running:
            positions = self.mt5.get_open_positions('XAUUSD')
            
            for position in positions:
                # Analisar posição
                analysis = await self.analyze_position(position)
                
                # Decidir ação
                if analysis['action'] == 'CLOSE':
                    await self.close_position(position)
                elif analysis['action'] == 'MODIFY':
                    await self.modify_position(position, analysis['sl'], analysis['tp'])
                elif analysis['action'] == 'PARTIAL_CLOSE':
                    await self.partial_close(position, analysis['percentage'])
            
            await asyncio.sleep(60)  # 1 minuto
```

## 📚 Recursos Úteis

### MetaTrader 5 Python
- Documentação: https://www.mql5.com/en/docs/python_metatrader5
- Exemplos: https://www.mql5.com/en/articles/8016

### Análise Técnica
- TA-Lib: https://mrjbq7.github.io/ta-lib/
- pandas-ta: https://github.com/twopirllc/pandas-ta

### Machine Learning
- XGBoost: https://xgboost.readthedocs.io/
- TensorFlow: https://www.tensorflow.org/

### Telegram Bot
- python-telegram-bot: https://docs.python-telegram-bot.org/

## 🐛 Troubleshooting

### MetaTrader 5 não conecta
1. Verificar se MT5 está instalado
2. Verificar credenciais no .env
3. Verificar se MT5 permite algoritmos automatizados
4. Verificar firewall/antivírus

### Telegram não envia mensagens
1. Verificar token do bot
2. Verificar chat_id
3. Iniciar conversa com o bot primeiro
4. Verificar se bot não foi bloqueado

### Docker não inicia
1. Verificar se Docker Desktop está rodando
2. Verificar portas disponíveis (5432, 6379)
3. Verificar logs: `docker-compose logs`

## 📝 Checklist Antes de Operar Real

- [ ] Testar extensivamente em conta demo
- [ ] Validar todas as estratégias com backtest
- [ ] Confirmar gerenciamento de risco funciona
- [ ] Testar reconexão MT5 em caso de queda
- [ ] Testar notificações Telegram
- [ ] Configurar alertas de erro
- [ ] Definir limites de perda diária
- [ ] Monitorar por pelo menos 1 semana em demo
- [ ] Documentar todos os trades
- [ ] Ter plano de contingência

## 🎯 Metas de Performance

### Conta Demo (30 dias)
- Win rate > 50%
- Profit factor > 1.3
- Max drawdown < 20%
- Mínimo 100 trades

### Conta Real (começar pequeno)
- Lote mínimo (0.01)
- Risco por trade: 1%
- Capital inicial: $1000
- Aumentar gradualmente após consistência

## 💡 Dicas Importantes

1. **Sempre teste em demo primeiro**
2. **Comece com uma estratégia simples**
3. **Monitore o bot diariamente**
4. **Mantenha logs detalhados**
5. **Revise trades semanalmente**
6. **Ajuste parâmetros gradualmente**
7. **Tenha paciência - não há dinheiro fácil**
8. **Risk management é mais importante que estratégia**

## 📞 Suporte

Se precisar de ajuda:
1. Consulte a documentação em `docs/`
2. Verifique logs em `logs/`
3. Revise configuração em `config/`
4. Teste componentes individualmente

---

**Lembre-se**: Trading automatizado requer supervisão constante. Nunca deixe o bot operar sem monitoramento, especialmente nos primeiros dias/semanas.

**Boa sorte! 🚀📈**
