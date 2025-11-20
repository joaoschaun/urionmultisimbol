"""
Prometheus Metrics Exporter
Exporta métricas do bot para Prometheus monitoring
"""

from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    start_http_server, generate_latest, REGISTRY
)
from loguru import logger
from typing import Optional, Dict, Any
import time
from datetime import datetime


class PrometheusMetrics:
    """Gerenciador de métricas Prometheus"""
    
    def __init__(self, port: int = 8000):
        """
        Inicializa métricas Prometheus
        
        Args:
            port: Porta HTTP para expor /metrics
        """
        self.port = port
        
        # MÉTRICAS DE TRADES
        self.trades_total = Counter(
            'urion_trades_total',
            'Total de trades executados',
            ['strategy', 'action', 'symbol']
        )
        
        self.trades_profit = Gauge(
            'urion_trades_profit_usd',
            'Lucro total em USD',
            ['strategy']
        )
        
        self.trade_duration = Histogram(
            'urion_trade_duration_minutes',
            'Duração dos trades em minutos',
            ['strategy'],
            buckets=(1, 5, 10, 30, 60, 120, 240, 480, 1440)  # 1min a 24h
        )
        
        # MÉTRICAS DE POSIÇÕES
        self.positions_open = Gauge(
            'urion_positions_open',
            'Número de posições abertas',
            ['symbol']
        )
        
        self.position_profit = Gauge(
            'urion_position_profit_usd',
            'Lucro/perda da posição em USD',
            ['ticket', 'strategy', 'symbol']
        )
        
        # MÉTRICAS DE CONTA
        self.account_balance = Gauge(
            'urion_account_balance_usd',
            'Saldo da conta em USD'
        )
        
        self.account_equity = Gauge(
            'urion_account_equity_usd',
            'Equity da conta em USD'
        )
        
        self.account_margin = Gauge(
            'urion_account_margin_usd',
            'Margem utilizada em USD'
        )
        
        self.account_margin_free = Gauge(
            'urion_account_margin_free_usd',
            'Margem livre em USD'
        )
        
        self.account_profit = Gauge(
            'urion_account_profit_usd',
            'Lucro/perda total em USD'
        )
        
        self.account_drawdown = Gauge(
            'urion_account_drawdown_percent',
            'Drawdown atual em percentual'
        )
        
        # MÉTRICAS DE ESTRATÉGIAS
        self.strategy_win_rate = Gauge(
            'urion_strategy_win_rate',
            'Taxa de acerto da estratégia (0-1)',
            ['strategy']
        )
        
        self.strategy_confidence = Gauge(
            'urion_strategy_confidence',
            'Confiança do sinal da estratégia (0-100)',
            ['strategy']
        )
        
        self.strategy_signals = Counter(
            'urion_strategy_signals_total',
            'Total de sinais gerados',
            ['strategy', 'action']
        )
        
        # MÉTRICAS DE SISTEMA
        self.mt5_connected = Gauge(
            'urion_mt5_connected',
            'Status da conexão MT5 (1=conectado, 0=desconectado)'
        )
        
        self.bot_uptime = Gauge(
            'urion_bot_uptime_seconds',
            'Tempo de execução do bot em segundos'
        )
        
        self.errors_total = Counter(
            'urion_errors_total',
            'Total de erros',
            ['type', 'component']
        )
        
        self.order_execution_time = Histogram(
            'urion_order_execution_seconds',
            'Tempo de execução de ordens em segundos',
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
        )
        
        # MÉTRICAS DE RISK MANAGEMENT
        self.risk_rejections = Counter(
            'urion_risk_rejections_total',
            'Total de trades rejeitados pelo RiskManager',
            ['reason']
        )
        
        self.spread_current = Gauge(
            'urion_spread_pips',
            'Spread atual em pips',
            ['symbol']
        )
        
        # Timestamps
        self.start_time = time.time()
        self.last_update = time.time()
        
        logger.success(f"✅ PrometheusMetrics inicializado na porta {port}")

    def start_server(self):
        """Inicia servidor HTTP para expor métricas"""
        try:
            start_http_server(self.port)
            logger.success(f"🚀 Prometheus metrics disponíveis em http://localhost:{self.port}/metrics")
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar servidor Prometheus: {e}")

    # === MÉTODOS PARA ATUALIZAR MÉTRICAS ===
    
    def record_trade(self, strategy: str, action: str, symbol: str, profit: float, duration_minutes: float):
        """
        Registra um trade completo
        
        Args:
            strategy: Nome da estratégia
            action: BUY ou SELL
            symbol: Símbolo negociado
            profit: Lucro/perda em USD
            duration_minutes: Duração do trade em minutos
        """
        self.trades_total.labels(strategy=strategy, action=action, symbol=symbol).inc()
        self.trades_profit.labels(strategy=strategy).set(profit)
        self.trade_duration.labels(strategy=strategy).observe(duration_minutes)
        
        logger.debug(f"📊 Métrica: Trade {action} {symbol} | {strategy} | ${profit:.2f} | {duration_minutes:.1f}min")

    def update_positions(self, positions: list, symbol: str = 'XAUUSD'):
        """
        Atualiza métricas de posições abertas
        
        Args:
            positions: Lista de posições abertas
            symbol: Símbolo principal
        """
        self.positions_open.labels(symbol=symbol).set(len(positions))
        
        for pos in positions:
            ticket = str(pos.get('ticket', ''))
            strategy = pos.get('strategy', 'unknown')
            pos_symbol = pos.get('symbol', symbol)
            profit = pos.get('profit', 0.0)
            
            self.position_profit.labels(
                ticket=ticket,
                strategy=strategy,
                symbol=pos_symbol
            ).set(profit)

    def update_account(self, account_info: Dict[str, float]):
        """
        Atualiza métricas da conta
        
        Args:
            account_info: Informações da conta MT5
        """
        balance = account_info.get('balance', 0.0)
        equity = account_info.get('equity', 0.0)
        margin = account_info.get('margin', 0.0)
        margin_free = account_info.get('margin_free', 0.0)
        profit = account_info.get('profit', 0.0)
        
        self.account_balance.set(balance)
        self.account_equity.set(equity)
        self.account_margin.set(margin)
        self.account_margin_free.set(margin_free)
        self.account_profit.set(profit)
        
        # Calcula drawdown
        if balance > 0:
            drawdown = ((balance - equity) / balance) * 100
            self.account_drawdown.set(drawdown)
        
        logger.debug(f"📊 Conta: Balance=${balance:.2f} | Equity=${equity:.2f} | Profit=${profit:.2f}")

    def update_strategy_stats(self, strategy: str, win_rate: float, confidence: float = None):
        """
        Atualiza estatísticas de estratégia
        
        Args:
            strategy: Nome da estratégia
            win_rate: Taxa de acerto (0-1)
            confidence: Confiança do último sinal (0-100)
        """
        self.strategy_win_rate.labels(strategy=strategy).set(win_rate)
        
        if confidence is not None:
            self.strategy_confidence.labels(strategy=strategy).set(confidence)

    def record_signal(self, strategy: str, action: str):
        """
        Registra um sinal gerado
        
        Args:
            strategy: Nome da estratégia
            action: BUY, SELL ou HOLD
        """
        self.strategy_signals.labels(strategy=strategy, action=action).inc()

    def set_mt5_connection(self, connected: bool):
        """
        Atualiza status da conexão MT5
        
        Args:
            connected: True se conectado, False caso contrário
        """
        self.mt5_connected.set(1 if connected else 0)
        logger.debug(f"📊 MT5 Connection: {'✅ Conectado' if connected else '❌ Desconectado'}")

    def update_uptime(self):
        """Atualiza tempo de execução do bot"""
        uptime = time.time() - self.start_time
        self.bot_uptime.set(uptime)

    def record_error(self, error_type: str, component: str):
        """
        Registra um erro
        
        Args:
            error_type: Tipo do erro (connection, trade, database, etc)
            component: Componente que gerou o erro
        """
        self.errors_total.labels(type=error_type, component=component).inc()
        logger.warning(f"📊 Erro registrado: {error_type} em {component}")

    def record_order_execution_time(self, seconds: float):
        """
        Registra tempo de execução de uma ordem
        
        Args:
            seconds: Tempo em segundos
        """
        self.order_execution_time.observe(seconds)

    def record_risk_rejection(self, reason: str):
        """
        Registra rejeição pelo RiskManager
        
        Args:
            reason: Motivo da rejeição
        """
        self.risk_rejections.labels(reason=reason).inc()
        logger.debug(f"📊 Trade rejeitado: {reason}")

    def update_spread(self, symbol: str, spread_pips: float):
        """
        Atualiza spread atual
        
        Args:
            symbol: Símbolo
            spread_pips: Spread em pips
        """
        self.spread_current.labels(symbol=symbol).set(spread_pips)

    def get_metrics(self) -> bytes:
        """
        Retorna métricas no formato Prometheus
        
        Returns:
            Métricas em formato texto (bytes)
        """
        return generate_latest(REGISTRY)

    def export_to_file(self, filepath: str = 'metrics/prometheus_metrics.txt'):
        """
        Exporta métricas para arquivo
        
        Args:
            filepath: Caminho do arquivo
        """
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'wb') as f:
            f.write(self.get_metrics())
        
        logger.info(f"📊 Métricas exportadas para {filepath}")


# Instância global
_metrics_instance: Optional[PrometheusMetrics] = None


def get_metrics() -> PrometheusMetrics:
    """
    Retorna instância global de PrometheusMetrics (Singleton)
    
    Returns:
        PrometheusMetrics instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = PrometheusMetrics()
        _metrics_instance.start_server()
    return _metrics_instance
