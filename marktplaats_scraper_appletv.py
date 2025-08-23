#!/usr/bin/env python3
"""
Marktplaats TV Monitor - Real-time new listing alerts via Discord
Updated with correct Gemini API implementation (2025)
"""

import time
import json
import requests
import logging
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Set, List, Dict, Optional
from dataclasses import asdict
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import hashlib
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file automatically
except ImportError:
    logging.warning("python-dotenv not installed. Using system environment variables only.")

from marktplaats_tv_scraper import MarktplaatsTVScraper, TVListing

# AI imports removed - simplifying to basic scraping only

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('appletv_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AppleTVMonitor:
    """Monitors Marktplaats for new Apple TV 4K listings and sends Discord alerts."""
    
    def __init__(self, discord_webhook_url: str):
        self.discord_webhook_url = discord_webhook_url
        self.scraper = MarktplaatsTVScraper()
        self.seen_listings_file = Path("seen_appletv_listings.json")
        self.seen_listings: Set[str] = self._load_seen_listings()
        
        # Target URL for Apple TV 4K listings
        self.target_url = "https://www.marktplaats.nl/q/apple%2btv%2b4k/"
        self.sort_params = {
            'sortBy': 'SORT_INDEX',
            'sortOrder': 'DECREASING'
        }
        
        # AI functionality removed for simplified Apple TV monitoring
        
        logger.info(f"🚨 Apple TV 4K Monitor initialized - 🎯 {self.target_url}")
        logger.info(f"📡 Discord: {'✅ Connected' if discord_webhook_url else '❌ Not set'}")
        logger.info(f"📊 Tracking {len(self.seen_listings)} known Apple TV listings")
    
    def _load_seen_listings(self) -> Set[str]:
        """Load previously seen listing IDs from file."""
        if self.seen_listings_file.exists():
            try:
                with open(self.seen_listings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('seen_ids', []))
            except Exception as e:
                logger.warning(f"Failed to load seen listings: {e}")
        return set()
    
    def _save_seen_listings(self):
        """Save seen listing IDs to file."""
        try:
            data = {
                'seen_ids': list(self.seen_listings),
                'last_updated': datetime.now().isoformat(),
                'total_count': len(self.seen_listings)
            }
            with open(self.seen_listings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save seen listings: {e}")
    
    def _create_listing_id(self, listing: TVListing) -> str:
        """Create a unique ID for a listing based on key characteristics."""
        unique_string = f"{listing.title}|{listing.price}|{listing.location}"
        return hashlib.md5(unique_string.encode('utf-8')).hexdigest()[:12]
    
    def _fetch_current_listings(self, silent_mode: bool = False, show_summary: bool = False) -> List[TVListing]:
        """Fetch current listings from the target URL."""
        try:
            logger.debug("🔍 Fetching current listings...")
            
            listings = []
            url = f"{self.target_url}?{urlencode(self.sort_params)}"
            
            logger.debug(f"Scraping URL: {url}")
            
            response = self.scraper.session.get(url, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to fetch page: HTTP {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find listing containers - Use comprehensive search like marktplaats_tv_scraper.py
            listing_elements = []
            
            # Try various listing container patterns based on actual HTML
            listing_patterns = [
                ('li', {'class': 'hz-Listing'}),
                ('li', {'class': 'mp-Listing'}),
                ('div', {'class': 'hz-Listing'}),
                ('div', {'class': 'mp-listing'}),
                ('article', {'class': 'mp-listing'}),
                ('div', {'class': 'listing-item'}),
                ('li', {'class': 'listing'}),
                ('div', {'data-item-id': True}),  # Items with data attributes
                ('a', {'href': re.compile(r'/v/.*/m\d+')}),  # Direct links to any listings
            ]
            
            for tag, attrs in listing_patterns:
                if isinstance(attrs, dict) and 'href' in attrs:
                    # Special handling for regex patterns
                    listing_elements = soup.find_all(tag, attrs)
                else:
                    listing_elements = soup.find_all(tag, attrs)
                    
                if listing_elements:
                    logger.debug(f"📺 Found {len(listing_elements)} elements with pattern {tag} {attrs}")
                    break
            
            # If still no elements found, try a broader search
            if not listing_elements:
                # Look for any elements containing listing URLs
                all_links = soup.find_all('a', href=re.compile(r'/v/.*/m\d+'))
                if all_links:
                    # Get parent containers that might be listing elements
                    for link in all_links:
                        parent = link.find_parent(['li', 'div', 'article'])
                        if parent and parent not in listing_elements:
                            listing_elements.append(parent)
                    logger.debug(f"🍎 Found {len(listing_elements)} elements by link analysis")
            
            logger.debug(f"Found {len(listing_elements)} listing elements total")
            
            for element in listing_elements:
                listing = self.scraper._extract_listing_data(element, soup, silent_mode=silent_mode)
                if listing:
                    listings.append(listing)
            
            # Only log fetch count if not in silent mode
            if not silent_mode:
                logger.info(f"🍎 Fetched {len(listings)} current Apple TV listings")
            
            # Show summary of found listings if requested
            if show_summary and listings:
                logger.info(f"🍎 Current Apple TV 4K listings found ({len(listings)} total):")
                for i, listing in enumerate(listings, 1):  # Show all listings
                    # Clean title for logging
                    clean_title = listing.title.replace('\n', ' ').replace('\r', ' ')
                    clean_title = re.sub(r'€\s*[0-9.,]+details.*$', '', clean_title)
                    clean_title = re.sub(r'details.*$', '', clean_title, flags=re.IGNORECASE)
                    clean_title = re.sub(r'\s+', ' ', clean_title).strip()[:60]
                    logger.info(f"🍎   {i:2d}. {clean_title} | {listing.price} | {listing.location}")
                
            return listings
            
        except Exception as e:
            logger.error(f"Error fetching listings: {e}")
            return []
    
    def _check_for_new_listings(self, show_current_listings: bool = False) -> List[TVListing]:
        """Check for new listings that haven't been seen before."""
        current_listings = self._fetch_current_listings(silent_mode=True, show_summary=show_current_listings)
        new_listings = []
        
        for listing in current_listings:
            listing_id = self._create_listing_id(listing)
            
            if listing_id not in self.seen_listings:
                new_listings.append(listing)
                self.seen_listings.add(listing_id)
                # Clean title for logging
                clean_title = listing.title.replace('\n', ' ').replace('\r', ' ')
                clean_title = re.sub(r'€\s*[0-9.,]+details.*$', '', clean_title)
                clean_title = re.sub(r'details.*$', '', clean_title, flags=re.IGNORECASE)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()[:80]
                logger.info(f"🆕 NEW APPLE TV: {clean_title} | {listing.price} | {listing.location}")
        
        if new_listings:
            self._save_seen_listings()
            logger.info(f"✅ Found {len(new_listings)} new Apple TV listings")
            logger.debug(f"💾 Updated seen listings file with {len(self.seen_listings)} total IDs")
        else:
            logger.debug("No new Apple TV listings found")
        
        return new_listings
    

    

    
    def _format_listing_for_discord(self, listing: TVListing) -> Dict:
        """Format a listing for Discord webhook."""
        logger.debug(f"📨 Formatting Discord embed for listing: {listing.title}")
        
        # Create a rich embed for the listing
        color = 0x1e90ff  # Apple blue color
        title_prefix = "🍎 NEW APPLE TV 4K"
        
        # Discord embed limits:
        # - Title: 256 characters
        # - Description: 4096 characters
        # - Field name: 256 characters
        # - Field value: 1024 characters
        # - Footer text: 2048 characters
        # - Total embed: 6000 characters
        
        # Build description with title and full listing description
        # Discord description field supports up to 4096 characters
        description_parts = []
        
        # Add the listing title (bold formatting)
        if listing.title:
            description_parts.append(f"**{listing.title}**")
        
        # Add the full listing description if available
        if listing.description and len(listing.description.strip()) > 0:
            description_parts.append(f"\n{listing.description.strip()}")
        
        # Combine and ensure we don't exceed Discord's 4096 character limit
        full_description = "\n".join(description_parts)
        if len(full_description) > 4090:  # Leave some buffer
            full_description = full_description[:4087] + "..."
        
        embed = {
            "title": title_prefix,
            "description": full_description,
            "color": color,
            "timestamp": datetime.now().isoformat(),
            "fields": []
        }
        logger.debug(f"📨 Base embed created with title: {title_prefix}, description length: {len(full_description)}")
        
        # Add compact metadata fields in organized rows
        # Row 1: Price, Location, Posted Date
        metadata_row1 = []
        if listing.price:
            metadata_row1.append(f"💰 **{listing.price}**")
        if listing.location:
            metadata_row1.append(f"📍 **{listing.location}**")
        if listing.posting_date:
            metadata_row1.append(f"📅 **{listing.posting_date}**")
        
        if metadata_row1:
            embed["fields"].append({
                "name": "📊 Listing Details",
                "value": " • ".join(metadata_row1),
                "inline": False
            })
        
        # Add seller info as separate field if meaningful
        if listing.seller_name and listing.seller_name not in ["Verkoper onbekend", "Zie advertentie"]:
            embed["fields"].append({
                "name": "👤 Seller",
                "value": listing.seller_name,
                "inline": True
            })
        else:
            logger.debug(f"📺 Skipping seller field (not available in search results)")
        
        # Description is now included in the main embed description field above
        # No need for a separate description field
        
        # Add link if available
        if listing.listing_url:
            if listing.listing_url.startswith('http'):
                # Normal direct link
                embed["fields"].append({
                    "name": "🔗 View Listing", 
                    "value": f"[Click here to view]({listing.listing_url})",
                    "inline": False
                })
            elif listing.listing_url.startswith('#'):
                # Placeholder URL for listings without direct links
                placeholder_text = listing.listing_url[2:]  # Remove "# " prefix
                embed["fields"].append({
                    "name": "ℹ️ Listing Info",
                    "value": placeholder_text,
                    "inline": False
                })
            else:
                # Relative URL - make absolute
                full_link = f"https://www.marktplaats.nl{listing.listing_url}"
                embed["fields"].append({
                    "name": "🔗 View Listing",
                    "value": f"[Click here to view]({full_link})",
                    "inline": False
                })
        
        # Add simple footer with timestamp
        embed["footer"] = {
            "text": f"Apple TV 4K Monitor • {datetime.now().strftime('%Y-%m-%d %I:%M %p')}"
        }
        
        # Final validation
        total_fields = len(embed.get("fields", []))
        logger.debug(f"📨 Embed completed with {total_fields} fields")
        
        # Discord allows max 25 fields per embed
        if total_fields > 25:
            logger.warning(f"📨 Too many fields ({total_fields}), truncating to 25")
            embed["fields"] = embed["fields"][:25]
        
        # Estimate total embed size
        embed_size = len(json.dumps(embed))
        logger.debug(f"📨 Estimated embed size: {embed_size} characters")
        
        if embed_size > 6000:
            logger.warning(f"📨 Embed size ({embed_size}) may exceed Discord limit (6000)")
        
        # Prepare the Discord payload
        payload = {
            "embeds": [embed]
        }
        
        # No special pinging for Apple TV listings - keep it simple
        
        return payload
    
    def _send_discord_notification(self, new_listings: List[TVListing]):
        """Send Discord notification for new Apple TV listings."""
        logger.info(f"📨 Starting Discord notifications for {len(new_listings)} new Apple TV listings")
        
        try:
            for i, listing in enumerate(new_listings, 1):
                logger.info(f"📨 Processing Apple TV listing {i}/{len(new_listings)}: {listing.title}")
                
                # Format notification (simplified without AI analysis)
                logger.debug(f"📨 Formatting Discord payload for: {listing.title}")
                try:
                    payload = self._format_listing_for_discord(listing)
                    logger.debug(f"📨 Payload created. Embed count: {len(payload.get('embeds', []))}")
                    
                    # Validate payload size
                    payload_size = len(json.dumps(payload))
                    logger.debug(f"📨 Payload size: {payload_size} bytes")
                    
                    if payload_size > 6000:  # Discord webhook payload limit
                        logger.warning(f"📨 Payload size ({payload_size}) may exceed Discord limits")
                    
                except Exception as e:
                    logger.error(f"📨 Failed to format Discord payload: {e}")
                    logger.debug("📨 Payload formatting error:", exc_info=True)
                    continue
                
                # Send Discord notification
                logger.debug(f"📨 Sending Discord webhook notification...")
                try:
                    response = requests.post(
                        self.discord_webhook_url,
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    
                    logger.debug(f"📨 Discord response status: {response.status_code}")
                    
                    if response.status_code == 204:
                        logger.info(f"✅ Discord notification sent for Apple TV: {listing.title}")
                    elif response.status_code == 429:
                        logger.error(f"❌ Discord rate limited: {response.status_code}")
                        logger.debug(f"Rate limit headers: {dict(response.headers)}")
                    else:
                        logger.error(f"❌ Discord notification failed: HTTP {response.status_code}")
                        logger.error(f"Response headers: {dict(response.headers)}")
                        logger.error(f"Response body: {response.text[:500]}...")
                        
                except requests.exceptions.Timeout:
                    logger.error(f"❌ Discord notification timed out for: {listing.title}")
                except requests.exceptions.RequestException as e:
                    logger.error(f"❌ Discord request failed for {listing.title}: {e}")
                    logger.debug("📨 Discord request error:", exc_info=True)
                
                # Delay between notifications to respect rate limits
                if len(new_listings) > 1 and i < len(new_listings):  # Don't delay after last notification
                    delay = 1  # Simple 1 second delay without AI processing
                    logger.debug(f"📨 Waiting {delay}s before next notification...")
                    time.sleep(delay)
                    
        except Exception as e:
            logger.error(f"📨 Critical error in Discord notification pipeline: {e}")
            logger.debug("📨 Discord notification pipeline error:", exc_info=True)
    
    def _send_startup_notification(self):
        """Send a notification when the monitor starts."""
        try:
            embed = {
                "title": "🍎 Apple TV 4K Monitor Started",
                "description": "Monitoring for new Apple TV 4K listings on Marktplaats",
                "color": 0x1e90ff,
                "timestamp": datetime.now().isoformat(),
                "fields": [
                    {
                        "name": "🎯 Target",
                        "value": "Apple TV 4K listings",
                        "inline": True
                    },
                    {
                        "name": "⏱️ Check Interval", 
                        "value": "Every 60 seconds",
                        "inline": True
                    },
                    {
                        "name": "💾 Known Listings",
                        "value": f"{len(self.seen_listings)} tracked",
                        "inline": True
                    }
                ]
            }
            
            payload = {"embeds": [embed]}
            
            response = requests.post(
                self.discord_webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 204:
                logger.debug("✅ Startup notification sent to Discord")
            else:
                logger.error(f"❌ Startup notification failed: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending startup notification: {e}")
    
    def run_single_check(self, show_current_listings: bool = False) -> int:
        """Run a single check for new listings. Returns number of new listings found."""
        logger.debug("🔍 Starting single check for new listings")
        
        try:
            start_time = datetime.now()
            new_listings = self._check_for_new_listings(show_current_listings=show_current_listings)
            check_duration = (datetime.now() - start_time).total_seconds()
            
            logger.debug(f"🔍 Check completed in {check_duration:.2f}s")
            
            if new_listings:
                logger.info(f"🎉 Found {len(new_listings)} new TV listings!")
                
                # Send notifications with timing
                notification_start = datetime.now()
                self._send_discord_notification(new_listings)
                notification_duration = (datetime.now() - notification_start).total_seconds()
                
                logger.info(f"📨 Notifications sent in {notification_duration:.2f}s")
                return len(new_listings)
            else:
                logger.debug("No new listings found this check")
                return 0
                
        except Exception as e:
            logger.error(f"😨 Error during listing check: {e}")
            logger.debug("😨 Single check error details:", exc_info=True)
            return 0
    
    def run_monitor(self, check_interval: int = 60):
        """Run the monitoring loop continuously."""
        logger.info(f"🚨 Starting monitor - checking every {check_interval}s")
        
        # Send startup notification
        try:
            self._send_startup_notification()
        except Exception as e:
            logger.warning(f"🚨 Failed to send startup notification: {e}")
        
        # Initialize with current listings
        logger.info("🔄 Initializing...")
        try:
            # Fetch current listings without verbose display
            initial_listings = self._fetch_current_listings(silent_mode=False, show_summary=False)
            for listing in initial_listings:
                listing_id = self._create_listing_id(listing)
                self.seen_listings.add(listing_id)
            
            self._save_seen_listings()
            logger.info(f"✅ Ready! Monitoring {len(initial_listings)} listings")
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            logger.info("🔄 Continuing with empty seen listings...")
        
        try:
            check_count = 0
            consecutive_failures = 0
            max_consecutive_failures = 5
            
            while True:
                check_count += 1
                check_start_time = datetime.now()
                
                # Show alive message every minute with current TV listings
                if check_count % 1 == 0:  # Every check since checks are every 60s
                    logger.info(f"🔄 Monitor alive - Check #{check_count}")
                
                logger.debug(f"🔍 Check #{check_count} at {check_start_time.strftime('%H:%M:%S')}")
                
                try:
                    # Run check without verbose listing display
                    new_count = self.run_single_check(show_current_listings=False)
                    consecutive_failures = 0  # Reset failure counter on success
                    
                    if new_count > 0:
                        logger.info(f"🎊 Alert sent for {new_count} new listings!")
                    
                    # Log performance metrics
                    check_duration = (datetime.now() - check_start_time).total_seconds()
                    logger.debug(f"📈 Check #{check_count} completed in {check_duration:.2f}s")
                    
                except Exception as e:
                    consecutive_failures += 1
                    logger.error(f"❌ Check #{check_count} failed: {e}")
                    logger.debug(f"❌ Check failure details:", exc_info=True)
                    
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(f"❌ Too many consecutive failures ({consecutive_failures}). Stopping monitor.")
                        break
                    else:
                        logger.info(f"🔄 Continuing... ({consecutive_failures}/{max_consecutive_failures} failures)")
                
                # Adaptive sleep with shorter intervals on failures
                sleep_duration = check_interval
                if consecutive_failures > 0:
                    sleep_duration = min(check_interval, 30)  # Shorter sleep on failures
                
                time.sleep(sleep_duration)
                
        except KeyboardInterrupt:
            logger.info("🛑 Monitor stopped by user")
        except Exception as e:
            logger.error(f"❌ Monitor crashed with critical error: {e}")
            logger.debug("❌ Monitor crash details:", exc_info=True)
            raise
        finally:
            try:
                self.scraper.close()
                logger.info("🔒 Monitor shut down gracefully")
            except Exception as e:
                logger.warning(f"🔒 Error during shutdown: {e}")

def main():
    """Main entry point."""
    # Get configuration from environment variables
    DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_URL')
    if not DISCORD_WEBHOOK:
        logger.error("❌ DISCORD_WEBHOOK_URL environment variable is required")
        logger.info("💡 Set environment variable: export DISCORD_WEBHOOK_URL='your-webhook-url'")
        sys.exit(1)
    
    try:
        monitor = AppleTVMonitor(DISCORD_WEBHOOK)
        monitor.run_monitor(check_interval=60)
    except Exception as e:
        logger.error(f"Failed to start Apple TV monitor: {e}")
        raise

if __name__ == "__main__":
    main()