#!/usr/bin/env python3
"""Teste detalhado do TechnicalAnalyzer"""

from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager
from src.analysis.technical_analyzer import TechnicalAnalyzer
from loguru import logger
import json


def main():
    # Setup
    config = ConfigManager()
    mt5 = MT5Connector(config)
    
    if not mt5.connect():
        logger.error("Falha ao conectar MT5")
        return
    
    analyzer = TechnicalAnalyzer(mt5, config)
    
    # Testar analyze_timeframe
    logger.info("Testando analyze_timeframe M15...")
    result = analyzer.analyze_timeframe("M15", bars=100)
    
    if result is None:
        logger.error("❌ analyze_timeframe retornou None")
        return
    
    logger.success("✅ analyze_timeframe funcionou!")
    logger.info(f"   Tipo: {type(result)}")
    logger.info(f"   Keys: {list(result.keys())}")
    
    # Verificar estrutura
    for key, value in result.items():
        logger.info(f"\n   {key}: {type(value)}")
        if key == 'ema':
            logger.info(f"      Valor EMA: {value}")
            logger.info(f"      Tipo EMA: {type(value)}")
        elif key == 'trend':
            logger.info(f"      Trend: {value}")
    
    mt5.disconnect()


if __name__ == "__main__":
    main()
