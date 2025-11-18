# Módulo de Análise de Notícias

## Visão Geral

O `NewsAnalyzer` é responsável por integrar múltiplas fontes de notícias e calendário econômico, analisar sentimento usando NLP e detectar janelas de bloqueio para evitar trading durante eventos de alto impacto.

## Características Principais

### 📰 Fontes de Dados

#### 1. ForexNewsAPI
- Notícias gerais de Forex e commodities
- Filtragem automática para GOLD/XAUUSD
- Análise de relevância

#### 2. Finazon
- Notícias específicas do ticker XAUUSD
- Dados de mercado em tempo real
- Alta precisão para gold

#### 3. Financial Modeling Prep (FMP)
- Calendário econômico completo
- Eventos de alto impacto
- Dados históricos e previsões

### 🧠 Análise de Sentimento (NLP)

- **TextBlob**: Análise de polaridade e subjetividade
- **Polaridade**: -1.0 (muito negativo) a +1.0 (muito positivo)
- **Subjetividade**: 0.0 (objetivo) a 1.0 (subjetivo)

### 🚫 Sistema de Bloqueio

- Detecta eventos de alto impacto
- Janela de bloqueio configurável (padrão: ±15 minutos)
- Evita trading durante:
  - Non-Farm Payrolls (NFP)
  - Decisões de taxas de juros
  - CPI / Inflação
  - Discursos do Fed

### 🎯 Sinais de Trading

- **BULLISH**: Sentimento positivo forte
- **BEARISH**: Sentimento negativo forte
- **HOLD**: Sentimento neutro ou incerto
- **BLOCK**: Janela de bloqueio ativa

## Uso Básico

### Exemplo 1: Buscar Top Notícias

```python
from src.core.config_manager import ConfigManager
from src.analysis.news_analyzer import NewsAnalyzer

# Carregar configuração
config = ConfigManager('config/config.yaml')

# Criar analisador
analyzer = NewsAnalyzer(config.config)

# Buscar top 5 notícias mais relevantes
top_news = analyzer.get_top_news(limit=5)

for news in top_news:
    print(f"📰 {news['title']}")
    print(f"   Relevância: {news['relevance']:.2%}")
    print(f"   Sentimento: {news['sentiment']['polarity']:.2f}")
    print(f"   Fonte: {news['source']}")
    print()
```

### Exemplo 2: Resumo de Sentimento

```python
# Obter resumo de sentimento geral
sentiment = analyzer.get_sentiment_summary(max_news=20)

print(f"Sentimento Geral: {sentiment['overall_sentiment']}")
print(f"Polaridade: {sentiment['polarity_avg']:.3f}")
print(f"Bullish: {sentiment['bullish_count']}")
print(f"Bearish: {sentiment['bearish_count']}")
print(f"Neutro: {sentiment['neutral_count']}")
```

### Exemplo 3: Verificar Bloqueio

```python
# Verificar se há janela de bloqueio ativa
is_blocking, event = analyzer.is_news_blocking_window(buffer_minutes=15)

if is_blocking:
    print(f"⛔ BLOQUEIO ATIVO!")
    print(f"   Evento: {event['event']}")
    print(f"   Data: {event['date']}")
    print(f"   Impacto: {event['impact']}")
else:
    print("✅ Seguro para operar")
```

### Exemplo 4: Gerar Sinal

```python
# Gerar sinal de trading baseado em notícias
signal = analyzer.get_news_signal()

print(f"Ação: {signal['action']}")
print(f"Confiança: {signal['confidence']:.2%}")
print(f"Razão: {signal['reason']}")

if signal['action'] == 'BULLISH':
    print("📈 Considerar COMPRA")
elif signal['action'] == 'BEARISH':
    print("📉 Considerar VENDA")
elif signal['action'] == 'BLOCK':
    print("⛔ NÃO OPERAR")
else:
    print("⏸️ AGUARDAR")
```

### Exemplo 5: Calendário Econômico

```python
# Buscar eventos econômicos
events = analyzer.fetch_economic_calendar(days=1)

for event in events:
    if event['impact'] == 'high':
        print(f"🔴 {event['event']}")
        print(f"   País: {event['country']}")
        print(f"   Data: {event['date']}")
        print(f"   Previsão: {event.get('estimate', 'N/A')}")
        print()
```

## Estrutura de Retorno

### get_top_news()

```python
[
    {
        'source': 'ForexNewsAPI',
        'title': 'Gold prices surge on inflation concerns',
        'description': 'Rising inflation pushes investors to safe haven',
        'url': 'https://example.com/news1',
        'published_at': '2024-01-15 10:00:00',
        'relevance': 0.85,
        'sentiment': {
            'polarity': 0.65,
            'subjectivity': 0.70,
            'method': 'textblob'
        }
    },
    ...
]
```

### get_sentiment_summary()

```python
{
    'overall_sentiment': 'bullish',  # bullish, bearish, neutral
    'polarity_avg': 0.45,  # Média ponderada
    'bullish_count': 12,
    'bearish_count': 5,
    'neutral_count': 3,
    'total_analyzed': 20
}
```

### get_news_signal()

```python
{
    'action': 'BULLISH',  # BULLISH, BEARISH, HOLD, BLOCK
    'reason': 'news_sentiment',
    'confidence': 0.75,
    'sentiment': { ... },  # Resumo completo
    'news_count': 20
}
```

**OU** durante evento:

```python
{
    'action': 'BLOCK',
    'reason': 'high_impact_event',
    'event': {
        'event': 'Non-Farm Payrolls',
        'country': 'United States',
        'date': '2024-01-15 13:30:00',
        'impact': 'high'
    },
    'confidence': 1.0
}
```

### fetch_economic_calendar()

```python
[
    {
        'source': 'FMP',
        'event': 'Non-Farm Payrolls',
        'country': 'United States',
        'date': '2024-01-15 13:30:00',
        'impact': 'high',
        'currency': 'USD',
        'estimate': '200K',
        'previous': '195K',
        'actual': '210K'  # Apenas após o evento
    },
    ...
]
```

## Configuração

No arquivo `config/config.yaml`:

```yaml
news:
  forexnews_api_key: ${FOREXNEWS_API_KEY}
  finazon_api_key: ${FINAZON_API_KEY}
  fmp_api_key: ${FMP_API_KEY}
  
  # Configurações de análise
  max_news_age_hours: 24
  sentiment_threshold: 0.2  # Mínimo para bullish/bearish
  blocking_buffer_minutes: 15  # Janela antes/depois de eventos
```

No arquivo `.env`:

```bash
FOREXNEWS_API_KEY=u2lyge5a8ehgtlikrv4owyqsitphrcxqu6afzuja
FINAZON_API_KEY=830c05bb65994f99ae39629a0e9f8edffw
FMP_API_KEY=ZvAVZ4inPZ4mtTnJ4cuLSQYYSrLQcfkr
```

## Palavras-Chave para GOLD

O sistema detecta relevância baseado em:

- `gold`, `xau`, `precious metals`
- `inflation`, `fed`, `interest rate`
- `dollar`, `usd`, `dxy`
- `geopolitical`, `war`, `safe haven`
- `central bank`, `monetary policy`
- `treasury`, `recession`

## Sistema de Cache

### Cache de Notícias
- **Timeout**: 5 minutos
- **Propósito**: Reduzir chamadas às APIs
- **Limpeza**: Automática ou manual via `clear_cache()`

### Cache de Eventos
- **Timeout**: 1 hora
- **Propósito**: Calendário econômico muda pouco
- **Atualização**: Automática quando expirado

## Análise de Relevância

### Cálculo

```python
relevance = min(matching_keywords / 5.0, 1.0)
```

- **0.0-0.2**: Baixa relevância
- **0.2-0.6**: Relevância moderada
- **0.6-1.0**: Alta relevância

### Filtragem

Apenas notícias com relevância > 0.0 são retornadas.

## Janelas de Bloqueio

### Eventos Bloqueados

- **Alto Impacto**: Sempre bloqueiam
  - Non-Farm Payrolls
  - FOMC (decisões de taxa)
  - CPI / PPI (inflação)
  - Discursos do Fed Chair

- **Médio Impacto**: Bloqueiam se relacionados a USD/GOLD
  - Dados de emprego
  - Vendas no varejo
  - Confiança do consumidor

### Buffer Padrão

- **±15 minutos** do horário do evento
- Configurável via parâmetro

## Integração com Order Generator

```python
from src.analysis.news_analyzer import NewsAnalyzer
from src.analysis.technical import TechnicalAnalyzer

# Analisadores
news_analyzer = NewsAnalyzer(config)
tech_analyzer = TechnicalAnalyzer(mt5, config)

# Verificar bloqueio PRIMEIRO
is_blocking, _ = news_analyzer.is_news_blocking_window()

if is_blocking:
    logger.warning("Janela de bloqueio ativa - não operar")
    return

# Obter sinais
news_signal = news_analyzer.get_news_signal()
tech_signal = tech_analyzer.get_signal('M5')

# Combinar sinais
if news_signal['action'] == tech_signal['action']:
    confidence = (news_signal['confidence'] + tech_signal['confidence']) / 2
    
    if confidence > 0.7:
        logger.info(f"Sinal forte de {news_signal['action']}")
        # Executar ordem...
```

## Limitações

### ⚠️ Avisos

1. **APIs podem ter limites de taxa**: Respeite os limites das APIs
2. **Análise de sentimento é imperfeita**: TextBlob tem ~60-70% de precisão
3. **Notícias podem ser atrasadas**: Não use para scalping ultra-rápido
4. **Calendário pode ter erros**: Sempre verifique múltiplas fontes

### 🔄 Melhorias Futuras

- [ ] BERT/Transformer para melhor análise de sentimento
- [ ] Integração com mais fontes (Bloomberg, Reuters)
- [ ] Análise de impacto histórico
- [ ] ML para prever reação do mercado
- [ ] Detecção de rumores e fake news

## Performance

### Tempo de Execução

- `fetch_forex_news()`: ~1-2s
- `fetch_finazon_news()`: ~1-2s
- `fetch_economic_calendar()`: ~1-2s
- `get_sentiment_summary()`: ~2-3s (20 notícias)
- `get_news_signal()`: ~3-4s (total)

### Otimizações

- ✅ Cache de 5 minutos para notícias
- ✅ Cache de 1 hora para eventos
- ✅ Requisições assíncronas (futuro)
- ✅ Pool de conexões HTTP

## Testes

Execute os testes com:

```bash
pytest tests/test_news_analyzer.py -v
```

**Cobertura**: 20+ testes unitários

- Busca de notícias (ForexNewsAPI, Finazon)
- Calendário econômico (FMP)
- Análise de sentimento
- Detecção de relevância
- Sistema de cache
- Janelas de bloqueio
- Geração de sinais

## Exemplo Completo

Veja `examples/news_analyzer_demo.py` para exemplo completo funcionando:

```bash
python examples/news_analyzer_demo.py
```

## Troubleshooting

### Erro: API key não configurada

```bash
# Verificar .env
cat .env | grep API_KEY

# Adicionar chaves
echo "FOREXNEWS_API_KEY=sua_chave" >> .env
```

### Erro: TextBlob não instalado

```bash
pip install textblob
python -m textblob.download_corpora
```

### Cache não atualizando

```python
# Limpar cache manualmente
analyzer.clear_cache()
```

### Timeout nas requisições

```python
# APIs podem estar lentas
# Tente aumentar timeout (padrão: 10s)
# Edite news_analyzer.py linha do requests.get
```

## Referências

### APIs

- **ForexNewsAPI**: https://forexnewsapi.com/documentation
- **Finazon**: https://finazon.io/docs
- **FMP**: https://financialmodelingprep.com/developer/docs/

### NLP

- **TextBlob**: https://textblob.readthedocs.io/
- **NLTK**: https://www.nltk.org/

---

**Status**: ✅ Completo e Testado  
**Última Atualização**: 18/11/2025  
**Versão**: 1.0.0
