"""
Metrics Dashboard
Dashboard web simples para visualização de métricas do bot

Features:
- Página HTML estática gerada automaticamente
- Gráficos interativos
- Atualização automática
- Exportável como arquivo HTML
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger


class MetricsDashboard:
    """
    Gerador de Dashboard de Métricas
    
    Cria páginas HTML estáticas com visualização de:
    - Performance geral
    - Equity curve
    - Drawdown
    - Trades por estratégia
    - Regime de mercado
    """
    
    TEMPLATE = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Urion Trading Bot - Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            padding: 20px;
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            color: #00d4ff;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            color: #888;
            font-size: 1.1em;
        }}
        
        .dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        
        .card.wide {{
            grid-column: span 2;
        }}
        
        .card h2 {{
            color: #00d4ff;
            margin-bottom: 15px;
            font-size: 1.3em;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 10px;
        }}
        
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }}
        
        .stat-item {{
            text-align: center;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
        }}
        
        .stat-value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #00d4ff;
        }}
        
        .stat-value.positive {{
            color: #00ff88;
        }}
        
        .stat-value.negative {{
            color: #ff4444;
        }}
        
        .stat-label {{
            color: #888;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        .chart-container {{
            position: relative;
            height: 250px;
        }}
        
        .trades-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        
        .trades-table th,
        .trades-table td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        
        .trades-table th {{
            color: #00d4ff;
            font-weight: 500;
        }}
        
        .win {{
            color: #00ff88;
        }}
        
        .loss {{
            color: #ff4444;
        }}
        
        .footer {{
            text-align: center;
            padding: 30px;
            color: #666;
            margin-top: 30px;
        }}
        
        .regime-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            margin: 5px;
        }}
        
        .regime-trending_up {{
            background: linear-gradient(45deg, #00ff88, #00cc66);
            color: #000;
        }}
        
        .regime-trending_down {{
            background: linear-gradient(45deg, #ff4444, #cc0000);
            color: #fff;
        }}
        
        .regime-ranging {{
            background: linear-gradient(45deg, #ffaa00, #ff8800);
            color: #000;
        }}
        
        .regime-volatile {{
            background: linear-gradient(45deg, #aa44ff, #8800cc);
            color: #fff;
        }}
        
        .progress-bar {{
            height: 10px;
            background: rgba(255,255,255,0.1);
            border-radius: 5px;
            overflow: hidden;
            margin-top: 10px;
        }}
        
        .progress-fill {{
            height: 100%;
            border-radius: 5px;
            transition: width 0.5s ease;
        }}
        
        @media (max-width: 768px) {{
            .card.wide {{
                grid-column: span 1;
            }}
            .stat-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Urion Trading Bot</h1>
        <div class="subtitle">Dashboard de Performance | Atualizado: {update_time}</div>
    </div>
    
    <div class="dashboard">
        <!-- Account Summary -->
        <div class="card">
            <h2>💰 Resumo da Conta</h2>
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-value">${balance:,.2f}</div>
                    <div class="stat-label">Balance</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${equity:,.2f}</div>
                    <div class="stat-label">Equity</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value {pnl_class}">${total_pnl:+,.2f}</div>
                    <div class="stat-label">P&L Total</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{total_trades}</div>
                    <div class="stat-label">Total Trades</div>
                </div>
            </div>
        </div>
        
        <!-- Performance Metrics -->
        <div class="card">
            <h2>📊 Métricas de Performance</h2>
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-value">{win_rate:.1f}%</div>
                    <div class="stat-label">Win Rate</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {win_rate}%; background: linear-gradient(90deg, #00ff88, #00d4ff);"></div>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{profit_factor:.2f}</div>
                    <div class="stat-label">Profit Factor</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{sharpe:.2f}</div>
                    <div class="stat-label">Sharpe Ratio</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{sqn:.2f}</div>
                    <div class="stat-label">SQN</div>
                </div>
            </div>
        </div>
        
        <!-- Risk Metrics -->
        <div class="card">
            <h2>⚠️ Gestão de Risco</h2>
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-value negative">{max_drawdown:.1f}%</div>
                    <div class="stat-label">Max Drawdown</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{avg_r:.2f}R</div>
                    <div class="stat-label">Avg R-Multiple</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{open_positions}</div>
                    <div class="stat-label">Posições Abertas</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value {open_pnl_class}">${open_pnl:+,.2f}</div>
                    <div class="stat-label">P&L Aberto</div>
                </div>
            </div>
        </div>
        
        <!-- Market Regime -->
        <div class="card">
            <h2>🌊 Regime de Mercado</h2>
            <div style="text-align: center; padding: 20px;">
                <span class="regime-badge regime-{regime}">{regime_display}</span>
                <div style="margin-top: 15px;">
                    <div class="stat-value">{regime_confidence:.0f}%</div>
                    <div class="stat-label">Confiança</div>
                </div>
                <div style="margin-top: 15px; color: #888;">
                    Estratégia recomendada: <strong style="color: #00d4ff;">{recommended_strategy}</strong>
                </div>
            </div>
        </div>
        
        <!-- Equity Curve -->
        <div class="card wide">
            <h2>📈 Curva de Equity</h2>
            <div class="chart-container">
                <canvas id="equityChart"></canvas>
            </div>
        </div>
        
        <!-- Trades by Strategy -->
        <div class="card">
            <h2>🎯 Performance por Estratégia</h2>
            <div class="chart-container">
                <canvas id="strategyChart"></canvas>
            </div>
        </div>
        
        <!-- Win/Loss Distribution -->
        <div class="card">
            <h2>📊 Distribuição W/L</h2>
            <div class="chart-container">
                <canvas id="wlChart"></canvas>
            </div>
        </div>
        
        <!-- Recent Trades -->
        <div class="card wide">
            <h2>📋 Trades Recentes</h2>
            <table class="trades-table">
                <thead>
                    <tr>
                        <th>Data</th>
                        <th>Símbolo</th>
                        <th>Tipo</th>
                        <th>P&L</th>
                        <th>Duração</th>
                        <th>Estratégia</th>
                    </tr>
                </thead>
                <tbody>
                    {trades_rows}
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="footer">
        <p>Urion Trading Bot v2.0 | Dashboard gerado automaticamente</p>
    </div>
    
    <script>
        // Equity Chart
        const equityCtx = document.getElementById('equityChart').getContext('2d');
        new Chart(equityCtx, {{
            type: 'line',
            data: {{
                labels: {equity_labels},
                datasets: [{{
                    label: 'Equity',
                    data: {equity_data},
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        grid: {{ color: 'rgba(255,255,255,0.1)' }},
                        ticks: {{ color: '#888' }}
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#888', maxTicksLimit: 10 }}
                    }}
                }}
            }}
        }});
        
        // Strategy Chart
        const strategyCtx = document.getElementById('strategyChart').getContext('2d');
        new Chart(strategyCtx, {{
            type: 'doughnut',
            data: {{
                labels: {strategy_labels},
                datasets: [{{
                    data: {strategy_data},
                    backgroundColor: [
                        '#00d4ff',
                        '#00ff88',
                        '#ffaa00',
                        '#ff4444',
                        '#aa44ff'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'right',
                        labels: {{ color: '#888' }}
                    }}
                }}
            }}
        }});
        
        // W/L Chart
        const wlCtx = document.getElementById('wlChart').getContext('2d');
        new Chart(wlCtx, {{
            type: 'bar',
            data: {{
                labels: ['Wins', 'Losses'],
                datasets: [{{
                    data: [{wins}, {losses}],
                    backgroundColor: ['#00ff88', '#ff4444']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        grid: {{ color: 'rgba(255,255,255,0.1)' }},
                        ticks: {{ color: '#888' }}
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#888' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
'''
    
    def __init__(self, output_dir: str = "data/dashboard"):
        """
        Inicializa o Dashboard
        
        Args:
            output_dir: Diretório para salvar HTML
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📊 Dashboard inicializado | Dir: {self.output_dir}")
    
    def generate(
        self,
        account_info: Dict[str, Any],
        metrics: Dict[str, Any],
        trades: List[Dict],
        equity_curve: Optional[List[Tuple[str, float]]] = None,
        strategy_stats: Optional[Dict[str, Dict]] = None,
        regime_info: Optional[Dict] = None
    ) -> str:
        """
        Gera dashboard HTML
        
        Args:
            account_info: Informações da conta
            metrics: Métricas de performance
            trades: Lista de trades recentes
            equity_curve: Lista de (data, equity)
            strategy_stats: Stats por estratégia
            regime_info: Informações do regime de mercado
            
        Returns:
            Caminho do arquivo HTML gerado
        """
        # Preparar dados
        pnl = metrics.get('total_pnl', 0)
        open_pnl = account_info.get('open_pnl', 0)
        
        # Equity curve
        if equity_curve:
            equity_labels = json.dumps([e[0] for e in equity_curve[-50:]])
            equity_data = json.dumps([e[1] for e in equity_curve[-50:]])
        else:
            equity_labels = json.dumps(['Start', 'Current'])
            equity_data = json.dumps([
                account_info.get('initial_balance', 10000),
                account_info.get('balance', 10000)
            ])
        
        # Strategy stats
        if strategy_stats:
            strategy_labels = json.dumps(list(strategy_stats.keys())[:5])
            strategy_data = json.dumps([s.get('count', 0) for s in list(strategy_stats.values())[:5]])
        else:
            strategy_labels = json.dumps(['No data'])
            strategy_data = json.dumps([1])
        
        # Regime info
        regime = regime_info.get('regime', 'unknown') if regime_info else 'unknown'
        regime_display = regime.replace('_', ' ').title()
        regime_confidence = regime_info.get('confidence', 0) * 100 if regime_info else 0
        recommended_strategy = regime_info.get('recommended_strategy', 'N/A') if regime_info else 'N/A'
        
        # Trades rows
        trades_rows = ""
        for trade in trades[:10]:
            pnl_class = "win" if trade.get('pnl', 0) > 0 else "loss"
            trades_rows += f"""
                <tr>
                    <td>{trade.get('time', 'N/A')}</td>
                    <td>{trade.get('symbol', 'N/A')}</td>
                    <td>{trade.get('type', 'N/A')}</td>
                    <td class="{pnl_class}">${trade.get('pnl', 0):+.2f}</td>
                    <td>{trade.get('duration', 'N/A')}</td>
                    <td>{trade.get('strategy', 'N/A')}</td>
                </tr>
            """
        
        if not trades_rows:
            trades_rows = "<tr><td colspan='6' style='text-align: center; color: #666;'>Nenhum trade registrado</td></tr>"
        
        # Gerar HTML
        html = self.TEMPLATE.format(
            update_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            balance=account_info.get('balance', 0),
            equity=account_info.get('equity', 0),
            total_pnl=pnl,
            pnl_class='positive' if pnl >= 0 else 'negative',
            total_trades=metrics.get('total_trades', 0),
            win_rate=metrics.get('win_rate', 0),
            profit_factor=metrics.get('profit_factor', 0),
            sharpe=metrics.get('sharpe_ratio', 0),
            sqn=metrics.get('sqn', 0),
            max_drawdown=metrics.get('max_drawdown_pct', 0),
            avg_r=metrics.get('avg_r_multiple', 0),
            open_positions=account_info.get('open_positions', 0),
            open_pnl=open_pnl,
            open_pnl_class='positive' if open_pnl >= 0 else 'negative',
            regime=regime,
            regime_display=regime_display,
            regime_confidence=regime_confidence,
            recommended_strategy=recommended_strategy,
            equity_labels=equity_labels,
            equity_data=equity_data,
            strategy_labels=strategy_labels,
            strategy_data=strategy_data,
            wins=metrics.get('wins', 0),
            losses=metrics.get('losses', 0),
            trades_rows=trades_rows
        )
        
        # Salvar arquivo
        output_path = self.output_dir / "dashboard.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"📊 Dashboard gerado: {output_path}")
        return str(output_path)
    
    def update_from_bot(
        self,
        mt5_connector,
        stats_db=None,
        trade_journal=None,
        regime_detector=None
    ) -> str:
        """
        Atualiza dashboard com dados do bot
        
        Args:
            mt5_connector: Instância do MT5Connector
            stats_db: StrategyStatsDB
            trade_journal: TradeJournal
            regime_detector: MarketRegimeDetector
            
        Returns:
            Caminho do arquivo HTML
        """
        import MetaTrader5 as mt5
        
        # Account info
        account = mt5.account_info()
        positions = mt5_connector.get_open_positions() if mt5_connector else []
        open_pnl = sum(p['profit'] for p in positions) if positions else 0
        
        account_info = {
            'balance': account.balance if account else 0,
            'equity': account.equity if account else 0,
            'initial_balance': 10000,
            'open_positions': len(positions),
            'open_pnl': open_pnl
        }
        
        # Metrics
        metrics = {
            'total_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'sharpe_ratio': 0,
            'sqn': 0,
            'max_drawdown_pct': 0,
            'avg_r_multiple': 0,
            'total_pnl': 0,
            'wins': 0,
            'losses': 0
        }
        
        if trade_journal:
            stats = trade_journal.get_statistics()
            metrics.update({
                'total_trades': stats.get('total_trades', 0),
                'win_rate': stats.get('win_rate', 0),
                'profit_factor': stats.get('profit_factor', 0),
                'total_pnl': stats.get('total_pnl', 0),
                'wins': stats.get('wins', 0),
                'losses': stats.get('losses', 0)
            })
        
        # Trades
        trades = []
        if trade_journal:
            recent = trade_journal.get_trades(limit=10)
            trades = [t.to_dict() for t in recent]
        
        # Regime
        regime_info = None
        if regime_detector:
            # Obter dados atuais
            data = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 200)
            if data is not None:
                import pandas as pd
                df = pd.DataFrame(data)
                info = regime_detector.detect_regime(df)
                regime_info = info.to_dict()
        
        return self.generate(
            account_info=account_info,
            metrics=metrics,
            trades=trades,
            regime_info=regime_info
        )


# Singleton
_dashboard: Optional[MetricsDashboard] = None


def get_dashboard(output_dir: str = "data/dashboard") -> MetricsDashboard:
    """Obtém instância singleton do Dashboard"""
    global _dashboard
    if _dashboard is None:
        _dashboard = MetricsDashboard(output_dir)
    return _dashboard
