"""
REST API Server - FastAPI
Fornece API HTTP/WebSocket para controle remoto do bot Urion

Endpoints:
- /api/status - Status do bot
- /api/account - Informações da conta
- /api/positions - Posições abertas
- /api/trades - Histórico de trades
- /api/metrics - Métricas avançadas
- /api/config - Configuração
- /api/control - Controle do bot
- /ws - WebSocket para atualizações em tempo real
"""
import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from loguru import logger


# ==================== Models ====================

class StatusResponse(BaseModel):
    """Resposta do status do bot"""
    status: str
    uptime_seconds: float
    uptime_formatted: str
    is_trading: bool
    market_open: bool
    last_cycle: Optional[str] = None
    version: str = "2.0.0"


class AccountInfo(BaseModel):
    """Informações da conta"""
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    profit: float
    currency: str = "USD"


class PositionInfo(BaseModel):
    """Informação de posição"""
    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    swap: float
    magic: int
    comment: str
    time_open: str


class TradeInfo(BaseModel):
    """Informação de trade histórico"""
    ticket: int
    symbol: str
    type: str
    volume: float
    price: float
    profit: float
    time: str
    strategy: Optional[str] = None


class MetricsResponse(BaseModel):
    """Métricas de trading"""
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    max_drawdown: float
    sqn: float
    sqn_rating: str
    avg_r_multiple: float
    r_expectancy: float
    sharpe_ratio: Optional[float] = None


class ConfigUpdate(BaseModel):
    """Atualização de configuração"""
    key: str
    value: Any


class ControlCommand(BaseModel):
    """Comando de controle"""
    action: str  # start, stop, pause, resume
    params: Optional[Dict[str, Any]] = None


# ==================== API Server ====================

class APIServer:
    """
    Servidor REST API para o Urion Trading Bot
    
    Features:
    - Endpoints RESTful para todas as funcionalidades
    - WebSocket para streaming em tempo real
    - Autenticação básica via token
    - CORS configurável
    """
    
    def __init__(
        self,
        mt5_connector=None,
        config_manager=None,
        stats_db=None,
        trade_journal=None,
        host: str = "0.0.0.0",
        port: int = 8080,
        api_key: Optional[str] = None
    ):
        """
        Inicializa o servidor API
        
        Args:
            mt5_connector: Instância do MT5Connector
            config_manager: Instância do ConfigManager
            stats_db: Instância do StrategyStatsDB
            trade_journal: Instância do TradeJournal
            host: Host para bind
            port: Porta
            api_key: Chave de API para autenticação
        """
        self.mt5 = mt5_connector
        self.config = config_manager
        self.stats_db = stats_db
        self.journal = trade_journal
        self.host = host
        self.port = port
        self.api_key = api_key or os.getenv('API_KEY', 'urion-secret-key')
        
        self.start_time = datetime.now(timezone.utc)
        self.is_trading = True
        self.is_paused = False
        
        # WebSocket connections
        self._websocket_clients: List[WebSocket] = []
        
        # Criar app FastAPI
        self.app = FastAPI(
            title="Urion Trading Bot API",
            description="API REST para controle e monitoramento do bot de trading",
            version="2.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Configurar CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Em produção, especificar origens
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Registrar rotas
        self._setup_routes()
        
        logger.info(
            f"🌐 API Server inicializado | "
            f"Host: {host}:{port} | "
            f"Docs: http://{host}:{port}/docs"
        )
    
    def _verify_api_key(self, api_key: str = Query(None, alias="api_key")):
        """Verifica chave de API"""
        if api_key != self.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return True
    
    def _setup_routes(self):
        """Configura rotas da API"""
        
        # ========== Status ==========
        @self.app.get("/api/status", response_model=StatusResponse)
        async def get_status():
            """Retorna status do bot"""
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            
            return StatusResponse(
                status="running" if self.is_trading else "stopped",
                uptime_seconds=uptime,
                uptime_formatted=f"{hours}h {minutes}m",
                is_trading=self.is_trading and not self.is_paused,
                market_open=self._is_market_open(),
                last_cycle=datetime.now().isoformat(),
                version="2.0.0"
            )
        
        # ========== Account ==========
        @self.app.get("/api/account", response_model=AccountInfo)
        async def get_account():
            """Retorna informações da conta"""
            if not self.mt5:
                raise HTTPException(status_code=503, detail="MT5 not available")
            
            try:
                import MetaTrader5 as mt5
                if not mt5.initialize():
                    raise HTTPException(status_code=503, detail="MT5 not connected")
                
                account = mt5.account_info()
                if not account:
                    raise HTTPException(status_code=500, detail="Failed to get account info")
                
                return AccountInfo(
                    login=account.login,
                    server=account.server,
                    balance=account.balance,
                    equity=account.equity,
                    margin=account.margin,
                    free_margin=account.margin_free,
                    margin_level=account.margin_level,
                    profit=account.profit,
                    currency=account.currency
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== Positions ==========
        @self.app.get("/api/positions", response_model=List[PositionInfo])
        async def get_positions():
            """Retorna posições abertas"""
            if not self.mt5:
                raise HTTPException(status_code=503, detail="MT5 not available")
            
            try:
                positions = self.mt5.get_open_positions()
                return [
                    PositionInfo(
                        ticket=p['ticket'],
                        symbol=p['symbol'],
                        type='BUY' if p['type'] == 0 else 'SELL',
                        volume=p['volume'],
                        price_open=p['price_open'],
                        price_current=p['price_current'],
                        sl=p.get('sl', 0),
                        tp=p.get('tp', 0),
                        profit=p['profit'],
                        swap=p.get('swap', 0),
                        magic=p.get('magic', 0),
                        comment=p.get('comment', ''),
                        time_open=str(p.get('time', ''))
                    )
                    for p in positions
                ]
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/positions/{ticket}")
        async def close_position(ticket: int):
            """Fecha uma posição específica"""
            if not self.mt5:
                raise HTTPException(status_code=503, detail="MT5 not available")
            
            try:
                success = self.mt5.close_position(ticket)
                if success:
                    return {"status": "closed", "ticket": ticket}
                else:
                    raise HTTPException(status_code=400, detail="Failed to close position")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/positions")
        async def close_all_positions():
            """Fecha todas as posições"""
            if not self.mt5:
                raise HTTPException(status_code=503, detail="MT5 not available")
            
            try:
                positions = self.mt5.get_open_positions()
                closed = 0
                for pos in positions:
                    if self.mt5.close_position(pos['ticket']):
                        closed += 1
                
                return {
                    "status": "completed",
                    "total": len(positions),
                    "closed": closed
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== Trades ==========
        @self.app.get("/api/trades")
        async def get_trades(
            days: int = 7,
            symbol: Optional[str] = None,
            strategy: Optional[str] = None
        ):
            """Retorna histórico de trades"""
            try:
                from datetime import date, timedelta
                
                trades = []
                today = date.today()
                
                if self.stats_db:
                    for i in range(days):
                        day = today - timedelta(days=i)
                        day_trades = self.stats_db.get_trades_by_date(day)
                        trades.extend(day_trades)
                
                # Filtrar
                if symbol:
                    trades = [t for t in trades if t.get('symbol') == symbol]
                if strategy:
                    trades = [t for t in trades if t.get('strategy') == strategy]
                
                return {"trades": trades, "count": len(trades)}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== Metrics ==========
        @self.app.get("/api/metrics", response_model=MetricsResponse)
        async def get_metrics(days: int = 30):
            """Retorna métricas avançadas"""
            try:
                from datetime import date, timedelta
                
                trades = []
                today = date.today()
                
                if self.stats_db:
                    for i in range(days):
                        day = today - timedelta(days=i)
                        trades.extend(self.stats_db.get_trades_by_date(day))
                
                if not trades:
                    return MetricsResponse(
                        total_trades=0,
                        wins=0,
                        losses=0,
                        win_rate=0,
                        profit_factor=0,
                        total_pnl=0,
                        avg_win=0,
                        avg_loss=0,
                        max_drawdown=0,
                        sqn=0,
                        sqn_rating="Insufficient Data",
                        avg_r_multiple=0,
                        r_expectancy=0
                    )
                
                # Calcular métricas
                wins = [t for t in trades if t.get('profit', 0) > 0]
                losses = [t for t in trades if t.get('profit', 0) < 0]
                
                total_wins = sum(t.get('profit', 0) for t in wins)
                total_losses = abs(sum(t.get('profit', 0) for t in losses))
                
                win_rate = len(wins) / len(trades) * 100 if trades else 0
                avg_win = total_wins / len(wins) if wins else 0
                avg_loss = total_losses / len(losses) if losses else 0
                pf = total_wins / total_losses if total_losses > 0 else 0
                
                # SQN aproximado
                import math
                profits = [t.get('profit', 0) for t in trades]
                if len(profits) >= 30:
                    mean_p = sum(profits) / len(profits)
                    var = sum((p - mean_p) ** 2 for p in profits) / len(profits)
                    std = math.sqrt(var) if var > 0 else 1
                    sqn = (mean_p * math.sqrt(len(profits))) / std if std > 0 else 0
                    
                    if sqn >= 3.0:
                        sqn_rating = "Excellent"
                    elif sqn >= 2.0:
                        sqn_rating = "Very Good"
                    elif sqn >= 1.5:
                        sqn_rating = "Good"
                    elif sqn >= 0.5:
                        sqn_rating = "Average"
                    else:
                        sqn_rating = "Poor"
                else:
                    sqn = 0
                    sqn_rating = "Insufficient Data"
                
                return MetricsResponse(
                    total_trades=len(trades),
                    wins=len(wins),
                    losses=len(losses),
                    win_rate=round(win_rate, 2),
                    profit_factor=round(pf, 2),
                    total_pnl=round(sum(t.get('profit', 0) for t in trades), 2),
                    avg_win=round(avg_win, 2),
                    avg_loss=round(avg_loss, 2),
                    max_drawdown=0,  # TODO: Calcular drawdown
                    sqn=round(sqn, 2),
                    sqn_rating=sqn_rating,
                    avg_r_multiple=0,  # TODO
                    r_expectancy=0  # TODO
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== Config ==========
        @self.app.get("/api/config")
        async def get_config():
            """Retorna configuração atual (sanitizada)"""
            if not self.config:
                raise HTTPException(status_code=503, detail="Config not available")
            
            config = self.config.get_all()
            # Remover dados sensíveis
            safe_config = {k: v for k, v in config.items() if k not in ['mt5']}
            return safe_config
        
        @self.app.put("/api/config")
        async def update_config(update: ConfigUpdate):
            """Atualiza configuração"""
            if not self.config:
                raise HTTPException(status_code=503, detail="Config not available")
            
            try:
                self.config.set(update.key, update.value)
                return {"status": "updated", "key": update.key}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        # ========== Control ==========
        @self.app.post("/api/control")
        async def control_bot(command: ControlCommand):
            """Controla o bot"""
            if command.action == "pause":
                self.is_paused = True
                return {"status": "paused"}
            
            elif command.action == "resume":
                self.is_paused = False
                return {"status": "resumed"}
            
            elif command.action == "stop":
                # Fecha posições antes de parar
                if self.mt5:
                    positions = self.mt5.get_open_positions()
                    for pos in positions:
                        self.mt5.close_position(pos['ticket'])
                
                self.is_trading = False
                return {"status": "stopping"}
            
            else:
                raise HTTPException(status_code=400, detail=f"Unknown action: {command.action}")
        
        # ========== WebSocket ==========
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket para atualizações em tempo real"""
            await websocket.accept()
            self._websocket_clients.append(websocket)
            
            try:
                while True:
                    # Enviar status periodicamente
                    status = {
                        "type": "status",
                        "timestamp": datetime.now().isoformat(),
                        "is_trading": self.is_trading,
                        "is_paused": self.is_paused,
                    }
                    
                    if self.mt5:
                        positions = self.mt5.get_open_positions()
                        status["positions"] = len(positions)
                        status["total_profit"] = sum(p['profit'] for p in positions)
                    
                    await websocket.send_json(status)
                    await asyncio.sleep(1)  # Atualizar a cada segundo
                    
            except WebSocketDisconnect:
                self._websocket_clients.remove(websocket)
        
        # ========== Health ==========
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        # ========== Export ==========
        @self.app.get("/api/export/trades")
        async def export_trades(format: str = "json", days: int = 30):
            """Exporta trades"""
            if self.journal:
                if format == "csv":
                    path = self.journal.export_csv()
                    return FileResponse(path, filename="trades.csv")
                elif format == "html":
                    path = self.journal.export_html_report()
                    return FileResponse(path, filename="report.html")
                else:
                    path = self.journal.export_json()
                    return FileResponse(path, filename="trades.json")
            
            raise HTTPException(status_code=503, detail="Journal not available")
    
    def _is_market_open(self) -> bool:
        """Verifica se mercado está aberto"""
        now = datetime.now()
        weekday = now.weekday()
        hour = now.hour
        
        # Forex: Dom 22:00 - Sex 22:00 UTC
        if weekday == 5:  # Sábado
            return False
        if weekday == 6 and hour < 22:  # Domingo antes das 22h
            return False
        if weekday == 4 and hour >= 22:  # Sexta após 22h
            return False
        
        return True
    
    async def broadcast(self, message: Dict):
        """Envia mensagem para todos os clientes WebSocket"""
        for client in self._websocket_clients:
            try:
                await client.send_json(message)
            except:
                pass
    
    def run(self):
        """Inicia o servidor"""
        import uvicorn
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
    
    async def run_async(self):
        """Inicia o servidor de forma assíncrona"""
        import uvicorn
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


# Função helper para iniciar API em thread separada
def start_api_server(
    mt5_connector=None,
    config_manager=None,
    stats_db=None,
    trade_journal=None,
    host: str = "0.0.0.0",
    port: int = 8080
):
    """Inicia servidor API em thread separada"""
    import threading
    
    server = APIServer(
        mt5_connector=mt5_connector,
        config_manager=config_manager,
        stats_db=stats_db,
        trade_journal=trade_journal,
        host=host,
        port=port
    )
    
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    
    logger.info(f"🌐 API Server iniciado em http://{host}:{port}")
    return server


# Exemplo de uso:
"""
from api.server import start_api_server

# Iniciar API junto com o bot
api_server = start_api_server(
    mt5_connector=mt5,
    config_manager=config,
    stats_db=stats_db,
    trade_journal=journal,
    port=8080
)

# Acessar:
# - http://localhost:8080/docs - Documentação Swagger
# - http://localhost:8080/api/status - Status do bot
# - http://localhost:8080/api/positions - Posições abertas
# - ws://localhost:8080/ws - WebSocket para updates
"""
