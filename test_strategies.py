#!/usr/bin/env python3
"""Teste das estratégias para debug"""

from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager
from src.analysis.technical_analyzer import TechnicalAnalyzer
from src.strategies.strategy_manager import StrategyManager
from loguru import logger


def main():
    # Setup
    config = ConfigManager()
    mt5 = MT5Connector(config)
    
    if not mt5.connect():
        logger.error("Falha ao conectar MT5")
        return
    
    # Análise Técnica
    analyzer = TechnicalAnalyzer(mt5, config)
    
    logger.info("🔍 Executando análise técnica multi-timeframe...")
    analysis = analyzer.analyze_multi_timeframe()
    
    if not analysis:
        logger.error("❌ Análise falhou!")
        return
    
    logger.success("✅ Análise completa!")
    logger.info(f"   Timeframes analisados: {len([k for k in analysis.keys() if k != 'consensus'])}")
    
    if 'consensus' in analysis:
        consensus = analysis['consensus']
        logger.info(f"   Consenso: {consensus.get('direction')}")
        logger.info(f"   Força: {consensus.get('strength', 0):.1%}")
        logger.info(f"   Acordo: {consensus.get('agreement', 0):.1%}")
    
    # Testar estratégias
    logger.info("\n🎯 Testando estratégias...")
    strategy_manager = StrategyManager(config)
    
    # Avaliar sinais
    logger.info("   Avaliando sinais com análise técnica...")
    signal = strategy_manager.get_consensus_signal(analysis)
    
    if signal:
        logger.success("✅ Sinal gerado!")
        logger.info(f"\n   📊 Sinal:")
        logger.info(f"      Tipo: {signal.get('type')}")
        logger.info(f"      Estratégia: {signal.get('strategy')}")
        logger.info(f"      Confiança: {signal.get('confidence', 0):.1%}")
        logger.info(f"      Preço entrada: {signal.get('entry_price')}")
        logger.info(f"      Stop Loss: {signal.get('stop_loss')}")
        logger.info(f"      Take Profit: {signal.get('take_profit')}")
    else:
        logger.warning("⚠️ Nenhum sinal gerado!")
        logger.info("\n   💡 Possíveis razões:")
        logger.info("      • Mercado lateral (sem tendência clara)")
        logger.info("      • Sinais conflitantes entre estratégias")
        logger.info("      • Filtros de qualidade bloquearam sinais fracos")
        logger.info("      • Condições de mercado não favoráveis")
        
        # Mostrar análise detalhada
        logger.info("\n   📈 Análise do mercado:")
        for tf, data in analysis.items():
            if tf == 'consensus':
                continue
            trend = data.get('trend', {})
            logger.info(f"\n      {tf}:")
            logger.info(f"         Tendência: {trend.get('direction', 'N/A')}")
            logger.info(f"         Força: {trend.get('strength', 0):.1%}")
            logger.info(f"         RSI: {data.get('rsi', 0):.1f}")
    
    mt5.disconnect()
    logger.success("\n✅ Teste completo!")


if __name__ == "__main__":
    main()
