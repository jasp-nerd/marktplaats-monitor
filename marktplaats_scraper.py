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

# Import Gemini AI - Updated import
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    try:
        # Fallback to google-generativeai if google-genai not available
        import google.generativeai as genai
        GEMINI_AVAILABLE = True
        LEGACY_GEMINI = True
    except ImportError:
        GEMINI_AVAILABLE = False
        LEGACY_GEMINI = False
        logging.warning("Neither google-genai nor google-generativeai installed. Run: pip install google-genai")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tv_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TVMonitor:
    """Monitors Marktplaats for new TV listings and sends Discord alerts with AI analysis."""
    
    def __init__(self, discord_webhook_url: str, gemini_api_key: Optional[str] = None):
        self.discord_webhook_url = discord_webhook_url
        self.scraper = MarktplaatsTVScraper()
        self.seen_listings_file = Path("seen_tv_listings.json")
        self.seen_listings: Set[str] = self._load_seen_listings()
        
        # Target URL with newest TVs
        self.target_url = "https://www.marktplaats.nl/l/audio-tv-en-foto/televisies"
        self.sort_params = {
            'sortBy': 'SORT_INDEX',
            'sortOrder': 'DECREASING'
        }
        
        # Initialize Gemini AI with updated API
        self.ai_enabled = False
        self.client = None
        
        if GEMINI_AVAILABLE and gemini_api_key:
            try:
                # Configure the modern google-genai client
                self.client = genai.Client(api_key=gemini_api_key)
                self.ai_enabled = True
                logger.debug("🤖 Gemini AI analysis enabled with Google Search grounding (google-genai)")
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid Gemini API key or configuration: {e}")
            except ImportError as e:
                logger.error(f"Gemini dependencies not properly installed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error initializing Gemini AI: {e}")
                logger.debug("Gemini initialization error details:", exc_info=True)
        elif not gemini_api_key:
            logger.debug("🤖 Gemini AI disabled - no API key provided")
        else:
            logger.debug("🤖 Gemini AI disabled - google-genai not installed")
        
        logger.info(f"🚨 TV Monitor initialized - 🎯 {self.target_url}")
        logger.info(f"📡 Discord: {'✅ Connected' if discord_webhook_url else '❌ Not set'} | 🤖 Gemini AI: {'✅ Active' if self.ai_enabled else '❌ Disabled'}")
        logger.info(f"📊 Tracking {len(self.seen_listings)} known listings")
    
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
                ('a', {'href': re.compile(r'/v/audio-tv-en-foto/televisies/m\d+')}),  # Direct links to TV listings
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
                # Look for any elements containing TV listing URLs
                all_links = soup.find_all('a', href=re.compile(r'/v/.*/televisies/'))
                if all_links:
                    # Get parent containers that might be listing elements
                    for link in all_links:
                        parent = link.find_parent(['li', 'div', 'article'])
                        if parent and parent not in listing_elements:
                            listing_elements.append(parent)
                    logger.debug(f"📺 Found {len(listing_elements)} elements by link analysis")
            
            logger.debug(f"Found {len(listing_elements)} listing elements total")
            
            for element in listing_elements:
                listing = self.scraper._extract_listing_data(element, soup, silent_mode=silent_mode)
                if listing:
                    listings.append(listing)
            
            # Only log fetch count if not in silent mode
            if not silent_mode:
                logger.info(f"📺 Fetched {len(listings)} current listings")
            
            # Show summary of found listings if requested
            if show_summary and listings:
                logger.info(f"📺 Current TV listings found ({len(listings)} total):")
                for i, listing in enumerate(listings, 1):  # Show all listings
                    # Clean title for logging
                    clean_title = listing.title.replace('\n', ' ').replace('\r', ' ')
                    clean_title = re.sub(r'€\s*[0-9.,]+details.*$', '', clean_title)
                    clean_title = re.sub(r'details.*$', '', clean_title, flags=re.IGNORECASE)
                    clean_title = re.sub(r'\s+', ' ', clean_title).strip()[:60]
                    logger.info(f"📺   {i:2d}. {clean_title} | {listing.price} | {listing.location}")
                
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
                logger.info(f"🆕 NEW: {clean_title} | {listing.price} | {listing.location}")
        
        if new_listings:
            self._save_seen_listings()
            logger.info(f"✅ Found {len(new_listings)} new listings")
            logger.debug(f"💾 Updated seen listings file with {len(self.seen_listings)} total IDs")
        else:
            logger.debug("No new listings found")
        
        return new_listings
    
    def _create_ai_analysis_prompt(self, listing_data: Dict) -> str:
        """Create the AI analysis prompt for a TV listing."""
        # Use full description for better analysis
        full_description = listing_data['description'] if listing_data['description'] else "No description available"
        
        return f"""# TV Deal Analysis - Dutch Secondhand Market

**SMART SEARCH STRATEGY:**
If the listing has clear TV model information (brand + model number/name), perform these Google searches:
1. Model identification: "{listing_data['brand']} {listing_data['title']}" specifications model number
2. Current retail prices: "{listing_data['brand']} {listing_data['title']}" prijs MediaMarkt.nl Coolblue.nl bol.com 
3. Secondhand market: "{listing_data['brand']} {listing_data['title']}" marktplaats.nl tweedehands prijs "€"
4. Reviews and features: "{listing_data['brand']} {listing_data['title']}" review test specifications features
5. Release year: "{listing_data['brand']} {listing_data['title']}" release year when launched

**IF UNCLEAR/VAGUE:** If the listing lacks clear model info or is too generic, search more broadly:
• "{listing_data['brand']} {listing_data['screen_size']} TV" general pricing
• Use description context clues for smart-guessing

**LISTING TO ANALYZE:**
• **Title:** {listing_data['title']}
• **Price:** {listing_data['price']} {f"(IMPORTANT: 'Bieden' = bidding/offers accepted, NOT free! Estimate market value for this.)" if listing_data['price'] == 'Bieden' else f"(€{listing_data['numeric_price']})" if listing_data['numeric_price'] > 0 else ""}
• **Location:** {listing_data['location']}
• **Brand/Size:** {listing_data['brand']} {listing_data['screen_size']}
• **Full Description:** {full_description}

## Analysis Requirements:
1. **ADAPTIVE SEARCH:** Search extensively if model is clear, search broadly if vague. Always use real search results.
2. **Extract smartly:** If specific model found, get exact prices. If generic, use brand/size averages.
3. **"Bieden" HANDLING:** If price shows "Bieden" (bidding), estimate fair market value and score based on that estimated price, NOT €0! Treat as negotiable listing.
4. **Score 1-100:** Price vs Market (40pts) + Condition from description (25pts) + Model/Brand Desirability (20pts) + Negotiation Potential (15pts)
5. **Evidence-based:** Reference actual search findings. If unclear, state "estimated based on [brand/size]"
6. **Optimize for Discord:** Total response under 900 characters (field limit 1024, leaving buffer)

**CRITICAL: Format response EXACTLY as:**
```
🔍 **[Brand Model/Best Guess]**
📊 **[X]/100** - [Max 80 chars specific reason]
✅ **PROS:** • [Feature/benefit, 60 chars] • [Price advantage, 60 chars] • [Condition/extras, 60 chars]
❌ **CONS:** • [Drawback, 60 chars] • [Market issue, 60 chars] • [Age/limit, 60 chars]
💰 **MARKET:** €[retail]/€[secondhand]/{"Bieden (est. €[estimated])" if listing_data['price'] == 'Bieden' else "€[this]"}
🤝 **OFFER: €[X]** - [Max 100 chars reasoning based on findings]
```

Maximize useful information within Discord field limits. Be specific when possible, honest when uncertain.
"""
    
    def _analyze_tv_listing(self, listing: TVListing) -> Optional[Dict]:
        """Analyze a TV listing using Gemini AI with Google Search grounding."""
        logger.debug(f"🤖 Starting AI analysis for listing: {listing.title}")
        
        if not self.ai_enabled or not self.client:
            logger.debug("🤖 AI analysis skipped - AI not enabled or client not available")
            return None
        
        try:
            logger.debug("🤖 Preparing listing data for AI analysis...")
            # Prepare listing data with safe attribute access
            listing_data = {
                'title': listing.title or 'Unknown TV',
                'price': listing.price or 'Not specified',
                'numeric_price': listing.price_numeric or 0,
                'location': listing.location or 'Not specified',
                'seller': listing.seller_name or 'Not specified',
                'posting_date': listing.posting_date or 'Not specified',
                'description': listing.description or 'No description',
                'listing_url': listing.listing_url or 'Not available',
                'brand': getattr(listing, 'brand', 'Unknown'),
                'screen_size': getattr(listing, 'screen_size', 'Unknown'),
                'features': getattr(listing, 'features', [])
            }
            
            # Create structured prompt
            prompt = self._create_ai_analysis_prompt(listing_data)
            
            logger.debug("🤖 Sending listing to Gemini AI for analysis with Google Search grounding...")
            logger.debug(f"🤖 Prompt length: {len(prompt)} characters")
            
            # Updated grounding tool configuration for 2025
            try:
                grounding_tool = types.Tool(
                    google_search=types.GoogleSearch()
                )
                logger.debug("🤖 Grounding tool configured successfully")
            except Exception as e:
                logger.warning(f"🤖 Failed to configure grounding tool: {e}")
                grounding_tool = None
            
            # Configure generation settings with grounding
            config = types.GenerateContentConfig(
                tools=[grounding_tool] if grounding_tool else []
            )
            logger.debug(f"🤖 Generation config created with {'grounding' if grounding_tool else 'no grounding'}")
            
            # Use the latest available model - Gemini 2.5 Flash is best for price/performance
            available_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
            
            response = None
            model_used = None
            
            for model in available_models:
                try:
                    logger.debug(f"🤖 Attempting to use model: {model}")
                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                    )
                    model_used = model
                    logger.info(f"🤖 Successfully used model: {model}")
                    logger.debug(f"🤖 Response type: {type(response)}")
                    logger.debug(f"🤖 Response has text: {hasattr(response, 'text')}")
                    if hasattr(response, 'text'):
                        text_length = len(response.text) if response.text is not None else 0
                        logger.debug(f"🤖 Response text length: {text_length}")
                        logger.debug(f"🤖 Response text is None: {response.text is None}")
                    break
                except Exception as e:
                    logger.warning(f"🤖 Model {model} failed: {e}")
                    logger.debug(f"🤖 Model {model} error details:", exc_info=True)
                    continue
            
            if response:
                logger.debug(f"🤖 Response received. Has text attribute: {hasattr(response, 'text')}")
                
                # Extract response text with better error handling
                response_text = None
                if hasattr(response, 'text') and response.text:
                    response_text = response.text.strip()
                    logger.debug(f"🤖 Extracted text length: {len(response_text)}")
                elif hasattr(response, 'candidates') and response.candidates:
                    # Try to get text from candidates
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        parts = candidate.content.parts
                        if parts and hasattr(parts[0], 'text'):
                            response_text = parts[0].text.strip()
                            logger.debug(f"🤖 Extracted text from candidate parts: {len(response_text)}")
                
                if response_text:
                    logger.info("🤖 AI analysis completed successfully with Google Search grounding")
                    logger.debug(f"🤖 Response text preview: {response_text[:100]}...")
                    logger.debug(f"🤖 About to check grounding metadata...")
                    
                    # Check if grounding was actually used
                    grounding_used = False
                    grounding_sources = 0
                    
                    try:
                        if hasattr(response, 'candidates') and response.candidates:
                            candidate = response.candidates[0]
                            logger.debug(f"🤖 Candidate available: {candidate is not None}")
                            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                                grounding_used = True
                                logger.debug(f"🤖 Grounding metadata found")
                                if hasattr(candidate.grounding_metadata, 'grounding_chunks'):
                                    chunks = candidate.grounding_metadata.grounding_chunks
                                    logger.debug(f"🤖 Grounding chunks type: {type(chunks)}")
                                    if chunks is not None and hasattr(chunks, '__len__'):
                                        try:
                                            grounding_sources = len(chunks)
                                            logger.debug(f"🤖 Grounding chunks length: {grounding_sources}")
                                        except Exception as len_error:
                                            logger.warning(f"🤖 Error getting chunks length: {len_error}")
                                            grounding_sources = 0
                                    else:
                                        logger.debug(f"🤖 Grounding chunks is None or not iterable")
                                        grounding_sources = 0
                                logger.info(f"🤖 Grounding used with {grounding_sources} sources")
                        
                        logger.debug(f"🤖 Creating return dictionary...")
                        result = {
                            'analysis': response_text,
                            'model_used': model_used,
                            'grounding_used': grounding_used,
                            'grounding_sources': grounding_sources
                        }
                        logger.debug(f"🤖 Return dictionary created successfully")
                        return result
                    except Exception as grounding_error:
                        logger.error(f"🤖 Error checking grounding metadata: {grounding_error}")
                        logger.debug("🤖 Grounding metadata error:", exc_info=True)
                        # Return basic result without grounding info
                        return {
                            'analysis': response_text,
                            'model_used': model_used,
                            'grounding_used': False,
                            'grounding_sources': 0
                        }
                else:
                    logger.warning("🤖 AI analysis returned empty or no text content")
                    logger.debug(f"🤖 Response structure: {dir(response)}")
                    return None
            else:
                logger.warning("🤖 AI analysis returned no response")
                return None
                
        except Exception as e:
            logger.error(f"🤖 AI analysis failed: {e}")
            logger.debug("🤖 AI analysis error details:", exc_info=True)
            return None
    
    def _format_listing_for_discord(self, listing: TVListing, ai_analysis: Optional[Dict] = None) -> Dict:
        """Format a listing for Discord webhook with optional AI analysis."""
        logger.debug(f"📨 Formatting Discord embed for listing: {listing.title}")
        
        # Create a rich embed for the listing
        color = 0x00ff00  # Default green
        title_prefix = "🆕 NEW TV LISTING"
        
        # Customize based on AI analysis if available
        if ai_analysis and ai_analysis.get('analysis'):
            analysis_text = ai_analysis['analysis']
            # Updated score parsing for new format
            if '📊 **' in analysis_text:
                try:
                    score_match = re.search(r'📊 \*\*(\d+)/100\*\*', analysis_text)
                    if score_match:
                        score = int(score_match.group(1))
                        
                        # Color based on deal quality
                        if score >= 80:
                            color = 0x00ff00  # Green - Excellent deal
                            title_prefix = "🔥 EXCELLENT TV DEAL"
                        elif score >= 60:
                            color = 0xffa500  # Orange - Good deal
                            title_prefix = "👍 GOOD TV DEAL"
                        elif score >= 40:
                            color = 0xffff00  # Yellow - Average deal
                            title_prefix = "⚖️ AVERAGE TV DEAL"
                        else:
                            color = 0xff0000  # Red - Poor deal
                            title_prefix = "⚠️ QUESTIONABLE TV DEAL"
                except Exception as e:
                    logger.debug(f"Could not parse deal score: {e}")
        
        # Discord embed limits:
        # - Title: 256 characters
        # - Description: 4096 characters
        # - Field name: 256 characters
        # - Field value: 1024 characters
        # - Footer text: 2048 characters
        # - Total embed: 6000 characters
        
        # Truncate title if needed
        safe_title = listing.title[:250] + "..." if len(listing.title) > 250 else listing.title
        
        embed = {
            "title": title_prefix,
            "description": safe_title,
            "color": color,
            "timestamp": datetime.now().isoformat(),
            "fields": []
        }
        logger.debug(f"📨 Base embed created with title: {title_prefix}")
        
        # Add price field
        if listing.price:
            embed["fields"].append({
                "name": "💰 Price",
                "value": listing.price,
                "inline": True
            })
        
        # Add location field
        if listing.location:
            embed["fields"].append({
                "name": "📍 Location", 
                "value": listing.location,
                "inline": True
            })
        
        # Add posting date
        if listing.posting_date:
            embed["fields"].append({
                "name": "📅 Posted",
                "value": listing.posting_date,
                "inline": True
            })
        
        # Add seller info (only if it's meaningful)
        if listing.seller_name and listing.seller_name not in ["Verkoper onbekend", "Zie advertentie"]:
            embed["fields"].append({
                "name": "👤 Seller",
                "value": listing.seller_name,
                "inline": True
            })
        else:
            # Add a note that seller info is available on the listing page
            logger.debug(f"📺 Skipping seller field (not available in search results)")
        
        # Add description if available (show more text)
        if listing.description and len(listing.description) > 0:
            # Discord field value limit is 1024 characters
            max_desc_length = 1000
            if len(listing.description) <= max_desc_length:
                desc_text = listing.description
            else:
                desc_text = listing.description[:max_desc_length] + "..."
            
            embed["fields"].append({
                "name": "📝 Description",
                "value": desc_text,
                "inline": False
            })
            logger.debug(f"📨 Added description field (length: {len(desc_text)})")
        
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
        
        # Add AI analysis if available
        if ai_analysis and ai_analysis.get('analysis'):
            analysis_text = ai_analysis.get('analysis', '')
            logger.debug(f"📨 Adding AI analysis to Discord embed. Text length: {len(analysis_text) if analysis_text else 0}")
            
            # Ensure analysis_text is not None and handle Discord field limits
            if analysis_text and isinstance(analysis_text, str):
                # Discord embed field value limit is 1024 characters
                if len(analysis_text) > 1020:
                    analysis_text = analysis_text[:1020] + "..."
                    logger.debug("📨 Truncated AI analysis to fit Discord field limit")
                
                embed["fields"].append({
                    "name": "🤖 AI Deal Analysis",
                    "value": analysis_text,
                    "inline": False
                })
                logger.debug("📨 AI analysis field added to embed")
            else:
                logger.warning(f"📨 AI analysis text is invalid: {type(analysis_text)} - {analysis_text}")
                embed["fields"].append({
                    "name": "🤖 AI Analysis",
                    "value": "Analysis failed - invalid response format",
                    "inline": False
                })
            
            # Add footer indicating AI was used with grounding info
            grounding_info = ""
            if ai_analysis.get('grounding_used', False):
                sources = ai_analysis.get('grounding_sources', 0)
                grounding_info = f" with Google Search grounding • {sources} sources"
            
            footer_text = f"Analyzed by {ai_analysis.get('model_used', 'Gemini AI')}{grounding_info} • Today at {datetime.now().strftime('%I:%M %p')}"
            
            # Discord footer text limit is 2048 characters
            if len(footer_text) > 2048:
                footer_text = footer_text[:2045] + "..."
            
            embed["footer"] = {
                "text": footer_text
            }
            logger.debug(f"📨 Added footer with AI info (length: {len(footer_text)})")
        
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
        
        # Add @everyone ping for excellent deals
        if title_prefix == "🔥 EXCELLENT TV DEAL":
            payload["content"] = "@everyone"
            logger.info(f"📨 Adding @everyone ping for excellent TV deal: {listing.title}")
        
        return payload
    
    def _send_discord_notification(self, new_listings: List[TVListing]):
        """Send Discord notification for new listings with AI analysis."""
        logger.info(f"📨 Starting Discord notifications for {len(new_listings)} new listings")
        
        try:
            for i, listing in enumerate(new_listings, 1):
                logger.info(f"📨 Processing listing {i}/{len(new_listings)}: {listing.title}")
                
                # Perform AI analysis if enabled
                ai_analysis = None
                if self.ai_enabled:
                    logger.info(f"🤖 Analyzing TV deal: {listing.title}")
                    ai_analysis = self._analyze_tv_listing(listing)
                    if ai_analysis and ai_analysis.get('analysis'):
                        logger.info("🤖 AI analysis completed successfully")
                        logger.debug(f"🤖 Analysis preview: {ai_analysis.get('analysis', '')[:100]}...")
                    else:
                        logger.warning("🤖 AI analysis failed or returned empty")
                        if ai_analysis:
                            logger.debug(f"🤖 AI analysis result: {ai_analysis}")
                else:
                    logger.debug("🤖 AI analysis skipped - not enabled")
                
                # Format notification with AI analysis
                logger.debug(f"📨 Formatting Discord payload for: {listing.title}")
                try:
                    payload = self._format_listing_for_discord(listing, ai_analysis)
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
                        ai_status = " (with AI analysis)" if ai_analysis and ai_analysis.get('analysis') else ""
                        logger.info(f"✅ Discord notification sent for: {listing.title}{ai_status}")
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
                    delay = 3 if self.ai_enabled else 1
                    logger.debug(f"📨 Waiting {delay}s before next notification...")
                    time.sleep(delay)
                    
        except Exception as e:
            logger.error(f"📨 Critical error in Discord notification pipeline: {e}")
            logger.debug("📨 Discord notification pipeline error:", exc_info=True)
    
    def _send_startup_notification(self):
        """Send a notification when the monitor starts."""
        try:
            ai_status = "✅ Enabled with Google Search" if self.ai_enabled else "❌ Disabled"
            
            embed = {
                "title": "🚨 TV Monitor Started",
                "description": "Monitoring for new TV listings on Marktplaats",
                "color": 0x0099ff,
                "timestamp": datetime.now().isoformat(),
                "fields": [
                    {
                        "name": "🎯 Target",
                        "value": "Newest TV listings",
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
                    },
                    {
                        "name": "🤖 AI Analysis",
                        "value": ai_status,
                        "inline": False
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
            # Show current listings during initialization
            initial_listings = self._fetch_current_listings(silent_mode=False, show_summary=True)
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
                    # Show current listings every alive check to help with debugging
                    new_count = self.run_single_check(show_current_listings=True)
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
    
    # Get Gemini API key from environment variable
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    if not GEMINI_API_KEY:
        logger.warning("🤖 GEMINI_API_KEY environment variable not set. AI analysis will be disabled.")
        logger.info("💡 To enable AI analysis, set: export GEMINI_API_KEY='your-api-key'")
    
    try:
        monitor = TVMonitor(DISCORD_WEBHOOK, gemini_api_key=GEMINI_API_KEY)
        monitor.run_monitor(check_interval=60)
    except Exception as e:
        logger.error(f"Failed to start monitor: {e}")
        raise

if __name__ == "__main__":
    main()