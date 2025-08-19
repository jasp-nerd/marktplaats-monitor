#!/usr/bin/env python3
"""
Configuration settings for Marktplaats TV Monitor
"""

import os
from typing import Optional

# Load environment variables from .env file automatically
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # Continue without dotenv if not installed

def _safe_int_conversion(value: str, default: int) -> int:
    """Safely convert string to int with fallback to default."""
    try:
        result = int(value)
        return result if result > 0 else default
    except (ValueError, TypeError):
        return default


class Config:
    """Configuration class for the TV Monitor."""
    
    # Discord settings
    DISCORD_WEBHOOK_URL: Optional[str] = os.environ.get('DISCORD_WEBHOOK_URL')
    
    # AI settings
    GEMINI_API_KEY: Optional[str] = os.environ.get('GEMINI_API_KEY')
    
    # Monitoring settings  
    CHECK_INTERVAL: int = _safe_int_conversion(os.environ.get('CHECK_INTERVAL', '60'), 60)
    MAX_PAGES: int = _safe_int_conversion(os.environ.get('MAX_PAGES', '3'), 3)
    
    # Notification settings
    SEND_STARTUP_NOTIFICATION: bool = os.environ.get('SEND_STARTUP_NOTIFICATION', 'true').lower() == 'true'
    
    # Scraping settings
    REQUEST_TIMEOUT: int = 10
    DELAY_BETWEEN_REQUESTS: float = 2.0
    DELAY_BETWEEN_NOTIFICATIONS: int = 3
    
    # File paths
    SEEN_LISTINGS_FILE: str = "seen_tv_listings.json"
    LOG_FILE: str = "tv_monitor.log"
    
    # Search settings
    TARGET_URL: str = "https://www.marktplaats.nl/l/audio-tv-en-foto/televisies"
    SORT_PARAMS = {
        'sortBy': 'SORT_INDEX',
        'sortOrder': 'DECREASING'
    }
    
    # Price filters (optional)
    MIN_PRICE: Optional[float] = None
    MAX_PRICE: Optional[float] = None
    
    # Keywords to filter (optional)
    INCLUDE_KEYWORDS: list = []  # Only include listings with these keywords
    EXCLUDE_KEYWORDS: list = []  # Exclude listings with these keywords
    
    @classmethod
    def validate(cls) -> bool:
        """Validate the configuration."""
        if not cls.DISCORD_WEBHOOK_URL:
            print("❌ Error: DISCORD_WEBHOOK_URL is required")
            return False
        
        if not cls.DISCORD_WEBHOOK_URL.startswith('https://discord.com/api/webhooks/'):
            print("❌ Error: Invalid Discord webhook URL format")
            return False
        
        if cls.CHECK_INTERVAL < 30:
            print("⚠️  Warning: CHECK_INTERVAL less than 30 seconds may cause rate limiting")
        
        if cls.GEMINI_API_KEY:
            print("✅ Gemini AI analysis enabled")
        else:
            print("ℹ️  Gemini AI analysis disabled (no API key)")
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration (hiding sensitive data)."""
        print("\n📋 Current Configuration:")
        print(f"  Discord Webhook: {cls.DISCORD_WEBHOOK_URL[:50] + '...' if cls.DISCORD_WEBHOOK_URL else 'Not set'}")
        print(f"  Gemini API Key: {'Set' if cls.GEMINI_API_KEY else 'Not set'}")
        print(f"  Check Interval: {cls.CHECK_INTERVAL} seconds")
        print(f"  Max Pages: {cls.MAX_PAGES}")
        print(f"  Startup Notifications: {cls.SEND_STARTUP_NOTIFICATION}")
        
        if cls.MIN_PRICE or cls.MAX_PRICE:
            print(f"  Price Range: €{cls.MIN_PRICE or 0} - €{cls.MAX_PRICE or '∞'}")
        
        if cls.INCLUDE_KEYWORDS:
            print(f"  Include Keywords: {', '.join(cls.INCLUDE_KEYWORDS)}")
        
        if cls.EXCLUDE_KEYWORDS:
            print(f"  Exclude Keywords: {', '.join(cls.EXCLUDE_KEYWORDS)}")
        
        print()


# Example configurations for different use cases
class DemoConfig(Config):
    """Demo configuration with safe defaults."""
    CHECK_INTERVAL = 120  # 2 minutes for demo
    MAX_PAGES = 2
    SEND_STARTUP_NOTIFICATION = False


class ProductionConfig(Config):
    """Production configuration with optimized settings."""
    CHECK_INTERVAL = 60  # 1 minute
    MAX_PAGES = 3
    DELAY_BETWEEN_REQUESTS = 3.0  # Be more polite to the server
    SEND_STARTUP_NOTIFICATION = True


class DevelopmentConfig(Config):
    """Development configuration for testing."""
    CHECK_INTERVAL = 300  # 5 minutes to avoid spam during development
    MAX_PAGES = 1
    SEND_STARTUP_NOTIFICATION = False
