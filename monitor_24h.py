"""
Monitor 24 Horas - URION Trading Bot
Monitora continuamente o bot e exibe estatísticas em tempo real
"""

import time
import os
from datetime import datetime, timedelta
from loguru import logger
import MetaTrader5 as mt5
from typing import Dict, List


class Monitor24h:
    """Monitor contínuo 24/7 do bot"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.check_interval = 30  # segundos
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'initial_balance': 0.0,
            'peak_balance': 0.0,
            'lowest_balance': 0.0
        }
        
    def clear_screen(self):
        """Limpa tela do terminal"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def connect_mt5(self) -> bool:
        """Conecta ao MT5"""
        try:
            if not mt5.initialize():
                logger.error("Falha ao inicializar MT5")
                return False
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar MT5: {e}")
            return False
    
    def get_account_info(self) -> Dict:
        """Obtém informações da conta"""
        try:
            account_info = mt5.account_info()
            if account_info is None:
                return {}
            
            return {
                'balance': account_info.balance,
                'equity': account_info.equity,
                'profit': account_info.profit,
                'margin': account_info.margin,
                'margin_free': account_info.margin_free,
                'margin_level': account_info.margin_level if account_info.margin > 0 else 0
            }
        except Exception as e:
            logger.error(f"Erro ao obter info da conta: {e}")
            return {}
    
    def get_positions(self) -> List[Dict]:
        """Obtém posições abertas"""
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            
            result = []
            for pos in positions:
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == 0 else 'SELL',
                    'volume': pos.volume,
                    'price_open': pos.price_open,
                    'price_current': pos.price_current,
                    'sl': pos.sl,
                    'tp': pos.tp,
                    'profit': pos.profit,
                    'magic': pos.magic,
                    'comment': pos.comment
                })
            return result
        except Exception as e:
            logger.error(f"Erro ao obter posições: {e}")
            return []
    
    def get_history_today(self) -> List[Dict]:
        """Obtém histórico de hoje"""
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            deals = mt5.history_deals_get(today, datetime.now())
            
            if deals is None:
                return []
            
            result = []
            for deal in deals:
                if deal.entry == 1:  # OUT (fechamento)
                    result.append({
                        'ticket': deal.ticket,
                        'time': datetime.fromtimestamp(deal.time),
                        'symbol': deal.symbol,
                        'type': 'BUY' if deal.type == 0 else 'SELL',
                        'volume': deal.volume,
                        'profit': deal.profit,
                        'magic': deal.magic
                    })
            return result
        except Exception as e:
            logger.error(f"Erro ao obter histórico: {e}")
            return []
    
    def update_stats(self, account_info: Dict, history: List[Dict]):
        """Atualiza estatísticas"""
        if self.stats['initial_balance'] == 0:
            self.stats['initial_balance'] = account_info.get('balance', 0)
            self.stats['peak_balance'] = self.stats['initial_balance']
            self.stats['lowest_balance'] = self.stats['initial_balance']
        
        current_balance = account_info.get('balance', 0)
        
        # Atualizar picos
        if current_balance > self.stats['peak_balance']:
            self.stats['peak_balance'] = current_balance
        if current_balance < self.stats['lowest_balance']:
            self.stats['lowest_balance'] = current_balance
        
        # Contar trades
        self.stats['total_trades'] = len(history)
        self.stats['winning_trades'] = len([h for h in history if h['profit'] > 0])
        self.stats['losing_trades'] = len([h for h in history if h['profit'] < 0])
        self.stats['total_profit'] = sum([h['profit'] for h in history])
    
    def get_strategy_name(self, magic: int) -> str:
        """Identifica estratégia pelo magic number"""
        # Base: 100000 + hash do nome
        strategies = {
            100541: 'TrendFollowing',
            100512: 'MeanReversion',
            100517: 'Breakout',
            100540: 'NewsTrading',
            100531: 'Scalping'
        }
        return strategies.get(magic, f'Unknown({magic})')
    
    def display_dashboard(self, account_info: Dict, positions: List[Dict], 
                         history: List[Dict]):
        """Exibe dashboard completo"""
        self.clear_screen()
        
        runtime = datetime.now() - self.start_time
        hours = int(runtime.total_seconds() // 3600)
        minutes = int((runtime.total_seconds() % 3600) // 60)
        
        balance = account_info.get('balance', 0)
        equity = account_info.get('equity', 0)
        profit = account_info.get('profit', 0)
        margin_level = account_info.get('margin_level', 0)
        
        # Calcular performance
        initial = self.stats['initial_balance']
        pnl = balance - initial if initial > 0 else 0
        pnl_pct = (pnl / initial * 100) if initial > 0 else 0
        
        win_rate = (self.stats['winning_trades'] / self.stats['total_trades'] * 100) if self.stats['total_trades'] > 0 else 0
        
        print("=" * 80)
        print("  URION TRADING BOT - MONITOR 24 HORAS".center(80))
        print("=" * 80)
        print()
        
        # Tempo de execução
        print(f"⏱️  TEMPO DE EXECUÇÃO: {hours}h {minutes}min")
        print(f"📅 Início: {self.start_time.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"🕐 Agora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print()
        
        # Conta
        print("💰 CONTA")
        print("-" * 80)
        print(f"Balance:      ${balance:,.2f}  |  Equity: ${equity:,.2f}")
        print(f"P&L Aberto:   ${profit:,.2f}  |  Margin Level: {margin_level:.0f}%")
        print()
        
        # Performance
        print("📊 PERFORMANCE")
        print("-" * 80)
        color_pnl = "🟢" if pnl >= 0 else "🔴"
        print(f"P&L Total:    {color_pnl} ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        print(f"Pico:         ${self.stats['peak_balance']:,.2f}")
        print(f"Mínimo:       ${self.stats['lowest_balance']:,.2f}")
        print()
        
        # Estatísticas de Trades
        print("📈 TRADES HOJE")
        print("-" * 80)
        print(f"Total:        {self.stats['total_trades']}")
        print(f"Ganhos:       🟢 {self.stats['winning_trades']} ({win_rate:.1f}%)")
        print(f"Perdas:       🔴 {self.stats['losing_trades']}")
        print(f"Lucro Total:  ${self.stats['total_profit']:,.2f}")
        print()
        
        # Posições abertas
        print("📍 POSIÇÕES ABERTAS")
        print("-" * 80)
        if positions:
            for pos in positions:
                strategy = self.get_strategy_name(pos['magic'])
                tipo = "🟢 BUY " if pos['type'] == 'BUY' else "🔴 SELL"
                profit_color = "🟢" if pos['profit'] >= 0 else "🔴"
                
                print(f"{tipo} | {pos['symbol']} | {pos['volume']:.2f} lot | "
                      f"{profit_color} ${pos['profit']:,.2f} | [{strategy}]")
        else:
            print("Nenhuma posição aberta")
        print()
        
        # Últimos trades
        print("📜 ÚLTIMOS 5 TRADES")
        print("-" * 80)
        if history:
            for trade in history[-5:]:
                strategy = self.get_strategy_name(trade['magic'])
                profit_color = "🟢" if trade['profit'] >= 0 else "🔴"
                time_str = trade['time'].strftime('%H:%M:%S')
                
                print(f"{time_str} | {trade['symbol']} | {trade['type']} | "
                      f"{profit_color} ${trade['profit']:,.2f} | [{strategy}]")
        else:
            print("Nenhum trade hoje")
        print()
        
        print("=" * 80)
        print(f"Próxima atualização em {self.check_interval}s... (Ctrl+C para parar)")
        print("=" * 80)
    
    def run(self):
        """Loop principal de monitoramento"""
        logger.info("Iniciando Monitor 24h...")
        
        if not self.connect_mt5():
            logger.error("Não foi possível conectar ao MT5")
            return
        
        logger.info(f"Monitor iniciado! Atualizando a cada {self.check_interval}s")
        
        try:
            while True:
                # Coletar dados
                account_info = self.get_account_info()
                positions = self.get_positions()
                history = self.get_history_today()
                
                # Atualizar estatísticas
                self.update_stats(account_info, history)
                
                # Exibir dashboard
                self.display_dashboard(account_info, positions, history)
                
                # Aguardar próxima atualização
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("\nMonitor encerrado pelo usuário")
            print("\n👋 Monitor finalizado!")
        except Exception as e:
            logger.error(f"Erro no monitor: {e}")
        finally:
            mt5.shutdown()


if __name__ == "__main__":
    monitor = Monitor24h()
    monitor.run()
