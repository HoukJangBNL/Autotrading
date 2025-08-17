"""
WebSocket message parser for Schwab streaming data.

This module parses Schwab WebSocket messages and converts them to internal Tick format
for processing by the Stream Processor.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import logging

from .stream_processor import Tick, TickType

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Schwab WebSocket message types."""
    RESPONSE = "response"
    DATA = "data"
    NOTIFY = "notify"
    SNAPSHOT = "snapshot"
    UPDATE = "update"
    ERROR = "error"


class ServiceType(str, Enum):
    """Schwab streaming service types."""
    ADMIN = "ADMIN"
    QUOTE = "QUOTE"
    TIMESALE = "TIMESALE"
    LEVEL_ONE_FUTURES = "LEVEL_ONE_FUTURES"
    LEVEL_ONE_FOREX = "LEVEL_ONE_FOREX"
    LEVEL_ONE_FUTURES_OPTIONS = "LEVEL_ONE_FUTURES_OPTIONS"
    OPTION = "OPTION"
    NEWS_HEADLINE = "NEWS_HEADLINE"
    CHART_EQUITY = "CHART_EQUITY"
    CHART_FUTURES = "CHART_FUTURES"
    NASDAQ_BOOK = "NASDAQ_BOOK"
    NYSE_BOOK = "NYSE_BOOK"
    OPTIONS_BOOK = "OPTIONS_BOOK"
    ACCT_ACTIVITY = "ACCT_ACTIVITY"


@dataclass
class ParsedMessage:
    """Parsed WebSocket message."""
    message_type: MessageType
    service: Optional[ServiceType]
    command: Optional[str]
    content: List[Dict[str, Any]]
    timestamp: datetime
    request_id: Optional[int] = None
    
    @property
    def is_data_message(self) -> bool:
        """Check if this is a data message."""
        return self.message_type == MessageType.DATA
    
    @property
    def is_response(self) -> bool:
        """Check if this is a response message."""
        return self.message_type == MessageType.RESPONSE
    
    @property
    def is_error(self) -> bool:
        """Check if this is an error message."""
        return self.message_type == MessageType.ERROR or (
            self.is_response and any(
                item.get('content', {}).get('code', 0) != 0
                for item in self.content
            )
        )


class SchwabMessageParser:
    """
    Parses Schwab WebSocket messages into internal format.
    
    Handles:
    - Quote updates (bid/ask/last)
    - Trade notifications
    - Level 2 data (if subscribed)
    - System messages
    """
    
    # Field mappings for Level 1 Equity quotes
    QUOTE_FIELDS = {
        0: "SYMBOL",
        1: "BID_PRICE",
        2: "ASK_PRICE",
        3: "LAST_PRICE",
        4: "BID_SIZE",
        5: "ASK_SIZE",
        6: "ASK_ID",
        7: "BID_ID",
        8: "TOTAL_VOLUME",
        9: "LAST_SIZE",
        10: "TRADE_TIME",
        11: "QUOTE_TIME",
        12: "HIGH_PRICE",
        13: "LOW_PRICE",
        14: "BID_TICK",
        15: "CLOSE_PRICE",
        16: "EXCHANGE_ID",
        17: "MARGINABLE",
        18: "SHORTABLE",
        19: "ISLAND_BID",
        20: "ISLAND_ASK",
        21: "ISLAND_VOLUME",
        22: "QUOTE_DAY",
        23: "TRADE_DAY",
        24: "VOLATILITY",
        25: "DESCRIPTION",
        26: "LAST_ID",
        27: "DIGITS",
        28: "OPEN_PRICE",
        29: "NET_CHANGE",
        30: "HIGH_52_WEEK",
        31: "LOW_52_WEEK",
        32: "PE_RATIO",
        33: "DIVIDEND_AMOUNT",
        34: "DIVIDEND_YIELD",
        35: "ISLAND_BID_SIZE",
        36: "ISLAND_ASK_SIZE",
        37: "NAV",
        38: "FUND_PRICE",
        39: "EXCHANGE_NAME",
        40: "DIVIDEND_DATE",
        41: "REGULAR_MARKET_QUOTE",
        42: "REGULAR_MARKET_TRADE",
        43: "REGULAR_MARKET_LAST_PRICE",
        44: "REGULAR_MARKET_LAST_SIZE",
        45: "REGULAR_MARKET_TRADE_TIME",
        46: "REGULAR_MARKET_TRADE_DAY",
        47: "REGULAR_MARKET_NET_CHANGE",
        48: "SECURITY_STATUS",
        49: "MARK",
        50: "QUOTE_TIME_IN_MILLIS",
        51: "TRADE_TIME_IN_MILLIS",
        52: "REGULAR_MARKET_TRADE_TIME_IN_MILLIS"
    }
    
    # Field mappings for Time & Sales (trades)
    TIMESALE_FIELDS = {
        0: "SYMBOL",
        1: "TRADE_TIME",
        2: "LAST_PRICE",
        3: "LAST_SIZE",
        4: "LAST_SEQUENCE"
    }
    
    # Field mappings for Chart data
    CHART_FIELDS = {
        0: "SYMBOL",
        1: "OPEN_PRICE",
        2: "HIGH_PRICE",
        3: "LOW_PRICE",
        4: "CLOSE_PRICE",
        5: "VOLUME",
        6: "SEQUENCE",
        7: "CHART_TIME",
        8: "CHART_DAY"
    }
    
    def __init__(self):
        """Initialize message parser."""
        self._field_maps = {
            ServiceType.QUOTE: self.QUOTE_FIELDS,
            ServiceType.TIMESALE: self.TIMESALE_FIELDS,
            ServiceType.CHART_EQUITY: self.CHART_FIELDS,
            ServiceType.CHART_FUTURES: self.CHART_FIELDS
        }
    
    def parse(self, raw_message: Union[str, Dict[str, Any]]) -> ParsedMessage:
        """
        Parse raw WebSocket message.
        
        Args:
            raw_message: Raw message string or dict
            
        Returns:
            ParsedMessage object
        """
        if isinstance(raw_message, str):
            import json
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                raise ValueError(f"Invalid JSON message: {e}")
        else:
            data = raw_message
        
        # Determine message type
        if "response" in data:
            return self._parse_response(data)
        elif "data" in data:
            return self._parse_data(data)
        elif "notify" in data:
            return self._parse_notify(data)
        else:
            raise ValueError(f"Unknown message format: {list(data.keys())}")
    
    def _parse_response(self, data: Dict[str, Any]) -> ParsedMessage:
        """Parse response message."""
        responses = data.get("response", [])
        
        content = []
        request_id = None
        service = None
        command = None
        
        for response in responses:
            content.append(response.get("content", {}))
            if not request_id:
                request_id = response.get("requestid")
            if not service:
                service = ServiceType(response.get("service", "ADMIN"))
            if not command:
                command = response.get("command")
        
        return ParsedMessage(
            message_type=MessageType.RESPONSE,
            service=service,
            command=command,
            content=content,
            timestamp=datetime.now(timezone.utc),
            request_id=request_id
        )
    
    def _parse_data(self, data: Dict[str, Any]) -> ParsedMessage:
        """Parse data message."""
        data_items = data.get("data", [])
        
        all_content = []
        service = None
        
        for item in data_items:
            service_name = item.get("service", "")
            if service_name:
                service = ServiceType(service_name)
            
            timestamp = item.get("timestamp", 0)
            content_list = item.get("content", [])
            
            # Apply field mapping if available
            if service in self._field_maps:
                field_map = self._field_maps[service]
                mapped_content = []
                
                for content in content_list:
                    mapped_item = {"key": content.get("key")}
                    
                    # Map numeric fields to names
                    for field_num, field_name in field_map.items():
                        if str(field_num) in content:
                            mapped_item[field_name] = content[str(field_num)]
                        elif field_num in content:
                            mapped_item[field_name] = content[field_num]
                    
                    # Include any unmapped fields
                    for key, value in content.items():
                        if key not in ["key"] and key not in mapped_item:
                            mapped_item[key] = value
                    
                    mapped_content.append(mapped_item)
                
                all_content.extend(mapped_content)
            else:
                all_content.extend(content_list)
        
        return ParsedMessage(
            message_type=MessageType.DATA,
            service=service,
            command="UPDATE",
            content=all_content,
            timestamp=datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc) if timestamp else datetime.now(timezone.utc)
        )
    
    def _parse_notify(self, data: Dict[str, Any]) -> ParsedMessage:
        """Parse notify message."""
        notifications = data.get("notify", [])
        
        content = []
        service = None
        
        for notification in notifications:
            content.append(notification.get("content", {}))
            if not service:
                service = ServiceType(notification.get("service", "ADMIN"))
        
        return ParsedMessage(
            message_type=MessageType.NOTIFY,
            service=service,
            command="NOTIFY",
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
    
    def to_ticks(self, parsed: ParsedMessage) -> List[Tick]:
        """
        Convert parsed message to Tick objects.
        
        Args:
            parsed: ParsedMessage object
            
        Returns:
            List of Tick objects
        """
        if not parsed.is_data_message:
            return []
        
        ticks = []
        
        if parsed.service == ServiceType.QUOTE:
            ticks.extend(self._extract_quote_ticks(parsed))
        elif parsed.service == ServiceType.TIMESALE:
            ticks.extend(self._extract_trade_ticks(parsed))
        elif parsed.service in [ServiceType.CHART_EQUITY, ServiceType.CHART_FUTURES]:
            # Chart data is OHLCV bars, not individual ticks
            # Stream processor will handle these differently
            pass
        
        return ticks
    
    def _extract_quote_ticks(self, parsed: ParsedMessage) -> List[Tick]:
        """Extract quote ticks from message content."""
        ticks = []
        
        for content in parsed.content:
            symbol = content.get("key") or content.get("SYMBOL")
            if not symbol:
                continue
            
            # Extract bid/ask data
            bid_price = content.get("BID_PRICE")
            ask_price = content.get("ASK_PRICE")
            last_price = content.get("LAST_PRICE")
            bid_size = content.get("BID_SIZE", 0)
            ask_size = content.get("ASK_SIZE", 0)
            last_size = content.get("LAST_SIZE", 0)
            
            # Get timestamp
            quote_time = content.get("QUOTE_TIME_IN_MILLIS", content.get("QUOTE_TIME"))
            if quote_time:
                timestamp = datetime.fromtimestamp(quote_time / 1000, tz=timezone.utc)
            else:
                timestamp = parsed.timestamp
            
            # Create bid tick
            if bid_price is not None and bid_price > 0:
                bid_tick = Tick(
                    symbol=symbol,
                    price=float(bid_price),
                    volume=int(bid_size),
                    timestamp=timestamp,
                    tick_type=TickType.BID,
                    bid_price=float(bid_price),
                    ask_price=float(ask_price) if ask_price else None,
                    bid_size=int(bid_size),
                    ask_size=int(ask_size) if ask_size else None,
                    exchange=content.get("EXCHANGE_NAME")
                )
                ticks.append(bid_tick)
            
            # Create ask tick
            if ask_price is not None and ask_price > 0:
                ask_tick = Tick(
                    symbol=symbol,
                    price=float(ask_price),
                    volume=int(ask_size),
                    timestamp=timestamp,
                    tick_type=TickType.ASK,
                    bid_price=float(bid_price) if bid_price else None,
                    ask_price=float(ask_price),
                    bid_size=int(bid_size) if bid_size else None,
                    ask_size=int(ask_size),
                    exchange=content.get("EXCHANGE_NAME")
                )
                ticks.append(ask_tick)
            
            # Create trade tick if last price is different from bid/ask
            if last_price is not None and last_price > 0:
                # Check if this is a new trade (not just bid/ask update)
                trade_time = content.get("TRADE_TIME_IN_MILLIS", content.get("TRADE_TIME"))
                if trade_time and trade_time != quote_time:
                    trade_timestamp = datetime.fromtimestamp(trade_time / 1000, tz=timezone.utc)
                    
                    trade_tick = Tick(
                        symbol=symbol,
                        price=float(last_price),
                        volume=int(last_size),
                        timestamp=trade_timestamp,
                        tick_type=TickType.TRADE,
                        bid_price=float(bid_price) if bid_price else None,
                        ask_price=float(ask_price) if ask_price else None,
                        bid_size=int(bid_size) if bid_size else None,
                        ask_size=int(ask_size) if ask_size else None,
                        exchange=content.get("LAST_ID")
                    )
                    ticks.append(trade_tick)
        
        return ticks
    
    def _extract_trade_ticks(self, parsed: ParsedMessage) -> List[Tick]:
        """Extract trade ticks from time & sales data."""
        ticks = []
        
        for content in parsed.content:
            symbol = content.get("key") or content.get("SYMBOL")
            if not symbol:
                continue
            
            last_price = content.get("LAST_PRICE")
            last_size = content.get("LAST_SIZE", 0)
            
            if last_price is None or last_price <= 0:
                continue
            
            # Get timestamp
            trade_time = content.get("TRADE_TIME")
            if trade_time:
                timestamp = datetime.fromtimestamp(trade_time / 1000, tz=timezone.utc)
            else:
                timestamp = parsed.timestamp
            
            trade_tick = Tick(
                symbol=symbol,
                price=float(last_price),
                volume=int(last_size),
                timestamp=timestamp,
                tick_type=TickType.TRADE,
                sequence_id=content.get("LAST_SEQUENCE")
            )
            ticks.append(trade_tick)
        
        return ticks
    
    def extract_quotes(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract quote data from message content.
        
        Returns a dictionary with quote information that can be used
        to create Quote objects or update existing ones.
        """
        return {
            'symbol': content.get('key') or content.get('SYMBOL'),
            'bid_price': content.get('BID_PRICE'),
            'ask_price': content.get('ASK_PRICE'),
            'last_price': content.get('LAST_PRICE'),
            'bid_size': content.get('BID_SIZE'),
            'ask_size': content.get('ASK_SIZE'),
            'last_size': content.get('LAST_SIZE'),
            'volume': content.get('TOTAL_VOLUME'),
            'high': content.get('HIGH_PRICE'),
            'low': content.get('LOW_PRICE'),
            'open': content.get('OPEN_PRICE'),
            'close': content.get('CLOSE_PRICE'),
            'mark': content.get('MARK'),
            'exchange': content.get('EXCHANGE_NAME'),
            'quote_time': content.get('QUOTE_TIME_IN_MILLIS'),
            'trade_time': content.get('TRADE_TIME_IN_MILLIS')
        }
    
    def extract_chart_data(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract OHLCV chart data from message content.
        
        Returns a dictionary with chart bar information.
        """
        return {
            'symbol': content.get('key') or content.get('SYMBOL'),
            'open': content.get('OPEN_PRICE'),
            'high': content.get('HIGH_PRICE'),
            'low': content.get('LOW_PRICE'),
            'close': content.get('CLOSE_PRICE'),
            'volume': content.get('VOLUME'),
            'sequence': content.get('SEQUENCE'),
            'chart_time': content.get('CHART_TIME'),
            'chart_day': content.get('CHART_DAY')
        }