"""
Diagnóstico - Por que o bot não está fazendo entradas
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from analysis.technical_analyzer import TechnicalAnalyzer
from strategies.strategy_manager import StrategyManager
from loguru import logger

def check_trading_hours(config):
    """Verifica se está no horário de trading"""
    generator_config = config.get('order_generator', {})
    trading_hours = generator_config.get('trading_hours', {})
    
    start_hour = trading_hours.get('start_hour', 18)
    start_minute = trading_hours.get('start_minute', 30)
    end_hour = trading_hours.get('end_hour', 16)
    end_minute = trading_hours.get('end_minute', 30)
    
    now_utc = datetime.now(timezone.utc)
    current_time = now_utc.hour * 60 + now_utc.minute
    
    # Horário de trading atravessa meia-noite
    start_time = start_hour * 60 + start_minute
    end_time = end_hour * 60 + end_minute
    
    if start_time > end_time:
        in_hours = current_time >= start_time or current_time <= end_time
    else:
        in_hours = start_time <= current_time <= end_time
    
    logger.info(f"\n⏰ HORÁRIO DE TRADING:")
    logger.info(f"   Configurado: {start_hour:02d}:{start_minute:02d} - {end_hour:02d}:{end_minute:02d} UTC")
    logger.info(f"   Hora atual: {now_utc.strftime('%H:%M')} UTC")
    logger.info(f"   Status: {'✅ DENTRO do horário' if in_hours else '❌ FORA do horário'}")
    
    return in_hours

def main():
    """Diagnóstico completo"""
    
    logger.info("="*70)
    logger.info("DIAGNÓSTICO - POR QUE NÃO HÁ ENTRADAS?")
    logger.info("="*70)
    
    # Carregar config
    config = ConfigManager().config
    
    # 1. Verificar MT5
    logger.info("\n1️⃣ VERIFICANDO CONEXÃO MT5...")
    mt5 = MT5Connector(config)
    
    if not mt5.connect():
        logger.error("❌ MT5 não conectado - BOT NÃO PODE OPERAR!")
        logger.error("   Solução: Verifique se MT5 está aberto e credenciais estão corretas")
        return
    
    logger.success("✅ MT5 conectado")
    
    # 2. Verificar conta
    logger.info("\n2️⃣ VERIFICANDO CONTA...")
    account_info = mt5.get_account_info()
    
    balance = account_info.get('balance', 0)
    equity = account_info.get('equity', 0)
    margin_free = account_info.get('margin_free', 0)
    
    logger.info(f"   Balance: ${balance:.2f}")
    logger.info(f"   Equity: ${equity:.2f}")
    logger.info(f"   Margin Free: ${margin_free:.2f}")
    
    if balance < 100:
        logger.warning("⚠️ Balance muito baixo para operar com segurança")
    
    # 3. Verificar horário de trading
    logger.info("\n3️⃣ VERIFICANDO HORÁRIO...")
    in_hours = check_trading_hours(config)
    
    if not in_hours:
        logger.warning("⚠️ BOT FORA DO HORÁRIO DE TRADING!")
        logger.warning("   Solução: Aguarde o horário ou ajuste em config.yaml")
    
    # 4. Verificar posições existentes
    logger.info("\n4️⃣ VERIFICANDO POSIÇÕES...")
    positions = mt5.get_positions()
    max_positions = config.get('trading', {}).get('max_open_positions', 3)
    
    logger.info(f"   Posições abertas: {len(positions)}")
    logger.info(f"   Máximo permitido: {max_positions}")
    
    if len(positions) >= max_positions:
        logger.warning("⚠️ LIMITE DE POSIÇÕES ATINGIDO!")
        logger.warning("   Bot não abrirá novas posições até que alguma feche")
    
    # 5. Verificar Risk Manager
    logger.info("\n5️⃣ VERIFICANDO RISK MANAGER...")
    risk_manager = RiskManager(config, mt5)
    
    # Testar com parâmetros dummy
    can_trade = risk_manager.can_open_position("XAUUSD", "BUY", 0.01)
    logger.info(f"   Pode abrir posição: {'✅ SIM' if can_trade else '❌ NÃO'}")
    
    if not can_trade:
        logger.warning("⚠️ RISK MANAGER BLOQUEANDO TRADES!")
        logger.warning("   Possíveis razões:")
        logger.warning("   - Máximo de posições atingido")
        logger.warning("   - Perda diária excedida")
        logger.warning("   - Drawdown muito alto")
    
    # 6. Análise técnica
    logger.info("\n6️⃣ TESTANDO ANÁLISE TÉCNICA...")
    tech_analyzer = TechnicalAnalyzer(mt5, config)
    
    try:
        logger.info(f"   Analisando XAUUSD multi-timeframe...")
        analysis = tech_analyzer.analyze_multi_timeframe()
        
        if analysis:
            signal = analysis.get('signal', 'NEUTRAL')
            confidence = analysis.get('confidence', 0)
            
            logger.info(f"   Sinal: {signal}")
            logger.info(f"   Confiança: {confidence:.1%}")
            
            if signal == 'NEUTRAL':
                logger.warning("⚠️ Sinal NEUTRO - sem oportunidade clara")
            elif confidence < 0.6:
                logger.warning(f"⚠️ Confiança baixa ({confidence:.1%}) - bot requer > 60%")
        else:
            logger.error("❌ Análise técnica falhou")
            
    except Exception as e:
        logger.error(f"❌ Erro na análise: {e}")
    
    # 7. Testar estratégias
    logger.info("\n7️⃣ TESTANDO ESTRATÉGIAS...")
    
    try:
        strategy_manager = StrategyManager(config)
        
        logger.info(f"   Estratégias carregadas: {len(strategy_manager.strategies)}")
        
        for strategy in strategy_manager.strategies:
            logger.info(f"   • {strategy.name}: Ativa = {strategy.enabled}")
        
        # Testar geração de sinal
        market_data = {
            'symbol': 'XAUUSD',
            'timeframe': 'M15',
            'technical': analysis if analysis else {},
            'news': {'impact': 'low'}
        }
        
        signal = strategy_manager.generate_signal(market_data)
        
        if signal:
            logger.success(f"✅ Sinal gerado: {signal.get('type')} com confiança {signal.get('confidence', 0):.1%}")
        else:
            logger.warning("⚠️ Nenhum sinal gerado pelas estratégias")
            logger.warning("   Possíveis razões:")
            logger.warning("   - Condições de mercado não favoráveis")
            logger.warning("   - Nenhuma estratégia teve sinal forte o suficiente")
            logger.warning("   - Filtros de qualidade bloquearam sinais fracos")
            
    except Exception as e:
        logger.error(f"❌ Erro ao testar estratégias: {e}")
    
    # 8. Resumo
    logger.info("\n" + "="*70)
    logger.info("📊 RESUMO DO DIAGNÓSTICO")
    logger.info("="*70)
    
    issues = []
    
    if not in_hours:
        issues.append("❌ Fora do horário de trading")
    
    if len(positions) >= max_positions:
        issues.append("❌ Limite de posições atingido")
    
    if not can_trade:
        issues.append("❌ Risk Manager bloqueando")
    
    if not signal:
        issues.append("⚠️ Nenhum sinal gerado (normal em mercado lateral)")
    
    if issues:
        logger.warning("\n🔍 PROBLEMAS IDENTIFICADOS:")
        for issue in issues:
            logger.warning(f"   {issue}")
    else:
        logger.success("\n✅ Tudo OK! Bot deve operar quando houver sinais")
        logger.info("\n💡 DICA: Mercado pode estar lateral (sem oportunidades claras)")
        logger.info("   O bot só opera quando há sinais fortes e alinhados")
    
    # Desconectar
    mt5.disconnect()
    
    logger.info("\n" + "="*70)
    logger.info("DIAGNÓSTICO CONCLUÍDO")
    logger.info("="*70)


if __name__ == "__main__":
    main()
