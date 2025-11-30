"""
Inicializador de Módulos Avançados v2.0
Centraliza a inicialização dos novos módulos do bot
"""
from typing import Dict, Optional, Callable, Any
from loguru import logger


def initialize_advanced_modules(
    config: Dict,
    alert_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Inicializa todos os módulos avançados v2.0
    
    Args:
        config: Configuração do bot
        alert_callback: Callback para alertas (ex: telegram.send_message_sync)
        
    Returns:
        Dict com instâncias dos módulos inicializados
    """
    modules = {}
    
    logger.info("=" * 50)
    logger.info("🔧 Inicializando Módulos Avançados v2.0...")
    logger.info("=" * 50)
    
    # === 1. CIRCUIT BREAKER ===
    try:
        from core.circuit_breaker import BotCircuitBreakers
        
        circuit_breakers = BotCircuitBreakers.get_all_breakers()
        modules['circuit_breakers'] = circuit_breakers
        logger.success("✅ Circuit Breakers inicializados (5 circuitos)")
    except ImportError as e:
        logger.warning(f"⚠️ Circuit Breaker não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Circuit Breaker: {e}")
    
    # === 2. HEALTH MONITOR ===
    try:
        from core.health_monitor import (
            get_health_monitor, 
            HealthAlert, 
            AlertSeverity
        )
        
        def health_alert_handler(alert: HealthAlert):
            """Handler para alertas de saúde"""
            if alert.severity in (AlertSeverity.ERROR, AlertSeverity.CRITICAL):
                msg = f"🚨 ALERTA [{alert.component}]: {alert.message}"
                if alert_callback:
                    try:
                        alert_callback(msg)
                    except Exception:
                        pass
                logger.warning(msg)
        
        health_config = config.get('health_monitor', {})
        check_interval = health_config.get('check_interval_seconds', 30)
        
        health_monitor = get_health_monitor(
            check_interval=check_interval,
            alert_callback=health_alert_handler
        )
        modules['health_monitor'] = health_monitor
        logger.success(f"✅ Health Monitor inicializado (intervalo: {check_interval}s)")
    except ImportError as e:
        logger.warning(f"⚠️ Health Monitor não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Health Monitor: {e}")
    
    # === 3. PERFORMANCE COLLECTOR ===
    try:
        from core.performance_collector import get_performance_collector
        
        perf_config = config.get('performance', {})
        data_dir = perf_config.get('data_dir', 'data')
        
        performance_collector = get_performance_collector(
            config={'data_dir': data_dir}
        )
        modules['performance_collector'] = performance_collector
        logger.success("✅ Performance Collector inicializado")
    except ImportError as e:
        logger.warning(f"⚠️ Performance Collector não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Performance Collector: {e}")
    
    # === 4. SESSION MANAGER ===
    try:
        from core.trading_session_manager import get_session_manager
        
        session_manager = get_session_manager()
        session_info = session_manager.get_current_session()
        modules['session_manager'] = session_manager
        
        logger.success(
            f"✅ Session Manager inicializado | "
            f"Sessão: {session_info['current_session']} "
            f"(qualidade: {session_info['quality']})"
        )
    except ImportError as e:
        logger.warning(f"⚠️ Session Manager não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Session Manager: {e}")
    
    # === 5. CORRELATION MANAGER ===
    try:
        from core.correlation_manager import get_correlation_manager
        
        corr_config = config.get('correlation', {})
        correlation_manager = get_correlation_manager(config=corr_config)
        modules['correlation_manager'] = correlation_manager
        logger.success("✅ Correlation Manager inicializado")
    except ImportError as e:
        logger.warning(f"⚠️ Correlation Manager não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Correlation Manager: {e}")
    
    # === 6. DYNAMIC RISK CALCULATOR ===
    try:
        from core.dynamic_risk_calculator import get_dynamic_calculator
        
        stops_config = config.get('dynamic_stops', {})
        risk_calculator = get_dynamic_calculator(config=stops_config)
        modules['risk_calculator'] = risk_calculator
        logger.success("✅ Dynamic Risk Calculator inicializado")
    except ImportError as e:
        logger.warning(f"⚠️ Dynamic Risk Calculator não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Dynamic Risk Calculator: {e}")
    
    # === 7. TRAILING STOP MANAGER ===
    try:
        from core.trailing_stop_manager import get_trailing_manager
        
        trailing_config = config.get('trailing_stop', {})
        trailing_manager = get_trailing_manager(config=trailing_config)
        modules['trailing_manager'] = trailing_manager
        logger.success("✅ Trailing Stop Manager inicializado")
    except ImportError as e:
        logger.warning(f"⚠️ Trailing Stop Manager não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Trailing Stop Manager: {e}")
    
    # === 8. DIVERGENCE DETECTOR ===
    try:
        from analysis.divergence_detector import get_divergence_detector
        
        div_config = config.get('divergence', {})
        divergence_detector = get_divergence_detector(config=div_config)
        modules['divergence_detector'] = divergence_detector
        logger.success("✅ Divergence Detector inicializado")
    except ImportError as e:
        logger.warning(f"⚠️ Divergence Detector não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Divergence Detector: {e}")
    
    # Resumo
    logger.info("=" * 50)
    logger.info(f"📦 {len(modules)}/8 módulos avançados carregados")
    logger.info("=" * 50)
    
    return modules


def start_health_monitoring(modules: Dict[str, Any]):
    """Inicia o monitoramento de saúde se disponível"""
    if 'health_monitor' in modules:
        modules['health_monitor'].start()
        logger.info("🏥 Health Monitor em execução")


def stop_advanced_modules(modules: Dict[str, Any]):
    """Para todos os módulos avançados de forma limpa"""
    if 'health_monitor' in modules:
        try:
            modules['health_monitor'].stop()
            logger.info("🏥 Health Monitor parado")
        except Exception as e:
            logger.error(f"Erro ao parar Health Monitor: {e}")


def get_session_info(modules: Dict[str, Any]) -> Optional[Dict]:
    """Obtém informações da sessão atual"""
    if 'session_manager' in modules:
        return modules['session_manager'].get_current_session()
    return None


def check_correlation(
    modules: Dict[str, Any],
    symbol: str,
    direction: str,
    volume: float
) -> bool:
    """
    Verifica se um novo trade pode ser aberto sem conflitos de correlação
    
    Returns:
        True se pode abrir, False se há conflito
    """
    if 'correlation_manager' not in modules:
        return True  # Sem verificação = permitir
    
    manager = modules['correlation_manager']
    conflicts = manager.check_correlation_conflicts(symbol, direction)
    
    if conflicts:
        logger.warning(
            f"⚠️ Conflito de correlação para {symbol} {direction}: {conflicts}"
        )
        return False
    
    return True


def record_trade_result(
    modules: Dict[str, Any],
    ticket: int,
    symbol: str,
    strategy: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    volume: float,
    profit: float,
    entry_time,
    exit_time,
    reason: str = "unknown"
):
    """Registra resultado de um trade no Performance Collector"""
    if 'performance_collector' not in modules:
        return
    
    try:
        modules['performance_collector'].record_trade(
            ticket=ticket,
            symbol=symbol,
            strategy=strategy,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            volume=volume,
            profit=profit,
            entry_time=entry_time,
            exit_time=exit_time,
            reason=reason
        )
    except Exception as e:
        logger.error(f"Erro ao registrar trade no collector: {e}")


def calculate_dynamic_stops(
    modules: Dict[str, Any],
    symbol: str,
    timeframe: str,
    strategy: str,
    atr: float
) -> Dict[str, float]:
    """
    Calcula SL/TP dinâmico baseado em ATR
    
    Returns:
        Dict com sl_pips e tp_pips
    """
    if 'risk_calculator' not in modules:
        # Fallback padrão
        return {'sl_pips': 50, 'tp_pips': 100}
    
    try:
        return modules['risk_calculator'].calculate_sl_tp(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            atr=atr
        )
    except Exception as e:
        logger.error(f"Erro ao calcular stops dinâmicos: {e}")
        return {'sl_pips': 50, 'tp_pips': 100}


def get_trailing_stop_level(
    modules: Dict[str, Any],
    symbol: str,
    direction: str,
    entry_price: float,
    current_price: float,
    current_stop: float,
    atr: float
) -> Optional[float]:
    """
    Calcula novo nível de trailing stop
    
    Returns:
        Novo stop loss ou None se não deve mover
    """
    if 'trailing_manager' not in modules:
        return None
    
    try:
        return modules['trailing_manager'].calculate_trailing_stop(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            current_price=current_price,
            current_stop=current_stop,
            atr=atr
        )
    except Exception as e:
        logger.error(f"Erro ao calcular trailing stop: {e}")
        return None


def detect_divergence(
    modules: Dict[str, Any],
    symbol: str,
    timeframe: str,
    data: Dict
) -> Optional[Dict]:
    """
    Detecta divergências nos indicadores
    
    Returns:
        Dict com informações da divergência ou None
    """
    if 'divergence_detector' not in modules:
        return None
    
    try:
        return modules['divergence_detector'].get_trade_signal(
            symbol=symbol,
            timeframe=timeframe,
            data=data
        )
    except Exception as e:
        logger.error(f"Erro ao detectar divergência: {e}")
        return None


def get_health_status(modules: Dict[str, Any]) -> Dict:
    """Obtém status de saúde do bot"""
    if 'health_monitor' not in modules:
        return {"status": "unknown", "message": "Health Monitor não disponível"}
    
    return modules['health_monitor'].get_overall_health()


def get_performance_report(modules: Dict[str, Any]) -> str:
    """Gera relatório de performance"""
    if 'performance_collector' not in modules:
        return "Performance Collector não disponível"
    
    return modules['performance_collector'].generate_report()


# Singleton para módulos globais
_global_modules: Optional[Dict[str, Any]] = None


def get_global_modules() -> Optional[Dict[str, Any]]:
    """Obtém módulos globais inicializados"""
    return _global_modules


def set_global_modules(modules: Dict[str, Any]):
    """Define módulos globais"""
    global _global_modules
    _global_modules = modules
