# -*- coding: utf-8 -*-
"""
Script para limpar dados de aprendizagem antigos
"""

import os
import sqlite3
import json
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent

def main():
    print("\n" + "=" * 60)
    print("LIMPEZA DE DADOS DE APRENDIZAGEM ANTIGOS")
    print("=" * 60)
    
    # Arquivos a serem removidos/resetados
    arquivos_remover = [
        "data/learning_data.json",
        "data/learning_data_backup_20251125_111350.json",
        "data/position_states.json",
        "data/strategy_stats.db",
        "src/data/strategy_stats.db",
        "backups/strategy_stats_20251128_000013.db",
        "backups/learning_data_20251128_000013.json",
    ]
    
    print("\n[1] ARQUIVOS IDENTIFICADOS PARA LIMPEZA:")
    print("-" * 50)
    
    total_size = 0
    for arquivo in arquivos_remover:
        path = BASE_DIR / arquivo
        if path.exists():
            size = path.stat().st_size
            total_size += size
            print(f"  ✓ {arquivo} ({size/1024:.1f} KB)")
        else:
            print(f"  ✗ {arquivo} (não existe)")
    
    print(f"\n  Total: {total_size/1024:.1f} KB")
    
    # Verificar banco de dados
    print("\n[2] CONTEÚDO DO BANCO DE DADOS:")
    print("-" * 50)
    
    db_path = BASE_DIR / "data" / "strategy_stats.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  - {table_name}: {count} registros")
        
        conn.close()
    
    # Fazer backup antes de limpar
    print("\n[3] CRIANDO BACKUP...")
    print("-" * 50)
    
    backup_dir = BASE_DIR / "backups" / f"pre_reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    for arquivo in arquivos_remover:
        path = BASE_DIR / arquivo
        if path.exists():
            dest = backup_dir / Path(arquivo).name
            shutil.copy2(path, dest)
            print(f"  ✓ Backup: {dest.name}")
    
    print(f"\n  Backup salvo em: {backup_dir}")
    
    # Limpar arquivos
    print("\n[4] LIMPANDO ARQUIVOS...")
    print("-" * 50)
    
    for arquivo in arquivos_remover:
        path = BASE_DIR / arquivo
        if path.exists():
            try:
                path.unlink()
                print(f"  ✓ Removido: {arquivo}")
            except Exception as e:
                print(f"  ✗ Erro ao remover {arquivo}: {e}")
    
    # Criar novos arquivos vazios
    print("\n[5] CRIANDO ARQUIVOS LIMPOS...")
    print("-" * 50)
    
    # learning_data.json vazio
    learning_data = {
        "version": "2.0",
        "created_at": datetime.now().isoformat(),
        "trades": [],
        "patterns": {},
        "strategies": {},
        "performance": {},
        "last_update": datetime.now().isoformat()
    }
    
    learning_path = BASE_DIR / "data" / "learning_data.json"
    with open(learning_path, 'w') as f:
        json.dump(learning_data, f, indent=2)
    print(f"  ✓ Criado: learning_data.json (limpo)")
    
    # position_states.json vazio
    position_states = {
        "version": "2.0",
        "positions": {},
        "last_update": datetime.now().isoformat()
    }
    
    position_path = BASE_DIR / "data" / "position_states.json"
    with open(position_path, 'w') as f:
        json.dump(position_states, f, indent=2)
    print(f"  ✓ Criado: position_states.json (limpo)")
    
    # Criar novo banco de dados
    db_path = BASE_DIR / "data" / "strategy_stats.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Tabela de trades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket INTEGER,
            symbol TEXT,
            type TEXT,
            volume REAL,
            open_price REAL,
            close_price REAL,
            profit REAL,
            open_time TEXT,
            close_time TEXT,
            strategy TEXT,
            magic INTEGER,
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de estatísticas de estratégias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT UNIQUE,
            total_trades INTEGER DEFAULT 0,
            winning_trades INTEGER DEFAULT 0,
            losing_trades INTEGER DEFAULT 0,
            total_profit REAL DEFAULT 0,
            total_loss REAL DEFAULT 0,
            max_drawdown REAL DEFAULT 0,
            avg_win REAL DEFAULT 0,
            avg_loss REAL DEFAULT 0,
            profit_factor REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            last_update TEXT
        )
    ''')
    
    # Tabela de padrões
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT,
            symbol TEXT,
            timeframe TEXT,
            success_rate REAL,
            occurrences INTEGER,
            last_seen TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de performance diária
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            trades INTEGER DEFAULT 0,
            profit REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"  ✓ Criado: strategy_stats.db (novo)")
    
    # Limpar Redis se disponível
    print("\n[6] LIMPANDO CACHE REDIS...")
    print("-" * 50)
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Listar chaves do Urion
        keys = r.keys("urion:*")
        if keys:
            r.delete(*keys)
            print(f"  ✓ Removidas {len(keys)} chaves do Redis")
        else:
            print("  ✓ Nenhuma chave encontrada no Redis")
    except Exception as e:
        print(f"  ⚠ Redis não disponível: {e}")
    
    print("\n" + "=" * 60)
    print("✅ LIMPEZA CONCLUÍDA COM SUCESSO!")
    print("=" * 60)
    print("\nO sistema está pronto para começar aprendizagem do zero.")
    print("Backup dos dados antigos salvo em:", backup_dir)
    print()

if __name__ == "__main__":
    main()
