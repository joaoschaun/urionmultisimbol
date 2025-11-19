"""
Sistema de tracking de performance por estratégia
Salva estatísticas detalhadas de cada trade e estratégia
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class StrategyStatsDB:
    """Banco de dados para estatísticas de estratégias"""
    
    def __init__(self, db_path: str = "data/strategy_stats.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Inicializa tabelas do banco de dados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela de trades por estratégia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                ticket INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                type TEXT NOT NULL,
                volume REAL NOT NULL,
                open_price REAL NOT NULL,
                close_price REAL,
                sl REAL,
                tp REAL,
                open_time TIMESTAMP NOT NULL,
                close_time TIMESTAMP,
                profit REAL,
                commission REAL,
                swap REAL,
                status TEXT DEFAULT 'open',
                signal_confidence REAL,
                market_conditions TEXT,
                notes TEXT
            )
        """)
        
        # Tabela de estatísticas diárias por estratégia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                date DATE NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                break_even_trades INTEGER DEFAULT 0,
                total_profit REAL DEFAULT 0,
                total_loss REAL DEFAULT 0,
                net_profit REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                profit_factor REAL DEFAULT 0,
                average_win REAL DEFAULT 0,
                average_loss REAL DEFAULT 0,
                largest_win REAL DEFAULT 0,
                largest_loss REAL DEFAULT 0,
                avg_confidence REAL DEFAULT 0,
                UNIQUE(strategy_name, date)
            )
        """)
        
        # Tabela de ranking semanal
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_weekly_ranking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                week_start DATE NOT NULL,
                week_end DATE NOT NULL,
                total_trades INTEGER DEFAULT 0,
                net_profit REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                profit_factor REAL DEFAULT 0,
                sharpe_ratio REAL DEFAULT 0,
                max_drawdown REAL DEFAULT 0,
                rank INTEGER,
                score REAL,
                status TEXT DEFAULT 'active',
                notes TEXT,
                UNIQUE(strategy_name, week_start)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database inicializado: {self.db_path}")
    
    def save_trade(self, trade_data: Dict):
        """
        Salva trade executado por uma estratégia
        
        Args:
            trade_data: Dict com dados do trade
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO strategy_trades (
                strategy_name, ticket, symbol, type, volume,
                open_price, sl, tp, open_time, signal_confidence,
                market_conditions, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data.get('strategy_name'),
            trade_data.get('ticket'),
            trade_data.get('symbol'),
            trade_data.get('type'),
            trade_data.get('volume'),
            trade_data.get('open_price'),
            trade_data.get('sl'),
            trade_data.get('tp'),
            trade_data.get('open_time', datetime.now()),
            trade_data.get('signal_confidence'),
            trade_data.get('market_conditions'),
            'open'
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Trade salvo: {trade_data.get('strategy_name')} - Ticket {trade_data.get('ticket')}")
    
    def update_trade_close(self, ticket: int, close_data: Dict):
        """
        Atualiza trade quando fechado
        
        Args:
            ticket: Número do ticket
            close_data: Dados do fechamento
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE strategy_trades
            SET close_price = ?, close_time = ?, profit = ?,
                commission = ?, swap = ?, status = ?
            WHERE ticket = ?
        """, (
            close_data.get('close_price'),
            close_data.get('close_time', datetime.now()),
            close_data.get('profit'),
            close_data.get('commission', 0),
            close_data.get('swap', 0),
            'closed',
            ticket
        ))
        
        conn.commit()
        conn.close()
        
        # Atualizar estatísticas diárias
        self._update_daily_stats(close_data.get('strategy_name'))
    
    def _update_daily_stats(self, strategy_name: str):
        """Atualiza estatísticas diárias da estratégia"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        # Buscar trades fechados hoje
        cursor.execute("""
            SELECT profit, signal_confidence
            FROM strategy_trades
            WHERE strategy_name = ?
            AND date(close_time) = ?
            AND status = 'closed'
        """, (strategy_name, today))
        
        trades = cursor.fetchall()
        
        if not trades:
            conn.close()
            return
        
        # Calcular estatísticas
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t[0] > 0)
        losing_trades = sum(1 for t in trades if t[0] < 0)
        break_even_trades = sum(1 for t in trades if t[0] == 0)
        
        total_profit = sum(t[0] for t in trades if t[0] > 0)
        total_loss = abs(sum(t[0] for t in trades if t[0] < 0))
        net_profit = sum(t[0] for t in trades)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        avg_win = (total_profit / winning_trades) if winning_trades > 0 else 0
        avg_loss = (total_loss / losing_trades) if losing_trades > 0 else 0
        
        largest_win = max((t[0] for t in trades if t[0] > 0), default=0)
        largest_loss = abs(min((t[0] for t in trades if t[0] < 0), default=0))
        
        avg_confidence = sum(t[1] or 0 for t in trades) / total_trades
        
        # Inserir ou atualizar
        cursor.execute("""
            INSERT OR REPLACE INTO strategy_daily_stats (
                strategy_name, date, total_trades, winning_trades,
                losing_trades, break_even_trades, total_profit, total_loss,
                net_profit, win_rate, profit_factor, average_win,
                average_loss, largest_win, largest_loss, avg_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_name, today, total_trades, winning_trades,
            losing_trades, break_even_trades, total_profit, total_loss,
            net_profit, win_rate, profit_factor, avg_win,
            avg_loss, largest_win, largest_loss, avg_confidence
        ))
        
        conn.commit()
        conn.close()
    
    def get_all_trades(self, days: int = 7, strategy_name: Optional[str] = None) -> List[Dict]:
        """
        Retorna todos os trades (abertos e fechados)
        
        Args:
            days: Número de dias para análise (padrão: 7)
            strategy_name: Filtrar por estratégia específica (opcional)
            
        Returns:
            Lista de dicts com dados dos trades
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = datetime.now().date() - timedelta(days=days)
        
        if strategy_name:
            cursor.execute("""
                SELECT 
                    strategy_name, ticket, symbol, type, volume,
                    open_price, close_price, sl, tp,
                    open_time, close_time, profit, commission, swap,
                    status, signal_confidence, market_conditions
                FROM strategy_trades
                WHERE strategy_name = ?
                AND date(open_time) >= ?
                ORDER BY open_time DESC
            """, (strategy_name, start_date))
        else:
            cursor.execute("""
                SELECT 
                    strategy_name, ticket, symbol, type, volume,
                    open_price, close_price, sl, tp,
                    open_time, close_time, profit, commission, swap,
                    status, signal_confidence, market_conditions
                FROM strategy_trades
                WHERE date(open_time) >= ?
                ORDER BY open_time DESC
            """, (start_date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            trades.append({
                'strategy_name': row[0],
                'ticket': row[1],
                'symbol': row[2],
                'type': row[3],
                'volume': row[4],
                'open_price': row[5],
                'close_price': row[6],
                'sl': row[7],
                'tp': row[8],
                'open_time': row[9],
                'close_time': row[10],
                'profit': row[11],
                'commission': row[12],
                'swap': row[13],
                'status': row[14],
                'signal_confidence': row[15],
                'market_conditions': row[16]
            })
        
        return trades
    
    def get_strategy_stats(self, strategy_name: str, days: int = 7) -> Dict:
        """
        Retorna estatísticas de uma estratégia
        
        Args:
            strategy_name: Nome da estratégia
            days: Número de dias para análise
            
        Returns:
            Dict com estatísticas
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = datetime.now().date() - timedelta(days=days)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(profit) as net_profit,
                AVG(CASE WHEN profit > 0 THEN profit END) as avg_win,
                AVG(CASE WHEN profit < 0 THEN profit END) as avg_loss,
                MAX(profit) as largest_win,
                MIN(profit) as largest_loss,
                AVG(signal_confidence) as avg_confidence
            FROM strategy_trades
            WHERE strategy_name = ?
            AND date(close_time) >= ?
            AND status = 'closed'
        """, (strategy_name, start_date))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or row[0] == 0:
            return {
                'strategy_name': strategy_name,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'net_profit': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'largest_win': 0,
                'largest_loss': 0,
                'avg_confidence': 0
            }
        
        total_trades = row[0]
        winning_trades = row[1] or 0
        losing_trades = row[2] or 0
        net_profit = row[3] or 0
        avg_win = row[4] or 0
        avg_loss = abs(row[5] or 0)
        largest_win = row[6] or 0
        largest_loss = abs(row[7] or 0)
        avg_confidence = row[8] or 0
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_profit = winning_trades * avg_win if avg_win > 0 else 0
        total_loss = losing_trades * avg_loss if avg_loss > 0 else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        return {
            'strategy_name': strategy_name,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'net_profit': net_profit,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'avg_confidence': avg_confidence
        }
    
    def get_all_strategies_ranking(self, days: int = 7) -> List[Dict]:
        """
        Retorna ranking de todas as estratégias
        
        Args:
            days: Número de dias para análise
            
        Returns:
            Lista de estratégias ordenadas por performance
        """
        strategies = [
            'TrendFollowing',
            'MeanReversion',
            'Breakout',
            'NewsTrading',
            'Scalping',
            'RangeTrading'
        ]
        
        ranking = []
        for strategy in strategies:
            stats = self.get_strategy_stats(strategy, days)
            
            # Calcular score (0-100)
            score = 0
            
            # Win rate (0-40 pontos)
            score += min(stats['win_rate'] * 0.8, 40)
            
            # Profit factor (0-30 pontos)
            if stats['profit_factor'] > 0:
                score += min(stats['profit_factor'] * 10, 30)
            
            # Net profit normalizado (0-20 pontos)
            if stats['net_profit'] > 0:
                score += min(stats['net_profit'] / 10, 20)
            
            # Confidence (0-10 pontos)
            score += stats['avg_confidence'] * 10
            
            stats['score'] = round(score, 2)
            ranking.append(stats)
        
        # Ordenar por score
        ranking.sort(key=lambda x: x['score'], reverse=True)
        
        # Adicionar rank
        for i, strategy in enumerate(ranking, 1):
            strategy['rank'] = i
        
        return ranking
    
    def save_weekly_ranking(self):
        """Salva ranking semanal no banco"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calcular início e fim da semana
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        ranking = self.get_all_strategies_ranking(days=7)
        
        for strategy in ranking:
            cursor.execute("""
                INSERT OR REPLACE INTO strategy_weekly_ranking (
                    strategy_name, week_start, week_end, total_trades,
                    net_profit, win_rate, profit_factor, rank, score, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy['strategy_name'],
                week_start,
                week_end,
                strategy['total_trades'],
                strategy['net_profit'],
                strategy['win_rate'],
                strategy['profit_factor'],
                strategy['rank'],
                strategy['score'],
                'active'
            ))
        
        conn.commit()
        conn.close()
        logger.success(f"Ranking semanal salvo: {week_start} a {week_end}")
    
    def get_historical_rankings(self, weeks: int = 4) -> List[Dict]:
        """
        Retorna rankings históricos
        
        Args:
            weeks: Número de semanas
            
        Returns:
            Lista de rankings por semana
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT week_start, week_end, strategy_name, total_trades,
                   net_profit, win_rate, profit_factor, rank, score
            FROM strategy_weekly_ranking
            WHERE week_start >= date('now', '-' || ? || ' days')
            ORDER BY week_start DESC, rank ASC
        """, (weeks * 7,))
        
        rows = cursor.fetchall()
        conn.close()
        
        rankings = []
        for row in rows:
            rankings.append({
                'week_start': row[0],
                'week_end': row[1],
                'strategy_name': row[2],
                'total_trades': row[3],
                'net_profit': row[4],
                'win_rate': row[5],
                'profit_factor': row[6],
                'rank': row[7],
                'score': row[8]
            })
        
        return rankings
