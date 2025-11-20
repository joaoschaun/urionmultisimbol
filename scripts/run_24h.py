"""
Executar Bot + Monitor por 24 horas
Script que inicia o bot e o monitor em processos separados
"""
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

def main():
    """Executa bot e monitor por 24 horas"""
    
    logger.info("="*60)
    logger.info("URION BOT - EXECUÇÃO 24 HORAS")
    logger.info("="*60)
    
    # Definir tempo de execução (24 horas)
    duration_hours = 24
    end_time = datetime.now() + timedelta(hours=duration_hours)
    
    logger.info(f"\n⏰ Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"⏰ Término previsto: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"⏰ Duração: {duration_hours} horas\n")
    
    # Caminhos
    venv_python = Path("venv/Scripts/python.exe")
    main_py = Path("main.py")
    monitor_py = Path("monitor.py")
    
    # Verificar arquivos
    if not venv_python.exists():
        logger.error("❌ Python do venv não encontrado!")
        return
    
    if not main_py.exists():
        logger.error("❌ main.py não encontrado!")
        return
    
    if not monitor_py.exists():
        logger.error("❌ monitor.py não encontrado!")
        return
    
    logger.success("✅ Todos os arquivos encontrados")
    
    try:
        # Iniciar o bot em background
        logger.info("\n🤖 Iniciando Bot...")
        bot_process = subprocess.Popen(
            [str(venv_python), str(main_py)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.success(f"✅ Bot iniciado (PID: {bot_process.pid})")
        
        # Aguardar 5 segundos para bot inicializar
        time.sleep(5)
        
        # Verificar se bot ainda está rodando
        if bot_process.poll() is not None:
            stdout, stderr = bot_process.communicate()
            logger.error("❌ Bot falhou ao iniciar!")
            logger.error(f"STDOUT: {stdout}")
            logger.error(f"STDERR: {stderr}")
            return
        
        logger.success("✅ Bot está rodando normalmente")
        
        # Iniciar o monitor em background
        logger.info("\n📊 Iniciando Monitor...")
        monitor_process = subprocess.Popen(
            [str(venv_python), str(monitor_py)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.success(f"✅ Monitor iniciado (PID: {monitor_process.pid})")
        
        logger.info("\n" + "="*60)
        logger.success("🎉 BOT E MONITOR RODANDO!")
        logger.info("="*60)
        logger.info("\n📊 INFORMAÇÕES:")
        logger.info(f"   • Bot PID: {bot_process.pid}")
        logger.info(f"   • Monitor PID: {monitor_process.pid}")
        logger.info(f"   • Duração: {duration_hours}h")
        logger.info(f"   • Término: {end_time.strftime('%d/%m/%Y %H:%M:%S')}")
        logger.info("\n⚠️  Para parar: Pressione Ctrl+C")
        logger.info("="*60)
        
        # Loop principal - verificar processos
        check_interval = 60  # Verificar a cada 1 minuto
        last_check = datetime.now()
        
        while datetime.now() < end_time:
            time.sleep(10)  # Checar a cada 10 segundos
            
            # Status periódico (a cada minuto)
            if (datetime.now() - last_check).seconds >= check_interval:
                remaining = end_time - datetime.now()
                hours_left = remaining.seconds // 3600
                minutes_left = (remaining.seconds % 3600) // 60
                
                logger.info(
                    f"⏰ Status: Bot rodando | "
                    f"Tempo restante: {hours_left}h {minutes_left}min"
                )
                last_check = datetime.now()
            
            # Verificar se bot ainda está rodando
            if bot_process.poll() is not None:
                logger.error("❌ Bot parou inesperadamente!")
                stdout, stderr = bot_process.communicate()
                logger.error(f"STDOUT: {stdout[-500:]}")  # Últimas 500 chars
                logger.error(f"STDERR: {stderr[-500:]}")
                
                # Tentar reiniciar
                logger.warning("🔄 Tentando reiniciar bot...")
                bot_process = subprocess.Popen(
                    [str(venv_python), str(main_py)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                logger.success(f"✅ Bot reiniciado (PID: {bot_process.pid})")
            
            # Verificar se monitor ainda está rodando
            if monitor_process.poll() is not None:
                logger.warning("⚠️ Monitor parou, reiniciando...")
                monitor_process = subprocess.Popen(
                    [str(venv_python), str(monitor_py)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                logger.success(f"✅ Monitor reiniciado (PID: {monitor_process.pid})")
        
        # Tempo esgotado
        logger.info("\n" + "="*60)
        logger.success("⏰ 24 HORAS COMPLETAS!")
        logger.info("="*60)
        
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Interrompido pelo usuário")
    
    except Exception as e:
        logger.error(f"\n\n❌ Erro: {e}")
    
    finally:
        # Parar processos
        logger.info("\n🛑 Parando processos...")
        
        try:
            bot_process.terminate()
            logger.info("   • Bot terminado")
        except:
            pass
        
        try:
            monitor_process.terminate()
            logger.info("   • Monitor terminado")
        except:
            pass
        
        # Aguardar processos finalizarem
        time.sleep(2)
        
        # Forçar se necessário
        try:
            bot_process.kill()
        except:
            pass
        
        try:
            monitor_process.kill()
        except:
            pass
        
        logger.success("\n✅ Execução finalizada com sucesso!")
        logger.info(f"⏰ Tempo total: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
