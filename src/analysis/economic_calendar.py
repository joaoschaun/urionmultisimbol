# -*- coding: utf-8 -*-
"""
Economic Calendar Integration
==============================
Modulo para integracao com calendario economico.
Permite evitar trading durante eventos de alto impacto.

Fontes de dados:
- Investing.com (gratis, scraping)
- ForexFactory (gratis, scraping)
- TradingView (via API, se disponivel)
- FCS API (gratis com limites)
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import json
import os
import re
from bs4 import BeautifulSoup
import hashlib


class EventImpact(Enum):
    """Impacto do evento economico"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    HOLIDAY = "holiday"


@dataclass
class EconomicEvent:
    """Evento economico"""
    id: str
    datetime: datetime
    currency: str
    country: str
    event_name: str
    impact: EventImpact
    
    # Dados do evento (se disponiveis)
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None
    
    # Metadados
    source: str = ""


class EconomicCalendar:
    """
    Calendario Economico
    Gerencia eventos economicos e verifica impacto no trading
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.calendar_config = config.get('economic_calendar', {})
        
        # Configuracoes
        self.check_interval_minutes = self.calendar_config.get('check_interval', 60)
        self.buffer_before_minutes = self.calendar_config.get('buffer_before', 15)
        self.buffer_after_minutes = self.calendar_config.get('buffer_after', 15)
        self.avoid_high_impact = self.calendar_config.get('avoid_high_impact', True)
        self.avoid_medium_impact = self.calendar_config.get('avoid_medium_impact', False)
        
        # Moedas de interesse
        self.currencies_of_interest = self.calendar_config.get('currencies', ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD'])
        
        # Cache de eventos
        self._events: List[EconomicEvent] = []
        self._last_update: Optional[datetime] = None
        self._cache_file = 'data/economic_calendar_cache.json'
        
        # Carregar cache se existir
        self._load_cache()
        
        logger.info("EconomicCalendar inicializado")
    
    def _load_cache(self):
        """Carrega eventos do cache"""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r') as f:
                    data = json.load(f)
                
                self._events = []
                for e in data.get('events', []):
                    event = EconomicEvent(
                        id=e['id'],
                        datetime=datetime.fromisoformat(e['datetime']),
                        currency=e['currency'],
                        country=e['country'],
                        event_name=e['event_name'],
                        impact=EventImpact(e['impact']),
                        actual=e.get('actual'),
                        forecast=e.get('forecast'),
                        previous=e.get('previous'),
                        source=e.get('source', '')
                    )
                    self._events.append(event)
                
                self._last_update = datetime.fromisoformat(data.get('last_update', datetime.min.isoformat()))
                logger.info(f"Carregados {len(self._events)} eventos do cache")
        except Exception as e:
            logger.warning(f"Erro ao carregar cache: {e}")
    
    def _save_cache(self):
        """Salva eventos no cache"""
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            
            data = {
                'last_update': datetime.now().isoformat(),
                'events': []
            }
            
            for e in self._events:
                data['events'].append({
                    'id': e.id,
                    'datetime': e.datetime.isoformat(),
                    'currency': e.currency,
                    'country': e.country,
                    'event_name': e.event_name,
                    'impact': e.impact.value,
                    'actual': e.actual,
                    'forecast': e.forecast,
                    'previous': e.previous,
                    'source': e.source
                })
            
            with open(self._cache_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")
    
    async def update_events(self, force: bool = False):
        """Atualiza eventos do calendario"""
        now = datetime.now()
        
        # Verificar se precisa atualizar
        if not force and self._last_update:
            time_since_update = (now - self._last_update).total_seconds() / 60
            if time_since_update < self.check_interval_minutes:
                return
        
        logger.info("Atualizando calendario economico...")
        
        # Tentar varias fontes
        events = []
        
        # 1. Tentar FCS API (gratis)
        try:
            fcs_events = await self._fetch_fcs_api()
            events.extend(fcs_events)
        except Exception as e:
            logger.warning(f"Erro FCS API: {e}")
        
        # 2. Tentar scraping ForexFactory
        if not events:
            try:
                ff_events = await self._fetch_forex_factory()
                events.extend(ff_events)
            except Exception as e:
                logger.warning(f"Erro ForexFactory: {e}")
        
        # Atualizar cache
        if events:
            # Remover eventos antigos (mais de 1 dia atras)
            cutoff = now - timedelta(days=1)
            self._events = [e for e in self._events if e.datetime > cutoff]
            
            # Adicionar novos eventos (evitar duplicatas)
            existing_ids = {e.id for e in self._events}
            for event in events:
                if event.id not in existing_ids:
                    self._events.append(event)
            
            self._last_update = now
            self._save_cache()
            
            logger.info(f"Calendario atualizado: {len(self._events)} eventos")
    
    async def _fetch_fcs_api(self) -> List[EconomicEvent]:
        """Busca eventos da FCS API"""
        events = []
        
        # Endpoint gratis (limitado)
        url = "https://fcsapi.com/api-v3/forex/economy_cal"
        
        async with aiohttp.ClientSession() as session:
            params = {
                'access_key': 'demo',  # API key gratis para testes
                'from': datetime.now().strftime('%Y-%m-%d'),
                'to': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            }
            
            try:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for item in data.get('response', []):
                            impact_map = {
                                '1': EventImpact.LOW,
                                '2': EventImpact.MEDIUM,
                                '3': EventImpact.HIGH
                            }
                            
                            event = EconomicEvent(
                                id=hashlib.md5(f"{item.get('date')}_{item.get('title')}".encode()).hexdigest()[:12],
                                datetime=datetime.strptime(item.get('date', ''), '%Y-%m-%d %H:%M'),
                                currency=item.get('country', '').upper()[:3],
                                country=item.get('country', ''),
                                event_name=item.get('title', ''),
                                impact=impact_map.get(str(item.get('impact', 1)), EventImpact.LOW),
                                actual=item.get('actual'),
                                forecast=item.get('forecast'),
                                previous=item.get('previous'),
                                source='FCS API'
                            )
                            events.append(event)
            except Exception as e:
                logger.warning(f"Erro ao buscar FCS API: {e}")
        
        return events
    
    async def _fetch_forex_factory(self) -> List[EconomicEvent]:
        """Busca eventos do ForexFactory via scraping"""
        events = []
        
        url = "https://www.forexfactory.com/calendar"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Parse calendar table
                        calendar_table = soup.find('table', class_='calendar__table')
                        
                        if calendar_table:
                            rows = calendar_table.find_all('tr', class_='calendar__row')
                            current_date = datetime.now().date()
                            
                            for row in rows:
                                try:
                                    # Data
                                    date_cell = row.find('td', class_='calendar__date')
                                    if date_cell:
                                        date_text = date_cell.get_text(strip=True)
                                        # Parse date (formato: "Mon Jan 1")
                                        # ... parsing complexo omitido para simplicidade
                                    
                                    # Hora
                                    time_cell = row.find('td', class_='calendar__time')
                                    time_text = time_cell.get_text(strip=True) if time_cell else ""
                                    
                                    # Moeda
                                    currency_cell = row.find('td', class_='calendar__currency')
                                    currency = currency_cell.get_text(strip=True) if currency_cell else ""
                                    
                                    # Evento
                                    event_cell = row.find('td', class_='calendar__event')
                                    event_name = event_cell.get_text(strip=True) if event_cell else ""
                                    
                                    # Impacto
                                    impact_cell = row.find('td', class_='calendar__impact')
                                    impact = EventImpact.LOW
                                    if impact_cell:
                                        if impact_cell.find(class_='high'):
                                            impact = EventImpact.HIGH
                                        elif impact_cell.find(class_='medium'):
                                            impact = EventImpact.MEDIUM
                                    
                                    if currency and event_name:
                                        event = EconomicEvent(
                                            id=hashlib.md5(f"{current_date}_{event_name}".encode()).hexdigest()[:12],
                                            datetime=datetime.combine(current_date, datetime.min.time()),
                                            currency=currency,
                                            country=currency,
                                            event_name=event_name,
                                            impact=impact,
                                            source='ForexFactory'
                                        )
                                        events.append(event)
                                        
                                except Exception as e:
                                    continue
                                    
            except Exception as e:
                logger.warning(f"Erro ao fazer scraping ForexFactory: {e}")
        
        return events
    
    def get_events_for_symbol(self, symbol: str, 
                             start: datetime = None,
                             end: datetime = None) -> List[EconomicEvent]:
        """
        Retorna eventos relevantes para um simbolo
        """
        # Extrair moedas do simbolo (ex: EURUSD -> EUR, USD)
        currencies = self._extract_currencies(symbol)
        
        start = start or datetime.now()
        end = end or start + timedelta(hours=24)
        
        relevant_events = []
        
        for event in self._events:
            # Verificar moeda
            if event.currency not in currencies:
                continue
            
            # Verificar periodo
            if event.datetime < start or event.datetime > end:
                continue
            
            relevant_events.append(event)
        
        # Ordenar por data/hora
        relevant_events.sort(key=lambda x: x.datetime)
        
        return relevant_events
    
    def _extract_currencies(self, symbol: str) -> List[str]:
        """Extrai moedas de um simbolo"""
        symbol = symbol.upper()
        
        # Mapeamento de simbolos para moedas
        symbol_currencies = {
            'XAUUSD': ['XAU', 'USD'],
            'XAGUSD': ['XAG', 'USD'],
            'BTCUSD': ['BTC', 'USD'],
            'ETHUSD': ['ETH', 'USD'],
        }
        
        if symbol in symbol_currencies:
            return symbol_currencies[symbol]
        
        # Forex pairs
        if len(symbol) == 6:
            return [symbol[:3], symbol[3:]]
        
        # Tentar extrair USD se presente
        if 'USD' in symbol:
            return ['USD']
        
        return []
    
    def is_high_impact_period(self, symbol: str, 
                             time: datetime = None) -> Dict:
        """
        Verifica se estamos em periodo de alto impacto
        Retorna detalhes do evento se estiver
        """
        time = time or datetime.now()
        
        # Considerar buffer antes e depois
        check_start = time - timedelta(minutes=self.buffer_before_minutes)
        check_end = time + timedelta(minutes=self.buffer_after_minutes)
        
        events = self.get_events_for_symbol(symbol, check_start, check_end)
        
        # Filtrar por impacto
        high_impact_events = [e for e in events if e.impact == EventImpact.HIGH]
        
        if not high_impact_events:
            return {
                'is_high_impact': False,
                'safe_to_trade': True,
                'events': []
            }
        
        return {
            'is_high_impact': True,
            'safe_to_trade': False,
            'events': [
                {
                    'name': e.event_name,
                    'currency': e.currency,
                    'datetime': e.datetime.isoformat(),
                    'impact': e.impact.value
                }
                for e in high_impact_events
            ],
            'reason': f"Evento de alto impacto: {high_impact_events[0].event_name}"
        }
    
    def should_avoid_trading(self, symbol: str, time: datetime = None) -> Tuple[bool, str]:
        """
        Verifica se deve evitar trading
        Retorna (should_avoid, reason)
        """
        time = time or datetime.now()
        
        check = self.is_high_impact_period(symbol, time)
        
        if check['is_high_impact'] and self.avoid_high_impact:
            return True, check.get('reason', 'Evento de alto impacto proximo')
        
        # Verificar eventos medium impact se configurado
        if self.avoid_medium_impact:
            events = self.get_events_for_symbol(
                symbol,
                time - timedelta(minutes=self.buffer_before_minutes),
                time + timedelta(minutes=self.buffer_after_minutes)
            )
            
            medium_events = [e for e in events if e.impact == EventImpact.MEDIUM]
            if medium_events:
                return True, f"Evento de impacto medio: {medium_events[0].event_name}"
        
        return False, ""
    
    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """Retorna eventos nas proximas horas"""
        now = datetime.now()
        end = now + timedelta(hours=hours_ahead)
        
        upcoming = [
            e for e in self._events
            if now <= e.datetime <= end
        ]
        
        # Ordenar e formatar
        upcoming.sort(key=lambda x: x.datetime)
        
        return [
            {
                'datetime': e.datetime.strftime('%Y-%m-%d %H:%M'),
                'currency': e.currency,
                'event': e.event_name,
                'impact': e.impact.value,
                'forecast': e.forecast,
                'previous': e.previous
            }
            for e in upcoming
        ]
    
    def get_high_impact_today(self) -> List[EconomicEvent]:
        """Retorna eventos de alto impacto de hoje"""
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        return [
            e for e in self._events
            if e.datetime.date() == today and e.impact == EventImpact.HIGH
        ]
    
    def get_next_safe_trading_window(self, symbol: str, 
                                     min_duration_minutes: int = 30) -> Optional[Dict]:
        """
        Encontra a proxima janela segura para trading
        """
        now = datetime.now()
        
        # Obter eventos das proximas 24h
        events = self.get_events_for_symbol(
            symbol,
            now,
            now + timedelta(hours=24)
        )
        
        # Filtrar por impacto relevante
        if self.avoid_high_impact:
            events = [e for e in events if e.impact in [EventImpact.HIGH]]
        
        if not events:
            return {
                'start': now.isoformat(),
                'end': (now + timedelta(hours=24)).isoformat(),
                'duration_hours': 24,
                'safe': True
            }
        
        # Encontrar gaps entre eventos
        windows = []
        
        # Janela inicial (agora ate primeiro evento)
        first_event = events[0]
        first_window_end = first_event.datetime - timedelta(minutes=self.buffer_before_minutes)
        
        if first_window_end > now:
            duration = (first_window_end - now).total_seconds() / 60
            if duration >= min_duration_minutes:
                windows.append({
                    'start': now,
                    'end': first_window_end,
                    'duration_minutes': duration
                })
        
        # Janelas entre eventos
        for i in range(len(events) - 1):
            current_event = events[i]
            next_event = events[i + 1]
            
            window_start = current_event.datetime + timedelta(minutes=self.buffer_after_minutes)
            window_end = next_event.datetime - timedelta(minutes=self.buffer_before_minutes)
            
            if window_end > window_start:
                duration = (window_end - window_start).total_seconds() / 60
                if duration >= min_duration_minutes:
                    windows.append({
                        'start': window_start,
                        'end': window_end,
                        'duration_minutes': duration
                    })
        
        if not windows:
            return None
        
        # Retornar primeira janela disponivel
        first_window = windows[0]
        return {
            'start': first_window['start'].isoformat(),
            'end': first_window['end'].isoformat(),
            'duration_minutes': first_window['duration_minutes'],
            'safe': True
        }


# Singleton
_calendar = None

def get_economic_calendar(config: Dict = None) -> EconomicCalendar:
    """Retorna instancia singleton"""
    global _calendar
    if _calendar is None:
        _calendar = EconomicCalendar(config or {})
    return _calendar
