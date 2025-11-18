"""
Teste das APIs de notícias
Verifica se as 3 APIs estão funcionando
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.config_manager import ConfigManager
from analysis.news_analyzer import NewsAnalyzer
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")


def test_forexnews_api(analyzer):
    """Testa ForexNewsAPI"""
    logger.info("\n" + "=" * 70)
    logger.info("TESTANDO FOREXNEWSAPI")
    logger.info("=" * 70)
    
    try:
        news = analyzer.fetch_forex_news(limit=10)
        
        if news:
            logger.success(f"✅ ForexNewsAPI: {len(news)} notícias obtidas")
            logger.info(f"Primeira notícia: {news[0].get('title', 'N/A')[:60]}...")
            return True
        else:
            logger.warning("⚠️  ForexNewsAPI: Nenhuma notícia retornada")
            return False
            
    except Exception as e:
        logger.error(f"❌ ForexNewsAPI: ERRO - {e}")
        return False


def test_finazon_api(analyzer):
    """Testa Finazon"""
    logger.info("\n" + "=" * 70)
    logger.info("TESTANDO FINAZON")
    logger.info("=" * 70)
    
    try:
        news = analyzer.fetch_finazon_news(limit=10)
        
        if news:
            logger.success(f"✅ Finazon: {len(news)} notícias obtidas")
            logger.info(f"Primeira notícia: {news[0].get('title', 'N/A')[:60]}...")
            return True
        else:
            logger.warning("⚠️  Finazon: Nenhuma notícia retornada")
            return False
            
    except Exception as e:
        logger.error(f"❌ Finazon: ERRO - {e}")
        return False


def test_finnhub_api(analyzer):
    """Testa Finnhub"""
    logger.info("\n" + "=" * 70)
    logger.info("TESTANDO FINNHUB")
    logger.info("=" * 70)
    
    try:
        news = analyzer.fetch_finnhub_news(limit=10)
        
        if news:
            logger.success(f"✅ Finnhub: {len(news)} notícias obtidas")
            logger.info(f"Primeira notícia: {news[0].get('title', 'N/A')[:60]}...")
            return True
        else:
            logger.warning("⚠️  Finnhub: Nenhuma notícia retornada")
            return False
            
    except Exception as e:
        logger.error(f"❌ Finnhub: ERRO - {e}")
        return False


def test_fmp_api(analyzer):
    """Testa Financial Modeling Prep"""
    logger.info("\n" + "=" * 70)
    logger.info("TESTANDO FMP (CALENDÁRIO ECONÔMICO)")
    logger.info("=" * 70)
    
    try:
        events = analyzer.fetch_economic_calendar(days=2)
        
        if events:
            logger.success(f"✅ FMP: {len(events)} eventos obtidos")
            logger.info(f"Primeiro evento: {events[0].get('event', 'N/A')[:60]}...")
            return True
        else:
            logger.warning("⚠️  FMP: Nenhum evento retornado")
            return False
            
    except Exception as e:
        logger.error(f"❌ FMP: ERRO - {e}")
        return False


def test_aggregated_news(analyzer):
    """Testa agregação de notícias"""
    logger.info("\n" + "=" * 70)
    logger.info("TESTANDO AGREGAÇÃO DE NOTÍCIAS")
    logger.info("=" * 70)
    
    try:
        news = analyzer.get_aggregated_news(max_age_hours=24)
        
        if news:
            logger.success(f"✅ Notícias agregadas: {len(news)} itens")
            
            # Contar por fonte
            sources = {}
            for item in news:
                source = item.get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1
            
            logger.info("Distribuição por fonte:")
            for source, count in sources.items():
                logger.info(f"  • {source}: {count} notícias")
            
            return True
        else:
            logger.warning("⚠️  Agregação: Nenhuma notícia retornada")
            return False
            
    except Exception as e:
        logger.error(f"❌ Agregação: ERRO - {e}")
        return False


def test_sentiment_analysis(analyzer):
    """Testa análise de sentimento"""
    logger.info("\n" + "=" * 70)
    logger.info("TESTANDO ANÁLISE DE SENTIMENTO")
    logger.info("=" * 70)
    
    try:
        sentiment = analyzer.get_sentiment_summary(max_news=20)
        
        logger.success("✅ Análise de sentimento concluída")
        logger.info(f"Sentimento geral: {sentiment['overall_sentiment'].upper()}")
        logger.info(f"Polaridade média: {sentiment['polarity_avg']:.3f}")
        logger.info(f"Bullish: {sentiment['bullish_count']} | "
                   f"Bearish: {sentiment['bearish_count']} | "
                   f"Neutral: {sentiment['neutral_count']}")
        logger.info(f"Total analisado: {sentiment['total_analyzed']} notícias")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Sentimento: ERRO - {e}")
        return False


def main():
    logger.info("=" * 70)
    logger.info("TESTE COMPLETO DAS APIs DE NOTÍCIAS")
    logger.info("=" * 70)
    
    # Carregar config
    config_manager = ConfigManager()
    config = config_manager.config
    
    # Verificar se há API keys configuradas
    news_config = config.get('news', {})
    
    logger.info("\nAPI KEYS CONFIGURADAS:")
    logger.info(f"  ForexNewsAPI: {'✅ SIM' if news_config.get('forexnews_api_key') else '❌ NÃO'}")
    logger.info(f"  Finnhub: {'✅ SIM' if news_config.get('finnhub_api_key') else '❌ NÃO'}")
    logger.info(f"  Finazon: {'✅ SIM' if news_config.get('finazon_api_key') else '❌ NÃO'}")
    logger.info(f"  FMP: {'✅ SIM' if news_config.get('fmp_api_key') else '❌ NÃO'}")
    
    # Inicializar analyzer
    analyzer = NewsAnalyzer(config)
    
    # Executar testes
    results = {
        'ForexNewsAPI': test_forexnews_api(analyzer),
        'Finnhub': test_finnhub_api(analyzer),
        'Finazon': test_finazon_api(analyzer),
        'FMP': test_fmp_api(analyzer),
        'Agregação': test_aggregated_news(analyzer),
        'Sentimento': test_sentiment_analysis(analyzer)
    }
    
    # Resumo final
    logger.info("\n" + "=" * 70)
    logger.info("RESUMO DOS TESTES")
    logger.info("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        logger.info(f"{test_name}: {status}")
    
    total_passed = sum(1 for v in results.values() if v)
    total_tests = len(results)
    
    logger.info("\n" + "=" * 70)
    logger.info(f"RESULTADO: {total_passed}/{total_tests} testes passaram")
    logger.info("=" * 70)
    
    if total_passed == total_tests:
        logger.success("\n🎉 TODAS AS APIs ESTÃO FUNCIONANDO!")
    elif total_passed > 0:
        logger.warning(f"\n⚠️  {total_tests - total_passed} API(s) com problema")
    else:
        logger.error("\n❌ NENHUMA API ESTÁ FUNCIONANDO")


if __name__ == "__main__":
    main()
