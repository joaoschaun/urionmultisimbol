"""
Exemplo de uso do TechnicalAnalyzer
Demonstra análise técnica multi-timeframe e geração de sinais
"""

import sys
import os
from datetime import datetime

# Adicionar diretório src ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager
from src.core.logger import setup_logger
from src.analysis.technical import TechnicalAnalyzer


def main():
    """Exemplo de análise técnica"""
    
    # Configurar logger
    logger = setup_logger('technical_demo')
    logger.info("=== Demo: Análise Técnica ===")
    
    try:
        # Carregar configuração
        config = ConfigManager('config/config.yaml')
        logger.info("Configuração carregada")
        
        # Conectar ao MT5
        mt5 = MT5Connector(config.config)
        if not mt5.connect():
            logger.error("Falha ao conectar ao MT5")
            return
        
        logger.info(f"Conectado ao MT5 - Conta: {mt5.account_info['login']}")
        
        # Criar analisador técnico
        analyzer = TechnicalAnalyzer(mt5, config.config)
        logger.info(f"TechnicalAnalyzer inicializado para {analyzer.symbol}")
        
        # ===== EXEMPLO 1: Análise de um único timeframe =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 1: Análise de Timeframe Único (M5)")
        logger.info("="*60)
        
        analysis_m5 = analyzer.analyze_timeframe('M5', bars=200)
        
        if analysis_m5:
            logger.info(f"\nTimeframe: {analysis_m5['timeframe']}")
            logger.info(f"Preço Atual: {analysis_m5['current_price']:.2f}")
            logger.info(f"Horário: {analysis_m5['current_time']}")
            
            # Médias Móveis
            logger.info("\nMédias Móveis Exponenciais (EMA):")
            for name, value in analysis_m5['ema'].items():
                logger.info(f"  {name}: {value:.2f}")
            
            # RSI
            logger.info(f"\nRSI (14): {analysis_m5['rsi']:.2f}")
            if analysis_m5['rsi'] > 70:
                logger.info("  → Sobrecomprado")
            elif analysis_m5['rsi'] < 30:
                logger.info("  → Sobrevendido")
            else:
                logger.info("  → Neutro")
            
            # MACD
            macd = analysis_m5['macd']
            logger.info(f"\nMACD:")
            logger.info(f"  MACD Line: {macd['macd']:.4f}")
            logger.info(f"  Signal Line: {macd['signal']:.4f}")
            logger.info(f"  Histogram: {macd['histogram']:.4f}")
            if macd['macd'] > macd['signal']:
                logger.info("  → Sinal de Alta")
            else:
                logger.info("  → Sinal de Baixa")
            
            # Bollinger Bands
            bb = analysis_m5['bollinger']
            logger.info(f"\nBandas de Bollinger:")
            logger.info(f"  Superior: {bb['upper']:.2f}")
            logger.info(f"  Média: {bb['middle']:.2f}")
            logger.info(f"  Inferior: {bb['lower']:.2f}")
            
            price = analysis_m5['current_price']
            if price > bb['upper']:
                logger.info("  → Preço acima da banda superior")
            elif price < bb['lower']:
                logger.info("  → Preço abaixo da banda inferior")
            else:
                logger.info("  → Preço dentro das bandas")
            
            # ATR
            logger.info(f"\nATR (14): {analysis_m5['atr']:.2f}")
            
            # ADX
            adx = analysis_m5['adx']
            logger.info(f"\nADX:")
            logger.info(f"  ADX: {adx['adx']:.2f}")
            logger.info(f"  DI+: {adx['di_plus']:.2f}")
            logger.info(f"  DI-: {adx['di_minus']:.2f}")
            if adx['adx'] > 25:
                logger.info("  → Tendência Forte")
            else:
                logger.info("  → Tendência Fraca")
            
            # Estocástico
            stoch = analysis_m5['stochastic']
            logger.info(f"\nEstocástico:")
            logger.info(f"  %K: {stoch['k']:.2f}")
            logger.info(f"  %D: {stoch['d']:.2f}")
            if stoch['k'] > 80:
                logger.info("  → Sobrecomprado")
            elif stoch['k'] < 20:
                logger.info("  → Sobrevendido")
            
            # Padrões de Candlestick
            patterns = analysis_m5['patterns']
            detected_patterns = [name for name, detected in patterns.items() if detected]
            
            logger.info(f"\nPadrões de Candlestick Detectados:")
            if detected_patterns:
                for pattern in detected_patterns:
                    logger.info(f"  ✓ {pattern}")
            else:
                logger.info("  Nenhum padrão detectado")
            
            # Análise de Tendência
            trend = analysis_m5['trend']
            logger.info(f"\nAnálise de Tendência:")
            logger.info(f"  Direção: {trend['direction'].upper()}")
            logger.info(f"  Força: {trend['strength']:.2%}")
            logger.info(f"  Sinais:")
            for signal in trend['signals'][:5]:  # Mostrar apenas 5 primeiros
                logger.info(f"    • {signal}")
        
        # ===== EXEMPLO 2: Análise Multi-Timeframe =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 2: Análise Multi-Timeframe")
        logger.info("="*60)
        
        mtf_analysis = analyzer.analyze_multi_timeframe(['M5', 'M15', 'M30', 'H1'])
        
        if mtf_analysis:
            # Mostrar tendência de cada timeframe
            logger.info("\nTendências por Timeframe:")
            for tf in ['M5', 'M15', 'M30', 'H1']:
                if tf in mtf_analysis:
                    trend = mtf_analysis[tf]['trend']
                    direction_emoji = {
                        'bullish': '📈',
                        'bearish': '📉',
                        'neutral': '➡️'
                    }
                    emoji = direction_emoji.get(trend['direction'], '❓')
                    logger.info(
                        f"  {tf:4s}: {emoji} {trend['direction']:8s} "
                        f"(Força: {trend['strength']:.2%})"
                    )
            
            # Consenso
            if 'consensus' in mtf_analysis:
                consensus = mtf_analysis['consensus']
                logger.info(f"\nConsenso Multi-Timeframe:")
                logger.info(f"  Direção: {consensus['direction'].upper()}")
                logger.info(f"  Força: {consensus['strength']:.2%}")
                logger.info(f"  Concordância: {consensus['agreement']:.2%}")
                logger.info(f"  Votos:")
                logger.info(f"    Alta: {consensus['bullish_count']}")
                logger.info(f"    Baixa: {consensus['bearish_count']}")
                logger.info(f"    Neutro: {consensus['neutral_count']}")
        
        # ===== EXEMPLO 3: Geração de Sinal =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 3: Geração de Sinal de Trading")
        logger.info("="*60)
        
        signal = analyzer.get_signal('M5')
        
        if signal:
            logger.info(f"\nSINAL GERADO:")
            logger.info(f"  Ação: {signal['action']}")
            logger.info(f"  Confiança: {signal['confidence']:.2%}")
            logger.info(f"  Direção: {signal['direction']}")
            logger.info(f"  Força: {signal['strength']:.2%}")
            logger.info(f"  Concordância: {signal['agreement']:.2%}")
            logger.info(f"  Timestamp: {signal['timestamp']}")
            
            # Recomendação
            if signal['action'] == 'BUY':
                logger.info("\n  ✅ RECOMENDAÇÃO: COMPRAR")
                logger.info(f"  Confiança {signal['confidence']:.0%} - "
                          f"Sinal favorável para entrada LONG")
            elif signal['action'] == 'SELL':
                logger.info("\n  ✅ RECOMENDAÇÃO: VENDER")
                logger.info(f"  Confiança {signal['confidence']:.0%} - "
                          f"Sinal favorável para entrada SHORT")
            else:
                logger.info("\n  ⏸️  RECOMENDAÇÃO: AGUARDAR")
                logger.info("  Sinal não possui confiança suficiente para entrada")
        
        # ===== EXEMPLO 4: Análise Contínua =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 4: Análise Contínua (3 iterações)")
        logger.info("="*60)
        
        import time
        
        for i in range(3):
            logger.info(f"\n--- Iteração {i+1} ---")
            
            # Limpar cache para forçar nova busca de dados
            analyzer.clear_cache()
            
            # Gerar novo sinal
            signal = analyzer.get_signal('M5')
            
            if signal:
                logger.info(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"{signal['action']} - Confiança: {signal['confidence']:.2%}"
                )
            
            if i < 2:  # Não esperar na última iteração
                logger.info("Aguardando 10 segundos...")
                time.sleep(10)
        
        logger.info("\n" + "="*60)
        logger.info("Demo concluído com sucesso!")
        logger.info("="*60)
        
    except KeyboardInterrupt:
        logger.info("\nDemo interrompido pelo usuário")
    
    except Exception as e:
        logger.error(f"Erro durante demo: {e}", exc_info=True)
    
    finally:
        # Desconectar
        if 'mt5' in locals():
            mt5.disconnect()
            logger.info("Desconectado do MT5")


if __name__ == '__main__':
    main()
