"""
Dashboard Web Simples e Funcional - Urion Trading Bot
Usa apenas Flask (já instalado)
"""
from flask import Flask, render_template, jsonify
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database.strategy_stats import StrategyStatsDB

app = Flask(__name__)
stats_db = StrategyStatsDB()

@app.route('/')
def index():
    """Página principal do dashboard"""
    return render_template('dashboard.html')

@app.route('/api/account')
def api_account():
    """Retorna dados da conta MT5"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 não conectado'}), 500
        
        account = mt5.account_info()
        if not account:
            return jsonify({'error': 'Falha ao obter dados da conta'}), 500
        
        return jsonify({
            'login': account.login,
            'balance': round(account.balance, 2),
            'equity': round(account.equity, 2),
            'margin': round(account.margin, 2),
            'free_margin': round(account.margin_free, 2),
            'profit': round(account.profit, 2),
            'margin_level': round(account.margin_level, 2) if account.margin > 0 else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions')
def api_positions():
    """Retorna posições abertas"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 não conectado'}), 500
        
        positions = mt5.positions_get()
        if positions is None:
            return jsonify([])
        
        result = []
        for pos in positions:
            result.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': 'BUY' if pos.type == 0 else 'SELL',
                'volume': pos.volume,
                'price_open': pos.price_open,
                'price_current': pos.price_current,
                'sl': pos.sl,
                'tp': pos.tp,
                'profit': round(pos.profit, 2),
                'magic': pos.magic,
                'time': datetime.fromtimestamp(pos.time).strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def api_history():
    """Retorna histórico de trades (últimas 24h)"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 não conectado'}), 500
        
        now = datetime.now()
        from_date = now - timedelta(days=1)
        
        deals = mt5.history_deals_get(from_date, now)
        if deals is None:
            return jsonify([])
        
        # Filtrar apenas deals de saída (fechamento)
        result = []
        for deal in deals:
            if deal.entry == 1:  # OUT (fechamento)
                result.append({
                    'ticket': deal.order,
                    'symbol': deal.symbol,
                    'type': 'BUY' if deal.type == 0 else 'SELL',
                    'volume': deal.volume,
                    'price': deal.price,
                    'profit': round(deal.profit, 2),
                    'time': datetime.fromtimestamp(deal.time).strftime('%Y-%m-%d %H:%M:%S')
                })
        
        # Últimos 20 trades
        return jsonify(sorted(result, key=lambda x: x['time'], reverse=True)[:20])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics')
def api_statistics():
    """Retorna estatísticas gerais"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 não conectado'}), 500
        
        # Histórico de 7 dias
        now = datetime.now()
        from_date = now - timedelta(days=7)
        
        deals = mt5.history_deals_get(from_date, now)
        
        total_trades = 0
        wins = 0
        losses = 0
        total_profit = 0
        
        if deals:
            for deal in deals:
                if deal.entry == 1:  # OUT
                    total_trades += 1
                    total_profit += deal.profit
                    if deal.profit > 0:
                        wins += 1
                    else:
                        losses += 1
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return jsonify({
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': round(win_rate, 1),
            'total_profit': round(total_profit, 2),
            'avg_win': round(total_profit / wins, 2) if wins > 0 else 0,
            'avg_loss': round(total_profit / losses, 2) if losses > 0 else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies')
def api_strategies():
    """Retorna performance por estratégia"""
    try:
        strategies = stats_db.get_all_strategies()
        result = []
        
        for strategy in strategies:
            stats = stats_db.get_strategy_stats(strategy, days=7)
            if stats:
                result.append({
                    'name': strategy,
                    'total_trades': stats['total_trades'],
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'win_rate': stats['win_rate'],
                    'total_profit': stats['total_profit']
                })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  URION TRADING BOT - DASHBOARD WEB")
    print("="*60)
    print("\n  Acesse: http://localhost:5000")
    print("  Pressione CTRL+C para parar\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
