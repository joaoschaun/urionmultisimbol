"""
Trade Journal - Sistema de Registro Avançado de Trades
Inspirado em plataformas profissionais de trading

Features:
- Registro detalhado de cada trade
- Screenshots automáticos
- Tags e categorização
- Análise de padrões
- Export múltiplos formatos (CSV, JSON, Excel, HTML)
- Notas e anotações
- Métricas por sessão/dia/semana/mês
"""
import os
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import sqlite3
from loguru import logger


class TradeOutcome(Enum):
    """Resultado do trade"""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PARTIAL = "partial"


class TradeRating(Enum):
    """Avaliação da qualidade do trade"""
    A_PLUS = "A+"    # Setup perfeito, execução perfeita
    A = "A"          # Setup bom, execução boa
    B = "B"          # Setup ok, poderia melhorar
    C = "C"          # Trade marginal
    D = "D"          # Não deveria ter entrado


@dataclass
class TradeEntry:
    """Representa uma entrada completa de trade"""
    # Identificação
    trade_id: str
    ticket: int
    symbol: str
    
    # Timing
    entry_time: datetime
    exit_time: Optional[datetime] = None
    hold_duration: Optional[float] = None  # em horas
    
    # Preços
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    sl_price: float = 0.0
    tp_price: float = 0.0
    
    # Volume
    volume: float = 0.0
    volume_closed: float = 0.0
    
    # Resultado
    pnl: float = 0.0
    pnl_pips: float = 0.0
    outcome: Optional[TradeOutcome] = None
    r_multiple: float = 0.0
    
    # Análise
    strategy: str = ""
    setup_type: str = ""
    timeframe: str = ""
    market_condition: str = ""
    
    # Contexto
    session: str = ""  # London, New York, Asian
    day_of_week: str = ""
    news_events: List[str] = field(default_factory=list)
    
    # Sinais
    entry_signals: Dict[str, Any] = field(default_factory=dict)
    exit_signals: Dict[str, Any] = field(default_factory=dict)
    ml_prediction: Optional[float] = None
    ml_confidence: Optional[float] = None
    
    # Avaliação
    rating: Optional[TradeRating] = None
    notes: str = ""
    lessons: str = ""
    mistakes: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    
    # Tags
    tags: List[str] = field(default_factory=list)
    
    # Screenshots
    screenshot_entry: Optional[str] = None
    screenshot_exit: Optional[str] = None
    
    # Meta
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        data = asdict(self)
        # Converter enums e datetimes
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, Enum):
                data[key] = value.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeEntry':
        """Cria instância a partir de dicionário"""
        # Converter strings para tipos apropriados
        if 'entry_time' in data and isinstance(data['entry_time'], str):
            data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        if 'exit_time' in data and isinstance(data['exit_time'], str):
            data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        if 'outcome' in data and isinstance(data['outcome'], str):
            data['outcome'] = TradeOutcome(data['outcome'])
        if 'rating' in data and isinstance(data['rating'], str):
            data['rating'] = TradeRating(data['rating'])
        return cls(**data)


class TradeJournal:
    """
    Sistema de Journal de Trading Avançado
    
    Armazena, analisa e exporta dados de trades
    """
    
    def __init__(
        self,
        data_dir: str = "data/journal",
        use_sqlite: bool = True
    ):
        """
        Inicializa o Trade Journal
        
        Args:
            data_dir: Diretório para dados
            use_sqlite: Se deve usar SQLite (recomendado)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.use_sqlite = use_sqlite
        self._db_path = self.data_dir / "trades.db"
        self._json_path = self.data_dir / "trades.json"
        
        # Cache em memória
        self._trades: Dict[str, TradeEntry] = {}
        
        # Inicializar storage
        if use_sqlite:
            self._init_database()
        self._load_trades()
        
        logger.info(
            f"📓 Trade Journal inicializado | "
            f"Dir: {self.data_dir} | "
            f"Trades: {len(self._trades)} | "
            f"SQLite: {use_sqlite}"
        )
    
    def _init_database(self):
        """Inicializa banco de dados SQLite"""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                ticket INTEGER,
                symbol TEXT,
                entry_time TEXT,
                exit_time TEXT,
                hold_duration REAL,
                entry_price REAL,
                exit_price REAL,
                sl_price REAL,
                tp_price REAL,
                volume REAL,
                volume_closed REAL,
                pnl REAL,
                pnl_pips REAL,
                outcome TEXT,
                r_multiple REAL,
                strategy TEXT,
                setup_type TEXT,
                timeframe TEXT,
                market_condition TEXT,
                session TEXT,
                day_of_week TEXT,
                news_events TEXT,
                entry_signals TEXT,
                exit_signals TEXT,
                ml_prediction REAL,
                ml_confidence REAL,
                rating TEXT,
                notes TEXT,
                lessons TEXT,
                mistakes TEXT,
                improvements TEXT,
                tags TEXT,
                screenshot_entry TEXT,
                screenshot_exit TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # Índices para queries comuns
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON trades(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entry_time ON trades(entry_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy ON trades(strategy)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_outcome ON trades(outcome)')
        
        conn.commit()
        conn.close()
    
    def _load_trades(self):
        """Carrega trades do storage"""
        if self.use_sqlite:
            self._load_from_sqlite()
        else:
            self._load_from_json()
    
    def _load_from_sqlite(self):
        """Carrega trades do SQLite"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM trades')
            rows = cursor.fetchall()
            
            for row in rows:
                data = dict(row)
                # Parsear campos JSON
                for field in ['news_events', 'entry_signals', 'exit_signals', 
                              'mistakes', 'improvements', 'tags']:
                    if data.get(field):
                        data[field] = json.loads(data[field])
                    else:
                        data[field] = [] if field in ['news_events', 'mistakes', 
                                                       'improvements', 'tags'] else {}
                
                trade = TradeEntry.from_dict(data)
                self._trades[trade.trade_id] = trade
            
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao carregar trades do SQLite: {e}")
    
    def _load_from_json(self):
        """Carrega trades do JSON"""
        try:
            if self._json_path.exists():
                with open(self._json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for trade_data in data:
                        trade = TradeEntry.from_dict(trade_data)
                        self._trades[trade.trade_id] = trade
        except Exception as e:
            logger.error(f"Erro ao carregar trades do JSON: {e}")
    
    def _save_trade_to_sqlite(self, trade: TradeEntry):
        """Salva trade no SQLite"""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        data = trade.to_dict()
        # Serializar campos complexos
        for field in ['news_events', 'entry_signals', 'exit_signals',
                      'mistakes', 'improvements', 'tags']:
            data[field] = json.dumps(data.get(field, []))
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())
        
        cursor.execute(f'''
            INSERT OR REPLACE INTO trades ({columns})
            VALUES ({placeholders})
        ''', values)
        
        conn.commit()
        conn.close()
    
    def _save_to_json(self):
        """Salva todos trades para JSON"""
        data = [trade.to_dict() for trade in self._trades.values()]
        with open(self._json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def generate_trade_id(self, ticket: int, entry_time: datetime) -> str:
        """Gera ID único para trade"""
        return f"{ticket}_{entry_time.strftime('%Y%m%d_%H%M%S')}"
    
    def log_trade_entry(
        self,
        ticket: int,
        symbol: str,
        entry_price: float,
        volume: float,
        sl_price: float = 0,
        tp_price: float = 0,
        strategy: str = "",
        setup_type: str = "",
        timeframe: str = "",
        signals: Optional[Dict] = None,
        ml_prediction: Optional[float] = None,
        ml_confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        notes: str = ""
    ) -> TradeEntry:
        """
        Registra entrada de um novo trade
        
        Returns:
            TradeEntry criado
        """
        entry_time = datetime.now()
        trade_id = self.generate_trade_id(ticket, entry_time)
        
        # Determinar sessão
        hour = entry_time.hour
        if 0 <= hour < 8:
            session = "Asian"
        elif 8 <= hour < 16:
            session = "London"
        else:
            session = "New York"
        
        trade = TradeEntry(
            trade_id=trade_id,
            ticket=ticket,
            symbol=symbol,
            entry_time=entry_time,
            entry_price=entry_price,
            volume=volume,
            sl_price=sl_price,
            tp_price=tp_price,
            strategy=strategy,
            setup_type=setup_type,
            timeframe=timeframe,
            session=session,
            day_of_week=entry_time.strftime('%A'),
            entry_signals=signals or {},
            ml_prediction=ml_prediction,
            ml_confidence=ml_confidence,
            tags=tags or [],
            notes=notes
        )
        
        self._trades[trade_id] = trade
        
        if self.use_sqlite:
            self._save_trade_to_sqlite(trade)
        else:
            self._save_to_json()
        
        logger.info(
            f"📓 Trade registrado | {trade_id} | "
            f"{symbol} @ {entry_price:.5f} | "
            f"Vol: {volume}"
        )
        
        return trade
    
    def log_trade_exit(
        self,
        ticket: int,
        exit_price: float,
        pnl: float,
        pnl_pips: float = 0,
        volume_closed: Optional[float] = None,
        exit_signals: Optional[Dict] = None,
        rating: Optional[TradeRating] = None,
        notes: str = "",
        lessons: str = "",
        mistakes: Optional[List[str]] = None,
        improvements: Optional[List[str]] = None
    ) -> Optional[TradeEntry]:
        """
        Registra saída de um trade existente
        
        Returns:
            TradeEntry atualizado ou None se não encontrado
        """
        # Encontrar trade pelo ticket
        trade = None
        for t in self._trades.values():
            if t.ticket == ticket and t.exit_time is None:
                trade = t
                break
        
        if not trade:
            logger.warning(f"Trade #{ticket} não encontrado para registrar saída")
            return None
        
        exit_time = datetime.now()
        
        # Calcular duração
        hold_duration = (exit_time - trade.entry_time).total_seconds() / 3600
        
        # Determinar outcome
        if pnl > 0:
            outcome = TradeOutcome.WIN
        elif pnl < 0:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BREAKEVEN
        
        # Se fechamento parcial
        if volume_closed and volume_closed < trade.volume:
            outcome = TradeOutcome.PARTIAL
        
        # Calcular R-Multiple
        risk = abs(trade.entry_price - trade.sl_price) if trade.sl_price else 0
        r_multiple = pnl / (risk * trade.volume) if risk > 0 else 0
        
        # Atualizar trade
        trade.exit_time = exit_time
        trade.exit_price = exit_price
        trade.hold_duration = hold_duration
        trade.pnl = pnl
        trade.pnl_pips = pnl_pips
        trade.outcome = outcome
        trade.r_multiple = r_multiple
        trade.volume_closed = volume_closed or trade.volume
        trade.exit_signals = exit_signals or {}
        trade.rating = rating
        trade.notes = notes if notes else trade.notes
        trade.lessons = lessons
        trade.mistakes = mistakes or []
        trade.improvements = improvements or []
        trade.updated_at = datetime.now()
        
        if self.use_sqlite:
            self._save_trade_to_sqlite(trade)
        else:
            self._save_to_json()
        
        logger.info(
            f"📓 Trade fechado | {trade.trade_id} | "
            f"P&L: ${pnl:.2f} ({r_multiple:.1f}R) | "
            f"{outcome.value} | Duration: {hold_duration:.1f}h"
        )
        
        return trade
    
    def add_note(self, trade_id: str, note: str):
        """Adiciona nota a um trade"""
        if trade_id in self._trades:
            trade = self._trades[trade_id]
            if trade.notes:
                trade.notes += f"\n[{datetime.now().strftime('%H:%M')}] {note}"
            else:
                trade.notes = f"[{datetime.now().strftime('%H:%M')}] {note}"
            trade.updated_at = datetime.now()
            
            if self.use_sqlite:
                self._save_trade_to_sqlite(trade)
    
    def add_tag(self, trade_id: str, tag: str):
        """Adiciona tag a um trade"""
        if trade_id in self._trades:
            trade = self._trades[trade_id]
            if tag not in trade.tags:
                trade.tags.append(tag)
                trade.updated_at = datetime.now()
                
                if self.use_sqlite:
                    self._save_trade_to_sqlite(trade)
    
    def set_rating(self, trade_id: str, rating: TradeRating):
        """Define rating de um trade"""
        if trade_id in self._trades:
            trade = self._trades[trade_id]
            trade.rating = rating
            trade.updated_at = datetime.now()
            
            if self.use_sqlite:
                self._save_trade_to_sqlite(trade)
    
    def get_trade(self, trade_id: str) -> Optional[TradeEntry]:
        """Obtém trade por ID"""
        return self._trades.get(trade_id)
    
    def get_trades_by_ticket(self, ticket: int) -> List[TradeEntry]:
        """Obtém trades por ticket"""
        return [t for t in self._trades.values() if t.ticket == ticket]
    
    def get_trades(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        outcome: Optional[TradeOutcome] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        min_r: Optional[float] = None,
        max_r: Optional[float] = None,
        rating: Optional[TradeRating] = None,
        limit: int = 1000
    ) -> List[TradeEntry]:
        """
        Busca trades com filtros
        
        Returns:
            Lista de trades que correspondem aos filtros
        """
        results = []
        
        for trade in sorted(
            self._trades.values(),
            key=lambda t: t.entry_time,
            reverse=True
        ):
            # Aplicar filtros
            if symbol and trade.symbol != symbol:
                continue
            if strategy and trade.strategy != strategy:
                continue
            if outcome and trade.outcome != outcome:
                continue
            if start_date and trade.entry_time < start_date:
                continue
            if end_date and trade.entry_time > end_date:
                continue
            if tags and not any(tag in trade.tags for tag in tags):
                continue
            if min_r is not None and trade.r_multiple < min_r:
                continue
            if max_r is not None and trade.r_multiple > max_r:
                continue
            if rating and trade.rating != rating:
                continue
            
            results.append(trade)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_statistics(
        self,
        trades: Optional[List[TradeEntry]] = None,
        period: str = "all"  # all, today, week, month
    ) -> Dict[str, Any]:
        """
        Calcula estatísticas dos trades
        
        Returns:
            Dicionário com métricas
        """
        if trades is None:
            trades = list(self._trades.values())
        
        # Filtrar por período
        now = datetime.now()
        if period == "today":
            trades = [t for t in trades if t.entry_time.date() == now.date()]
        elif period == "week":
            week_start = now - timedelta(days=now.weekday())
            trades = [t for t in trades if t.entry_time >= week_start]
        elif period == "month":
            month_start = now.replace(day=1, hour=0, minute=0, second=0)
            trades = [t for t in trades if t.entry_time >= month_start]
        
        # Filtrar apenas trades fechados
        closed_trades = [t for t in trades if t.exit_time is not None]
        
        if not closed_trades:
            return {"total_trades": 0, "message": "Sem trades fechados"}
        
        wins = [t for t in closed_trades if t.outcome == TradeOutcome.WIN]
        losses = [t for t in closed_trades if t.outcome == TradeOutcome.LOSS]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        total_wins = sum(t.pnl for t in wins)
        total_losses = sum(t.pnl for t in losses)
        
        win_rate = len(wins) / len(closed_trades) if closed_trades else 0
        avg_win = total_wins / len(wins) if wins else 0
        avg_loss = abs(total_losses / len(losses)) if losses else 0
        
        # Profit Factor
        profit_factor = abs(total_wins / total_losses) if total_losses != 0 else float('inf')
        
        # R-Multiples
        r_multiples = [t.r_multiple for t in closed_trades if t.r_multiple]
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0
        
        # Duração média
        durations = [t.hold_duration for t in closed_trades if t.hold_duration]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Por estratégia
        by_strategy = {}
        for trade in closed_trades:
            strat = trade.strategy or "Unknown"
            if strat not in by_strategy:
                by_strategy[strat] = {"count": 0, "pnl": 0, "wins": 0}
            by_strategy[strat]["count"] += 1
            by_strategy[strat]["pnl"] += trade.pnl
            if trade.outcome == TradeOutcome.WIN:
                by_strategy[strat]["wins"] += 1
        
        # Por sessão
        by_session = {}
        for trade in closed_trades:
            sess = trade.session or "Unknown"
            if sess not in by_session:
                by_session[sess] = {"count": 0, "pnl": 0, "wins": 0}
            by_session[sess]["count"] += 1
            by_session[sess]["pnl"] += trade.pnl
            if trade.outcome == TradeOutcome.WIN:
                by_session[sess]["wins"] += 1
        
        return {
            "period": period,
            "total_trades": len(closed_trades),
            "open_trades": len([t for t in trades if t.exit_time is None]),
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len([t for t in closed_trades if t.outcome == TradeOutcome.BREAKEVEN]),
            "win_rate": round(win_rate * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_r_multiple": round(avg_r, 2),
            "avg_hold_time_hours": round(avg_duration, 1),
            "by_strategy": by_strategy,
            "by_session": by_session,
            "best_trade": max(closed_trades, key=lambda t: t.pnl).to_dict() if closed_trades else None,
            "worst_trade": min(closed_trades, key=lambda t: t.pnl).to_dict() if closed_trades else None,
        }
    
    def export_csv(
        self,
        output_path: Optional[str] = None,
        trades: Optional[List[TradeEntry]] = None
    ) -> str:
        """
        Exporta trades para CSV
        
        Returns:
            Caminho do arquivo gerado
        """
        if trades is None:
            trades = list(self._trades.values())
        
        output_path = output_path or str(
            self.data_dir / f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if not trades:
            return ""
        
        fieldnames = [
            'trade_id', 'ticket', 'symbol', 'entry_time', 'exit_time',
            'hold_duration', 'entry_price', 'exit_price', 'sl_price', 'tp_price',
            'volume', 'pnl', 'pnl_pips', 'outcome', 'r_multiple',
            'strategy', 'setup_type', 'timeframe', 'session', 'day_of_week',
            'rating', 'notes', 'tags'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for trade in sorted(trades, key=lambda t: t.entry_time):
                data = trade.to_dict()
                data['tags'] = ','.join(data.get('tags', []))
                writer.writerow(data)
        
        logger.info(f"📁 Exportado {len(trades)} trades para {output_path}")
        return output_path
    
    def export_json(
        self,
        output_path: Optional[str] = None,
        trades: Optional[List[TradeEntry]] = None,
        pretty: bool = True
    ) -> str:
        """
        Exporta trades para JSON
        
        Returns:
            Caminho do arquivo gerado
        """
        if trades is None:
            trades = list(self._trades.values())
        
        output_path = output_path or str(
            self.data_dir / f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        data = [trade.to_dict() for trade in sorted(trades, key=lambda t: t.entry_time)]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)
        
        logger.info(f"📁 Exportado {len(trades)} trades para {output_path}")
        return output_path
    
    def export_html_report(
        self,
        output_path: Optional[str] = None,
        trades: Optional[List[TradeEntry]] = None,
        title: str = "Trade Journal Report"
    ) -> str:
        """
        Exporta relatório HTML formatado
        
        Returns:
            Caminho do arquivo gerado
        """
        if trades is None:
            trades = list(self._trades.values())
        
        output_path = output_path or str(
            self.data_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        
        stats = self.get_statistics(trades)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        h1, h2 {{ color: #00d4ff; }}
        .summary {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: #16213e; padding: 20px; border-radius: 10px; min-width: 150px; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ color: #888; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f3460; color: #00d4ff; }}
        tr:hover {{ background: #1f4068; }}
        .win {{ color: #00ff88; }}
        .loss {{ color: #ff4444; }}
        .breakeven {{ color: #888; }}
    </style>
</head>
<body>
    <h1>📓 {title}</h1>
    <p>Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>📊 Resumo</h2>
    <div class="summary">
        <div class="stat-card">
            <div class="stat-value">{stats['total_trades']}</div>
            <div class="stat-label">Total Trades</div>
        </div>
        <div class="stat-card">
            <div class="stat-value {'win' if stats['total_pnl'] >= 0 else 'loss'}">${stats['total_pnl']:.2f}</div>
            <div class="stat-label">P&L Total</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['win_rate']}%</div>
            <div class="stat-label">Win Rate</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['profit_factor']:.2f}</div>
            <div class="stat-label">Profit Factor</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['avg_r_multiple']:.2f}R</div>
            <div class="stat-label">Média R</div>
        </div>
    </div>
    
    <h2>📋 Histórico de Trades</h2>
    <table>
        <tr>
            <th>Data</th>
            <th>Symbol</th>
            <th>Strategy</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>P&L</th>
            <th>R</th>
            <th>Duration</th>
            <th>Rating</th>
        </tr>
"""
        
        for trade in sorted(trades, key=lambda t: t.entry_time, reverse=True)[:100]:
            outcome_class = ""
            if trade.outcome == TradeOutcome.WIN:
                outcome_class = "win"
            elif trade.outcome == TradeOutcome.LOSS:
                outcome_class = "loss"
            else:
                outcome_class = "breakeven"
            
            html += f"""
        <tr>
            <td>{trade.entry_time.strftime('%Y-%m-%d %H:%M')}</td>
            <td>{trade.symbol}</td>
            <td>{trade.strategy}</td>
            <td>{trade.entry_price:.5f}</td>
            <td>{trade.exit_price:.5f if trade.exit_price else '-'}</td>
            <td class="{outcome_class}">${trade.pnl:.2f}</td>
            <td class="{outcome_class}">{trade.r_multiple:.1f}R</td>
            <td>{f'{trade.hold_duration:.1f}h' if trade.hold_duration else '-'}</td>
            <td>{trade.rating.value if trade.rating else '-'}</td>
        </tr>
"""
        
        html += """
    </table>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"📁 Relatório HTML gerado: {output_path}")
        return output_path


# Singleton
_trade_journal: Optional[TradeJournal] = None


def get_trade_journal(data_dir: str = "data/journal") -> TradeJournal:
    """Obtém instância singleton do Trade Journal"""
    global _trade_journal
    if _trade_journal is None:
        _trade_journal = TradeJournal(data_dir=data_dir)
    return _trade_journal


# Exemplo de uso:
"""
from core.trade_journal import get_trade_journal, TradeRating

journal = get_trade_journal()

# Registrar entrada
trade = journal.log_trade_entry(
    ticket=12345,
    symbol="EURUSD",
    entry_price=1.0850,
    volume=0.1,
    sl_price=1.0800,
    tp_price=1.0950,
    strategy="trend_following",
    setup_type="breakout",
    timeframe="H1",
    signals={"rsi": 45, "macd": "bullish"},
    tags=["momentum", "london"]
)

# Registrar saída
journal.log_trade_exit(
    ticket=12345,
    exit_price=1.0920,
    pnl=70.0,
    pnl_pips=70,
    rating=TradeRating.A,
    lessons="Segurar mais tempo em tendência forte",
    mistakes=["Saí cedo demais"]
)

# Estatísticas
stats = journal.get_statistics(period="week")
print(f"Win Rate: {stats['win_rate']}%")

# Exportar
journal.export_csv()
journal.export_html_report()
"""
