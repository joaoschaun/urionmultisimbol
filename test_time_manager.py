"""
Teste do Adaptive Time Manager
"""
import sys
sys.path.insert(0, 'src')

from datetime import datetime, timezone, timedelta
from core.adaptive_time_manager import AdaptiveTimeManager, TimeAction, TimeStatus

def test_time_manager():
    print("=" * 60)
    print("🧪 TESTE ADAPTIVE TIME MANAGER")
    print("=" * 60)
    
    # Criar manager
    config = {
        'time_manager': {
            'enabled': True,
            'expected_times': {
                'scalping': 5,
                'trend_following': 120
            }
        }
    }
    
    tm = AdaptiveTimeManager(config)
    print(f"✅ TimeManager criado | Enabled: {tm.enabled}")
    print(f"   Tempos esperados: {tm.expected_times}")
    
    # Simular posição
    ticket = 12345678
    symbol = "EURUSD"
    entry_price = 1.0500
    sl = 1.0490  # 10 pips de risco
    
    print("\n" + "-" * 60)
    print("📊 CENÁRIO 1: Trade SCALPING - Dentro do tempo (3 min)")
    print("-" * 60)
    
    # Trade aberto há 3 minutos
    open_time = datetime.now(timezone.utc) - timedelta(minutes=3)
    current_price = 1.0510  # +10 pips de lucro
    
    analysis = tm.analyze_position(
        ticket=ticket,
        symbol=symbol,
        strategy="scalping",
        open_time=open_time,
        entry_price=entry_price,
        current_price=current_price,
        sl=sl,
        position_type='BUY',
        current_profit=10.0,
        volume=0.1
    )
    
    print(f"   Tempo aberto: {analysis.time_open_minutes:.1f} min")
    print(f"   Tempo esperado: {analysis.expected_time_minutes} min")
    print(f"   Ratio: {analysis.time_ratio:.2f}x")
    print(f"   Status: {analysis.status.value}")
    print(f"   RR: {analysis.current_rr:.2f}")
    print(f"   Ação: {analysis.action.value}")
    print(f"   Razão: {analysis.reason}")
    
    assert analysis.status == TimeStatus.ON_TIME, "Deveria estar ON_TIME"
    assert analysis.action == TimeAction.HOLD, "Deveria ser HOLD"
    print("   ✅ PASSOU!")
    
    print("\n" + "-" * 60)
    print("📊 CENÁRIO 2: Trade SCALPING - Atrasado (12 min = 2.4x)")
    print("-" * 60)
    
    # Trade aberto há 12 minutos (2.4x do esperado de 5 min)
    open_time = datetime.now(timezone.utc) - timedelta(minutes=12)
    current_price = 1.0515  # +15 pips = 1.5R
    
    analysis = tm.analyze_position(
        ticket=ticket,
        symbol=symbol,
        strategy="scalping",
        open_time=open_time,
        entry_price=entry_price,
        current_price=current_price,
        sl=sl,
        position_type='BUY',
        current_profit=15.0,
        volume=0.1
    )
    
    print(f"   Tempo aberto: {analysis.time_open_minutes:.1f} min")
    print(f"   Tempo esperado: {analysis.expected_time_minutes} min")
    print(f"   Ratio: {analysis.time_ratio:.2f}x")
    print(f"   Status: {analysis.status.value}")
    print(f"   RR: {analysis.current_rr:.2f}")
    print(f"   Ação: {analysis.action.value}")
    print(f"   Razão: {analysis.reason}")
    if analysis.new_sl:
        print(f"   Novo SL: {analysis.new_sl:.5f}")
    
    assert analysis.status == TimeStatus.LATE, f"Deveria estar LATE, mas está {analysis.status.value}"
    assert analysis.action == TimeAction.TIGHTEN_SL, "Deveria apertar SL"
    print("   ✅ PASSOU!")
    
    print("\n" + "-" * 60)
    print("📊 CENÁRIO 3: Trade SCALPING - MUITO atrasado E perdendo (15 min)")
    print("-" * 60)
    
    # Trade aberto há 15 minutos (3x do esperado) e perdendo
    open_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    current_price = 1.0495  # -5 pips = -0.5R
    
    analysis = tm.analyze_position(
        ticket=ticket,
        symbol=symbol,
        strategy="scalping",
        open_time=open_time,
        entry_price=entry_price,
        current_price=current_price,
        sl=sl,
        position_type='BUY',
        current_profit=-5.0,
        volume=0.1
    )
    
    print(f"   Tempo aberto: {analysis.time_open_minutes:.1f} min")
    print(f"   Tempo esperado: {analysis.expected_time_minutes} min")
    print(f"   Ratio: {analysis.time_ratio:.2f}x")
    print(f"   Status: {analysis.status.value}")
    print(f"   RR: {analysis.current_rr:.2f}")
    print(f"   Ação: {analysis.action.value}")
    print(f"   Razão: {analysis.reason}")
    
    assert analysis.status == TimeStatus.VERY_LATE, f"Deveria estar VERY_LATE, mas está {analysis.status.value}"
    assert analysis.action == TimeAction.CLOSE_FULL, "Deveria fechar totalmente"
    print("   ✅ PASSOU!")
    
    print("\n" + "-" * 60)
    print("📊 CENÁRIO 4: Trade TREND_FOLLOWING - Longo prazo OK (90 min)")
    print("-" * 60)
    
    # Trade aberto há 90 minutos (esperado: 120 min = 0.75x)
    open_time = datetime.now(timezone.utc) - timedelta(minutes=90)
    current_price = 1.0530  # +30 pips = 3R
    
    analysis = tm.analyze_position(
        ticket=ticket,
        symbol=symbol,
        strategy="trend_following",
        open_time=open_time,
        entry_price=entry_price,
        current_price=current_price,
        sl=sl,
        position_type='BUY',
        current_profit=30.0,
        volume=0.1
    )
    
    print(f"   Tempo aberto: {analysis.time_open_minutes:.1f} min")
    print(f"   Tempo esperado: {analysis.expected_time_minutes} min")
    print(f"   Ratio: {analysis.time_ratio:.2f}x")
    print(f"   Status: {analysis.status.value}")
    print(f"   RR: {analysis.current_rr:.2f}")
    print(f"   Ação: {analysis.action.value}")
    print(f"   Razão: {analysis.reason}")
    
    assert analysis.status == TimeStatus.ON_TIME, f"Deveria estar ON_TIME, mas está {analysis.status.value}"
    assert analysis.action == TimeAction.HOLD, "Deveria ser HOLD"
    print("   ✅ PASSOU!")
    
    print("\n" + "-" * 60)
    print("📊 CENÁRIO 5: Trade SCALPING - OVERTIME mas lucrando (25 min)")
    print("-" * 60)
    
    # Trade aberto há 25 minutos (5x do esperado) mas lucrando
    open_time = datetime.now(timezone.utc) - timedelta(minutes=25)
    current_price = 1.0520  # +20 pips = 2R
    
    analysis = tm.analyze_position(
        ticket=ticket,
        symbol=symbol,
        strategy="scalping",
        open_time=open_time,
        entry_price=entry_price,
        current_price=current_price,
        sl=sl,
        position_type='BUY',
        current_profit=20.0,
        volume=0.1
    )
    
    print(f"   Tempo aberto: {analysis.time_open_minutes:.1f} min")
    print(f"   Tempo esperado: {analysis.expected_time_minutes} min")
    print(f"   Ratio: {analysis.time_ratio:.2f}x")
    print(f"   Status: {analysis.status.value}")
    print(f"   RR: {analysis.current_rr:.2f}")
    print(f"   Ação: {analysis.action.value}")
    print(f"   Razão: {analysis.reason}")
    if analysis.new_sl:
        print(f"   Novo SL: {analysis.new_sl:.5f}")
    
    assert analysis.status == TimeStatus.OVERTIME, f"Deveria estar OVERTIME, mas está {analysis.status.value}"
    assert analysis.action == TimeAction.TIGHTEN_SL, "Deveria apertar SL (proteger 90%)"
    print("   ✅ PASSOU!")
    
    print("\n" + "=" * 60)
    print("✅ TODOS OS TESTES PASSARAM!")
    print("=" * 60)
    
    # Resumo
    print("\n📋 RESUMO DO SISTEMA:")
    print("-" * 40)
    print("⏱️ Adaptive Time Manager:")
    print("   - Monitora TEMPO vs PERFORMANCE")
    print("   - ON_TIME → HOLD (deixa correr)")
    print("   - LATE + lucrando → TIGHTEN_SL")
    print("   - VERY_LATE + perdendo → CLOSE")
    print("   - OVERTIME + lucrando → Protege 90%")
    print("\n🤝 Trabalha em harmonia com ProfitProtector:")
    print("   - ProfitProtector → Foca em LUCRO")
    print("   - TimeManager → Foca em TEMPO")

if __name__ == "__main__":
    test_time_manager()
