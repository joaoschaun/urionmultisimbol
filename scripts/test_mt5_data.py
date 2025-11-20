#!/usr/bin/env python3
"""Script para testar dados do MT5"""

import MetaTrader5 as mt5
from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager
from loguru import logger

def main():
    # Carregar config
    config = ConfigManager()
    
    # Conectar MT5
    mt5_conn = MT5Connector(config)
    
    if not mt5_conn.connect():
        logger.error("Falha ao conectar MT5")
        return
    
    # Testar get_rates
    logger.info("Testando get_rates...")
    rates = mt5_conn.get_rates("XAUUSD", mt5.TIMEFRAME_M15, 10)
    
    if rates is None:
        logger.error("❌ get_rates retornou None")
        return
    
    logger.info(f"✅ Dados recebidos!")
    logger.info(f"   Tipo: {type(rates)}")
    logger.info(f"   Tamanho: {len(rates) if hasattr(rates, '__len__') else 'N/A'}")
    
    if hasattr(rates, 'dtype'):
        logger.info(f"   Dtype: {rates.dtype}")
        logger.info(f"   Colunas: {rates.dtype.names}")
    
    if hasattr(rates, '__getitem__') and len(rates) > 0:
        logger.info(f"\n   Primeira linha:")
        first = rates[0]
        logger.info(f"   {first}")
    
    # Verificar estrutura específica
    import pandas as pd
    df = pd.DataFrame(rates)
    logger.info(f"\n   DataFrame shape: {df.shape}")
    logger.info(f"   DataFrame columns: {list(df.columns)}")
    logger.info(f"\n   Primeiras 3 linhas:")
    logger.info(f"\n{df.head(3)}")
    
    mt5_conn.disconnect()
    logger.success("✅ Teste completo!")

if __name__ == "__main__":
    main()
