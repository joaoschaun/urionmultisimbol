import MetaTrader5 as mt5
import time
from datetime import datetime

def apply_sl_tp():
    print("=== Aplicando SL/TP em posições abertas ===")
    
    if not mt5.initialize():
        print(f"Erro ao inicializar MT5: {mt5.last_error()}")
        return

    positions = mt5.positions_get()
    if positions is None:
        print("Nenhuma posição encontrada ou erro ao obter posições.")
        mt5.shutdown()
        return

    print(f"Encontradas {len(positions)} posições.")

    # Configurações de SL/TP (em pontos)
    # Ajuste conforme necessário. Ex: 500 pontos = 50 pips (se 5 digitos)
    # Para XAUUSD, 1000 pontos = $10.00
    SL_POINTS = 2000  # $20.00 no Gold
    TP_POINTS = 4000  # $40.00 no Gold

    for pos in positions:
        symbol = pos.symbol
        ticket = pos.ticket
        pos_type = pos.type
        open_price = pos.price_open
        current_sl = pos.sl
        current_tp = pos.tp
        
        print(f"Posição {ticket} ({symbol}): Tipo={pos_type}, Open={open_price}, SL={current_sl}, TP={current_tp}")

        # Verificar se precisa de SL/TP
        if current_sl > 0 and current_tp > 0:
            print(f"  -> Já possui SL/TP. Ignorando.")
            continue

        # Calcular novos SL/TP
        point = mt5.symbol_info(symbol).point
        
        if pos_type == mt5.POSITION_TYPE_BUY:
            sl = open_price - (SL_POINTS * point)
            tp = open_price + (TP_POINTS * point)
        elif pos_type == mt5.POSITION_TYPE_SELL:
            sl = open_price + (SL_POINTS * point)
            tp = open_price - (TP_POINTS * point)
        else:
            print("  -> Tipo desconhecido.")
            continue

        # Normalizar preços
        sl = round(sl, mt5.symbol_info(symbol).digits)
        tp = round(tp, mt5.symbol_info(symbol).digits)

        print(f"  -> Aplicando SL={sl}, TP={tp}...")

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": sl,
            "tp": tp
        }

        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"  -> Sucesso! SL/TP aplicados.")
        else:
            print(f"  -> Falha: {result.comment} ({result.retcode})")

    mt5.shutdown()
    print("=== Concluído ===")

if __name__ == "__main__":
    apply_sl_tp()
