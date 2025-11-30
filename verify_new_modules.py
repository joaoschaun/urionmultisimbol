"""
Script de Verificação dos Módulos Criados
=========================================
Verifica se todos os novos módulos importam corretamente.
"""

import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Testa imports de todos os módulos novos"""
    results = []
    
    # === Core Modules ===
    print("\n=== Core Modules ===")
    
    try:
        from src.core.partial_tp_manager import PartialTPManager, PartialTPLevel
        print("✅ partial_tp_manager - PartialTPManager, PartialTPLevel")
        results.append(("partial_tp_manager", True))
    except Exception as e:
        print(f"❌ partial_tp_manager - {e}")
        results.append(("partial_tp_manager", False))
    
    try:
        from src.core.config_hot_reload import ConfigHotReloader
        print("✅ config_hot_reload - ConfigHotReloader")
        results.append(("config_hot_reload", True))
    except Exception as e:
        print(f"❌ config_hot_reload - {e}")
        results.append(("config_hot_reload", False))
    
    try:
        from src.core.trade_journal import TradeJournal, TradeEntry
        print("✅ trade_journal - TradeJournal, TradeEntry")
        results.append(("trade_journal", True))
    except Exception as e:
        print(f"❌ trade_journal - {e}")
        results.append(("trade_journal", False))
    
    try:
        from src.core.advanced_metrics import AdvancedMetrics
        print("✅ advanced_metrics - AdvancedMetrics")
        results.append(("advanced_metrics", True))
    except Exception as e:
        print(f"❌ advanced_metrics - {e}")
        results.append(("advanced_metrics", False))
    
    # === Analysis Modules ===
    print("\n=== Analysis Modules ===")
    
    try:
        from src.analysis.market_regime import MarketRegimeDetector, MarketRegime
        print("✅ market_regime - MarketRegimeDetector, MarketRegime")
        results.append(("market_regime", True))
    except Exception as e:
        print(f"❌ market_regime - {e}")
        results.append(("market_regime", False))
    
    # === Backtesting Modules ===
    print("\n=== Backtesting Modules ===")
    
    try:
        from src.backtesting.engine import BacktestEngine, BaseStrategy
        print("✅ backtesting.engine - BacktestEngine, BaseStrategy")
        results.append(("backtesting.engine", True))
    except Exception as e:
        print(f"❌ backtesting.engine - {e}")
        results.append(("backtesting.engine", False))
    
    try:
        from src.backtesting.data_manager import HistoricalDataManager
        print("✅ backtesting.data_manager - HistoricalDataManager")
        results.append(("backtesting.data_manager", True))
    except Exception as e:
        print(f"❌ backtesting.data_manager - {e}")
        results.append(("backtesting.data_manager", False))
    
    try:
        from src.backtesting.optimizer import StrategyOptimizer
        print("✅ backtesting.optimizer - StrategyOptimizer")
        results.append(("backtesting.optimizer", True))
    except Exception as e:
        print(f"❌ backtesting.optimizer - {e}")
        results.append(("backtesting.optimizer", False))
    
    # === API Modules ===
    print("\n=== API Modules ===")
    
    try:
        from src.api.server import app, UrionAPI
        print("✅ api.server - app, UrionAPI")
        results.append(("api.server", True))
    except Exception as e:
        print(f"❌ api.server - {e}")
        results.append(("api.server", False))
    
    # === Monitoring Modules ===
    print("\n=== Monitoring Modules ===")
    
    try:
        from src.monitoring.dashboard import MetricsDashboard
        print("✅ monitoring.dashboard - MetricsDashboard")
        results.append(("monitoring.dashboard", True))
    except Exception as e:
        print(f"❌ monitoring.dashboard - {e}")
        results.append(("monitoring.dashboard", False))
    
    # === Summary ===
    print("\n" + "="*50)
    print("RESUMO DA VERIFICAÇÃO")
    print("="*50)
    
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    
    print(f"\n✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {len(results)}")
    
    if failed > 0:
        print("\n⚠️  Módulos com falha:")
        for name, ok in results:
            if not ok:
                print(f"   - {name}")
    else:
        print("\n🎉 Todos os módulos importam corretamente!")
    
    return failed == 0

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
