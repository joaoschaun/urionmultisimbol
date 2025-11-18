"""
Script de diagnóstico detalhado - Mostra exatamente por que não há entradas
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import MetaTrader5 as mt5
from dotenv import load_dotenv
import yaml
from datetime import datetime
from loguru import logger

# Imports do bot
from src.core.mt5_connector import MT5Connector
from src.analysis.technical_analyzer import TechnicalAnalyzer
from src.analysis.news_analyzer import NewsAnalyzer
from src.strategies.strategy_manager import StrategyManager
from src.core.risk_manager import RiskManager

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def main():
    print_header("🔍 DIAGNÓSTICO DETALHADO - POR QUE NÃO HÁ ENTRADAS?")
    
    # Carregar .env PRIMEIRO
    load_dotenv('.env')
    
    # Carregar config
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 1. VERIFICAR MT5
    print_header("1️⃣ CONEXÃO MT5")
    connector = MT5Connector(config)
    if not connector.connect():
        print("❌ MT5 não conectado!")
        return
    
    account_info = mt5.account_info()
    print(f"✅ Conectado à conta: {account_info.login}")
    print(f"   Balance: ${account_info.balance:.2f}")
    print(f"   Equity: ${account_info.equity:.2f}")
    print(f"   Margin Free: ${account_info.margin_free:.2f}")
    
    # Verificar posições atuais
    positions = mt5.positions_get(symbol="XAUUSD")
    print(f"\n📊 Posições abertas: {len(positions) if positions else 0}")
    
    # 2. VERIFICAR RISK MANAGER
    print_header("2️⃣ RISK MANAGER")
    risk_manager = RiskManager(config, connector)
    
    print(f"Max Risk por Trade: {config['risk_management']['max_risk_per_trade']*100}%")
    print(f"Max Posições Simultâneas: {config['risk_management']['max_positions']}")
    print(f"Max Daily Loss: {config['risk_management']['max_daily_loss']*100}%")
    
    can_trade, reason = risk_manager.can_trade()
    if can_trade:
        print("✅ Risk Manager: APROVADO")
    else:
        print(f"❌ Risk Manager BLOQUEANDO: {reason}")
    
    # 3. ANÁLISE TÉCNICA ATUAL
    print_header("3️⃣ ANÁLISE TÉCNICA (M5)")
    tech_analyzer = TechnicalAnalyzer('XAUUSD', config)
    analysis = tech_analyzer.analyze_multi_timeframe()
    
    if 'M5' in analysis:
        m5 = analysis['M5']
        price = m5.get('current_price', 0)
        rsi = m5.get('rsi', 0)
        macd = m5.get('macd', {})
        adx = m5.get('adx', {})
        ema = m5.get('ema', {})
        
        print(f"Preço Atual: ${price:.2f}")
        print(f"RSI: {rsi:.1f}")
        print(f"ADX: {adx.get('adx', 0):.1f}")
        print(f"MACD: {macd.get('macd', 0):.4f}")
        print(f"MACD Signal: {macd.get('signal', 0):.4f}")
        print(f"EMA 9: ${ema.get('ema_9', 0):.2f}")
        print(f"EMA 21: ${ema.get('ema_21', 0):.2f}")
        print(f"EMA 50: ${ema.get('ema_50', 0):.2f}")
    
    # 4. TESTAR CADA ESTRATÉGIA
    print_header("4️⃣ TESTE DE ESTRATÉGIAS")
    
    strategy_manager = StrategyManager(config)
    news_analyzer = NewsAnalyzer(config)
    news_data = news_analyzer.get_sentiment_summary()
    
    strategies_config = {
        'trend_following': {'min_confidence': 0.65, 'ciclo': 900},
        'mean_reversion': {'min_confidence': 0.70, 'ciclo': 600},
        'breakout': {'min_confidence': 0.75, 'ciclo': 1800},
        'news_trading': {'min_confidence': 0.80, 'ciclo': 300},
        'scalping': {'min_confidence': 0.60, 'ciclo': 60}
    }
    
    for name, strategy in strategy_manager.strategies.items():
        if not strategy.is_enabled():
            continue
            
        print(f"\n📈 Estratégia: {name.upper()}")
        print(f"   Min Confiança: {strategies_config[name]['min_confidence']*100:.0f}%")
        print(f"   Ciclo: {strategies_config[name]['ciclo']}s")
        
        # Executar análise
        signal = strategy.analyze(analysis, news_data)
        
        if signal:
            action = signal.get('action', 'HOLD')
            confidence = signal.get('confidence', 0)
            reason = signal.get('reason', 'unknown')
            
            print(f"   Ação: {action}")
            print(f"   Confiança: {confidence*100:.1f}%")
            print(f"   Razão: {reason}")
            
            if action in ['BUY', 'SELL']:
                if confidence >= strategies_config[name]['min_confidence']:
                    print(f"   ✅ SINAL VÁLIDO! {action} com {confidence*100:.1f}% de confiança")
                else:
                    print(f"   ❌ BLOQUEADO: Confiança {confidence*100:.1f}% < {strategies_config[name]['min_confidence']*100:.0f}%")
            else:
                print(f"   ⏸️  Sem sinal de entrada")
        else:
            print("   ❌ Sem análise disponível")
    
    # 5. RESUMO
    print_header("📋 RESUMO DO DIAGNÓSTICO")
    
    print("\n🔴 POSSÍVEIS RAZÕES PARA NÃO HAVER ENTRADAS:")
    print("\n1. Mercado sem condições claras:")
    print("   - RSI neutro (não em extremos)")
    print("   - Sem tendência forte (ADX baixo)")
    print("   - EMAs muito próximas (consolidação)")
    
    print("\n2. Thresholds de confiança altos:")
    print("   - TrendFollowing: precisa 65% (5/8 condições)")
    print("   - MeanReversion: precisa 70% (4/6 condições)")
    print("   - Breakout: precisa 75% (6/8 condições)")
    print("   - NewsTrading: precisa 80% (mais difícil)")
    print("   - Scalping: precisa 60% (3/5 condições)")
    
    print("\n3. Risk Manager pode estar bloqueando:")
    print("   - Posições abertas atingiram o limite")
    print("   - Drawdown diário excedido")
    print("   - Margem insuficiente")
    
    print("\n💡 SUGESTÕES:")
    print("   1. Reduzir thresholds de confiança (ex: TrendFollowing para 55%)")
    print("   2. Aguardar movimento mais claro no mercado")
    print("   3. Verificar se há posições abertas bloqueando novas")
    
    connector.disconnect()

if __name__ == "__main__":
    main()
