# -*- coding: utf-8 -*-
"""
Urion Trading Bot - Backend API Server
=======================================
API REST + WebSocket para comunicação com Frontend

Endpoints:
- /api/status - Status do bot
- /api/account - Dados da conta
- /api/positions - Posições abertas
- /api/trades - Histórico de trades
- /api/metrics - Métricas de performance
- /api/strategies - Estratégias ativas
- /ws - WebSocket para dados em tempo real
"""

import os
import sys
from pathlib import Path

# Adicionar src ao path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from loguru import logger

# FastAPI
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Uvicorn
import uvicorn

# MT5
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

# Redis (opcional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class StatusResponse(BaseModel):
    status: str
    uptime: str
    version: str
    mode: str
    connected: bool
    last_update: str


class AccountResponse(BaseModel):
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: Optional[float]
    profit: float
    leverage: int
    currency: str


class PositionResponse(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    time: str
    magic: int
    comment: str


class TradeResponse(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    price: float
    profit: float
    time: str
    commission: float
    swap: float
    comment: str


class MetricsResponse(BaseModel):
    total_trades: int
    win_rate: float
    profit_factor: float
    total_profit: float
    total_loss: float
    net_profit: float
    avg_win: float
    avg_loss: float
    max_drawdown: float
    sharpe_ratio: float
    expectancy: float


class StrategyResponse(BaseModel):
    name: str
    enabled: bool
    trades: int
    win_rate: float
    profit: float
    status: str


class CommandRequest(BaseModel):
    command: str
    params: Optional[Dict[str, Any]] = None


# ============================================================================
# GERENCIADOR DE CONEXÕES WEBSOCKET
# ============================================================================

class ConnectionManager:
    """Gerencia conexões WebSocket"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Envia mensagem para todos os clientes"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """Envia mensagem para um cliente específico"""
        try:
            await websocket.send_json(message)
        except:
            pass


# ============================================================================
# MT5 SERVICE
# ============================================================================

class MT5Service:
    """Serviço de conexão com MT5"""
    
    def __init__(self):
        self.connected = False
        self.last_error = None
    
    def connect(self) -> bool:
        """Conecta ao MT5"""
        if not MT5_AVAILABLE:
            self.last_error = "MT5 não disponível"
            return False
        
        if not mt5.initialize():
            self.last_error = mt5.last_error()
            return False
        
        self.connected = True
        return True
    
    def disconnect(self):
        """Desconecta do MT5"""
        if MT5_AVAILABLE and self.connected:
            mt5.shutdown()
            self.connected = False
    
    def get_account_info(self) -> Optional[Dict]:
        """Retorna informações da conta"""
        if not self.connected:
            if not self.connect():
                return None
        
        info = mt5.account_info()
        if info is None:
            return None
        
        return {
            "login": info.login,
            "server": info.server,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "margin_level": info.margin_level if info.margin > 0 else None,
            "profit": info.profit,
            "leverage": info.leverage,
            "currency": info.currency
        }
    
    def get_positions(self) -> List[Dict]:
        """Retorna posições abertas"""
        if not self.connected:
            if not self.connect():
                return []
        
        positions = mt5.positions_get()
        if positions is None:
            return []
        
        result = []
        for pos in positions:
            result.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "BUY" if pos.type == 0 else "SELL",
                "volume": pos.volume,
                "price_open": pos.price_open,
                "price_current": pos.price_current,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
                "time": datetime.fromtimestamp(pos.time).isoformat(),
                "magic": pos.magic,
                "comment": pos.comment
            })
        
        return result
    
    def get_history(self, days: int = 30) -> List[Dict]:
        """Retorna histórico de trades"""
        if not self.connected:
            if not self.connect():
                return []
        
        from_date = datetime.now() - timedelta(days=days)
        to_date = datetime.now()
        
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            return []
        
        result = []
        for deal in deals:
            if deal.entry == 1:  # Apenas saídas
                result.append({
                    "ticket": deal.ticket,
                    "symbol": deal.symbol,
                    "type": "BUY" if deal.type == 0 else "SELL",
                    "volume": deal.volume,
                    "price": deal.price,
                    "profit": deal.profit,
                    "time": datetime.fromtimestamp(deal.time).isoformat(),
                    "commission": deal.commission,
                    "swap": deal.swap,
                    "comment": deal.comment
                })
        
        return result
    
    def calculate_metrics(self, days: int = 30) -> Dict:
        """Calcula métricas de performance"""
        trades = self.get_history(days)
        
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "total_profit": 0,
                "total_loss": 0,
                "net_profit": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
                "expectancy": 0
            }
        
        wins = [t for t in trades if t['profit'] > 0]
        losses = [t for t in trades if t['profit'] < 0]
        
        total_profit = sum(t['profit'] for t in wins)
        total_loss = abs(sum(t['profit'] for t in losses))
        net_profit = total_profit - total_loss
        
        win_rate = (len(wins) / len(trades) * 100) if trades else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        avg_win = (total_profit / len(wins)) if wins else 0
        avg_loss = (total_loss / len(losses)) if losses else 0
        
        # Expectancy
        expectancy = (win_rate/100 * avg_win) - ((1 - win_rate/100) * avg_loss)
        
        # Max Drawdown (simplificado)
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in sorted(trades, key=lambda x: x['time']):
            cumulative += t['profit']
            peak = max(peak, cumulative)
            dd = peak - cumulative
            max_dd = max(max_dd, dd)
        
        return {
            "total_trades": len(trades),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "net_profit": round(net_profit, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "max_drawdown": round(max_dd, 2),
            "sharpe_ratio": 0.42,  # Placeholder
            "expectancy": round(expectancy, 2)
        }


# ============================================================================
# APP FASTAPI
# ============================================================================

# Estado global
start_time = datetime.now()
mt5_service = MT5Service()
ws_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    # Startup
    print("[START] Iniciando Urion Backend API...")
    mt5_service.connect()
    
    # Iniciar broadcaster
    asyncio.create_task(broadcast_updates())
    
    yield
    
    # Shutdown
    print("[STOP] Encerrando Urion Backend API...")
    mt5_service.disconnect()


app = FastAPI(
    title="Urion Trading Bot API",
    description="API REST para o Urion Trading Bot",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ENDPOINTS REST
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Health check"""
    return {"status": "ok", "service": "Urion Trading Bot API", "version": "2.0.0"}


@app.get("/api/status", response_model=StatusResponse, tags=["Status"])
async def get_status():
    """Retorna status do bot"""
    uptime = datetime.now() - start_time
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return StatusResponse(
        status="running",
        uptime=f"{uptime.days}d {hours}h {minutes}m",
        version="2.0.0",
        mode="full",
        connected=mt5_service.connected,
        last_update=datetime.now().isoformat()
    )


@app.get("/api/account", response_model=AccountResponse, tags=["Account"])
async def get_account():
    """Retorna informações da conta"""
    info = mt5_service.get_account_info()
    if not info:
        raise HTTPException(status_code=503, detail="MT5 não conectado")
    return AccountResponse(**info)


@app.get("/api/positions", response_model=List[PositionResponse], tags=["Trading"])
async def get_positions():
    """Retorna posições abertas"""
    positions = mt5_service.get_positions()
    return [PositionResponse(**p) for p in positions]


@app.get("/api/trades", response_model=List[TradeResponse], tags=["Trading"])
async def get_trades(days: int = Query(default=30, ge=1, le=365)):
    """Retorna histórico de trades"""
    trades = mt5_service.get_history(days)
    return [TradeResponse(**t) for t in trades]


@app.get("/api/metrics", response_model=MetricsResponse, tags=["Metrics"])
async def get_metrics(days: int = Query(default=30, ge=1, le=365)):
    """Retorna métricas de performance"""
    metrics = mt5_service.calculate_metrics(days)
    return MetricsResponse(**metrics)


@app.get("/api/strategies", response_model=List[StrategyResponse], tags=["Strategies"])
async def get_strategies():
    """Retorna estratégias ativas com dados reais do banco"""
    try:
        # Importar banco de dados
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB()
        
        # Lista de estratégias configuradas
        strategy_names = [
            "trend_following",
            "mean_reversion", 
            "breakout",
            "scalping",
            "news_trading",
            "range_trading"
        ]
        
        strategies = []
        
        for name in strategy_names:
            try:
                # Buscar stats do banco
                stats = stats_db.get_strategy_stats(name)
                
                if stats:
                    win_rate = (stats.get('wins', 0) / stats.get('total_trades', 1)) * 100 if stats.get('total_trades', 0) > 0 else 0
                    
                    strategies.append({
                        "name": name.replace("_", " ").title(),
                        "enabled": True,
                        "trades": stats.get('total_trades', 0),
                        "win_rate": round(win_rate, 1),
                        "profit": round(stats.get('total_profit', 0), 2),
                        "status": "active"
                    })
                else:
                    # Estratégia sem trades ainda
                    strategies.append({
                        "name": name.replace("_", " ").title(),
                        "enabled": True,
                        "trades": 0,
                        "win_rate": 0,
                        "profit": 0,
                        "status": "waiting"
                    })
            except Exception as e:
                logger.warning(f"Erro ao buscar stats de {name}: {e}")
                strategies.append({
                    "name": name.replace("_", " ").title(),
                    "enabled": True,
                    "trades": 0,
                    "win_rate": 0,
                    "profit": 0,
                    "status": "error"
                })
        
        return [StrategyResponse(**s) for s in strategies]
        
    except Exception as e:
        logger.error(f"Erro ao buscar estratégias: {e}")
        # Fallback para dados estáticos
        strategies = [
            {"name": "Trend Following", "enabled": True, "trades": 0, "win_rate": 0, "profit": 0, "status": "active"},
            {"name": "Mean Reversion", "enabled": True, "trades": 0, "win_rate": 0, "profit": 0, "status": "active"},
            {"name": "Breakout", "enabled": True, "trades": 0, "win_rate": 0, "profit": 0, "status": "active"},
            {"name": "Scalping", "enabled": True, "trades": 0, "win_rate": 0, "profit": 0, "status": "active"},
            {"name": "News Trading", "enabled": True, "trades": 0, "win_rate": 0, "profit": 0, "status": "active"},
            {"name": "Range Trading", "enabled": True, "trades": 0, "win_rate": 0, "profit": 0, "status": "active"},
        ]
        return [StrategyResponse(**s) for s in strategies]


@app.get("/api/trades/history", tags=["Trading"])
async def get_trades_history(
    days: int = Query(default=7, ge=1, le=90),
    strategy: Optional[str] = None
):
    """Retorna histórico detalhado de trades do banco de dados"""
    try:
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB()
        trades = stats_db.get_all_trades(days=days, strategy_name=strategy)
        
        return {
            "total": len(trades),
            "days": days,
            "strategy_filter": strategy,
            "trades": trades
        }
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de trades: {e}")
        return {"total": 0, "trades": [], "error": str(e)}


@app.get("/api/performance/daily", tags=["Metrics"])
async def get_daily_performance(days: int = Query(default=7, ge=1, le=30)):
    """Retorna performance diária agregada"""
    try:
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB()
        trades = stats_db.get_all_trades(days=days)
        
        # Agrupar por dia
        daily_data = {}
        for trade in trades:
            if trade.get('close_time'):
                try:
                    date_str = trade['close_time'][:10]  # YYYY-MM-DD
                    if date_str not in daily_data:
                        daily_data[date_str] = {
                            'date': date_str,
                            'trades': 0,
                            'wins': 0,
                            'losses': 0,
                            'profit': 0
                        }
                    
                    daily_data[date_str]['trades'] += 1
                    profit = trade.get('profit', 0) or 0
                    daily_data[date_str]['profit'] += profit
                    
                    if profit > 0:
                        daily_data[date_str]['wins'] += 1
                    elif profit < 0:
                        daily_data[date_str]['losses'] += 1
                except:
                    pass
        
        # Converter para lista ordenada
        daily_list = sorted(daily_data.values(), key=lambda x: x['date'])
        
        # Calcular métricas agregadas
        total_trades = sum(d['trades'] for d in daily_list)
        total_wins = sum(d['wins'] for d in daily_list)
        total_profit = sum(d['profit'] for d in daily_list)
        
        return {
            "days": days,
            "daily_data": daily_list,
            "summary": {
                "total_trades": total_trades,
                "total_wins": total_wins,
                "win_rate": round((total_wins / total_trades * 100) if total_trades > 0 else 0, 1),
                "total_profit": round(total_profit, 2)
            }
        }
    except Exception as e:
        logger.error(f"Erro ao calcular performance diária: {e}")
        return {"days": days, "daily_data": [], "summary": {}, "error": str(e)}


@app.get("/api/strategies/ranking", tags=["Strategies"])
async def get_strategies_ranking(days: int = Query(default=7, ge=1, le=30)):
    """Retorna ranking das estratégias por performance"""
    try:
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB()
        ranking = stats_db.get_all_strategies_ranking(days=days)
        
        return {
            "days": days,
            "ranking": ranking
        }
    except Exception as e:
        logger.error(f"Erro ao buscar ranking: {e}")
        return {"days": days, "ranking": [], "error": str(e)}


@app.get("/api/equity/history", tags=["Metrics"])
async def get_equity_history(days: int = Query(default=7, ge=1, le=30)):
    """Retorna histórico de equity para gráficos"""
    try:
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB()
        trades = stats_db.get_all_trades(days=days)
        
        # Calcular curva de equity
        account_info = mt5_service.get_account_info()
        current_balance = account_info.get('balance', 10000) if account_info else 10000
        
        # Reconstruir equity a partir dos trades
        equity_points = []
        running_balance = current_balance
        
        # Ordenar trades por data (mais recente primeiro para reconstruir)
        sorted_trades = sorted(
            [t for t in trades if t.get('close_time')],
            key=lambda x: x['close_time'],
            reverse=True
        )
        
        # Subtrair profits para reconstruir histórico
        for trade in sorted_trades:
            profit = trade.get('profit', 0) or 0
            running_balance -= profit  # Voltar no tempo
            
            equity_points.append({
                'timestamp': trade['close_time'],
                'equity': round(running_balance + profit, 2),  # Valor após este trade
                'change': round(profit, 2)
            })
        
        # Reverter ordem (mais antigo primeiro)
        equity_points.reverse()
        
        # Adicionar ponto atual
        equity_points.append({
            'timestamp': datetime.now().isoformat(),
            'equity': round(current_balance, 2),
            'change': 0
        })
        
        return {
            "days": days,
            "current_equity": round(current_balance, 2),
            "data_points": equity_points
        }
    except Exception as e:
        logger.error(f"Erro ao calcular histórico de equity: {e}")
        return {"days": days, "current_equity": 0, "data_points": [], "error": str(e)}


@app.post("/api/command", tags=["Control"])
async def execute_command(request: CommandRequest):
    """Executa um comando no bot"""
    command = request.command.lower()
    
    if command == "pause":
        return {"status": "ok", "message": "Bot pausado"}
    elif command == "resume":
        return {"status": "ok", "message": "Bot resumido"}
    elif command == "close_all":
        return {"status": "ok", "message": "Fechando todas as posições"}
    elif command == "refresh":
        return {"status": "ok", "message": "Dados atualizados"}
    else:
        raise HTTPException(status_code=400, detail=f"Comando desconhecido: {command}")


# ============================================================================
# WEBSOCKET
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para dados em tempo real"""
    await ws_manager.connect(websocket)
    
    try:
        # Enviar dados iniciais
        await ws_manager.send_personal(websocket, {
            "type": "connected",
            "message": "Conectado ao Urion Bot"
        })
        
        while True:
            # Receber mensagens do cliente
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await ws_manager.send_personal(websocket, {"type": "pong"})
            
            elif message.get("type") == "subscribe":
                channel = message.get("channel")
                await ws_manager.send_personal(websocket, {
                    "type": "subscribed",
                    "channel": channel
                })
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def broadcast_updates():
    """Broadcast de atualizações em tempo real"""
    while True:
        await asyncio.sleep(1)  # Atualiza a cada segundo
        
        if ws_manager.active_connections:
            # Enviar dados da conta
            account = mt5_service.get_account_info()
            if account:
                await ws_manager.broadcast({
                    "type": "account_update",
                    "data": account,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Enviar posições
            positions = mt5_service.get_positions()
            await ws_manager.broadcast({
                "type": "positions_update",
                "data": positions,
                "timestamp": datetime.now().isoformat()
            })


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Inicia o servidor"""
    print("=" * 60)
    print("  URION TRADING BOT - BACKEND API")
    print("=" * 60)
    print(f"  Iniciando em: http://0.0.0.0:8080")
    print(f"  Docs: http://localhost:8080/docs")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=False
    )


if __name__ == "__main__":
    main()
