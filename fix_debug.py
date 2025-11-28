# Script temporário para adicionar debug log
with open(r'c:\Users\Administrator\Desktop\urion\src\order_manager.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Adicionar debug log na linha 1509 (após strategy_name =)
debug_code = """        
        # 🔥 DEBUG: Log magic number e estratégia identificada
        if strategy_name == 'unknown':
            logger.error(
                f"❌ #{ticket} magic_number {magic_number} NÃO MAPEADO! "
                f"Estratégias conhecidas: {list(self.strategy_map.keys())}"
            )
        
"""

lines.insert(1509, debug_code)

with open(r'c:\Users\Administrator\Desktop\urion\src\order_manager.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Debug log adicionado na linha 1509")
