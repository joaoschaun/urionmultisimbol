"""
Análise Completa do Bot URION
Gera relatório detalhado de todos os módulos
"""

import sys
import os
import importlib
import inspect

sys.path.insert(0, 'src')

def analyze_module(module_path, module_name):
    """Analisa um módulo e retorna suas classes e funções"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        classes = []
        functions = []
        
        for name, obj in inspect.getmembers(module):
            if name.startswith('_'):
                continue
            if inspect.isclass(obj) and obj.__module__ == module.__name__:
                methods = [m for m in dir(obj) if not m.startswith('_')]
                classes.append({
                    'name': name,
                    'methods': methods[:10],  # Limitar a 10
                    'doc': obj.__doc__[:100] if obj.__doc__ else ''
                })
            elif inspect.isfunction(obj):
                functions.append(name)
        
        return {'classes': classes, 'functions': functions, 'status': 'OK'}
    except Exception as e:
        return {'classes': [], 'functions': [], 'status': f'ERRO: {str(e)[:50]}'}


def main():
    print("=" * 80)
    print("           ANÁLISE COMPLETA DO BOT URION v2.1")
    print("=" * 80)
    print()
    
    # Estrutura de módulos
    modules = {
        'CORE': [
            ('src/core/mt5_connector.py', 'mt5_connector'),
            ('src/core/config_manager.py', 'config_manager'),
            ('src/core/risk_manager.py', 'risk_manager'),
            ('src/core/strategy_executor.py', 'strategy_executor'),
            ('src/core/watchdog.py', 'watchdog'),
        ],
        'ANALYSIS': [
            ('src/analysis/technical_analyzer.py', 'technical_analyzer'),
            ('src/analysis/news_analyzer.py', 'news_analyzer'),
            ('src/analysis/macro_context_analyzer.py', 'macro_context_analyzer'),
            ('src/analysis/smart_money_detector.py', 'smart_money_detector'),
            ('src/analysis/session_analyzer.py', 'session_analyzer'),
        ],
        'STRATEGIES': [
            ('src/strategies/base_strategy.py', 'base_strategy'),
            ('src/strategies/strategy_manager.py', 'strategy_manager'),
            ('src/strategies/trend_following.py', 'trend_following'),
            ('src/strategies/mean_reversion.py', 'mean_reversion'),
            ('src/strategies/breakout.py', 'breakout'),
            ('src/strategies/scalping.py', 'scalping'),
            ('src/strategies/range_trading.py', 'range_trading'),
            ('src/strategies/news_trading.py', 'news_trading'),
        ],
        'ADVANCED': [
            ('src/advanced/order_flow.py', 'order_flow'),
            ('src/advanced/manipulation_detector.py', 'manipulation_detector'),
            ('src/advanced/position_intelligence.py', 'position_intelligence'),
            ('src/advanced/execution_algorithms.py', 'execution_algorithms'),
        ],
        'ML': [
            ('src/ml/strategy_learner.py', 'strategy_learner'),
            ('src/ml/training_pipeline.py', 'training_pipeline'),
        ],
        'DATABASE': [
            ('src/database/strategy_stats_db.py', 'strategy_stats_db'),
        ],
        'INFRASTRUCTURE': [
            ('src/infrastructure/data_hub.py', 'data_hub'),
            ('src/infrastructure/redis_manager.py', 'redis_manager'),
            ('src/infrastructure/influxdb_manager.py', 'influxdb_manager'),
        ],
        'NOTIFICATIONS': [
            ('src/notifications/telegram_bot.py', 'telegram_bot'),
        ],
        'ORDER_MANAGEMENT': [
            ('src/order_generator.py', 'order_generator'),
            ('src/order_manager.py', 'order_manager'),
        ],
        'BACKTEST': [
            ('src/backtest/backtester.py', 'backtester'),
        ],
    }
    
    total_ok = 0
    total_error = 0
    all_classes = []
    
    for category, mods in modules.items():
        print(f"\n{'─' * 40}")
        print(f"📦 {category}")
        print(f"{'─' * 40}")
        
        for path, name in mods:
            if os.path.exists(path):
                result = analyze_module(path, name)
                status = "✅" if result['status'] == 'OK' else "❌"
                
                if result['status'] == 'OK':
                    total_ok += 1
                else:
                    total_error += 1
                
                print(f"  {status} {name}")
                
                for cls in result['classes']:
                    all_classes.append(f"{category}.{cls['name']}")
                    methods_str = ", ".join(cls['methods'][:5])
                    print(f"      └─ {cls['name']}: {methods_str}...")
            else:
                print(f"  ❌ {name} (arquivo não encontrado)")
                total_error += 1
    
    # Resumo
    print()
    print("=" * 80)
    print("                          RESUMO")
    print("=" * 80)
    print(f"  Módulos OK:     {total_ok}")
    print(f"  Módulos ERRO:   {total_error}")
    print(f"  Total Classes:  {len(all_classes)}")
    print()
    
    # Testar conexão MT5
    print("─" * 40)
    print("🔌 TESTE DE CONEXÃO MT5")
    print("─" * 40)
    
    try:
        from core.mt5_connector import MT5Connector
        from core.config_manager import ConfigManager
        
        config = ConfigManager().config
        mt5 = MT5Connector(config)
        
        if mt5.connect():
            info = mt5.get_account_info()
            print(f"  ✅ MT5 Conectado")
            print(f"     Conta: {info.get('login', 'N/A')}")
            print(f"     Balance: ${info.get('balance', 0):,.2f}")
            print(f"     Servidor: {info.get('server', 'N/A')}")
        else:
            print("  ❌ Falha na conexão MT5")
    except Exception as e:
        print(f"  ❌ Erro MT5: {e}")
    
    # Testar Session Analyzer
    print()
    print("─" * 40)
    print("⏰ SESSÃO DE MERCADO ATUAL")
    print("─" * 40)
    
    try:
        from analysis.session_analyzer import SessionAnalyzer
        sa = SessionAnalyzer()
        summary = sa.get_session_summary()
        
        print(f"  Sessão: {summary['current_session'].upper()}")
        print(f"  Volatilidade: {summary['volatility']}")
        print(f"  Tempo restante: {summary['time_remaining']}")
        print(f"  Melhores pares: {', '.join(summary['best_pairs'])}")
        
        print()
        print("  Estratégias recomendadas:")
        for strat, weight in summary['recommended_strategies'].items():
            bar = "█" * int(weight * 10)
            print(f"    {strat:20s} {bar} {weight:.0%}")
    except Exception as e:
        print(f"  ❌ Erro: {e}")
    
    # Testar OrderGenerator
    print()
    print("─" * 40)
    print("🤖 ORDER GENERATOR")
    print("─" * 40)
    
    try:
        from order_generator import OrderGenerator
        og = OrderGenerator()
        
        print(f"  Total Executors: {len(og.executors)}")
        
        by_symbol = {}
        for ex in og.executors:
            if ex.symbol not in by_symbol:
                by_symbol[ex.symbol] = []
            by_symbol[ex.symbol].append(ex.strategy_name)
        
        for symbol, strategies in by_symbol.items():
            print(f"  {symbol}: {len(strategies)} estratégias")
            for strat in strategies:
                print(f"    └─ {strat}")
    except Exception as e:
        print(f"  ❌ Erro: {e}")
    
    print()
    print("=" * 80)
    print("                    ANÁLISE CONCLUÍDA")
    print("=" * 80)


if __name__ == "__main__":
    main()
