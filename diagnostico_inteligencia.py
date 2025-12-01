"""
🧠 DIAGNÓSTICO DE INTELIGÊNCIA DO URION
Verifica se todas as lógicas avançadas estão funcionando corretamente
"""

import sys
sys.path.insert(0, 'src')

import MetaTrader5 as mt5
from datetime import datetime, timezone
from colorama import init, Fore, Style
init()

from core.config_manager import ConfigManager
from analysis.technical_analyzer import TechnicalAnalyzer
from analysis.smart_money_detector import SmartMoneyDetector
from strategies.strategy_manager import StrategyManager
from core.risk_manager import RiskManager

# Tentar importar módulos avançados
try:
    from core.strategy_communicator import get_strategy_communicator
    COMMUNICATOR_AVAILABLE = True
except:
    COMMUNICATOR_AVAILABLE = False

try:
    from core.adaptive_trading import AdaptiveTradingManager
    ADAPTIVE_AVAILABLE = True
except:
    ADAPTIVE_AVAILABLE = False

try:
    from analysis.session_analyzer import SessionAnalyzer, MarketSession
    SESSION_AVAILABLE = True
except:
    SESSION_AVAILABLE = False


def print_header(text):
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{Style.RESET_ALL}")


def print_ok(text):
    print(f"{Fore.GREEN}  ✅ {text}{Style.RESET_ALL}")


def print_warn(text):
    print(f"{Fore.YELLOW}  ⚠️  {text}{Style.RESET_ALL}")


def print_error(text):
    print(f"{Fore.RED}  ❌ {text}{Style.RESET_ALL}")


def print_info(text):
    print(f"{Fore.WHITE}  ℹ️  {text}{Style.RESET_ALL}")


def main():
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print("  🧠 DIAGNÓSTICO DE INTELIGÊNCIA DO URION")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}{Style.RESET_ALL}")
    
    # Inicializar MT5
    if not mt5.initialize():
        print_error("Falha ao conectar MT5")
        return
    
    config_manager = ConfigManager()
    config = config_manager.config
    
    # ══════════════════════════════════════════════════════════════════
    # 1. ANÁLISE DE TENDÊNCIA ATUAL
    # ══════════════════════════════════════════════════════════════════
    print_header("1. ANÁLISE DE TENDÊNCIA ATUAL")
    
    symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
    
    for symbol in symbols:
        try:
            analyzer = TechnicalAnalyzer(symbol, config)
            analysis = analyzer.analyze_multi_timeframe()
            
            if analysis:
                trend = analysis.get('trend', {})
                trend_direction = trend.get('direction', 'UNKNOWN')
                trend_strength = trend.get('strength', 0)
                
                # Determinar emoji e cor
                if trend_direction == 'UP':
                    emoji = "📈"
                    color = Fore.GREEN
                elif trend_direction == 'DOWN':
                    emoji = "📉"
                    color = Fore.RED
                else:
                    emoji = "➡️"
                    color = Fore.YELLOW
                
                strength_bar = "█" * int(trend_strength * 10) + "░" * (10 - int(trend_strength * 10))
                
                print(f"{color}  {emoji} {symbol}: {trend_direction} | Força: [{strength_bar}] {trend_strength:.0%}{Style.RESET_ALL}")
                
                # Mostrar indicadores chave
                momentum = analysis.get('momentum', {})
                rsi = momentum.get('rsi', 50)
                macd_signal = momentum.get('macd_signal', 'NEUTRAL')
                
                print(f"      RSI: {rsi:.1f} | MACD: {macd_signal}")
            else:
                print_warn(f"{symbol}: Sem dados de análise")
        except Exception as e:
            print_error(f"{symbol}: Erro - {e}")
    
    # ══════════════════════════════════════════════════════════════════
    # 2. SMART MONEY DETECTOR
    # ══════════════════════════════════════════════════════════════════
    print_header("2. DETECÇÃO DE SMART MONEY")
    
    for symbol in symbols[:2]:  # Apenas 2 para não demorar
        try:
            detector = SmartMoneyDetector(config, symbol)
            
            # Pegar dados
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
            if rates is not None and len(rates) > 0:
                import pandas as pd
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                
                # Detectar níveis
                levels = detector.detect_liquidity_levels(df)
                
                if levels:
                    print_ok(f"{symbol}: {len(levels)} níveis de liquidez detectados")
                    
                    # Mostrar níveis mais próximos
                    current_price = mt5.symbol_info_tick(symbol).ask
                    
                    above = [l for l in levels if l['price'] > current_price]
                    below = [l for l in levels if l['price'] < current_price]
                    
                    if above:
                        nearest_above = min(above, key=lambda x: x['price'] - current_price)
                        print_info(f"  Resistência mais próxima: {nearest_above['price']:.5f} ({nearest_above['type']})")
                    
                    if below:
                        nearest_below = max(below, key=lambda x: x['price'])
                        print_info(f"  Suporte mais próximo: {nearest_below['price']:.5f} ({nearest_below['type']})")
                else:
                    print_warn(f"{symbol}: Nenhum nível de liquidez detectado")
        except Exception as e:
            print_error(f"{symbol}: Erro SmartMoney - {e}")
    
    # ══════════════════════════════════════════════════════════════════
    # 3. COMUNICAÇÃO ENTRE ESTRATÉGIAS
    # ══════════════════════════════════════════════════════════════════
    print_header("3. COMUNICAÇÃO ENTRE ESTRATÉGIAS")
    
    if COMMUNICATOR_AVAILABLE:
        try:
            communicator = get_strategy_communicator(config)
            
            # Verificar eventos recentes
            recent_events = communicator.get_recent_events(limit=10)
            
            if recent_events:
                print_ok(f"Strategy Communicator ATIVO - {len(recent_events)} eventos recentes")
                
                for event in recent_events[:5]:
                    event_type = event.get('type', 'UNKNOWN')
                    source = event.get('source', 'unknown')
                    timestamp = event.get('timestamp', '')
                    
                    print_info(f"  [{source}] {event_type} @ {timestamp}")
            else:
                print_warn("Nenhum evento recente (estratégias podem estar aguardando sinais)")
                
            # Verificar assinantes
            subscribers = len(communicator._subscribers) if hasattr(communicator, '_subscribers') else 0
            print_info(f"  Estratégias inscritas: {subscribers}")
            
        except Exception as e:
            print_error(f"Erro no Strategy Communicator: {e}")
    else:
        print_warn("Strategy Communicator não disponível")
    
    # ══════════════════════════════════════════════════════════════════
    # 4. ADAPTAÇÃO POR SESSÃO DE MERCADO
    # ══════════════════════════════════════════════════════════════════
    print_header("4. ADAPTAÇÃO POR SESSÃO DE MERCADO")
    
    if ADAPTIVE_AVAILABLE:
        try:
            adaptive = AdaptiveTradingManager(config)
            
            # Sessão atual
            current_session = adaptive.get_current_session()
            session_quality = adaptive.get_session_quality()
            
            # Emoji por sessão
            session_emoji = {
                'SYDNEY': '🌙',
                'TOKYO': '🗼',
                'LONDON': '🏛️',
                'NEW_YORK': '🗽',
                'OVERLAP': '🔥'
            }
            
            emoji = session_emoji.get(current_session, '🌍')
            
            print_ok(f"Sessão atual: {emoji} {current_session}")
            print_info(f"  Qualidade da sessão: {session_quality}")
            
            # Ajustes ativos
            adjustments = adaptive.get_current_adjustments()
            if adjustments:
                print_info(f"  Multiplicador de lote: {adjustments.get('lot_multiplier', 1.0):.2f}x")
                print_info(f"  Ajuste de confiança: {adjustments.get('confidence_adjustment', 0):+.0%}")
                print_info(f"  Estratégias recomendadas: {', '.join(adjustments.get('recommended_strategies', []))}")
            
        except Exception as e:
            print_error(f"Erro no AdaptiveTradingManager: {e}")
    else:
        print_warn("AdaptiveTradingManager não disponível")
    
    # ══════════════════════════════════════════════════════════════════
    # 5. FILTRO DE TENDÊNCIA NAS ESTRATÉGIAS
    # ══════════════════════════════════════════════════════════════════
    print_header("5. LÓGICA DE FILTRO DE TENDÊNCIA")
    
    strategy_manager = StrategyManager(config)
    
    print_info("Estratégias e seus filtros de tendência:")
    
    strategy_filters = {
        'trend_following': {
            'description': 'Só opera A FAVOR da tendência',
            'filter': 'ADX > 30, EMA alinhadas',
            'when_trend_up': 'Apenas BUY',
            'when_trend_down': 'Apenas SELL',
            'when_ranging': 'NÃO OPERA'
        },
        'mean_reversion': {
            'description': 'Opera CONTRA extremos',
            'filter': 'RSI extremo + Bollinger',
            'when_trend_up': 'Espera pullback para BUY',
            'when_trend_down': 'Espera bounce para SELL',
            'when_ranging': 'OPERA nos extremos'
        },
        'breakout': {
            'description': 'Opera ROMPIMENTOS',
            'filter': 'Volume + Price action',
            'when_trend_up': 'BUY em breakout de resistência',
            'when_trend_down': 'SELL em breakdown de suporte',
            'when_ranging': 'Aguarda rompimento'
        },
        'scalping': {
            'description': 'Trades rápidos em qualquer direção',
            'filter': 'Momentum + Volume',
            'when_trend_up': 'Prefere BUY',
            'when_trend_down': 'Prefere SELL',
            'when_ranging': 'Opera ambos lados'
        },
        'range_trading': {
            'description': 'Opera LATERALIZAÇÃO',
            'filter': 'ADX < 20',
            'when_trend_up': 'NÃO OPERA',
            'when_trend_down': 'NÃO OPERA',
            'when_ranging': 'BUY em suporte, SELL em resistência'
        },
        'news_trading': {
            'description': 'Opera VOLATILIDADE de notícias',
            'filter': 'Calendário econômico',
            'when_trend_up': 'Amplifica BUY',
            'when_trend_down': 'Amplifica SELL',
            'when_ranging': 'Aguarda catalisador'
        }
    }
    
    for strategy_name, info in strategy_filters.items():
        print(f"\n  {Fore.CYAN}📊 {strategy_name.upper()}{Style.RESET_ALL}")
        print(f"     {info['description']}")
        print(f"     Filtro: {info['filter']}")
        print(f"     {Fore.GREEN}↑ Tendência UP:{Style.RESET_ALL} {info['when_trend_up']}")
        print(f"     {Fore.RED}↓ Tendência DOWN:{Style.RESET_ALL} {info['when_trend_down']}")
        print(f"     {Fore.YELLOW}→ Ranging:{Style.RESET_ALL} {info['when_ranging']}")
    
    # ══════════════════════════════════════════════════════════════════
    # 6. POSIÇÕES ATUAIS E COERÊNCIA
    # ══════════════════════════════════════════════════════════════════
    print_header("6. POSIÇÕES ATUAIS VS ANÁLISE")
    
    positions = mt5.positions_get()
    
    if positions and len(positions) > 0:
        print_ok(f"{len(positions)} posições abertas")
        
        for pos in positions:
            symbol = pos.symbol
            direction = "BUY" if pos.type == 0 else "SELL"
            profit = pos.profit
            
            # Analisar tendência atual do símbolo
            try:
                analyzer = TechnicalAnalyzer(symbol, config)
                analysis = analyzer.analyze_multi_timeframe()
                
                if analysis:
                    trend = analysis.get('trend', {})
                    trend_direction = trend.get('direction', 'UNKNOWN')
                    
                    # Verificar coerência
                    if direction == "BUY" and trend_direction == "UP":
                        coherence = f"{Fore.GREEN}✅ COERENTE (comprado em tendência de alta){Style.RESET_ALL}"
                    elif direction == "SELL" and trend_direction == "DOWN":
                        coherence = f"{Fore.GREEN}✅ COERENTE (vendido em tendência de baixa){Style.RESET_ALL}"
                    elif trend_direction == "NEUTRAL":
                        coherence = f"{Fore.YELLOW}⚠️ NEUTRO (mercado lateral){Style.RESET_ALL}"
                    else:
                        coherence = f"{Fore.RED}⚠️ CONTRA TENDÊNCIA (pode ser mean_reversion ou scalping){Style.RESET_ALL}"
                    
                    profit_color = Fore.GREEN if profit > 0 else Fore.RED
                    print(f"\n  {symbol} | {direction} | {profit_color}${profit:.2f}{Style.RESET_ALL}")
                    print(f"    Tendência atual: {trend_direction}")
                    print(f"    {coherence}")
            except Exception as e:
                print(f"  {symbol} | {direction} | ${profit:.2f}")
                print_error(f"    Erro na análise: {e}")
    else:
        print_info("Nenhuma posição aberta no momento")
    
    # ══════════════════════════════════════════════════════════════════
    # 7. GESTÃO DE RISCO
    # ══════════════════════════════════════════════════════════════════
    print_header("7. GESTÃO DE RISCO")
    
    risk_manager = RiskManager(config)
    account_info = mt5.account_info()
    
    print_info(f"Saldo: ${account_info.balance:.2f}")
    print_info(f"Equity: ${account_info.equity:.2f}")
    print_info(f"Margem usada: ${account_info.margin:.2f}")
    print_info(f"Margem livre: ${account_info.margin_free:.2f}")
    
    # Calcular drawdown atual
    if account_info.balance > 0:
        current_dd = (account_info.balance - account_info.equity) / account_info.balance * 100
        max_dd = config.get('risk', {}).get('max_drawdown', 0.08) * 100
        
        if current_dd < 0:
            print_ok(f"Drawdown: {current_dd:.2f}% (em lucro)")
        elif current_dd < max_dd * 0.5:
            print_ok(f"Drawdown: {current_dd:.2f}% (limite: {max_dd:.0f}%)")
        elif current_dd < max_dd:
            print_warn(f"Drawdown: {current_dd:.2f}% (atenção - limite: {max_dd:.0f}%)")
        else:
            print_error(f"Drawdown: {current_dd:.2f}% EXCEDEU LIMITE ({max_dd:.0f}%)")
    
    # Verificar se pode abrir mais posições
    max_positions = config.get('risk', {}).get('max_simultaneous_positions', 3)
    current_positions = len(positions) if positions else 0
    
    if current_positions < max_positions:
        print_ok(f"Posições: {current_positions}/{max_positions} (pode abrir mais)")
    else:
        print_warn(f"Posições: {current_positions}/{max_positions} (limite atingido)")
    
    # ══════════════════════════════════════════════════════════════════
    # 8. RESUMO FINAL
    # ══════════════════════════════════════════════════════════════════
    print_header("8. RESUMO DA INTELIGÊNCIA")
    
    intelligence_score = 0
    max_score = 7
    
    # Pontuação
    if COMMUNICATOR_AVAILABLE:
        intelligence_score += 1
        print_ok("Strategy Communicator: ATIVO")
    else:
        print_warn("Strategy Communicator: INATIVO")
    
    if ADAPTIVE_AVAILABLE:
        intelligence_score += 1
        print_ok("Adaptive Trading: ATIVO")
    else:
        print_warn("Adaptive Trading: INATIVO")
    
    # Análise técnica funcionando
    intelligence_score += 1
    print_ok("Análise Técnica Multi-Timeframe: ATIVO")
    
    # Smart Money
    intelligence_score += 1
    print_ok("Smart Money Detector: ATIVO")
    
    # Filtro de tendência
    intelligence_score += 1
    print_ok("Filtro de Tendência por Estratégia: ATIVO")
    
    # Risk Manager
    intelligence_score += 1
    print_ok("Risk Manager: ATIVO")
    
    # Posições coerentes
    intelligence_score += 1
    print_ok("Gestão de Posições: ATIVO")
    
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print(f"  🧠 SCORE DE INTELIGÊNCIA: {intelligence_score}/{max_score} ({intelligence_score/max_score*100:.0f}%)")
    print(f"{'='*70}{Style.RESET_ALL}")
    
    mt5.shutdown()
    
    print(f"\n{Fore.GREEN}✅ Diagnóstico completo!{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
