"""
Automated Backup System
Sistema de backup automático para dados críticos
"""
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import List
from loguru import logger
import schedule
import threading
import time


class AutoBackup:
    """Sistema de backup automático"""
    
    def __init__(self, enabled: bool = True):
        """
        Inicializa sistema de backup
        
        Args:
            enabled: Se backup está ativo
        """
        self.enabled = enabled
        self.backup_dir = Path("backups")
        self.data_dir = Path("data")
        
        # Criar diretório de backups
        self.backup_dir.mkdir(exist_ok=True)
        
        # Arquivos críticos para backup
        self.critical_files = [
            self.data_dir / "strategy_stats.db",
            self.data_dir / "learning_data.json",
            self.data_dir / "position_states.json",
        ]
        
        # Thread de backup
        self.backup_thread = None
        self.stop_event = threading.Event()
        
        logger.info(f"AutoBackup inicializado (enabled={enabled})")
        
        if self.enabled:
            # Agendar backup diário às 00:00
            schedule.every().day.at("00:00").do(self.run_backup)
            logger.info("📅 Backup agendado: diariamente às 00:00")
    
    def run_backup(self) -> bool:
        """
        Executa backup de todos os arquivos críticos
        
        Returns:
            True se sucesso
        """
        if not self.enabled:
            logger.debug("Backup desabilitado")
            return False
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_count = 0
        
        logger.info(f"🔄 Iniciando backup automático: {timestamp}")
        
        try:
            for file_path in self.critical_files:
                if not file_path.exists():
                    logger.warning(f"⚠️ Arquivo não encontrado: {file_path}")
                    continue
                
                # Criar nome do backup
                backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
                backup_path = self.backup_dir / backup_name
                
                # Copiar arquivo
                shutil.copy2(file_path, backup_path)
                backup_count += 1
                
                # Tamanho do arquivo
                size_kb = backup_path.stat().st_size / 1024
                logger.debug(f"✅ Backup criado: {backup_name} ({size_kb:.1f} KB)")
            
            logger.success(f"✅ Backup concluído: {backup_count} arquivos | {timestamp}")
            
            # Limpar backups antigos (manter últimos 30)
            self._cleanup_old_backups(keep_last=30)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no backup: {e}")
            return False
    
    def _cleanup_old_backups(self, keep_last: int = 30):
        """
        Remove backups antigos, mantendo os últimos N
        
        Args:
            keep_last: Quantos backups manter
        """
        try:
            # Listar todos os backups
            all_backups = sorted(
                self.backup_dir.glob("*"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Remover backups excedentes
            removed_count = 0
            for backup_file in all_backups[keep_last:]:
                backup_file.unlink()
                removed_count += 1
            
            if removed_count > 0:
                logger.debug(f"🗑️ Removidos {removed_count} backups antigos")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao limpar backups: {e}")
    
    def backup_now(self) -> bool:
        """
        Força backup imediato (manualmente)
        
        Returns:
            True se sucesso
        """
        logger.info("🔄 Backup manual solicitado")
        return self.run_backup()
    
    def start_scheduler(self):
        """Inicia thread de agendamento de backups"""
        if not self.enabled:
            logger.debug("Backup scheduler desabilitado")
            return
        
        def scheduler_loop():
            logger.info("📅 Backup scheduler iniciado")
            while not self.stop_event.is_set():
                schedule.run_pending()
                time.sleep(60)  # Verificar a cada 1 minuto
            logger.info("📅 Backup scheduler parado")
        
        self.backup_thread = threading.Thread(
            target=scheduler_loop,
            name="BackupScheduler",
            daemon=True
        )
        self.backup_thread.start()
        logger.success("✅ Backup scheduler ativo em thread separada")
    
    def stop_scheduler(self):
        """Para thread de agendamento"""
        if self.backup_thread and self.backup_thread.is_alive():
            logger.info("Parando backup scheduler...")
            self.stop_event.set()
            self.backup_thread.join(timeout=5)
            logger.success("✅ Backup scheduler parado")
    
    def get_backup_stats(self) -> dict:
        """
        Retorna estatísticas de backups
        
        Returns:
            Dict com estatísticas
        """
        all_backups = list(self.backup_dir.glob("*"))
        total_size = sum(f.stat().st_size for f in all_backups)
        
        return {
            "total_backups": len(all_backups),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest_backup": max(
                (f.stat().st_mtime for f in all_backups),
                default=None
            ),
            "backup_dir": str(self.backup_dir.absolute()),
        }
    
    def restore_from_backup(self, backup_file: str, target_file: str) -> bool:
        """
        Restaura arquivo de backup
        
        Args:
            backup_file: Nome do arquivo de backup
            target_file: Arquivo de destino
            
        Returns:
            True se sucesso
        """
        try:
            backup_path = self.backup_dir / backup_file
            target_path = Path(target_file)
            
            if not backup_path.exists():
                logger.error(f"❌ Backup não encontrado: {backup_file}")
                return False
            
            # Criar backup do arquivo atual antes de sobrescrever
            if target_path.exists():
                temp_backup = target_path.with_suffix(target_path.suffix + ".temp")
                shutil.copy2(target_path, temp_backup)
                logger.info(f"💾 Backup temporário criado: {temp_backup.name}")
            
            # Restaurar
            shutil.copy2(backup_path, target_path)
            logger.success(f"✅ Restaurado: {backup_file} → {target_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao restaurar backup: {e}")
            return False


# 🎯 Singleton instance
_auto_backup_instance = None

def get_auto_backup(enabled: bool = True) -> AutoBackup:
    """Retorna instância singleton do AutoBackup"""
    global _auto_backup_instance
    if _auto_backup_instance is None:
        _auto_backup_instance = AutoBackup(enabled=enabled)
    return _auto_backup_instance
