"""
Auto Trading Service - Main entry point for automated crypto trading
This file maintains backward compatibility while delegating to split services
"""
import logging

# Import from the new split services

from services.trading_commands import (
    AUTO_TRADE_JOB_ID as _AUTO_TRADE_JOB_ID,
    AI_TRADE_JOB_ID as _AI_TRADE_JOB_ID,
)


logger = logging.getLogger(__name__)


# Backward compatibility - re-export main functions
# All the actual implementation is now in the split service files

# These constants are kept for backward compatibility
AUTO_TRADE_JOB_ID = _AUTO_TRADE_JOB_ID
AI_TRADE_JOB_ID = _AI_TRADE_JOB_ID
