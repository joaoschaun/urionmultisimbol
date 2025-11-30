"""
Performance Metrics Collector
Coleta e analisa métricas de performance do bot

Métricas:
- Win Rate
- Profit Factor
- Average Win/Loss
- Sharpe Ratio
- Max Drawdown
- Recovery Factor
"""
import json
import os
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from loguru import logger
from dataclasses import dataclass, asdict
import threading


@dataclass
class TradeMetrics:
    """Métricas de um trade individual"""
    ticket: int
    symbol: str
    strategy: str
    direction: str  # BUY ou SELL
    entry_price: float
    exit_price: float
    volume: float
    profit: float
    profit_pips: float
    duration_minutes: int
    entry_time: datetime
    exit_time: datetime
    reason: str  # TP, SL, Manual, etc


@dataclass
class StrategyStats:
    """Estatísticas por estratégia"""
    name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit: float
    total_loss: float
    profit_factor: float
    average_win: float
    average_loss: float
    average_profit: float
    max_win: float
    max_loss: float
    average_duration_minutes: float
    expectancy: float  # (Win% * AvgWin) - (Loss% * AvgLoss)


class PerformanceCollector:
    """
    Coletor de métricas de performance
    
    Coleta:
    - Resultados de trades
    - Estatísticas por estratégia
    - Métricas gerais do bot
    """
    
    def __init__(self, config: Optional[Dict] = None, data_dir: str = "data"):
        """
        Inicializa o coletor
        
        Args:
            config: Configuração opcional
            data_dir: Diretório para armazenar dados
        """
        self.config = config or {}
        self.data_dir = data_dir
        
        # Criar diretório se não existir
        os.makedirs(data_dir, exist_ok=True)
        
        # Arquivos de dados
        self.trades_file = os.path.join(data_dir, "trades_history.json")
        self.stats_file = os.path.join(data_dir, "strategy_stats.json")
        
        # Dados em memória
        self._trades: List[Dict] = []
        self._strategy_stats: Dict[str, StrategyStats] = {}
        
        # Thread lock
        self._lock = threading.RLock()
        
        # Carregar dados existentes
        self._load_data()
        
        # Balance tracking para drawdown
        self._peak_balance = 0.0
        self._initial_balance = 0.0
        self._current_balance = 0.0
        
        logger.info(
            f"📊 Performance Collector inicializado | "
            f"Trades carregados: {len(self._trades)}"
        )
    
    def _load_data(self):
        """Carrega dados históricos do arquivo"""
        try:
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    self._trades = json.load(f)
                logger.debug(f"Carregados {len(self._trades)} trades do histórico")
        except Exception as e:
            logger.error(f"Erro ao carregar histórico de trades: {e}")
            self._trades = []
    
    def _save_data(self):
        """Salva dados no arquivo"""
        try:
            with open(self.trades_file, 'w') as f:
                json.dump(self._trades, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Erro ao salvar trades: {e}")
    
    def record_trade(
        self,
        ticket: int,
        symbol: str,
        strategy: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        volume: float,
        profit: float,
        entry_time: datetime,
        exit_time: datetime,
        reason: str = "unknown"
    ):
        """
        Registra um trade completado
        
        Args:
            ticket: Número do ticket
            symbol: Símbolo
            strategy: Nome da estratégia
            direction: BUY ou SELL
            entry_price: Preço de entrada
            exit_price: Preço de saída
            volume: Volume em lotes
            profit: Lucro/prejuízo
            entry_time: Hora de entrada
            exit_time: Hora de saída
            reason: Razão do fechamento
        """
        with self._lock:
            try:
                # Calcular profit em pips
                if direction == 'BUY':
                    profit_pips = (exit_price - entry_price) / 0.1  # XAUUSD
                else:
                    profit_pips = (entry_price - exit_price) / 0.1
                
                # Calcular duração
                duration = (exit_time - entry_time).total_seconds() / 60
                
                trade_data = {
                    'ticket': ticket,
                    'symbol': symbol,
                    'strategy': strategy,
                    'direction': direction,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'volume': volume,
                    'profit': profit,
                    'profit_pips': round(profit_pips, 1),
                    'duration_minutes': round(duration, 1),
                    'entry_time': entry_time.isoformat(),
                    'exit_time': exit_time.isoformat(),
                    'reason': reason,
                }
                
                self._trades.append(trade_data)
                self._save_data()
                
                # Atualizar estatísticas da estratégia
                self._update_strategy_stats(strategy)
                
                # Log
                emoji = "✅" if profit >= 0 else "❌"
                logger.info(
                    f"📊 Trade registrado {emoji} | "
                    f"#{ticket} {strategy} {direction} {symbol} | "
                    f"Profit: ${profit:.2f} ({profit_pips:.1f} pips) | "
                    f"Duration: {duration:.0f}min"
                )
                
            except Exception as e:
                logger.error(f"Erro ao registrar trade: {e}")
    
    def _update_strategy_stats(self, strategy: str):
        """Atualiza estatísticas de uma estratégia"""
        try:
            # Filtrar trades da estratégia
            strategy_trades = [t for t in self._trades if t['strategy'] == strategy]
            
            if not strategy_trades:
                return
            
            # Calcular métricas
            winning = [t for t in strategy_trades if t['profit'] >= 0]
            losing = [t for t in strategy_trades if t['profit'] < 0]
            
            total = len(strategy_trades)
            win_count = len(winning)
            loss_count = len(losing)
            
            total_profit = sum(t['profit'] for t in winning)
            total_loss = abs(sum(t['profit'] for t in losing))
            
            avg_win = total_profit / win_count if win_count > 0 else 0
            avg_loss = total_loss / loss_count if loss_count > 0 else 0
            
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
            win_rate = (win_count / total) * 100 if total > 0 else 0
            
            avg_duration = sum(t['duration_minutes'] for t in strategy_trades) / total
            
            max_win = max((t['profit'] for t in winning), default=0)
            max_loss = abs(min((t['profit'] for t in losing), default=0))
            
            avg_profit = sum(t['profit'] for t in strategy_trades) / total
            
            # Expectancy
            win_pct = win_count / total if total > 0 else 0
            loss_pct = loss_count / total if total > 0 else 0
            expectancy = (win_pct * avg_win) - (loss_pct * avg_loss)
            
            self._strategy_stats[strategy] = StrategyStats(
                name=strategy,
                total_trades=total,
                winning_trades=win_count,
                losing_trades=loss_count,
                win_rate=round(win_rate, 2),
                total_profit=round(total_profit, 2),
                total_loss=round(total_loss, 2),
                profit_factor=round(profit_factor, 2),
                average_win=round(avg_win, 2),
                average_loss=round(avg_loss, 2),
                average_profit=round(avg_profit, 2),
                max_win=round(max_win, 2),
                max_loss=round(max_loss, 2),
                average_duration_minutes=round(avg_duration, 1),
                expectancy=round(expectancy, 2),
            )
            
        except Exception as e:
            logger.error(f"Erro ao atualizar stats de {strategy}: {e}")
    
    def get_strategy_stats(self, strategy: str) -> Optional[Dict]:
        """Retorna estatísticas de uma estratégia"""
        with self._lock:
            if strategy in self._strategy_stats:
                return asdict(self._strategy_stats[strategy])
            
            # Tentar calcular
            self._update_strategy_stats(strategy)
            
            if strategy in self._strategy_stats:
                return asdict(self._strategy_stats[strategy])
            
            return None
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Retorna estatísticas de todas as estratégias"""
        with self._lock:
            # Atualizar todas
            strategies = set(t['strategy'] for t in self._trades)
            for strategy in strategies:
                self._update_strategy_stats(strategy)
            
            return {k: asdict(v) for k, v in self._strategy_stats.items()}
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas gerais do bot"""
        with self._lock:
            try:
                if not self._trades:
                    return {
                        "total_trades": 0,
                        "message": "Nenhum trade registrado ainda"
                    }
                
                total = len(self._trades)
                winning = [t for t in self._trades if t['profit'] >= 0]
                losing = [t for t in self._trades if t['profit'] < 0]
                
                total_profit = sum(t['profit'] for t in self._trades)
                gross_profit = sum(t['profit'] for t in winning)
                gross_loss = abs(sum(t['profit'] for t in losing))
                
                # Win rate
                win_rate = (len(winning) / total) * 100 if total > 0 else 0
                
                # Profit factor
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                # Averages
                avg_win = gross_profit / len(winning) if winning else 0
                avg_loss = gross_loss / len(losing) if losing else 0
                avg_trade = total_profit / total if total > 0 else 0
                
                # Best/Worst
                best_trade = max(self._trades, key=lambda x: x['profit'])
                worst_trade = min(self._trades, key=lambda x: x['profit'])
                
                # Por período
                today = datetime.now().date()
                today_trades = [
                    t for t in self._trades 
                    if datetime.fromisoformat(t['exit_time']).date() == today
                ]
                today_profit = sum(t['profit'] for t in today_trades)
                
                week_ago = today - timedelta(days=7)
                week_trades = [
                    t for t in self._trades 
                    if datetime.fromisoformat(t['exit_time']).date() >= week_ago
                ]
                week_profit = sum(t['profit'] for t in week_trades)
                
                # Estatísticas por direção
                buy_trades = [t for t in self._trades if t['direction'] == 'BUY']
                sell_trades = [t for t in self._trades if t['direction'] == 'SELL']
                
                buy_profit = sum(t['profit'] for t in buy_trades)
                sell_profit = sum(t['profit'] for t in sell_trades)
                
                buy_win_rate = (
                    len([t for t in buy_trades if t['profit'] >= 0]) / len(buy_trades) * 100
                    if buy_trades else 0
                )
                sell_win_rate = (
                    len([t for t in sell_trades if t['profit'] >= 0]) / len(sell_trades) * 100
                    if sell_trades else 0
                )
                
                return {
                    "total_trades": total,
                    "winning_trades": len(winning),
                    "losing_trades": len(losing),
                    "win_rate": round(win_rate, 2),
                    "total_profit": round(total_profit, 2),
                    "gross_profit": round(gross_profit, 2),
                    "gross_loss": round(gross_loss, 2),
                    "profit_factor": round(profit_factor, 2),
                    "average_win": round(avg_win, 2),
                    "average_loss": round(avg_loss, 2),
                    "average_trade": round(avg_trade, 2),
                    "best_trade": {
                        "profit": best_trade['profit'],
                        "strategy": best_trade['strategy'],
                        "symbol": best_trade['symbol'],
                    },
                    "worst_trade": {
                        "profit": worst_trade['profit'],
                        "strategy": worst_trade['strategy'],
                        "symbol": worst_trade['symbol'],
                    },
                    "today_trades": len(today_trades),
                    "today_profit": round(today_profit, 2),
                    "week_trades": len(week_trades),
                    "week_profit": round(week_profit, 2),
                    "buy_trades": len(buy_trades),
                    "buy_profit": round(buy_profit, 2),
                    "buy_win_rate": round(buy_win_rate, 2),
                    "sell_trades": len(sell_trades),
                    "sell_profit": round(sell_profit, 2),
                    "sell_win_rate": round(sell_win_rate, 2),
                }
                
            except Exception as e:
                logger.error(f"Erro ao calcular overall stats: {e}")
                return {"error": str(e)}
    
    def update_balance(self, balance: float):
        """Atualiza balance para cálculo de drawdown"""
        with self._lock:
            if self._initial_balance == 0:
                self._initial_balance = balance
            
            self._current_balance = balance
            self._peak_balance = max(self._peak_balance, balance)
    
    def get_drawdown_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de drawdown"""
        with self._lock:
            if self._peak_balance == 0:
                return {"message": "Balance não rastreado ainda"}
            
            current_drawdown = (self._peak_balance - self._current_balance) / self._peak_balance
            total_return = (self._current_balance - self._initial_balance) / self._initial_balance
            
            return {
                "initial_balance": round(self._initial_balance, 2),
                "current_balance": round(self._current_balance, 2),
                "peak_balance": round(self._peak_balance, 2),
                "current_drawdown_pct": round(current_drawdown * 100, 2),
                "total_return_pct": round(total_return * 100, 2),
            }
    
    def get_recent_trades(self, count: int = 10) -> List[Dict]:
        """Retorna os últimos N trades"""
        with self._lock:
            return self._trades[-count:] if self._trades else []
    
    def get_trade_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> List[Dict]:
        """Retorna histórico de trades filtrado"""
        with self._lock:
            trades = self._trades.copy()
            
            if start_date:
                trades = [
                    t for t in trades 
                    if datetime.fromisoformat(t['exit_time']) >= start_date
                ]
            
            if end_date:
                trades = [
                    t for t in trades 
                    if datetime.fromisoformat(t['exit_time']) <= end_date
                ]
            
            if strategy:
                trades = [t for t in trades if t['strategy'] == strategy]
            
            if symbol:
                trades = [t for t in trades if t['symbol'] == symbol]
            
            return trades
    
    def generate_report(self) -> str:
        """Gera relatório de performance em texto"""
        overall = self.get_overall_stats()
        all_stats = self.get_all_stats()
        drawdown = self.get_drawdown_stats()
        
        report = []
        report.append("=" * 60)
        report.append("📊 RELATÓRIO DE PERFORMANCE - URION BOT")
        report.append("=" * 60)
        report.append("")
        
        # Estatísticas gerais
        report.append("📈 ESTATÍSTICAS GERAIS:")
        report.append(f"  Total de trades: {overall.get('total_trades', 0)}")
        report.append(f"  Win Rate: {overall.get('win_rate', 0):.2f}%")
        report.append(f"  Profit Factor: {overall.get('profit_factor', 0):.2f}")
        report.append(f"  Lucro Total: ${overall.get('total_profit', 0):.2f}")
        report.append(f"  Média por Trade: ${overall.get('average_trade', 0):.2f}")
        report.append("")
        
        # Hoje
        report.append("📅 HOJE:")
        report.append(f"  Trades: {overall.get('today_trades', 0)}")
        report.append(f"  Lucro: ${overall.get('today_profit', 0):.2f}")
        report.append("")
        
        # Por direção
        report.append("⬆️⬇️ POR DIREÇÃO:")
        report.append(f"  BUY: {overall.get('buy_trades', 0)} trades, ${overall.get('buy_profit', 0):.2f}, {overall.get('buy_win_rate', 0):.1f}% WR")
        report.append(f"  SELL: {overall.get('sell_trades', 0)} trades, ${overall.get('sell_profit', 0):.2f}, {overall.get('sell_win_rate', 0):.1f}% WR")
        report.append("")
        
        # Por estratégia
        report.append("🎯 POR ESTRATÉGIA:")
        for name, stats in all_stats.items():
            report.append(f"  {name}:")
            report.append(f"    Trades: {stats['total_trades']} | WR: {stats['win_rate']:.1f}% | PF: {stats['profit_factor']:.2f}")
            report.append(f"    Profit: ${stats['total_profit'] - stats['total_loss']:.2f} | Expectancy: ${stats['expectancy']:.2f}")
        report.append("")
        
        # Drawdown
        if 'current_drawdown_pct' in drawdown:
            report.append("📉 DRAWDOWN:")
            report.append(f"  Drawdown Atual: {drawdown['current_drawdown_pct']:.2f}%")
            report.append(f"  Retorno Total: {drawdown['total_return_pct']:.2f}%")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)


# Singleton
_collector: Optional[PerformanceCollector] = None


def get_performance_collector(
    config: Optional[Dict] = None
) -> PerformanceCollector:
    """Obtém instância singleton do collector"""
    global _collector
    if _collector is None:
        _collector = PerformanceCollector(config)
    return _collector


# Exemplo de uso:
"""
from core.performance_collector import get_performance_collector

collector = get_performance_collector()

# Registrar trade
collector.record_trade(
    ticket=12345,
    symbol="XAUUSD",
    strategy="Scalping",
    direction="BUY",
    entry_price=2650.50,
    exit_price=2655.50,
    volume=0.1,
    profit=50.0,
    entry_time=datetime.now() - timedelta(minutes=30),
    exit_time=datetime.now(),
    reason="TP"
)

# Obter estatísticas
overall = collector.get_overall_stats()
print(f"Win Rate: {overall['win_rate']:.2f}%")

# Relatório completo
print(collector.generate_report())
"""
