# -*- coding: utf-8 -*-
"""
Script de Teste - Todos os Modulos Novos v2.0
=============================================
Testa a importacao e inicializacao de todos os novos modulos.
"""

import sys
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

def test_module(name: str, import_func) -> bool:
    """Testa importacao de um modulo"""
    try:
        import_func()
        print(f"  ✓ {name}")
        return True
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        return False

def main():
    print("=" * 60)
    print("TESTE DE MODULOS - URION BOT v2.0 PROFESSIONAL EDITION")
    print("=" * 60)
    print()
    
    results = []
    
    # Carregar config
    print("[1/5] Testando Config Manager...")
    try:
        from core.config_manager import ConfigManager
        config_mgr = ConfigManager()
        config = config_mgr.config
        print(f"  ✓ Config carregado ({len(config)} chaves)")
        results.append(True)
    except Exception as e:
        print(f"  ✗ Config: {e}")
        config = {}
        results.append(False)
    
    # Modulos de Infraestrutura
    print("\n[2/5] Testando Infraestrutura...")
    
    results.append(test_module("Redis Client", 
        lambda: __import__('infrastructure.redis_client', fromlist=['get_redis_client'])))
    
    results.append(test_module("InfluxDB Client", 
        lambda: __import__('infrastructure.influxdb_client', fromlist=['get_influxdb_client'])))
    
    results.append(test_module("Data Hub", 
        lambda: __import__('infrastructure.data_hub', fromlist=['get_data_hub'])))
    
    results.append(test_module("Sentiment Analyzer", 
        lambda: __import__('infrastructure.sentiment_analyzer', fromlist=['get_sentiment_analyzer'])))
    
    # Modulos de Analise
    print("\n[3/5] Testando Analise...")
    
    results.append(test_module("Order Flow Analyzer", 
        lambda: __import__('analysis.order_flow_analyzer', fromlist=['get_order_flow_analyzer'])))
    
    results.append(test_module("Manipulation Detector", 
        lambda: __import__('analysis.manipulation_detector', fromlist=['ManipulationDetector'])))
    
    results.append(test_module("TradingView Integration", 
        lambda: __import__('analysis.tradingview_integration', fromlist=['get_tradingview_integration'])))
    
    results.append(test_module("Economic Calendar", 
        lambda: __import__('analysis.economic_calendar', fromlist=['get_economic_calendar'])))
    
    # Modulos Core
    print("\n[4/5] Testando Core...")
    
    results.append(test_module("Position Intelligence", 
        lambda: __import__('core.position_intelligence', fromlist=['PositionIntelligenceManager'])))
    
    results.append(test_module("Strategy Communicator", 
        lambda: __import__('core.strategy_communicator', fromlist=['get_strategy_communicator'])))
    
    results.append(test_module("Execution Algorithms", 
        lambda: __import__('core.execution_algorithms', fromlist=['get_execution_manager', 'get_smart_router'])))
    
    # Modulos de Risk e ML
    print("\n[5/5] Testando Risk & ML...")
    
    results.append(test_module("Monte Carlo Simulator", 
        lambda: __import__('risk.monte_carlo', fromlist=['get_monte_carlo_simulator'])))
    
    results.append(test_module("VaR Calculator", 
        lambda: __import__('risk.var_calculator', fromlist=['get_var_calculator'])))
    
    results.append(test_module("ML Training Pipeline", 
        lambda: __import__('ml.training_pipeline', fromlist=['get_ml_training_pipeline'])))
    
    results.append(test_module("Walk-Forward Optimizer", 
        lambda: __import__('backtesting.walk_forward', fromlist=['get_walk_forward_optimizer'])))
    
    # Resumo
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTADO: {passed}/{total} modulos OK")
    
    if passed == total:
        print("\n✓ TODOS OS MODULOS FUNCIONANDO!")
        print("  O bot esta pronto para rodar com todos os recursos avancados.")
    else:
        print(f"\n✗ {total - passed} modulos com problemas.")
        print("  Verifique as dependencias e corrija os erros.")
    
    print("=" * 60)
    
    # Testar inicializacao completa
    print("\n[BONUS] Testando Inicializacao Completa...")
    try:
        from analysis.order_flow_analyzer import get_order_flow_analyzer
        from analysis.manipulation_detector import ManipulationDetector
        from analysis.economic_calendar import get_economic_calendar
        from core.position_intelligence import PositionIntelligenceManager
        from core.strategy_communicator import get_strategy_communicator
        from core.execution_algorithms import get_execution_manager
        from risk.monte_carlo import get_monte_carlo_simulator
        from risk.var_calculator import get_var_calculator
        from ml.training_pipeline import get_ml_training_pipeline
        
        # Inicializar
        order_flow = get_order_flow_analyzer(config)
        manipulation = ManipulationDetector(config)
        calendar = get_economic_calendar(config)
        position_intel = PositionIntelligenceManager(config)
        strategy_comm = get_strategy_communicator(config)
        exec_mgr = get_execution_manager(config)
        monte_carlo = get_monte_carlo_simulator(config)
        var_calc = get_var_calculator(config)
        ml_pipeline = get_ml_training_pipeline(config)
        
        print("  ✓ Todos os modulos inicializados com sucesso!")
        
        # Mostrar status
        print("\n  Modulos ativos:")
        print(f"    - Order Flow: Pronto")
        print(f"    - Manipulation Detector: Pronto")
        print(f"    - Economic Calendar: {len(calendar._events)} eventos")
        print(f"    - Position Intelligence: Pronto")
        print(f"    - Strategy Communicator: Pronto")
        print(f"    - Execution Manager: Pronto")
        print(f"    - Monte Carlo: Pronto")
        print(f"    - VaR Calculator: Pronto")
        print(f"    - ML Pipeline: Pronto")
        
    except Exception as e:
        print(f"  ✗ Erro na inicializacao: {e}")
        import traceback
        traceback.print_exc()
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
