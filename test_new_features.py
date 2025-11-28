"""
Script de teste das novas funcionalidades:
1. NewsNotifier - Notificações de notícias em português
2. Relatórios melhorados (Diário, Semanal, Mensal)
"""
from src.core.config_manager import ConfigManager
from src.notifications.telegram_bot import TelegramNotifier
from src.notifications.news_notifier import NewsNotifier
from src.analysis.news_analyzer import NewsAnalyzer
from src.reporting.daily_report import DailyReportGenerator
from src.reporting.weekly_report import WeeklyReportGenerator
from src.reporting.monthly_report import MonthlyReportGenerator
from database.strategy_stats import StrategyStatsDB
from loguru import logger

def test_news_system():
    """Testa sistema de notícias"""
    print("\n" + "="*60)
    print("TESTE 1: Sistema de Notícias em Português")
    print("="*60)
    
    try:
        # Carregar config
        config_manager = ConfigManager('config/config.yaml')
        config = config_manager.config
        
        # Inicializar componentes
        telegram = TelegramNotifier(config)
        news_analyzer = NewsAnalyzer(config)
        news_notifier = NewsNotifier(news_analyzer, telegram, config)
        
        # Verificar configuração
        print(f"✅ NewsNotifier criado")
        print(f"   - Habilitado: {news_notifier.enabled}")
        print(f"   - Importância mínima: {news_notifier.min_importance}")
        print(f"   - Intervalo: {news_notifier.notification_interval} minutos")
        print(f"   - Símbolos: {news_notifier.symbols}")
        
        # Enviar resumo manual (teste)
        print("\n📰 Enviando resumo manual de notícias...")
        news_notifier.send_manual_news_summary('XAUUSD')
        
        print("✅ Teste de notícias concluído!")
        
    except Exception as e:
        print(f"❌ Erro no teste de notícias: {e}")
        logger.exception(e)

def test_daily_report():
    """Testa relatório diário melhorado"""
    print("\n" + "="*60)
    print("TESTE 2: Relatório Diário Melhorado")
    print("="*60)
    
    try:
        config_manager = ConfigManager('config/config.yaml')
        config = config_manager.config
        
        telegram = TelegramNotifier(config)
        stats_db = StrategyStatsDB()
        
        daily_report = DailyReportGenerator(stats_db, telegram)
        
        # Gerar relatório
        print("📊 Gerando relatório diário...")
        report_data = daily_report.generate_report()
        
        if report_data:
            formatted = daily_report.format_report(report_data)
            print("\n" + "="*60)
            print("RELATÓRIO GERADO (PREVIEW):")
            print("="*60)
            print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
            print("\n✅ Relatório diário testado!")
        else:
            print("⚠️ Sem dados para relatório hoje")
            
    except Exception as e:
        print(f"❌ Erro no teste de relatório diário: {e}")
        logger.exception(e)

def test_weekly_report():
    """Testa relatório semanal melhorado"""
    print("\n" + "="*60)
    print("TESTE 3: Relatório Semanal Melhorado")
    print("="*60)
    
    try:
        config_manager = ConfigManager('config/config.yaml')
        config = config_manager.config
        
        telegram = TelegramNotifier(config)
        stats_db = StrategyStatsDB()
        
        weekly_report = WeeklyReportGenerator(stats_db, telegram)
        
        # Gerar relatório
        print("📊 Gerando relatório semanal...")
        report_data = weekly_report.generate_report()
        
        if report_data.get('total_trades', 0) > 0:
            formatted = weekly_report.format_report(report_data)
            print("\n" + "="*60)
            print("RELATÓRIO GERADO (PREVIEW):")
            print("="*60)
            print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
            print("\n✅ Relatório semanal testado!")
        else:
            print("⚠️ Sem dados para relatório semanal")
            
    except Exception as e:
        print(f"❌ Erro no teste de relatório semanal: {e}")
        logger.exception(e)

def test_monthly_report():
    """Testa relatório mensal melhorado"""
    print("\n" + "="*60)
    print("TESTE 4: Relatório Mensal Melhorado")
    print("="*60)
    
    try:
        config_manager = ConfigManager('config/config.yaml')
        config = config_manager.config
        
        telegram = TelegramNotifier(config)
        stats_db = StrategyStatsDB()
        
        monthly_report = MonthlyReportGenerator(stats_db, telegram)
        
        # Gerar relatório
        print("📊 Gerando relatório mensal...")
        report_data = monthly_report.generate_report()
        
        if report_data.get('total_trades', 0) > 0:
            formatted = monthly_report.format_report(report_data)
            print("\n" + "="*60)
            print("RELATÓRIO GERADO (PREVIEW):")
            print("="*60)
            print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
            print("\n✅ Relatório mensal testado!")
        else:
            print("⚠️ Sem dados para relatório mensal")
            
    except Exception as e:
        print(f"❌ Erro no teste de relatório mensal: {e}")
        logger.exception(e)

if __name__ == "__main__":
    print("\n🚀 TESTES DAS NOVAS FUNCIONALIDADES")
    print("Notificações em Português + Relatórios Detalhados")
    print("="*60)
    
    # Executar todos os testes
    test_news_system()
    test_daily_report()
    test_weekly_report()
    test_monthly_report()
    
    print("\n" + "="*60)
    print("✅ TODOS OS TESTES CONCLUÍDOS!")
    print("="*60)
    print("\n💡 PRÓXIMOS PASSOS:")
    print("1. Bot está rodando em background")
    print("2. NewsNotifier monitorará notícias a cada 15min")
    print("3. Relatórios serão enviados automaticamente:")
    print("   - Diário: 23:59")
    print("   - Semanal: Domingo 23:59")
    print("   - Mensal: Último dia do mês 23:59")
    print("\n📱 Todas as notificações serão enviadas ao Telegram em PORTUGUÊS")
    print("="*60 + "\n")
