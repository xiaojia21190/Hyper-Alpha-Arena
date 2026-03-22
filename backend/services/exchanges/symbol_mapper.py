"""
Symbol mapping utilities for multi-exchange support.

Handles bidirectional conversion between internal symbol format (e.g., "BTC")
and exchange-specific formats (e.g., "BTCUSDT" for Binance).
"""

import logging

logger = logging.getLogger(__name__)


class SymbolMapper:
    """
    Bidirectional symbol mapper for exchange-specific symbol formats.

    Internal format: "BTC", "ETH" (base currency only)
    Binance format: "BTCUSDT", "ETHUSDT" (with quote currency suffix)
    Hyperliquid format: "BTC", "ETH" (same as internal)
    """

    # Quote currency for each exchange's perpetual contracts
    EXCHANGE_QUOTE_CURRENCY = {
        "binance": "USDT",
        "hyperliquid": "",  # Hyperliquid uses base currency only
    }

    # Special symbol mappings (if any symbol has non-standard naming)
    SPECIAL_MAPPINGS = {
        "binance": {
            # internal -> exchange
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
            # Add special cases here if needed
        }
    }

    REVERSE_MAPPINGS = {
        "binance": {
            # exchange -> internal
            "BTCUSDT": "BTC",
            "ETHUSDT": "ETH",
        }
    }

    @classmethod
    def to_exchange(cls, symbol: str, exchange: str) -> str:
        """
        Convert internal symbol to exchange-specific format.

        Args:
            symbol: Internal symbol (e.g., "BTC")
            exchange: Exchange name (e.g., "binance")

        Returns:
            Exchange-specific symbol (e.g., "BTCUSDT")
        """
        exchange = exchange.lower()

        if exchange == "hyperliquid":
            return symbol

        # Check special mappings first
        special = cls.SPECIAL_MAPPINGS.get(exchange, {})
        if symbol in special:
            return special[symbol]

        # Default conversion: append quote currency
        quote = cls.EXCHANGE_QUOTE_CURRENCY.get(exchange, "")
        if quote:
            return f"{symbol}{quote}"

        return symbol

    @classmethod
    def to_internal(cls, symbol: str, exchange: str) -> str:
        """
        Convert exchange-specific symbol to internal format.

        Args:
            symbol: Exchange symbol (e.g., "BTCUSDT")
            exchange: Exchange name (e.g., "binance")

        Returns:
            Internal symbol (e.g., "BTC")
        """
        exchange = exchange.lower()

        if exchange == "hyperliquid":
            return symbol

        # Check reverse mappings first
        reverse = cls.REVERSE_MAPPINGS.get(exchange, {})
        if symbol in reverse:
            return reverse[symbol]

        # Default conversion: strip quote currency suffix
        quote = cls.EXCHANGE_QUOTE_CURRENCY.get(exchange, "")
        if quote and symbol.endswith(quote):
            return symbol[:-len(quote)]

        return symbol

    @classmethod
    def get_supported_symbols(cls, exchange: str) -> list:
        """Get list of supported symbols for an exchange."""
        # This could be expanded to fetch from exchange API
        return ["BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "AVAX", "LINK"]
