"""
Script de teste para executar uma ordem no MT5
"""
import sys
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from loguru import logger

def main():
    """Teste de ordem"""
    
    logger.info("="*60)
    logger.info("TESTE DE ORDEM - URION BOT")
    logger.info("="*60)
    
    # Carregar config
    config_manager = ConfigManager()
    config = config_manager.config
    
    # Conectar MT5
    logger.info("\n1. Conectando ao MT5...")
    mt5 = MT5Connector(config)
    
    if not mt5.connect():
        logger.error("❌ Falha ao conectar no MT5")
        return
    
    logger.success("✅ Conectado ao MT5")
    
    # Verificar informações da conta
    logger.info("\n2. Informações da Conta:")
    account_info = mt5.get_account_info()
    if account_info:
        logger.info(f"   Login: {account_info.get('login')}")
        logger.info(f"   Servidor: {account_info.get('server')}")
        logger.info(f"   Saldo: ${account_info.get('balance', 0):.2f}")
        logger.info(f"   Equity: ${account_info.get('equity', 0):.2f}")
        logger.info(f"   Margin Free: ${account_info.get('margin_free', 0):.2f}")
    
    # Verificar símbolo
    symbol = "XAUUSD"
    logger.info(f"\n3. Verificando símbolo {symbol}...")
    symbol_info = mt5.get_symbol_info(symbol)
    
    if not symbol_info:
        logger.error(f"❌ Símbolo {symbol} não encontrado")
        mt5.disconnect()
        return
    
    logger.success(f"✅ Símbolo {symbol} disponível")
    logger.info(f"   Bid: {symbol_info.get('bid', 0):.2f}")
    logger.info(f"   Ask: {symbol_info.get('ask', 0):.2f}")
    logger.info(f"   Spread: {symbol_info.get('spread', 0)} pontos")
    
    # Verificar posições abertas
    logger.info("\n4. Posições Abertas:")
    positions = mt5.get_positions(symbol)
    if positions:
        logger.info(f"   {len(positions)} posição(ões) aberta(s)")
        for pos in positions:
            logger.info(f"   - Ticket: {pos['ticket']} | {pos['type']} | Volume: {pos['volume']} | Profit: ${pos['profit']:.2f}")
    else:
        logger.info("   Nenhuma posição aberta")
    
    # Perguntar se quer abrir ordem
    logger.info("\n5. Teste de Ordem:")
    logger.info("   Esta é uma conta DEMO? Confirme antes de continuar.")
    
    response = input("\n   Deseja abrir uma ordem de TESTE (0.01 lote)? (s/N): ").strip().lower()
    
    if response != 's':
        logger.info("   Teste cancelado pelo usuário")
        mt5.disconnect()
        return
    
    # Escolher tipo
    order_type = input("   Tipo de ordem (BUY/SELL): ").strip().upper()
    
    if order_type not in ['BUY', 'SELL']:
        logger.error("   Tipo inválido. Use BUY ou SELL")
        mt5.disconnect()
        return
    
    # Calcular SL e TP
    current_price = symbol_info['ask'] if order_type == 'BUY' else symbol_info['bid']
    point = symbol_info.get('point', 0.01)
    
    # SL: 50 pontos (5 USD para XAUUSD)
    # TP: 100 pontos (10 USD para XAUUSD)
    if order_type == 'BUY':
        sl = current_price - (50 * point)
        tp = current_price + (100 * point)
    else:
        sl = current_price + (50 * point)
        tp = current_price - (100 * point)
    
    logger.info(f"\n   Preparando ordem:")
    logger.info(f"   - Símbolo: {symbol}")
    logger.info(f"   - Tipo: {order_type}")
    logger.info(f"   - Volume: 0.01 lote")
    logger.info(f"   - Preço: {current_price:.2f}")
    logger.info(f"   - Stop Loss: {sl:.2f}")
    logger.info(f"   - Take Profit: {tp:.2f}")
    
    confirm = input("\n   Confirmar ordem? (s/N): ").strip().lower()
    
    if confirm != 's':
        logger.info("   Ordem cancelada")
        mt5.disconnect()
        return
    
    # Executar ordem
    logger.info("\n6. Executando ordem...")
    
    result = mt5.place_order(
        symbol=symbol,
        order_type=order_type,
        volume=0.01,
        sl=sl,
        tp=tp,
        comment="URION_TEST"
    )
    
    if result:
        logger.success("✅ ORDEM EXECUTADA COM SUCESSO!")
        logger.info(f"   Ticket: {result.get('order')}")
        logger.info(f"   Volume: {result.get('volume')}")
        logger.info(f"   Preço: {result.get('price'):.2f}")
        logger.info(f"   Comentário: {result.get('comment')}")
    else:
        logger.error("❌ Falha ao executar ordem")
    
    # Verificar posições novamente
    logger.info("\n7. Posições após ordem:")
    positions = mt5.get_positions(symbol)
    if positions:
        for pos in positions:
            logger.info(f"   - Ticket: {pos['ticket']} | {pos['type']} | Volume: {pos['volume']} | Profit: ${pos['profit']:.2f}")
    
    # Desconectar
    logger.info("\n8. Desconectando...")
    mt5.disconnect()
    
    logger.info("\n" + "="*60)
    logger.success("TESTE CONCLUÍDO!")
    logger.info("="*60)


if __name__ == "__main__":
    main()
