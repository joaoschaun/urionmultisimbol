"""
Exemplo de uso do NewsAnalyzer
Demonstra integração com APIs de notícias e análise de sentimento
"""

import sys
import os
from datetime import datetime

# Adicionar diretório src ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.config_manager import ConfigManager
from src.core.logger import setup_logger
from src.analysis.news_analyzer import NewsAnalyzer


def main():
    """Exemplo de análise de notícias"""
    
    # Configurar logger
    logger = setup_logger('news_demo')
    logger.info("=== Demo: Análise de Notícias ===")
    
    try:
        # Carregar configuração
        config = ConfigManager('config/config.yaml')
        logger.info("Configuração carregada")
        
        # Criar analisador de notícias
        analyzer = NewsAnalyzer(config.config)
        logger.info("NewsAnalyzer inicializado")
        
        # ===== EXEMPLO 1: Buscar Top Notícias =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 1: Top Notícias Relevantes para GOLD")
        logger.info("="*60)
        
        top_news = analyzer.get_top_news(limit=5)
        
        if top_news:
            for i, news in enumerate(top_news, 1):
                logger.info(f"\n📰 Notícia {i}:")
                logger.info(f"  Fonte: {news.get('source', 'N/A')}")
                logger.info(f"  Título: {news.get('title', 'N/A')}")
                logger.info(f"  Relevância: {news.get('relevance', 0):.2%}")
                
                sentiment = news.get('sentiment', {})
                polarity = sentiment.get('polarity', 0)
                
                if polarity > 0.1:
                    sentiment_emoji = "📈"
                    sentiment_text = "POSITIVO"
                elif polarity < -0.1:
                    sentiment_emoji = "📉"
                    sentiment_text = "NEGATIVO"
                else:
                    sentiment_emoji = "➡️"
                    sentiment_text = "NEUTRO"
                
                logger.info(f"  Sentimento: {sentiment_emoji} {sentiment_text} ({polarity:.2f})")
                logger.info(f"  URL: {news.get('url', 'N/A')}")
        else:
            logger.info("Nenhuma notícia encontrada")
        
        # ===== EXEMPLO 2: Resumo de Sentimento =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 2: Resumo de Sentimento Geral")
        logger.info("="*60)
        
        sentiment_summary = analyzer.get_sentiment_summary(max_news=20)
        
        logger.info(f"\nAnálise de {sentiment_summary['total_analyzed']} notícias:")
        logger.info(f"  Sentimento Geral: {sentiment_summary['overall_sentiment'].upper()}")
        logger.info(f"  Polaridade Média: {sentiment_summary['polarity_avg']:.3f}")
        logger.info(f"\nDistribuição:")
        logger.info(f"  📈 Bullish: {sentiment_summary['bullish_count']} notícias")
        logger.info(f"  📉 Bearish: {sentiment_summary['bearish_count']} notícias")
        logger.info(f"  ➡️  Neutro: {sentiment_summary['neutral_count']} notícias")
        
        overall = sentiment_summary['overall_sentiment']
        if overall == 'bullish':
            logger.info("\n  ✅ Sentimento favorável para COMPRA de GOLD")
        elif overall == 'bearish':
            logger.info("\n  ⚠️  Sentimento favorável para VENDA de GOLD")
        else:
            logger.info("\n  ⏸️  Sentimento neutro - aguardar confirmação")
        
        # ===== EXEMPLO 3: Calendário Econômico =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 3: Eventos Econômicos Importantes")
        logger.info("="*60)
        
        events = analyzer.fetch_economic_calendar(days=1)
        
        if events:
            logger.info(f"\nEncontrados {len(events)} eventos de alto impacto:")
            
            for i, event in enumerate(events, 1):
                impact_emoji = "🔴" if event['impact'] == 'high' else "🟡"
                
                logger.info(f"\n{impact_emoji} Evento {i}:")
                logger.info(f"  Nome: {event['event']}")
                logger.info(f"  País: {event['country']}")
                logger.info(f"  Data: {event['date']}")
                logger.info(f"  Impacto: {event['impact'].upper()}")
                logger.info(f"  Moeda: {event['currency']}")
                
                if event.get('estimate'):
                    logger.info(f"  Previsão: {event['estimate']}")
                if event.get('previous'):
                    logger.info(f"  Anterior: {event['previous']}")
        else:
            logger.info("Nenhum evento de alto impacto nas próximas 24h")
        
        # ===== EXEMPLO 4: Verificar Janela de Bloqueio =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 4: Verificação de Janela de Bloqueio")
        logger.info("="*60)
        
        is_blocking, blocking_event = analyzer.is_news_blocking_window(buffer_minutes=15)
        
        if is_blocking:
            logger.warning("\n⛔ JANELA DE BLOQUEIO ATIVA!")
            logger.warning(f"  Evento: {blocking_event['event']}")
            logger.warning(f"  Data: {blocking_event['date']}")
            logger.warning(f"  Impacto: {blocking_event['impact'].upper()}")
            logger.warning("\n  ⚠️  NÃO OPERAR durante este período!")
        else:
            logger.info("\n✅ Nenhuma janela de bloqueio ativa")
            logger.info("  Seguro para operar (do ponto de vista de notícias)")
        
        # ===== EXEMPLO 5: Sinal de Trading Baseado em Notícias =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 5: Sinal de Trading")
        logger.info("="*60)
        
        signal = analyzer.get_news_signal()
        
        logger.info(f"\nSINAL GERADO:")
        logger.info(f"  Ação: {signal['action']}")
        logger.info(f"  Razão: {signal['reason']}")
        logger.info(f"  Confiança: {signal['confidence']:.2%}")
        
        if signal['action'] == 'BLOCK':
            logger.warning("\n  ⛔ BLOQUEIO: Evento de alto impacto detectado")
            logger.warning("  NÃO abrir novas posições!")
            
            if signal.get('event'):
                event = signal['event']
                logger.warning(f"  Evento: {event['event']} ({event['country']})")
                logger.warning(f"  Horário: {event['date']}")
        
        elif signal['action'] == 'BULLISH':
            logger.info("\n  📈 SINAL DE COMPRA")
            logger.info(f"  Confiança: {signal['confidence']:.0%}")
            logger.info("  Notícias indicam sentimento positivo para GOLD")
            
            if signal['confidence'] > 0.7:
                logger.info("  ✅ Alta confiança - Considerar entrada LONG")
            else:
                logger.info("  ⚠️  Confiança moderada - Aguardar confirmação técnica")
        
        elif signal['action'] == 'BEARISH':
            logger.info("\n  📉 SINAL DE VENDA")
            logger.info(f"  Confiança: {signal['confidence']:.0%}")
            logger.info("  Notícias indicam sentimento negativo para GOLD")
            
            if signal['confidence'] > 0.7:
                logger.info("  ✅ Alta confiança - Considerar entrada SHORT")
            else:
                logger.info("  ⚠️  Confiança moderada - Aguardar confirmação técnica")
        
        else:  # HOLD
            logger.info("\n  ⏸️  AGUARDAR")
            logger.info("  Sentimento neutro ou confiança insuficiente")
            logger.info("  Esperar sinais mais claros")
        
        # ===== EXEMPLO 6: Análise Detalhada de Notícias =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 6: Análise Detalhada")
        logger.info("="*60)
        
        all_news = analyzer.get_aggregated_news(max_age_hours=6)
        
        logger.info(f"\nNotícias das últimas 6 horas: {len(all_news)}")
        
        if all_news:
            # Agrupar por fonte
            by_source = {}
            for news in all_news:
                source = news.get('source', 'Unknown')
                by_source[source] = by_source.get(source, 0) + 1
            
            logger.info("\nDistribuição por fonte:")
            for source, count in by_source.items():
                logger.info(f"  {source}: {count} notícias")
            
            # Calcular relevância média
            avg_relevance = sum(n.get('relevance', 0) for n in all_news) / len(all_news)
            logger.info(f"\nRelevância média: {avg_relevance:.2%}")
        
        # ===== EXEMPLO 7: Monitoramento Contínuo =====
        logger.info("\n" + "="*60)
        logger.info("EXEMPLO 7: Monitoramento Contínuo (3 iterações)")
        logger.info("="*60)
        
        import time
        
        for i in range(3):
            logger.info(f"\n--- Iteração {i+1} ---")
            
            # Limpar cache para forçar atualização
            analyzer.clear_cache()
            
            # Verificar bloqueio
            is_blocking, _ = analyzer.is_news_blocking_window()
            
            # Obter sentimento
            sentiment = analyzer.get_sentiment_summary(max_news=10)
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            logger.info(
                f"[{timestamp}] Bloqueio: {'❌ SIM' if is_blocking else '✅ NÃO'} | "
                f"Sentimento: {sentiment['overall_sentiment'].upper()} | "
                f"Polaridade: {sentiment['polarity_avg']:+.2f}"
            )
            
            if i < 2:  # Não esperar na última iteração
                logger.info("Aguardando 10 segundos...")
                time.sleep(10)
        
        logger.info("\n" + "="*60)
        logger.info("Demo concluído com sucesso!")
        logger.info("="*60)
        
    except KeyboardInterrupt:
        logger.info("\nDemo interrompido pelo usuário")
    
    except Exception as e:
        logger.error(f"Erro durante demo: {e}", exc_info=True)


if __name__ == '__main__':
    main()
