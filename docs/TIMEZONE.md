# Configuração de Fuso Horário - URION Trading Bot

## 📍 Timezone Configurado

**America/New_York (EST/EDT)**

O bot agora opera no fuso horário de Nova York, que é o fuso horário padrão dos mercados financeiros globais.

## ⏰ Horários de Operação

### Horário EST (Eastern Standard Time) - Novembro a Março
**UTC -5 horas**

### Horário EDT (Eastern Daylight Time) - Março a Novembro  
**UTC -4 horas**

> 🔄 O bot ajusta automaticamente entre EST e EDT

## 📅 Janelas de Trading

### Domingo
- **Abertura**: 18:30 EST/EDT
- Mercado inicia a semana

### Segunda a Quinta
- **Sessão 1**: 00:00 - 16:30 EST/EDT
- **Pausa**: 16:30 - 18:20 EST/EDT (mercado fechado)
- **Sessão 2**: 18:20 - 23:59 EST/EDT

### Sexta-feira
- **Trading**: 00:00 - 16:30 EST/EDT
- **Fechamento semanal**: 16:30 EST/EDT

## ⚠️ Regras de Segurança

### Fechamento Automático de Posições
- **30 minutos antes** do fechamento do mercado
- Sexta às 16:00 EST/EDT
- Quinta a Sexta às 16:00 EST/EDT (pausa diária)

### Bloqueio de Novas Operações
- **15 minutos após** abertura do mercado
- Reduz risco de volatilidade na abertura

### Pausa Diária
- **16:30 - 18:20 EST/EDT**
- Todas as posições são fechadas antes da pausa
- Não abre novas posições durante a pausa

## 🔧 Arquivos Configurados

### config/config.yaml
```yaml
schedule:
  timezone: America/New_York
  trading_days: [0, 1, 2, 3, 4]  # Segunda a Sexta
  market_open:
    hour: 18
    minute: 30
  market_close:
    hour: 16
    minute: 30
```

### .env.example
```bash
# Trading Hours (America/New_York - EST/EDT)
MARKET_OPEN_HOUR=18
MARKET_OPEN_MINUTE=30
MARKET_CLOSE_HOUR=16
MARKET_CLOSE_MINUTE=30
```

## 🧪 Teste de Timezone

Execute o script de teste para verificar a configuração:

```bash
python test_timezone.py
```

Este script exibe:
- Timezone configurado
- Hora atual em diferentes fusos (Local, UTC, New York)
- Diferença horária
- Status do mercado (aberto/fechado)
- Próximo evento de mercado
- Horários de trading detalhados

## 📊 Conversão de Horários

### Exemplos (EST - Inverno)

| New York (EST) | UTC | Brasília (BRT) |
|---------------|-----|----------------|
| 18:30 | 23:30 | 20:30 |
| 00:00 | 05:00 | 02:00 |
| 16:30 | 21:30 | 18:30 |

### Exemplos (EDT - Verão)

| New York (EDT) | UTC | Brasília (BRT) |
|---------------|-----|----------------|
| 18:30 | 22:30 | 19:30 |
| 00:00 | 04:00 | 01:00 |
| 16:30 | 20:30 | 17:30 |

> 📝 **Nota**: Brasília não tem horário de verão desde 2019

## 🔍 Verificação em Logs

Os logs do sistema mostram o timezone em uso:

```
2025-11-19 18:18:11 EST | INFO | MarketHoursManager inicializado
2025-11-19 18:18:11 EST | INFO | Timezone: America/New_York
```

## 🌍 Por que New York?

1. **Padrão do mercado Forex**: Horários de trading globais baseados em EST/EDT
2. **Liquidez**: Maior volume de negociações durante horário de NY
3. **Sincronização**: Alinha com fechamento de Chicago Mercantile Exchange
4. **Notícias econômicas**: Releases de dados dos EUA seguem horário de NY

## ⚙️ Ajuste Automático DST

O bot usa `pytz` para gerenciar automaticamente:
- Mudança para EDT (segundo domingo de março)
- Mudança para EST (primeiro domingo de novembro)
- Não requer intervenção manual

## 📞 Suporte

Se houver problemas com timezone:
1. Execute `python test_timezone.py`
2. Verifique logs: `logs/urion.log`
3. Confirme que `pytz` está instalado: `pip install pytz`

---

**Data da configuração**: 19/11/2025  
**Versão**: URION Trading Bot v2.0
