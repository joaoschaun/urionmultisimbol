# Módulo de Análise Técnica

## Visão Geral

O `TechnicalAnalyzer` é o módulo responsável por realizar análise técnica multi-timeframe do XAUUSD, calculando indicadores técnicos, detectando padrões de candlestick e gerando sinais de trading baseados em consenso de múltiplos timeframes.

## Características Principais

### ✅ Análise Multi-Timeframe
- Suporte para 7 timeframes: M1, M5, M15, M30, H1, H4, D1
- Sistema de consenso entre timeframes
- Cache inteligente de dados (30 segundos)

### 📊 Indicadores Técnicos Implementados

#### Médias Móveis
- **EMA (Exponential Moving Average)**: Períodos configuráveis (padrão: 9, 21, 50, 200)
- **SMA (Simple Moving Average)**: Períodos configuráveis (padrão: 20, 50, 100, 200)

#### Osciladores
- **RSI (Relative Strength Index)**: Período 14, detecta sobrecompra (>70) e sobrevenda (<30)
- **Stochastic Oscillator**: %K e %D, identifica extremos de preço
- **MACD (Moving Average Convergence Divergence)**: Detecta mudanças de momentum

#### Volatilidade
- **Bollinger Bands**: Bandas superior, média e inferior (20 períodos, 2 desvios padrão)
- **ATR (Average True Range)**: Mede volatilidade do mercado (14 períodos)

#### Tendência
- **ADX (Average Directional Index)**: Força da tendência + DI+ e DI-
- Análise de cruzamento de médias móveis

### 🕯️ Padrões de Candlestick

#### Padrões de Reversão
- **Doji**: Indecisão do mercado
- **Hammer**: Reversão de baixa para alta
- **Inverted Hammer**: Possível reversão de baixa
- **Shooting Star**: Reversão de alta para baixa
- **Engulfing Bullish**: Forte reversão para alta
- **Engulfing Bearish**: Forte reversão para baixa
- **Morning Star**: Padrão de 3 candles - reversão de baixa
- **Evening Star**: Padrão de 3 candles - reversão de alta

#### Padrões de Continuação
- **Pin Bar Bullish**: Continuação de alta
- **Pin Bar Bearish**: Continuação de baixa

### 🎯 Sistema de Sinais

O módulo gera sinais de trading (BUY/SELL/HOLD) baseados em:
1. **Análise Multi-Timeframe**: Consenso entre M5, M15 e H1
2. **Força da Tendência**: Baseada em ADX e convergência de indicadores
3. **Confiança do Sinal**: Média entre força e concordância (> 60% para ação)

## Uso Básico

### Exemplo 1: Análise de Timeframe Único

```python
from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager
from src.analysis.technical import TechnicalAnalyzer

# Conectar ao MT5
config = ConfigManager('config/config.yaml')
mt5 = MT5Connector(config.config)
mt5.connect()

# Criar analisador
analyzer = TechnicalAnalyzer(mt5, config.config)

# Analisar M5
analysis = analyzer.analyze_timeframe('M5', bars=200)

print(f"Preço: {analysis['current_price']:.2f}")
print(f"RSI: {analysis['rsi']:.2f}")
print(f"Tendência: {analysis['trend']['direction']}")
print(f"Força: {analysis['trend']['strength']:.2%}")
```

### Exemplo 2: Análise Multi-Timeframe

```python
# Analisar múltiplos timeframes
mtf_analysis = analyzer.analyze_multi_timeframe(['M5', 'M15', 'M30', 'H1'])

# Verificar consenso
consensus = mtf_analysis['consensus']
print(f"Direção: {consensus['direction']}")
print(f"Concordância: {consensus['agreement']:.2%}")
print(f"Votos Alta: {consensus['bullish_count']}")
print(f"Votos Baixa: {consensus['bearish_count']}")
```

### Exemplo 3: Geração de Sinais

```python
# Gerar sinal de trading
signal = analyzer.get_signal('M5')

if signal:
    print(f"Ação: {signal['action']}")  # BUY/SELL/HOLD
    print(f"Confiança: {signal['confidence']:.2%}")
    
    if signal['action'] == 'BUY' and signal['confidence'] > 0.7:
        print("✅ Sinal forte de COMPRA!")
    elif signal['action'] == 'SELL' and signal['confidence'] > 0.7:
        print("✅ Sinal forte de VENDA!")
```

### Exemplo 4: Análise de Indicadores Individuais

```python
# Obter dados de mercado
df = analyzer.get_market_data('M5', bars=100)

# Calcular indicadores individualmente
ema_20 = analyzer.calculate_ema(df, 20)
rsi = analyzer.calculate_rsi(df, 14)
macd = analyzer.calculate_macd(df)
bb = analyzer.calculate_bollinger_bands(df)

print(f"EMA(20): {ema_20.iloc[-1]:.2f}")
print(f"RSI(14): {rsi.iloc[-1]:.2f}")
print(f"MACD: {macd['macd'].iloc[-1]:.4f}")
print(f"BB Superior: {bb['upper'].iloc[-1]:.2f}")
```

## Estrutura de Retorno

### analyze_timeframe()

```python
{
    'timeframe': 'M5',
    'last_update': '2024-01-15T10:30:00',
    'current_price': 2050.25,
    'current_time': '2024-01-15T10:30:00',
    
    'ema': {
        'ema_9': 2048.50,
        'ema_21': 2045.30,
        'ema_50': 2042.10
    },
    
    'sma': {
        'sma_20': 2046.80,
        'sma_50': 2043.20
    },
    
    'rsi': 65.5,
    
    'macd': {
        'macd': 2.5,
        'signal': 1.8,
        'histogram': 0.7
    },
    
    'bollinger': {
        'upper': 2055.00,
        'middle': 2048.00,
        'lower': 2041.00
    },
    
    'atr': 5.25,
    
    'adx': {
        'adx': 32.5,
        'di_plus': 28.0,
        'di_minus': 18.5
    },
    
    'stochastic': {
        'k': 75.2,
        'd': 72.8
    },
    
    'patterns': {
        'doji': False,
        'hammer': False,
        'engulfing_bullish': True,
        'engulfing_bearish': False,
        ...
    },
    
    'trend': {
        'direction': 'bullish',
        'strength': 0.75,
        'signals': [
            'EMA 9 > 21 (bullish)',
            'MACD > Signal (bullish)',
            'ADX 32.5 + DI+ > DI- (tendência de alta forte)'
        ]
    }
}
```

### get_signal()

```python
{
    'action': 'BUY',  # BUY, SELL, HOLD
    'confidence': 0.82,  # 0.0 a 1.0
    'direction': 'bullish',
    'strength': 0.78,
    'agreement': 0.86,
    'timeframe': 'M5',
    'timestamp': '2024-01-15T10:30:00',
    'analysis': { ... }  # Análise completa multi-timeframe
}
```

## Configuração

No arquivo `config/config.yaml`:

```yaml
technical_analysis:
  indicators:
    ema_periods: [9, 21, 50, 200]
    sma_periods: [20, 50, 100, 200]
    rsi_period: 14
    macd:
      fast: 12
      slow: 26
      signal: 9
    bollinger:
      period: 20
      std: 2.0
    atr_period: 14
    adx_period: 14
    stochastic:
      period: 14
      smooth: 3
```

## Cache de Dados

O módulo implementa cache inteligente de dados de mercado:
- **Timeout**: 30 segundos
- **Benefícios**: Reduz chamadas ao MT5, melhora performance
- **Limpeza**: Use `analyzer.clear_cache()` para forçar atualização

## Análise de Tendência

O sistema analisa tendências baseado em múltiplos critérios:

### Sinais de Alta (Bullish)
- EMA 9 > EMA 21 > EMA 50
- RSI < 30 (sobrevendido)
- MACD > Signal
- ADX > 25 com DI+ > DI-
- Preço abaixo da banda inferior de Bollinger

### Sinais de Baixa (Bearish)
- EMA 9 < EMA 21 < EMA 50
- RSI > 70 (sobrecomprado)
- MACD < Signal
- ADX > 25 com DI- > DI+
- Preço acima da banda superior de Bollinger

### Força da Tendência
- **0.0 - 0.3**: Tendência fraca ou inexistente
- **0.3 - 0.6**: Tendência moderada
- **0.6 - 1.0**: Tendência forte

## Integração com Order Generator

O Order Generator utiliza o TechnicalAnalyzer para:

1. **Análise de Contexto**: Determinar condições de mercado
2. **Geração de Sinais**: Identificar oportunidades de entrada
3. **Validação de Setup**: Confirmar qualidade do sinal
4. **Filtragem de Ruído**: Evitar sinais fracos ou contraditórios

```python
# No Order Generator
signal = technical_analyzer.get_signal('M5')

if signal['action'] in ['BUY', 'SELL'] and signal['confidence'] > 0.7:
    # Validar com Risk Manager
    if risk_manager.can_open_position(signal['action']):
        # Gerar ordem
        ...
```

## Performance

### Otimizações Implementadas
- ✅ Cache de dados de mercado (30s)
- ✅ Cálculo preguiçoso de indicadores
- ✅ Reutilização de DataFrames
- ✅ Bibliotecas otimizadas (ta, pandas_ta)

### Tempo de Execução Médio
- Análise de 1 timeframe: ~0.2s
- Análise multi-timeframe (4 TFs): ~0.8s
- Geração de sinal: ~1.0s

## Bibliotecas Utilizadas

```bash
pip install ta pandas-ta pandas numpy
```

- **ta**: Biblioteca principal de indicadores técnicos
- **pandas-ta**: Indicadores adicionais
- **pandas**: Manipulação de dados
- **numpy**: Cálculos numéricos

## Testes

Execute os testes com:

```bash
pytest tests/test_technical_analyzer.py -v
```

**Cobertura**: 24 testes unitários
- Cálculo de indicadores
- Detecção de padrões
- Análise de tendência
- Geração de sinais
- Sistema de cache
- Análise multi-timeframe

## Limitações e Considerações

### ⚠️ Avisos Importantes
1. **Indicadores são atrasados**: Baseados em dados históricos
2. **Não garantem lucro**: Análise técnica é probabilística
3. **Falsos sinais**: Sempre validar com outras ferramentas
4. **Contexto de mercado**: Considerar notícias e eventos fundamentais

### 🔄 Melhorias Futuras
- [ ] Volume Profile Analysis
- [ ] Order Flow Analysis
- [ ] Machine Learning para otimização de parâmetros
- [ ] Suporte para mais símbolos
- [ ] Análise de correlação entre ativos
- [ ] Detecção automática de suporte/resistência

## Exemplo Completo

Veja `examples/technical_analysis_demo.py` para exemplo completo funcionando.

```bash
python examples/technical_analysis_demo.py
```

## Troubleshooting

### Erro: Biblioteca 'ta' não encontrada
```bash
pip install ta
```

### Erro: Dados insuficientes
```python
# Aumentar número de barras
analysis = analyzer.analyze_timeframe('M5', bars=500)
```

### Cache desatualizado
```python
# Limpar cache manualmente
analyzer.clear_cache()
```

## Suporte

Para dúvidas ou problemas, verifique:
1. Logs em `logs/trading_bot.log`
2. Documentação do MT5: https://www.mql5.com/en/docs
3. Biblioteca ta: https://technical-analysis-library-in-python.readthedocs.io/

---

**Status**: ✅ Completo e Testado
**Última Atualização**: 18/11/2025
**Versão**: 1.0.0
