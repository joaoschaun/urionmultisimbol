"""
News Notifier - Sistema de notificação automática de notícias importantes
Monitora e envia notícias relevantes ao Telegram em português
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from loguru import logger
import threading
import time


class NewsNotifier:
    """
    Sistema automático de notificação de notícias importantes
    Filtra por relevância, impacto e envia traduzido ao Telegram
    """
    
    def __init__(self, news_analyzer, telegram, config: Dict):
        """
        Inicializa o notificador de notícias
        
        Args:
            news_analyzer: Instância do NewsAnalyzer
            telegram: Instância do TelegramNotifier
            config: Configuração do bot
        """
        self.news_analyzer = news_analyzer
        self.telegram = telegram
        self.config = config
        
        # Configurações de notificação
        news_config = config.get('notifications', {}).get('news', {})
        self.enabled = news_config.get('enabled', True)
        self.min_importance = int(news_config.get('min_importance', 3))
        # Converter para inteiro (pode vir como string do YAML)
        interval_raw = news_config.get('interval_minutes', 15)
        self.notification_interval = int(interval_raw) if isinstance(interval_raw, (int, float, str)) else 15
        
        # Símbolos monitorados
        multi_config = config.get('multi_symbol', {})
        default_symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
        self.symbols = multi_config.get('symbols', default_symbols)
        
        # Rastreamento de notícias já notificadas
        self.notified_news: Dict[str, datetime] = {}
        self.last_check = datetime.now(timezone.utc)
        
        # Thread de monitoramento
        self.running = False
        self.monitor_thread = None
        
        logger.info(
            f"📰 NewsNotifier inicializado: "
            f"importance>={self.min_importance}, "
            f"interval={self.notification_interval}min"
        )
    
    def start(self):
        """Inicia o monitoramento automático de notícias"""
        if not self.enabled:
            logger.info("📰 NewsNotifier desabilitado na configuração")
            return
        
        if self.running:
            logger.warning("NewsNotifier já está rodando")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="NewsNotifier-Monitor",
            daemon=True
        )
        self.monitor_thread.start()
        logger.success("✅ NewsNotifier: Monitoramento iniciado")
    
    def stop(self):
        """Para o monitoramento de notícias"""
        if not self.running:
            return
        
        logger.info("🛑 Parando NewsNotifier...")
        self.running = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        logger.success("✅ NewsNotifier parado")
    
    def _monitor_loop(self):
        """Loop principal de monitoramento"""
        logger.info("📰 NewsNotifier: Loop de monitoramento iniciado")
        
        while self.running:
            try:
                self._check_and_notify_news()
                
                # Aguardar próxima verificação
                time.sleep(self.notification_interval * 60)
                
            except Exception as e:
                logger.error(
                    f"❌ Erro no loop de monitoramento de notícias: {e}"
                )
                time.sleep(60)  # Aguardar 1min em caso de erro
    
    def _check_and_notify_news(self):
        """Verifica e notifica notícias importantes"""
        try:
            now = datetime.now(timezone.utc)
            
            # Buscar notícias de cada símbolo
            for symbol in self.symbols:
                news_list = self._fetch_important_news(symbol)
                
                if news_list:
                    logger.info(
                        f"📰 {symbol}: {len(news_list)} "
                        f"notícia(s) importante(s) encontrada(s)"
                    )
                    
                    for news in news_list:
                        self._send_news_notification(symbol, news)
            
            self.last_check = now
            self._cleanup_old_news()
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar notícias: {e}")
    
    def _fetch_important_news(self, symbol: str) -> List[Dict]:
        """
        Busca notícias importantes para um símbolo
        
        Args:
            symbol: Símbolo a verificar (ex: EURUSD)
            
        Returns:
            Lista de notícias importantes não notificadas
        """
        try:
            # Buscar notícias agregadas
            all_news = self.news_analyzer.get_aggregated_news(symbol)
            
            if not all_news:
                return []
            
            important_news = []
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(minutes=self.notification_interval)
            
            for news in all_news:
                # Verificar se já foi notificada
                news_id = self._generate_news_id(news)
                if news_id in self.notified_news:
                    continue
                
                # Verificar importância
                importance = news.get('importance', 0)
                if importance < self.min_importance:
                    continue
                
                # Verificar se é recente
                news_time = news.get('published_at')
                if news_time and news_time < cutoff_time:
                    continue
                
                important_news.append(news)
            
            return important_news
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar notícias de {symbol}: {e}")
            return []
    
    def _send_news_notification(self, symbol: str, news: Dict):
        """
        Envia notificação de notícia ao Telegram
        
        Args:
            symbol: Símbolo relacionado
            news: Dados da notícia
        """
        try:
            # Marcar como notificada
            news_id = self._generate_news_id(news)
            self.notified_news[news_id] = datetime.now(timezone.utc)
            
            # Formatar mensagem
            message = self._format_news_message(symbol, news)
            
            # Enviar ao Telegram
            self.telegram.send_message_sync(message, parse_mode='Markdown')
            
            logger.info(f"📨 Notícia enviada: {symbol} - {news.get('title', '')[:50]}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar notificação: {e}")
    
    def _format_news_message(self, symbol: str, news: Dict) -> str:
        """
        Formata mensagem de notícia para o Telegram em português
        
        Args:
            symbol: Símbolo relacionado
            news: Dados da notícia
            
        Returns:
            Mensagem formatada em Markdown
        """
        # Traduzir título e descrição
        title = news.get('title', 'Sem título')
        description = news.get('description', news.get('summary', ''))
        
        # Traduzir para português
        try:
            title_pt = self.telegram._translate_to_portuguese(title) if title else title
            description_pt = self.telegram._translate_to_portuguese(description) if description else description
        except:
            title_pt = title
            description_pt = description
        
        # Dados da notícia
        source = news.get('source', 'Desconhecida')
        importance = news.get('importance', 0)
        sentiment = news.get('sentiment', 'neutro')
        impact = news.get('impact', 'médio')
        published = news.get('published_at', datetime.now(timezone.utc))
        
        # Emojis de importância
        importance_emoji = {
            5: "🔴🔴🔴",
            4: "🔴🔴",
            3: "🟡",
            2: "🟢",
            1: "⚪"
        }.get(importance, "⚪")
        
        # Emoji de sentimento
        sentiment_emoji = {
            'positivo': '📈',
            'negativo': '📉',
            'neutro': '➖'
        }.get(sentiment.lower(), '➖')
        
        # Emoji de impacto
        impact_emoji = {
            'alto': '⚠️',
            'médio': '⚡',
            'baixo': 'ℹ️'
        }.get(impact.lower(), 'ℹ️')
        
        # Formatar hora local (assumindo UTC-3 para Brasil)
        published_local = published - timedelta(hours=3) if published else None
        time_str = published_local.strftime("%d/%m/%Y %H:%M") if published_local else "Não disponível"
        
        # Construir mensagem
        message = f"""
📰 *NOTÍCIA IMPORTANTE*

{importance_emoji} *Importância:* {importance}/5
{symbol} *Ativo:* `{symbol}`
{sentiment_emoji} *Sentimento:* {sentiment.title()}
{impact_emoji} *Impacto:* {impact.title()}

*{title_pt}*

{description_pt}

📅 *Data:* {time_str}
🔗 *Fonte:* {source}

#News #{symbol} #Forex
"""
        
        return message.strip()
    
    def _generate_news_id(self, news: Dict) -> str:
        """
        Gera ID único para uma notícia
        
        Args:
            news: Dados da notícia
            
        Returns:
            ID único
        """
        title = news.get('title', '')
        source = news.get('source', '')
        published = news.get('published_at', datetime.now(timezone.utc))
        
        # Hash simples baseado em título + fonte + data
        return f"{title[:50]}_{source}_{published.strftime('%Y%m%d%H%M')}"
    
    def _cleanup_old_news(self):
        """Remove notícias antigas do cache (>24h)"""
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=24)
            
            old_news = [
                news_id for news_id, notif_time in self.notified_news.items()
                if notif_time < cutoff
            ]
            
            for news_id in old_news:
                del self.notified_news[news_id]
            
            if old_news:
                logger.debug(f"🧹 NewsNotifier: {len(old_news)} notícia(s) antiga(s) removida(s) do cache")
                
        except Exception as e:
            logger.error(f"❌ Erro ao limpar cache de notícias: {e}")
    
    def send_manual_news_summary(self, symbol: Optional[str] = None):
        """
        Envia resumo manual de notícias importantes
        
        Args:
            symbol: Símbolo específico ou None para todos
        """
        try:
            symbols_to_check = [symbol] if symbol else self.symbols
            
            for sym in symbols_to_check:
                news_list = self._fetch_important_news(sym)
                
                if not news_list:
                    continue
                
                # Enviar até 5 notícias mais importantes
                for news in news_list[:5]:
                    self._send_news_notification(sym, news)
                    time.sleep(2)  # Evitar rate limit
            
            logger.info(f"📨 Resumo manual de notícias enviado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar resumo manual: {e}")
