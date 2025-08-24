#!/usr/bin/env python3
"""
Marktplaats TV Scraper - Core scraping functionality for TV listings
"""

import requests
import re
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

logger = logging.getLogger(__name__)

@dataclass
class TVListing:
    """Data class representing a TV listing from Marktplaats."""
    title: str
    price: str
    price_numeric: float
    location: str
    seller_name: str
    posting_date: str
    description: str
    listing_url: str
    brand: str = "Unknown"
    screen_size: str = "Unknown"
    features: List[str] = None
    condition: str = "Unknown"
    image_url: str = ""
    
    def __post_init__(self):
        if self.features is None:
            self.features = []
        
        # Extract brand and screen size from title if possible
        if self.brand == "Unknown":
            self.brand = self._extract_brand()
        
        if self.screen_size == "Unknown":
            self.screen_size = self._extract_screen_size()
    
    def _extract_brand(self) -> str:
        """Extract TV brand from title."""
        # Use TV brands directly to avoid circular import
        TV_BRANDS = [
            'Samsung', 'LG', 'Sony', 'Philips', 'TCL', 'Hisense', 
            'Panasonic', 'Sharp', 'Toshiba', 'JVC', 'Grundig',
            'Bang & Olufsen', 'Loewe', 'Xiaomi', 'OnePlus', 'Huawei'
        ]
        
        title_upper = self.title.upper()
        for brand in TV_BRANDS:
            if brand.upper() in title_upper:
                return brand
        return "Unknown"
    
    def _extract_screen_size(self) -> str:
        """Extract screen size from title."""
        # Look for patterns like 55", 65 inch, 75"
        size_patterns = [
            r'(\d{2,3})\s*["\']',  # 55", 65'
            r'(\d{2,3})\s*inch',   # 55 inch
            r'(\d{2,3})\s*cm',     # 140cm
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, self.title, re.IGNORECASE)
            if match:
                size = int(match.group(1))
                if 20 <= size <= 100:  # Reasonable TV size range in inches
                    return f'{size}"'
                elif 50 <= size <= 250:  # CM range
                    inches = round(size / 2.54)
                    return f'{inches}"'
        
        return "Unknown"


class MarktplaatsTVScraper:
    """Scraper for Marktplaats TV listings."""
    
    # Known TV brands for extraction from titles
    TV_BRANDS = [
        'Samsung', 'LG', 'Sony', 'Philips', 'TCL', 'Hisense', 
        'Panasonic', 'Sharp', 'Toshiba', 'JVC', 'Grundig',
        'Bang & Olufsen', 'Loewe', 'Xiaomi', 'OnePlus', 'Huawei'
    ]
    
    def __init__(self):
        self.base_url = "https://www.marktplaats.nl"
        self.session = requests.Session()
        
        # Set up session with proper headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        logger.debug("MarktplaatsTVScraper initialized")
    
    def _parse_dutch_price(self, price_text: str) -> float:
        """Parse Dutch-formatted price strings to float."""
        try:
            price_match = re.search(r'€\s*([0-9.,]+)', price_text)
            if not price_match:
                return 0.0
            
            price_str = price_match.group(1)
            
            # Handle different Dutch number formats
            if ',' in price_str and '.' in price_str:
                # Format like 1.000,50 (thousands separator . and decimal separator ,)
                price_str = price_str.replace('.', '').replace(',', '.')
            elif ',' in price_str and price_str.count(',') == 1:
                # Format like 1000,50 (decimal separator ,)
                price_str = price_str.replace(',', '.')
            elif '.' in price_str and len(price_str.split('.')[-1]) <= 2:
                # Format like 1000.50 (decimal separator .)
                pass  # Already in correct format
            else:
                # Format like 1000 or 1.000 (integer, remove dots)
                price_str = price_str.replace('.', '')
            
            return float(price_str)
        except (ValueError, AttributeError):
            return 0.0
    
    def scrape_tv_listings(self, max_pages: int = 3) -> List[TVListing]:
        """Scrape TV listings from Marktplaats."""
        all_listings = []
        
        for page in range(1, max_pages + 1):
            logger.info(f"Scraping page {page}/{max_pages}")
            
            page_listings = self._scrape_page(page)
            all_listings.extend(page_listings)
            
            if len(page_listings) == 0:
                logger.info(f"No listings found on page {page}, stopping")
                break
            
            # Be polite to the server
            time.sleep(2)
        
        logger.info(f"Total listings scraped: {len(all_listings)}")
        return all_listings
    
    def _scrape_page(self, page: int = 1) -> List[TVListing]:
        """Scrape a single page of TV listings."""
        try:
            url = f"{self.base_url}/l/audio-tv-en-foto/televisies"
            if page > 1:
                url += f"?offset={(page - 1) * 30}"
            
            logger.debug(f"Fetching: {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find listing containers - Updated for current Marktplaats structure
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
            
            logger.info(f"📺 Found {len(listing_elements)} listing elements on page {page}")
            
            if not listing_elements:
                logger.warning(f"📺 No listing elements found on page {page}")
                logger.debug(f"📺 Page HTML structure preview: {str(soup)[:500]}...")
            
            listings = []
            for i, element in enumerate(listing_elements, 1):
                logger.debug(f"📺 Processing element {i}/{len(listing_elements)}")
                try:
                    listing = self._extract_listing_data(element, soup)
                    if listing:
                        listings.append(listing)
                        logger.debug(f"📺 Successfully extracted listing {i}: {listing.title}")
                    else:
                        logger.debug(f"📺 Failed to extract listing {i}")
                except Exception as e:
                    logger.warning(f"📺 Error processing element {i}: {e}")
                    continue
            
            logger.info(f"📺 Successfully extracted {len(listings)} listings from {len(listing_elements)} elements")
            return listings
            
        except Exception as e:
            logger.error(f"Error scraping page {page}: {e}")
            return []
    
    def _extract_listing_data(self, element, soup, silent_mode: bool = False) -> Optional[TVListing]:
        """Extract data from a single listing element."""
        try:
            # Extract title - More robust approach for various Marktplaats structures
            title = ""
            
            # Try multiple title extraction patterns
            title_patterns = [
                ('h3', {'class': 'mp-listing-title'}),
                ('h2', {'class': 'mp-listing-title'}),
                ('h3', {'class': 'hz-Listing-title'}),
                ('h2', {'class': 'hz-Listing-title'}),
                ('a', {'class': 'hz-Link'}),
                ('a', {'class': 'mp-listing-link'}),
                ('a', {'href': re.compile(r'/v/.*/televisies/')}),  # Any TV listing link
            ]
            
            for tag, attrs in title_patterns:
                title_elem = element.find(tag, attrs)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title:  # Found a non-empty title
                        break
            
            # If still no title found, try a broader search within the element
            if not title:
                # Look for any text that looks like a TV title (contains common TV keywords)
                all_text = element.get_text(separator=' ', strip=True)
                
                # Split by common delimiters and look for the main title part
                parts = re.split(r'€\s*[0-9.,]+|details|vandaag|gisteren', all_text, flags=re.IGNORECASE)
                if parts and len(parts[0].strip()) > 5:
                    title = parts[0].strip()
            
            if not title or len(title) < 3:
                # Last resort: return None if we can't extract a meaningful title
                return None
            
            # Clean up the title immediately after extraction
            # Remove common patterns that shouldn't be part of the title
            title = re.sub(r'€\s*[0-9.,]+.*$', '', title)  # Remove price and everything after
            title = re.sub(r'details.*$', '', title, flags=re.IGNORECASE)  # Remove details text
            title = re.sub(r'\s+', ' ', title).strip()  # Clean whitespace
            
            if not title:
                return None
            
            logger.debug(f"📺 Extracting listing: {title[:50]}...")
            
            # Extract URL - More robust approach for various link structures
            listing_url = ""
            
            # Try multiple link extraction patterns in order of preference
            link_patterns = [
                ('a', {'class': 'hz-Link'}),  # Most common working pattern
                ('a', {'class': 'hz-Listing-coverLink'}),  # Cover link
                ('a', {'href': re.compile(r'/v/.*/televisies/')}),  # TV listing links
                ('a', {'class': 'mp-listing-link'}),
                ('a', {'class': re.compile(r'.*[Ll]ink.*')}),  # Any class containing "link"
            ]
            
            for tag, attrs in link_patterns:
                link_elem = element.find(tag, attrs)
                if link_elem and link_elem.get('href'):
                    listing_url = link_elem.get('href')
                    break
            
            # If no specific link found, try broader searches
            if not listing_url:
                # Try any link with TV-related href
                tv_link = element.find('a', href=re.compile(r'(televisies|tv)'))
                if tv_link and tv_link.get('href'):
                    listing_url = tv_link.get('href')
                else:
                    # Try any link in the element as last resort
                    any_link = element.find('a', href=True)
                    if any_link:
                        listing_url = any_link.get('href', '')
            
            # For listings without direct links, try to construct URL from title/content
            if not listing_url and title:
                # Some listings might be external (website links, phone-only, etc.)
                # Check if this is a business listing that redirects to external sites
                business_indicators = ['hellotv', 'mediamarkt', 'coolblue', 'bol.com', 'website']
                is_business = any(indicator in title.lower() for indicator in business_indicators)
                
                if is_business:
                    # For business listings without direct links, note this in the URL
                    listing_url = "# Business listing - check original search page"
                    logger.debug(f"📺 Business listing detected without direct link: {title[:30]}...")
                else:
                    # For user listings without links, this might be an ad or external listing
                    listing_url = "# External listing - no direct link available"
                    logger.debug(f"📺 User listing without direct link: {title[:30]}...")
            
            # Make URL absolute if needed (skip constructed placeholder URLs)
            if listing_url and not listing_url.startswith('#') and not listing_url.startswith('http'):
                listing_url = urljoin(self.base_url, listing_url)
            
            logger.debug(f"📺 Found URL: {listing_url}")
            
            # Extract price - More robust price extraction
            price = "Prijs onbekend"
            price_numeric = 0.0
            
            # First try to find price in the full text using regex
            all_text = element.get_text(separator=' ', strip=True)
            
            # Look for various price patterns in the text
            price_patterns = [
                r'€\s*([0-9.,]+)',  # Standard euro prices
                r'([0-9]+[.,][0-9]+)\s*€',  # Price before euro symbol
                r'([0-9]+)\s*€',  # Simple number before euro
            ]
            
            price_found = False
            for pattern in price_patterns:
                price_match = re.search(pattern, all_text)
                if price_match:
                    price_text = price_match.group(0)
                    price = price_text
                    price_numeric = self._parse_dutch_price(price_text)
                    price_found = True
                    logger.debug(f"📺 Found price in text: {price}")
                    break
            
            # If no price found in text, try HTML elements
            if not price_found:
                price_element_patterns = [
                    {'class': 'mp-listing-price'},
                    {'class': 'ListingPrice-root'},
                    {'class': 'price-label'},
                    {'class': 'hz-Listing-price'}
                ]
                
                for pattern in price_element_patterns:
                    price_elem = element.find('span', pattern) or element.find('div', pattern)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price = price_text
                        price_numeric = self._parse_dutch_price(price_text)
                        logger.debug(f"📺 Found price in element: {price}")
                        break
            
            # Check for special cases (bidding, reserved, etc.)
            if not price_found or price == "Prijs onbekend":
                if re.search(r'\b(Gereserveerd|Bod|Bieden)\b', all_text, re.IGNORECASE):
                    if 'Bieden' in all_text:
                        price = "Bieden"
                    else:
                        price = "Gereserveerd"
                    logger.debug(f"📺 Special pricing: {price}")
            
            # Extract location - More robust location extraction from text
            location = "Locatie onbekend"
            
            # First try to find location in the full text using common Dutch patterns
            all_text = element.get_text(separator=' ', strip=True)
            
            # Look for Dutch postal codes and city names
            location_patterns = [
                r'\b([A-Z][a-z]+(?:\s+[a-z]+)*)\s+\d{1,3}\s*km\b',  # City + distance (Amsterdam 50 km)
                r'\b\d{4}\s*[A-Z]{2}\s+([A-Z][a-z]+(?:\s+[a-z]+)*)\b',  # Postal code + city (1234 AB Amsterdam)
                r'\b([A-Z][a-z]+(?:\s+[a-z]+)*)\s+\d{4}\s*[A-Z]{2}\b',  # City + postal code (Amsterdam 1234 AB)
                r'\b([A-Z][a-z]+(?:-[A-Z][a-z]+)*)\b',  # Simple city names (including hyphenated like Den-Bosch)
            ]
            
            location_found = False
            for pattern in location_patterns:
                location_match = re.search(pattern, all_text)
                if location_match:
                    potential_location = location_match.group(1) if location_match.lastindex else location_match.group(0)
                    # Filter out obvious non-location words including TV brands
                    excluded_words = [
                        # Categories and actions
                        'Audio', 'Televisies', 'Ophalen', 'Verzenden', 'Gebruikt', 'Nieuw', 'Details', 'Vandaag', 'Gisteren',
                        # TV technologies
                        'OLED', 'QLED', 'LED', 'Smart', 'Ultra', 'HD', 'UHD', 'HDR', 'Ambilight', 'Crystal', 'Frame',
                        # TV brands (from TV_BRANDS list)
                        'Samsung', 'LG', 'Sony', 'Philips', 'TCL', 'Hisense', 'Panasonic', 'Sharp', 'Toshiba', 'JVC', 'Grundig',
                        'Bang', 'Olufsen', 'Loewe', 'Xiaomi', 'OnePlus', 'Huawei',
                        # Business names
                        'HelloTV', 'Hellotv', 'MediaMarkt', 'Coolblue', 'Bol'
                    ]
                    # Case-insensitive check for excluded words
                    if potential_location.lower() not in [word.lower() for word in excluded_words] and len(potential_location) > 2:
                        location = potential_location
                        location_found = True
                        logger.debug(f"📺 Found location in text: {location}")
                        break
            
            # If no location found in text, try HTML elements
            if not location_found:
                location_element_patterns = [
                    {'class': 'mp-listing-location'},
                    {'class': 'hz-Listing-location'},
                    {'class': 'ListingLocation-root'},
                    {'class': 'location'}
                ]
                
                for pattern in location_element_patterns:
                    location_elem = element.find('span', pattern) or element.find('div', pattern)
                    if location_elem:
                        potential_location = location_elem.get_text(strip=True)
                        # Apply same brand filtering to HTML-extracted locations
                        if potential_location.lower() not in [word.lower() for word in excluded_words] and len(potential_location) > 2:
                            location = potential_location
                            logger.debug(f"📺 Found location in element: {location}")
                            break
            
            # Extract seller name - Accept that it's not available in search results
            # Note: Marktplaats search results don't include seller information
            # Seller info is only available on individual listing pages
            seller_name = "Zie advertentie"  # More user-friendly message
            
            # Log that this is expected behavior
            logger.debug(f"📺 Seller info not available in search results (expected)")
            
            # Extract posting date - More robust date extraction from text
            posting_date = "Datum onbekend"
            
            # First try to find date in the full text using Dutch date patterns
            all_text = element.get_text(separator=' ', strip=True)
            
            date_patterns = [
                r'\b(vandaag|gisteren)\b',  # Today/yesterday
                r'\b\d{1,2}\s+(jan|feb|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec)\b',  # 15 jan
                r'\b\d{1,2}\s+(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\b',  # 15 januari
                r'\b\d{1,2}-\d{1,2}-\d{4}\b',  # 15-01-2025
                r'\b\d{1,2}/\d{1,2}/\d{4}\b'   # 15/01/2025
            ]
            
            date_found = False
            for pattern in date_patterns:
                date_match = re.search(pattern, all_text, re.IGNORECASE)
                if date_match:
                    posting_date = date_match.group(0)
                    date_found = True
                    logger.debug(f"📺 Found date in text: {posting_date}")
                    break
            
            # If no date found in text, try HTML elements
            if not date_found:
                date_element_patterns = [
                    {'class': 'mp-listing-date'},
                    {'class': 'hz-Listing-date'},
                    {'class': 'ListingDate-root'},
                    {'class': 'date'}
                ]
                
                for pattern in date_element_patterns:
                    date_elem = element.find('span', pattern) or element.find('div', pattern) or element.find('time', pattern)
                    if date_elem:
                        posting_date = date_elem.get_text(strip=True)
                        logger.debug(f"📺 Found date in element: {posting_date}")
                        break
            
            # Extract description - Get from listing element and optionally listing page
            description = self._extract_description(element, listing_url)
            logger.debug(f"📺 Extracted description: {description[:100]}...")
            
            # Extract image URL
            img_elem = element.find('img')
            image_url = img_elem.get('src', '') if img_elem else ''
            
            listing = TVListing(
                title=title,
                price=price,
                price_numeric=price_numeric,
                location=location,
                seller_name=seller_name,
                posting_date=posting_date,
                description=description,
                listing_url=listing_url,
                image_url=image_url
            )
            
            # Clean the title for logging - remove extra metadata
            clean_title = title.replace('\n', ' ').replace('\r', ' ')
            # Remove common patterns that get mixed into titles
            clean_title = re.sub(r'€\s*[0-9.,]+details.*$', '', clean_title)
            clean_title = re.sub(r'details.*$', '', clean_title, flags=re.IGNORECASE)
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()[:100]
            
            if not silent_mode:
                logger.info(f"📺 Successfully extracted: {clean_title} | {price} | {location} | {posting_date}")
            return listing
            
        except Exception as e:
            logger.error(f"Error extracting listing data: {e}")
            return None
    
    def _extract_description(self, element, listing_url: str) -> str:
        """Extract description from listing element or preview."""
        try:
            # Try multiple description patterns
            description = ""
            
            # Pattern 1: Look for description class elements
            desc_patterns = [
                {'class': 'mp-listing-description'},
                {'class': 'hz-Listing-description'},
                {'class': 'ListingDescription-root'},
                {'class': 'description'},
                {'class': 'hz-Listing-summary'}
            ]
            
            for pattern in desc_patterns:
                desc_elem = element.find('div', pattern) or element.find('p', pattern) or element.find('span', pattern)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    if description and len(description) > 10:
                        logger.debug(f"📺 Found description in element: {description[:50]}...")
                        return description[:500]  # Limit length
            
            # Pattern 2: Try to extract from structured text (more selective approach)
            # Get all text but be very selective about what we consider description
            all_text = element.get_text(separator=' ', strip=True)
            
            if all_text and len(all_text) > 50:
                # More aggressive filtering to avoid jumbled text
                filters = [
                    r'€\s*[0-9.,]+',  # Price
                    r'\d{4}\s*[A-Z]{2}\s*\w*',  # Postal code and city
                    r'(vandaag|gisteren|\d+\s*(jan|feb|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec))',  # Date
                    r'(Bieden|Kopen|Ophalen|Verzenden|details|Topadvertentie|Dagtopper)',  # Action buttons & labels
                    r'(Gebruikt|Nieuw|Zo\s+goed\s+als\s+nieuw|Refurbished)',  # Conditions
                    r'\b(Samsung|LG|Sony|Philips|TCL|Hisense|Panasonic|Sharp|Toshiba)\b',  # Brand names
                    r'\b\d+\s*(inch|cm|Hz)\b',  # Technical specs
                    r'\b(TV|televisie|Smart\s*TV|OLED|QLED|LCD|LED|Ultra\s*HD|4K|Full\s*HD)\b',  # TV terms
                    r'\b(100\s*cm\s*of\s*meer|80\s*tot\s*100\s*cm)\b',  # Size categories
                    r'\bOok\s+voor\s+de\s+tweedehands\b',  # Common ad text
                ]
                
                # First, extract potential description sentences
                sentences = re.split(r'[.!?]\s+', all_text)
                description_candidates = []
                
                for sentence in sentences:
                    # Skip very short or very long sentences
                    if len(sentence) < 15 or len(sentence) > 200:
                        continue
                    
                    # Apply filters to see if this looks like description content
                    clean_sentence = sentence
                    for pattern in filters:
                        clean_sentence = re.sub(pattern, '', clean_sentence, flags=re.IGNORECASE)
                    
                    # Clean up whitespace
                    clean_sentence = re.sub(r'\s+', ' ', clean_sentence).strip()
                    
                    # If after filtering we still have substantial content, it might be description
                    if len(clean_sentence) > 10 and len(clean_sentence.split()) >= 3:
                        # Check if it contains descriptive words rather than just metadata
                        descriptive_patterns = [
                            r'\b(beschrijving|combineer|perfect|uitstekend|fantastisch|mooi|goed|kwaliteit)\b',
                            r'\b(televisie|tv|scherm|beeld|kijk|entertainment)\b',
                            r'\b(staat|conditie|werkt|functioneert)\b'
                        ]
                        
                        has_descriptive_content = any(re.search(pattern, clean_sentence, re.IGNORECASE) for pattern in descriptive_patterns)
                        
                        if has_descriptive_content:
                            description_candidates.append(clean_sentence)
                
                # Use the best description candidate
                if description_candidates:
                    best_description = max(description_candidates, key=len)
                    logger.debug(f"📺 Extracted description from text: {best_description[:50]}...")
                    return best_description[:300]  # Shorter limit for cleaner output
            
            # Pattern 3: Fallback to basic information
            # Don't try to fetch from URL to avoid overwhelming the site with requests
            # Instead, provide a clean minimal description
            return "Zie advertentie voor volledige beschrijving"
            
        except Exception as e:
            logger.debug(f"📺 Error extracting description: {e}")
            return "Geen beschrijving beschikbaar"
    
    def get_listing_details(self, listing_url: str) -> Dict[str, Any]:
        """Get detailed information from individual listing page."""
        try:
            if not listing_url:
                return {}
            
            response = self.session.get(listing_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            details = {}
            
            # Extract full description
            desc_elem = soup.find('div', class_='description') or soup.find('div', id='description')
            if desc_elem:
                details['full_description'] = desc_elem.get_text(strip=True)
            
            # Extract specifications table
            specs_table = soup.find('table', class_='specifications') or soup.find('dl', class_='specifications')
            if specs_table:
                specs = {}
                # Extract key-value pairs from specifications
                rows = specs_table.find_all(['tr', 'dt'])
                for row in rows:
                    if row.name == 'tr':
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            key = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            specs[key] = value
                    elif row.name == 'dt':
                        key = row.get_text(strip=True)
                        next_elem = row.find_next_sibling('dd')
                        if next_elem:
                            value = next_elem.get_text(strip=True)
                            specs[key] = value
                
                details['specifications'] = specs
            
            # Extract additional images
            image_elements = soup.find_all('img', src=True)
            image_urls = []
            for img in image_elements:
                src = img.get('src')
                if src and ('listing' in src or 'photo' in src):
                    if not src.startswith('http'):
                        src = urljoin(self.base_url, src)
                    image_urls.append(src)
            
            details['images'] = image_urls[:10]  # Limit to 10 images
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting listing details for {listing_url}: {e}")
            return {}
    
    def close(self):
        """Close the session."""
        self.session.close()
        logger.info("MarktplaatsTVScraper session closed")
