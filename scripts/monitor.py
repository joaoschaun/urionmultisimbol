"""
Monitor em Tempo Real - Urion Trading Bot
Exibe estatísticas ao vivo do bot
"""
import sys
import time
import os
from pathlib import Path
from datetime import datetime

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from core.mt5_connector import MT5Connector
from core.config_manager import ConfigManager
from loguru import logger

def clear_screen():
    """Limpa a tela"""
    os.system('cls' if os.name == 'nt' else 'clear')

def format_profit_color(profit: float) -> str:
    """Retorna cor baseada no lucro"""
    if profit > 0:
        return f"🟢 +${profit:.2f}"
    elif profit < 0:
        return f"🔴 ${profit:.2f}"
    else:
        return f"⚪ ${profit:.2f}"

def monitor_bot():
    """Monitora o bot em tempo real"""
    
    # Conectar MT5
    config = ConfigManager().config
    mt5 = MT5Connector(config)
    
    if not mt5.connect():
        logger.error("❌ Falha ao conectar no MT5")
        return
    
    logger.success("✅ Monitor conectado ao MT5")
    logger.info("Pressione Ctrl+C para sair\n")
    
    try:
        while True:
            clear_screen()
            
            # Header
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("=" * 80)
            print(f"{'URION BOT - MONITOR EM TEMPO REAL':^80}")
            print(f"{now:^80}")
            print("=" * 80)
            
            # Informações da Conta
            account_info = mt5.get_account_info()
            if account_info:
                print("\n📊 INFORMAÇÕES DA CONTA:")
                print(f"   Conta: {account_info.get('login')} | {account_info.get('server')}")
                
                balance = account_info.get('balance', 0)
                equity = account_info.get('equity', 0)
                profit = account_info.get('profit', 0)
                margin = account_info.get('margin', 0)
                margin_free = account_info.get('margin_free', 0)
                margin_level = account_info.get('margin_level', 0)
                
                print(f"   Balance: ${balance:.2f}")
                print(f"   Equity: ${equity:.2f} {format_profit_color(profit)}")
                print(f"   Margin: ${margin:.2f} | Free: ${margin_free:.2f}")
                if margin > 0:
                    print(f"   Margin Level: {margin_level:.2f}%")
            
            # Posições Abertas
            positions = mt5.get_positions()
            print(f"\n📈 POSIÇÕES ABERTAS ({len(positions)}):")
            
            if positions:
                total_profit = 0
                print(f"\n   {'Ticket':<12} {'Tipo':<6} {'Volume':<8} {'Preço':<10} {'Atual':<10} {'SL':<10} {'TP':<10} {'Lucro':<12}")
                print(f"   {'-'*90}")
                
                for pos in positions:
                    ticket = pos['ticket']
                    type_str = pos['type']
                    volume = pos['volume']
                    price_open = pos['price_open']
                    price_current = pos['price_current']
                    sl = pos['sl']
                    tp = pos['tp']
                    profit = pos['profit']
                    total_profit += profit
                    
                    profit_str = format_profit_color(profit)
                    
                    print(f"   {ticket:<12} {type_str:<6} {volume:<8.2f} {price_open:<10.2f} {price_current:<10.2f} {sl:<10.2f} {tp:<10.2f} {profit_str:<12}")
                
                print(f"   {'-'*90}")
                print(f"   {'TOTAL':<70} {format_profit_color(total_profit)}")
            else:
                print("   Nenhuma posição aberta")
            
            # Histórico Recente (últimas 5 operações)
            print("\n📜 HISTÓRICO RECENTE (últimas 5 operações):")
            
            try:
                import MetaTrader5 as mt5_module
                from datetime import timedelta
                
                # Pegar deals dos últimos 7 dias
                now_time = datetime.now()
                from_date = now_time - timedelta(days=7)
                
                deals = mt5_module.history_deals_get(from_date, now_time)
                
                if deals:
                    # Filtrar apenas deals de fechamento (out)
                    closed_deals = [d for d in deals if d.entry == 1][-5:]  # Últimos 5
                    
                    if closed_deals:
                        print(f"\n   {'Ticket':<12} {'Tipo':<6} {'Volume':<8} {'Preço':<10} {'Lucro':<12} {'Data':<20}")
                        print(f"   {'-'*75}")
                        
                        for deal in closed_deals:
                            ticket = deal.position_id
                            type_str = "BUY" if deal.type == 0 else "SELL"
                            volume = deal.volume
                            price = deal.price
                            profit = deal.profit
                            deal_time = datetime.fromtimestamp(deal.time).strftime("%Y-%m-%d %H:%M:%S")
                            
                            profit_str = format_profit_color(profit)
                            
                            print(f"   {ticket:<12} {type_str:<6} {volume:<8.2f} {price:<10.2f} {profit_str:<12} {deal_time:<20}")
                    else:
                        print("   Nenhuma operação fechada nos últimos 7 dias")
                else:
                    print("   Sem histórico disponível")
                    
            except Exception as e:
                print(f"   Erro ao carregar histórico: {e}")
            
            # Símbolo Info
            symbol_info = mt5.get_symbol_info("XAUUSD")
            if symbol_info:
                print("\n💰 XAUUSD:")
                bid = symbol_info.get('bid', 0)
                ask = symbol_info.get('ask', 0)
                spread = symbol_info.get('spread', 0)
                
                print(f"   Bid: {bid:.2f} | Ask: {ask:.2f} | Spread: {spread} pontos")
            
            # Status do Bot
            print("\n🤖 STATUS DO BOT:")
            print("   Order Generator: Rodando (ciclo 5 min)")
            print("   Order Manager: Rodando (ciclo 1 min)")
            
            # Footer
            print("\n" + "=" * 80)
            print("Atualização automática a cada 5 segundos | Pressione Ctrl+C para sair")
            print("=" * 80)
            
            # Aguardar 5 segundos
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n✅ Monitor encerrado pelo usuário")
        mt5.disconnect()
    except Exception as e:
        print(f"\n\n❌ Erro no monitor: {e}")
        mt5.disconnect()

if __name__ == "__main__":
    monitor_bot()
