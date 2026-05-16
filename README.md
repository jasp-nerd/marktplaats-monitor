# Marktplaats Item Monitor

A Python script that monitors Marktplaats for new item listings of any type and sends Discord notifications.

## Features

- Real-time monitoring of Marktplaats listings for any search query
- Location filtering by postcode + radius (honored server-side)
- Discord webhook notifications
- Duplicate detection to avoid spam
- Configurable monitoring for any item category

## Setup

1. **Install dependencies**
```bash
pip install -r requirements.txt
```

2. **Configure environment**
```bash
cp env.example .env
# Edit .env with your Discord webhook URL and search URL
```

3. **Run the monitor**
```bash
python app.py
```

## Configuration

Required:
- `DISCORD_WEBHOOK_URL` - Discord webhook for notifications
- `SEARCH_URL` - Marktplaats search URL for the items you want to monitor

Optional:
- `ITEM_NAME` - Friendly name for the items being monitored (default: `items`)
- `CHECK_INTERVAL` - Monitoring interval in seconds (default: `60`)
- `MAX_PAGES` - Pages to fetch per check, 30 listings each (default: `1`)
- `DISTANCE_KM` - Radius used when `SEARCH_URL` has a postcode but no explicit
  distance (default: `50`)

## Project Structure

```
├── app.py             # Main application (the monitor loop)
├── scraper_core.py    # Core scraping logic (Marktplaats search API)
├── requirements.txt   # Dependencies
├── env.example        # Environment template
└── Procfile           # Deployment configuration (worker: python app.py)
```

## Discord Setup

1. Go to your Discord server settings
2. Navigate to Integrations → Webhooks
3. Create a new webhook and copy the URL
4. Add the URL to your `.env` file as `DISCORD_WEBHOOK_URL`

## Finding Search URLs

1. Go to [Marktplaats.nl](https://www.marktplaats.nl)
2. Search for the item you want to monitor
3. Apply any filters you want (price range, location, category, etc.)
4. Copy the URL from your browser's address bar
5. Use this URL as your `SEARCH_URL`

### Location filtering

The scraper uses Marktplaats' own search API, so location filters work even
when they're in the URL fragment (`#...`). Both of these are honored:

```
https://www.marktplaats.nl/q/apple+homepod+mini/#postcode:2342CM
https://www.marktplaats.nl/q/apple+homepod+mini/?postcode=2342CM&distanceMeters=25000
```

If you supply a postcode without a radius, `DISTANCE_KM` (default 50 km) is
used. A postcode only filters when combined with a radius.

## Examples

### Monitor Apple HomePod mini listings near a postcode:
```bash
export SEARCH_URL="https://www.marktplaats.nl/q/apple+homepod+mini/#postcode:2342CM"
export ITEM_NAME="HomePod mini"
export DISCORD_WEBHOOK_URL="your-webhook-url"
python app.py
```

### Monitor Apple TV 4K listings (nationwide):
```bash
export SEARCH_URL="https://www.marktplaats.nl/q/apple+tv+4k/"
export ITEM_NAME="Apple TV 4K"
export DISCORD_WEBHOOK_URL="your-webhook-url"
python app.py
```

### Monitor Nintendo Switch listings:
```bash
export SEARCH_URL="https://www.marktplaats.nl/q/nintendo+switch/"
export ITEM_NAME="Nintendo Switch"
export DISCORD_WEBHOOK_URL="your-webhook-url"
python app.py
```

## License

This project is open source. Feel free to use and modify as needed.
