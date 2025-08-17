"""
Tests for WebSocket message parser.
"""

import pytest
from datetime import datetime, timezone
from src.data.websocket_parser import (
    SchwabMessageParser,
    MessageType,
    ServiceType,
    ParsedMessage,
    Tick,
    TickType
)


class TestSchwabMessageParser:
    """Test suite for Schwab WebSocket message parser."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return SchwabMessageParser()
    
    def test_parse_response_message(self, parser):
        """Test parsing response messages."""
        message = {
            "response": [{
                "service": "ADMIN",
                "command": "LOGIN",
                "requestid": 1,
                "content": {
                    "code": 0,
                    "msg": "Login successful"
                }
            }]
        }
        
        parsed = parser.parse(message)
        
        assert parsed.message_type == MessageType.RESPONSE
        assert parsed.service == ServiceType.ADMIN
        assert parsed.command == "LOGIN"
        assert parsed.request_id == 1
        assert len(parsed.content) == 1
        assert parsed.content[0]["code"] == 0
        assert parsed.content[0]["msg"] == "Login successful"
    
    def test_parse_error_response(self, parser):
        """Test parsing error response."""
        message = {
            "response": [{
                "service": "QUOTE",
                "command": "SUBS",
                "requestid": 2,
                "content": {
                    "code": 500,
                    "msg": "Invalid symbol"
                }
            }]
        }
        
        parsed = parser.parse(message)
        
        assert parsed.is_response
        assert parsed.is_error  # Should detect error code != 0
        assert parsed.content[0]["code"] == 500
    
    def test_parse_quote_data_message(self, parser):
        """Test parsing quote data messages with field mapping."""
        message = {
            "data": [{
                "service": "QUOTE",
                "timestamp": 1640995200000,  # 2022-01-01 00:00:00 UTC
                "content": [{
                    "key": "AAPL",
                    "1": 150.50,  # BID_PRICE
                    "2": 150.55,  # ASK_PRICE
                    "3": 150.52,  # LAST_PRICE
                    "4": 100,     # BID_SIZE
                    "5": 200,     # ASK_SIZE
                    "8": 1234567, # TOTAL_VOLUME
                    "50": 1640995200000  # QUOTE_TIME_IN_MILLIS
                }]
            }]
        }
        
        parsed = parser.parse(message)
        
        assert parsed.message_type == MessageType.DATA
        assert parsed.service == ServiceType.QUOTE
        assert len(parsed.content) == 1
        
        content = parsed.content[0]
        assert content["key"] == "AAPL"
        assert content["BID_PRICE"] == 150.50
        assert content["ASK_PRICE"] == 150.55
        assert content["LAST_PRICE"] == 150.52
        assert content["BID_SIZE"] == 100
        assert content["ASK_SIZE"] == 200
        assert content["TOTAL_VOLUME"] == 1234567
        assert content["QUOTE_TIME_IN_MILLIS"] == 1640995200000
    
    def test_parse_timesale_data_message(self, parser):
        """Test parsing time & sales data messages."""
        message = {
            "data": [{
                "service": "TIMESALE",
                "timestamp": 1640995200000,
                "content": [{
                    "key": "AAPL",
                    "0": "AAPL",      # SYMBOL
                    "1": 1640995200,  # TRADE_TIME
                    "2": 150.52,      # LAST_PRICE
                    "3": 100,         # LAST_SIZE
                    "4": 12345        # LAST_SEQUENCE
                }]
            }]
        }
        
        parsed = parser.parse(message)
        
        assert parsed.service == ServiceType.TIMESALE
        content = parsed.content[0]
        assert content["SYMBOL"] == "AAPL"
        assert content["TRADE_TIME"] == 1640995200
        assert content["LAST_PRICE"] == 150.52
        assert content["LAST_SIZE"] == 100
        assert content["LAST_SEQUENCE"] == 12345
    
    def test_parse_notify_message(self, parser):
        """Test parsing notify messages."""
        message = {
            "notify": [{
                "service": "ADMIN",
                "content": {
                    "code": 0,
                    "msg": "Heartbeat"
                }
            }]
        }
        
        parsed = parser.parse(message)
        
        assert parsed.message_type == MessageType.NOTIFY
        assert parsed.service == ServiceType.ADMIN
        assert parsed.content[0]["msg"] == "Heartbeat"
    
    def test_to_ticks_from_quote_data(self, parser):
        """Test converting quote data to tick objects."""
        parsed = ParsedMessage(
            message_type=MessageType.DATA,
            service=ServiceType.QUOTE,
            command="UPDATE",
            content=[{
                "key": "AAPL",
                "BID_PRICE": 150.50,
                "ASK_PRICE": 150.55,
                "LAST_PRICE": 150.52,
                "BID_SIZE": 100,
                "ASK_SIZE": 200,
                "LAST_SIZE": 50,
                "QUOTE_TIME_IN_MILLIS": 1640995200000,
                "TRADE_TIME_IN_MILLIS": 1640995201000,
                "EXCHANGE_NAME": "NASDAQ"
            }],
            timestamp=datetime.fromtimestamp(1640995200, tz=timezone.utc)
        )
        
        ticks = parser.to_ticks(parsed)
        
        # Should create bid, ask, and trade ticks
        assert len(ticks) == 3
        
        # Check bid tick
        bid_tick = next(t for t in ticks if t.tick_type == TickType.BID)
        assert bid_tick.symbol == "AAPL"
        assert bid_tick.price == 150.50
        assert bid_tick.volume == 100
        assert bid_tick.bid_price == 150.50
        assert bid_tick.ask_price == 150.55
        assert bid_tick.exchange == "NASDAQ"
        
        # Check ask tick
        ask_tick = next(t for t in ticks if t.tick_type == TickType.ASK)
        assert ask_tick.price == 150.55
        assert ask_tick.volume == 200
        
        # Check trade tick
        trade_tick = next(t for t in ticks if t.tick_type == TickType.TRADE)
        assert trade_tick.price == 150.52
        assert trade_tick.volume == 50
        # Trade should have different timestamp
        assert trade_tick.timestamp != bid_tick.timestamp
    
    def test_to_ticks_from_timesale_data(self, parser):
        """Test converting time & sales data to tick objects."""
        parsed = ParsedMessage(
            message_type=MessageType.DATA,
            service=ServiceType.TIMESALE,
            command="UPDATE",
            content=[{
                "key": "AAPL",
                "LAST_PRICE": 150.52,
                "LAST_SIZE": 100,
                "TRADE_TIME": 1640995200000,
                "LAST_SEQUENCE": 12345
            }],
            timestamp=datetime.fromtimestamp(1640995200, tz=timezone.utc)
        )
        
        ticks = parser.to_ticks(parsed)
        
        assert len(ticks) == 1
        tick = ticks[0]
        assert tick.symbol == "AAPL"
        assert tick.price == 150.52
        assert tick.volume == 100
        assert tick.tick_type == TickType.TRADE
        assert tick.sequence_id == 12345
    
    def test_to_ticks_non_data_message(self, parser):
        """Test that non-data messages return empty tick list."""
        parsed = ParsedMessage(
            message_type=MessageType.RESPONSE,
            service=ServiceType.ADMIN,
            command="LOGIN",
            content=[{"code": 0}],
            timestamp=datetime.now(timezone.utc)
        )
        
        ticks = parser.to_ticks(parsed)
        assert len(ticks) == 0
    
    def test_extract_quotes(self, parser):
        """Test extracting quote data for Quote object creation."""
        content = {
            "key": "AAPL",
            "BID_PRICE": 150.50,
            "ASK_PRICE": 150.55,
            "LAST_PRICE": 150.52,
            "BID_SIZE": 100,
            "ASK_SIZE": 200,
            "LAST_SIZE": 50,
            "TOTAL_VOLUME": 1234567,
            "HIGH_PRICE": 151.00,
            "LOW_PRICE": 149.50,
            "OPEN_PRICE": 150.00,
            "CLOSE_PRICE": 150.25,
            "MARK": 150.53,
            "EXCHANGE_NAME": "NASDAQ",
            "QUOTE_TIME_IN_MILLIS": 1640995200000,
            "TRADE_TIME_IN_MILLIS": 1640995201000
        }
        
        quote_data = parser.extract_quotes(content)
        
        assert quote_data["symbol"] == "AAPL"
        assert quote_data["bid_price"] == 150.50
        assert quote_data["ask_price"] == 150.55
        assert quote_data["last_price"] == 150.52
        assert quote_data["volume"] == 1234567
        assert quote_data["high"] == 151.00
        assert quote_data["low"] == 149.50
        assert quote_data["mark"] == 150.53
    
    def test_extract_chart_data(self, parser):
        """Test extracting OHLCV chart data."""
        content = {
            "key": "AAPL",
            "OPEN_PRICE": 150.00,
            "HIGH_PRICE": 151.00,
            "LOW_PRICE": 149.50,
            "CLOSE_PRICE": 150.75,
            "VOLUME": 50000,
            "SEQUENCE": 123,
            "CHART_TIME": 1640995200000,
            "CHART_DAY": 1
        }
        
        chart_data = parser.extract_chart_data(content)
        
        assert chart_data["symbol"] == "AAPL"
        assert chart_data["open"] == 150.00
        assert chart_data["high"] == 151.00
        assert chart_data["low"] == 149.50
        assert chart_data["close"] == 150.75
        assert chart_data["volume"] == 50000
        assert chart_data["sequence"] == 123
        assert chart_data["chart_time"] == 1640995200000
    
    def test_parse_invalid_json(self, parser):
        """Test handling of invalid JSON."""
        with pytest.raises(ValueError, match="Invalid JSON message"):
            parser.parse("invalid json{")
    
    def test_parse_unknown_message_format(self, parser):
        """Test handling of unknown message format."""
        with pytest.raises(ValueError, match="Unknown message format"):
            parser.parse({"unknown": "format"})
    
    def test_field_mapping_with_string_keys(self, parser):
        """Test field mapping when keys are strings instead of integers."""
        message = {
            "data": [{
                "service": "QUOTE",
                "timestamp": 1640995200000,
                "content": [{
                    "key": "AAPL",
                    "1": 150.50,  # Numeric key
                    "2": 150.55,
                    "BID_SIZE": 100,  # Already mapped field
                    "CUSTOM_FIELD": "value"  # Unmapped field
                }]
            }]
        }
        
        parsed = parser.parse(message)
        content = parsed.content[0]
        
        # Should map numeric fields
        assert content["BID_PRICE"] == 150.50
        assert content["ASK_PRICE"] == 150.55
        # Should preserve already mapped fields
        assert content["BID_SIZE"] == 100
        # Should include unmapped fields
        assert content["CUSTOM_FIELD"] == "value"
    
    def test_multiple_symbols_in_data(self, parser):
        """Test parsing data with multiple symbols."""
        message = {
            "data": [{
                "service": "QUOTE",
                "timestamp": 1640995200000,
                "content": [
                    {
                        "key": "AAPL",
                        "1": 150.50,
                        "2": 150.55,
                        "3": 150.52
                    },
                    {
                        "key": "GOOGL", 
                        "1": 2800.00,
                        "2": 2800.50,
                        "3": 2800.25
                    }
                ]
            }]
        }
        
        parsed = parser.parse(message)
        assert len(parsed.content) == 2
        
        # Check both symbols are parsed correctly
        aapl = next(c for c in parsed.content if c["key"] == "AAPL")
        googl = next(c for c in parsed.content if c["key"] == "GOOGL")
        
        assert aapl["BID_PRICE"] == 150.50
        assert googl["BID_PRICE"] == 2800.00
    
    def test_missing_optional_fields(self, parser):
        """Test handling of missing optional fields."""
        parsed = ParsedMessage(
            message_type=MessageType.DATA,
            service=ServiceType.QUOTE,
            command="UPDATE",
            content=[{
                "key": "AAPL",
                "BID_PRICE": 150.50,
                # Missing ASK_PRICE, LAST_PRICE, sizes, etc.
            }],
            timestamp=datetime.now(timezone.utc)
        )
        
        ticks = parser.to_ticks(parsed)
        
        # Should only create bid tick
        assert len(ticks) == 1
        assert ticks[0].tick_type == TickType.BID
        assert ticks[0].price == 150.50
        assert ticks[0].ask_price is None