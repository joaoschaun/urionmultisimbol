# 🌐 Documentação da API REST

A API REST do Urion permite controle remoto completo do bot de trading.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Autenticação](#autenticação)
- [Endpoints](#endpoints)
- [WebSocket](#websocket)
- [Exemplos](#exemplos)
- [Códigos de Erro](#códigos-de-erro)

---

## 🎯 Visão Geral

### Base URL
```
http://localhost:8000/api/v1
```

### Formato de Resposta
Todas as respostas são em JSON:
```json
{
    "success": true,
    "data": { ... },
    "message": "OK",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Headers Requeridos
```
Content-Type: application/json
Authorization: Bearer <token>
```

---

## 🔐 Autenticação

### Obter Token

```http
POST /api/v1/auth/login
```

**Request:**
```json
{
    "username": "admin",
    "password": "sua_senha"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIs...",
        "token_type": "bearer",
        "expires_in": 3600
    }
}
```

### Usar Token
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
     http://localhost:8000/api/v1/status
```

---

## 📚 Endpoints

### Status do Bot

#### GET /status
Retorna status atual do bot.

**Response:**
```json
{
    "success": true,
    "data": {
        "running": true,
        "connected": true,
        "trading_enabled": true,
        "last_cycle": "2024-01-15T10:30:00Z",
        "uptime_seconds": 86400,
        "version": "2.0.0"
    }
}
```

---

### Conta

#### GET /account
Retorna informações da conta MT5.

**Response:**
```json
{
    "success": true,
    "data": {
        "login": 12345678,
        "name": "John Doe",
        "server": "Broker-Server",
        "balance": 10000.00,
        "equity": 10250.00,
        "margin": 500.00,
        "free_margin": 9750.00,
        "margin_level": 2050.00,
        "profit": 250.00,
        "currency": "USD",
        "leverage": 100
    }
}
```

---

### Posições

#### GET /positions
Retorna posições abertas.

**Response:**
```json
{
    "success": true,
    "data": {
        "positions": [
            {
                "ticket": 123456789,
                "symbol": "XAUUSD",
                "type": "buy",
                "volume": 0.1,
                "price_open": 2000.50,
                "price_current": 2005.30,
                "sl": 1995.00,
                "tp": 2015.00,
                "profit": 48.00,
                "swap": -1.20,
                "commission": -0.50,
                "time": "2024-01-15T08:00:00Z",
                "strategy": "trend_following",
                "comment": "TF_H1_2024.01.15"
            }
        ],
        "total_positions": 1,
        "total_profit": 48.00
    }
}
```

#### POST /positions/close/{ticket}
Fecha uma posição específica.

**Parameters:**
- `ticket` (path): Ticket da posição

**Response:**
```json
{
    "success": true,
    "data": {
        "ticket": 123456789,
        "closed_at": 2005.50,
        "profit": 50.00
    },
    "message": "Position closed successfully"
}
```

#### POST /positions/close-all
Fecha todas as posições abertas.

**Response:**
```json
{
    "success": true,
    "data": {
        "closed_count": 3,
        "total_profit": 150.00
    }
}
```

---

### Trades (Histórico)

#### GET /trades
Retorna histórico de trades.

**Query Parameters:**
- `start_date` (optional): Data inicial (YYYY-MM-DD)
- `end_date` (optional): Data final (YYYY-MM-DD)
- `symbol` (optional): Filtrar por símbolo
- `strategy` (optional): Filtrar por estratégia
- `limit` (optional): Número máximo de resultados (default: 100)
- `offset` (optional): Offset para paginação

**Request:**
```http
GET /trades?start_date=2024-01-01&symbol=XAUUSD&limit=50
```

**Response:**
```json
{
    "success": true,
    "data": {
        "trades": [
            {
                "ticket": 123456788,
                "symbol": "XAUUSD",
                "type": "buy",
                "volume": 0.1,
                "price_open": 1998.00,
                "price_close": 2005.00,
                "sl": 1993.00,
                "tp": 2010.00,
                "profit": 70.00,
                "swap": -0.50,
                "commission": -0.50,
                "time_open": "2024-01-14T10:00:00Z",
                "time_close": "2024-01-14T18:30:00Z",
                "duration_minutes": 510,
                "strategy": "trend_following",
                "r_multiple": 1.4
            }
        ],
        "total_count": 150,
        "returned_count": 50,
        "summary": {
            "total_profit": 1500.00,
            "win_rate": 0.62,
            "profit_factor": 1.85
        }
    }
}
```

---

### Estratégias

#### GET /strategies
Retorna status de todas as estratégias.

**Response:**
```json
{
    "success": true,
    "data": {
        "strategies": [
            {
                "name": "trend_following",
                "enabled": true,
                "symbols": ["XAUUSD", "EURUSD"],
                "timeframes": ["H1", "H4"],
                "stats": {
                    "total_trades": 45,
                    "win_rate": 0.64,
                    "profit_factor": 2.1,
                    "avg_r_multiple": 1.3,
                    "sharpe_ratio": 1.8
                },
                "last_signal": "2024-01-15T10:00:00Z"
            },
            {
                "name": "mean_reversion",
                "enabled": true,
                "symbols": ["XAUUSD"],
                "timeframes": ["M15", "H1"],
                "stats": {
                    "total_trades": 78,
                    "win_rate": 0.58,
                    "profit_factor": 1.6,
                    "avg_r_multiple": 0.9,
                    "sharpe_ratio": 1.2
                },
                "last_signal": "2024-01-15T09:45:00Z"
            }
        ]
    }
}
```

#### POST /strategies/{name}/enable
Ativa uma estratégia.

#### POST /strategies/{name}/disable
Desativa uma estratégia.

---

### Métricas

#### GET /metrics
Retorna métricas de performance.

**Response:**
```json
{
    "success": true,
    "data": {
        "overall": {
            "total_trades": 500,
            "winning_trades": 310,
            "losing_trades": 190,
            "win_rate": 0.62,
            "profit_factor": 1.95,
            "total_profit": 15000.00,
            "max_drawdown": 0.08,
            "sharpe_ratio": 1.75,
            "sortino_ratio": 2.10,
            "calmar_ratio": 2.50,
            "sqn": 2.8,
            "avg_r_multiple": 1.2,
            "expectancy": 30.00
        },
        "by_symbol": {
            "XAUUSD": {
                "trades": 300,
                "win_rate": 0.65,
                "profit": 10000.00
            },
            "EURUSD": {
                "trades": 200,
                "win_rate": 0.58,
                "profit": 5000.00
            }
        },
        "by_strategy": {
            "trend_following": {
                "trades": 150,
                "win_rate": 0.68,
                "profit": 8000.00
            }
        },
        "daily": {
            "today_profit": 250.00,
            "today_trades": 5,
            "today_win_rate": 0.80
        }
    }
}
```

#### GET /metrics/equity-curve
Retorna dados da curva de equity.

**Response:**
```json
{
    "success": true,
    "data": {
        "points": [
            {"date": "2024-01-01", "equity": 10000.00},
            {"date": "2024-01-02", "equity": 10150.00},
            {"date": "2024-01-03", "equity": 10080.00},
            ...
        ]
    }
}
```

---

### Configurações

#### GET /settings
Retorna configurações atuais.

**Response:**
```json
{
    "success": true,
    "data": {
        "trading": {
            "enabled": true,
            "symbols": ["XAUUSD", "EURUSD"],
            "max_positions": 5,
            "risk_per_trade": 0.02
        },
        "risk_management": {
            "max_daily_loss": 0.05,
            "max_drawdown": 0.10,
            "trailing_stop": true,
            "break_even": true
        },
        "notifications": {
            "telegram_enabled": true,
            "trade_alerts": true,
            "daily_report": true
        }
    }
}
```

#### PUT /settings
Atualiza configurações.

**Request:**
```json
{
    "trading": {
        "max_positions": 3,
        "risk_per_trade": 0.01
    }
}
```

**Response:**
```json
{
    "success": true,
    "message": "Settings updated successfully"
}
```

---

### Market Data

#### GET /market/quote/{symbol}
Retorna cotação atual.

**Response:**
```json
{
    "success": true,
    "data": {
        "symbol": "XAUUSD",
        "bid": 2005.50,
        "ask": 2005.70,
        "spread": 0.20,
        "time": "2024-01-15T10:30:00Z"
    }
}
```

#### GET /market/regime/{symbol}
Retorna regime de mercado atual.

**Response:**
```json
{
    "success": true,
    "data": {
        "symbol": "XAUUSD",
        "regime": "STRONG_TREND",
        "direction": "bullish",
        "confidence": 0.85,
        "recommended_strategies": ["trend_following", "breakout"],
        "indicators": {
            "adx": 35.5,
            "volatility": "medium",
            "trend_strength": "strong"
        }
    }
}
```

---

## 🔌 WebSocket

### Conectar

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
    console.log('Connected');
    // Subscrever a canais
    ws.send(JSON.stringify({
        action: 'subscribe',
        channels: ['trades', 'positions', 'quotes']
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```

### Eventos Disponíveis

#### trade_opened
```json
{
    "event": "trade_opened",
    "data": {
        "ticket": 123456789,
        "symbol": "XAUUSD",
        "type": "buy",
        "volume": 0.1,
        "price": 2000.50,
        "sl": 1995.00,
        "tp": 2015.00,
        "strategy": "trend_following"
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

#### trade_closed
```json
{
    "event": "trade_closed",
    "data": {
        "ticket": 123456789,
        "symbol": "XAUUSD",
        "profit": 50.00,
        "close_reason": "take_profit"
    }
}
```

#### position_updated
```json
{
    "event": "position_updated",
    "data": {
        "ticket": 123456789,
        "profit": 48.00,
        "sl_moved": true,
        "new_sl": 2000.00
    }
}
```

#### quote_update
```json
{
    "event": "quote_update",
    "data": {
        "symbol": "XAUUSD",
        "bid": 2005.50,
        "ask": 2005.70
    }
}
```

#### alert
```json
{
    "event": "alert",
    "data": {
        "type": "warning",
        "message": "Daily loss limit approaching (4.5%)",
        "action_required": false
    }
}
```

---

## 💻 Exemplos

### Python

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "seu_token_aqui"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Obter status
response = requests.get(f"{BASE_URL}/status", headers=headers)
print(response.json())

# Listar posições
positions = requests.get(f"{BASE_URL}/positions", headers=headers)
for pos in positions.json()['data']['positions']:
    print(f"{pos['symbol']}: {pos['profit']}")

# Fechar posição
ticket = 123456789
close = requests.post(f"{BASE_URL}/positions/close/{ticket}", headers=headers)
print(close.json())
```

### JavaScript

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';
const TOKEN = 'seu_token_aqui';

async function getStatus() {
    const response = await fetch(`${BASE_URL}/status`, {
        headers: {
            'Authorization': `Bearer ${TOKEN}`,
            'Content-Type': 'application/json'
        }
    });
    return await response.json();
}

async function closePosition(ticket) {
    const response = await fetch(`${BASE_URL}/positions/close/${ticket}`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${TOKEN}`,
            'Content-Type': 'application/json'
        }
    });
    return await response.json();
}

// Uso
getStatus().then(console.log);
```

### cURL

```bash
# Status
curl -X GET "http://localhost:8000/api/v1/status" \
     -H "Authorization: Bearer $TOKEN"

# Posições
curl -X GET "http://localhost:8000/api/v1/positions" \
     -H "Authorization: Bearer $TOKEN"

# Fechar posição
curl -X POST "http://localhost:8000/api/v1/positions/close/123456789" \
     -H "Authorization: Bearer $TOKEN"

# Atualizar configurações
curl -X PUT "http://localhost:8000/api/v1/settings" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"trading": {"max_positions": 3}}'
```

---

## ❌ Códigos de Erro

| Código | Descrição |
|--------|-----------|
| 400 | Bad Request - Parâmetros inválidos |
| 401 | Unauthorized - Token inválido ou expirado |
| 403 | Forbidden - Sem permissão |
| 404 | Not Found - Recurso não encontrado |
| 409 | Conflict - Conflito de estado |
| 422 | Unprocessable Entity - Dados inválidos |
| 429 | Too Many Requests - Rate limit excedido |
| 500 | Internal Server Error - Erro interno |
| 503 | Service Unavailable - Bot não conectado |

### Formato de Erro

```json
{
    "success": false,
    "error": {
        "code": "POSITION_NOT_FOUND",
        "message": "Position with ticket 123456789 not found",
        "details": {}
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Códigos de Erro Específicos

| Código | Descrição |
|--------|-----------|
| `AUTH_INVALID` | Credenciais inválidas |
| `TOKEN_EXPIRED` | Token expirado |
| `MT5_DISCONNECTED` | MT5 desconectado |
| `POSITION_NOT_FOUND` | Posição não encontrada |
| `INSUFFICIENT_MARGIN` | Margem insuficiente |
| `TRADING_DISABLED` | Trading desabilitado |
| `RATE_LIMIT_EXCEEDED` | Limite de requisições excedido |

---

## 🔒 Rate Limiting

| Endpoint | Limite |
|----------|--------|
| `/auth/*` | 5/min |
| `/positions/*` | 30/min |
| `/trades/*` | 60/min |
| Outros | 120/min |

Headers de resposta:
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 115
X-RateLimit-Reset: 1705318200
```

---

## 📞 Suporte

Para dúvidas sobre a API:
- Email: api-support@exemplo.com
- Documentação: [docs/](.)
- Issues: GitHub Issues
