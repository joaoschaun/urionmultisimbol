"""
Flask Dashboard for Urion Trading Bot
Real-time monitoring with interactive charts
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.mt5_connector import MT5Connector
from database.strategy_stats import StrategyStatsDB
from core.config_manager import ConfigManager
from loguru import logger

app = Flask(__name__)
CORS(app)

# Global instances
config = None
mt5 = None
stats_db = None


def init_app():
    """Initialize app with config, MT5 and DB"""
    global config, mt5, stats_db
    
    try:
        config_manager = ConfigManager('config/config.yaml')
        config = config_manager.config
        
        mt5 = MT5Connector(config)
        stats_db = StrategyStatsDB()
        
        logger.success("✅ Dashboard inicializado")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar dashboard: {e}")
        return False


@app.route('/')
def index():
    """Dashboard principal"""
    return render_template('dashboard.html')


@app.route('/api/account')
def get_account():
    """Retorna informações da conta"""
    try:
        if not mt5 or not mt5.connected:
            mt5.connect()
        
        account_info = mt5.get_account_info()
        
        if account_info:
            return jsonify({
                'success': True,
                'data': account_info
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Não foi possível obter informações da conta'
            }), 500
            
    except Exception as e:
        logger.error(f"Erro em /api/account: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/positions')
def get_positions():
    """Retorna posições abertas"""
    try:
        if not mt5 or not mt5.connected:
            mt5.connect()
        
        positions = mt5.get_open_positions()
        
        return jsonify({
            'success': True,
            'data': positions or []
        })
            
    except Exception as e:
        logger.error(f"Erro em /api/positions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trades/today')
def get_trades_today():
    """Retorna trades de hoje"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get all trades from database
        all_trades = stats_db.get_all_trades()
        
        # Filter today's trades
        today_trades = [
            t for t in all_trades 
            if t['open_time'] and t['open_time'].startswith(today)
        ]
        
        return jsonify({
            'success': True,
            'data': today_trades
        })
            
    except Exception as e:
        logger.error(f"Erro em /api/trades/today: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trades/history')
def get_trades_history():
    """Retorna histórico de trades"""
    try:
        days = int(request.args.get('days', 7))
        
        all_trades = stats_db.get_all_trades()
        
        # Get trades from last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        recent_trades = [
            t for t in all_trades
            if t['open_time'] and t['open_time'] >= cutoff_str
        ]
        
        return jsonify({
            'success': True,
            'data': recent_trades
        })
            
    except Exception as e:
        logger.error(f"Erro em /api/trades/history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/strategies/stats')
def get_strategy_stats():
    """Retorna estatísticas por estratégia"""
    try:
        # Get daily stats for all strategies
        daily_stats = stats_db.get_daily_stats(datetime.now().strftime('%Y-%m-%d'))
        
        # Get weekly ranking
        weekly_ranking = stats_db.get_weekly_ranking()
        
        return jsonify({
            'success': True,
            'data': {
                'daily': daily_stats,
                'weekly': weekly_ranking
            }
        })
            
    except Exception as e:
        logger.error(f"Erro em /api/strategies/stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/equity/curve')
def get_equity_curve():
    """Retorna curva de equity"""
    try:
        days = int(request.args.get('days', 30))
        
        # Get all trades
        all_trades = stats_db.get_all_trades()
        
        # Calculate equity curve
        equity_points = []
        current_balance = 10000  # Initial balance (should come from config)
        
        for trade in sorted(all_trades, key=lambda x: x['open_time'] or ''):
            if trade['close_time'] and trade['profit']:
                current_balance += trade['profit']
                equity_points.append({
                    'timestamp': trade['close_time'],
                    'equity': current_balance,
                    'trade_id': trade['ticket']
                })
        
        return jsonify({
            'success': True,
            'data': equity_points
        })
            
    except Exception as e:
        logger.error(f"Erro em /api/equity/curve: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/performance/summary')
def get_performance_summary():
    """Retorna resumo de performance"""
    try:
        all_trades = stats_db.get_all_trades()
        
        # Calculate metrics
        closed_trades = [t for t in all_trades if t['status'] == 'closed']
        winning_trades = [t for t in closed_trades if (t['profit'] or 0) > 0]
        losing_trades = [t for t in closed_trades if (t['profit'] or 0) < 0]
        
        total_profit = sum(t['profit'] or 0 for t in closed_trades)
        total_trades = len(closed_trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        avg_win = sum(t['profit'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['profit'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        profit_factor = abs(sum(t['profit'] for t in winning_trades) / sum(t['profit'] for t in losing_trades)) if losing_trades else 0
        
        summary = {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate * 100,
            'total_profit': total_profit,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'best_trade': max((t['profit'] or 0 for t in closed_trades), default=0),
            'worst_trade': min((t['profit'] or 0 for t in closed_trades), default=0)
        }
        
        return jsonify({
            'success': True,
            'data': summary
        })
            
    except Exception as e:
        logger.error(f"Erro em /api/performance/summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        mt5_status = mt5.connected if mt5 else False
        
        return jsonify({
            'success': True,
            'data': {
                'status': 'online',
                'mt5_connected': mt5_status,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def start_dashboard(host='0.0.0.0', port=5000, debug=False):
    """
    Inicia o servidor Flask
    
    Args:
        host: Host para bind
        port: Porta para bind
        debug: Modo debug
    """
    if init_app():
        logger.info(f"🚀 Dashboard iniciando em http://{host}:{port}")
        app.run(host=host, port=port, debug=debug)
    else:
        logger.error("❌ Falha ao inicializar dashboard")


if __name__ == '__main__':
    start_dashboard(debug=True)
