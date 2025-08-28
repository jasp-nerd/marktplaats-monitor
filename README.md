# Marktplaats Item Monitor

A Python script that monitors Marktplaats for new item listings of any type and sends Discord notifications with optional AI-powered deal analysis.

## Features

- Real-time monitoring of Marktplaats item listings for any search query
- Discord webhook notifications
- AI deal analysis with Google Gemini (optional)
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
# Edit .env with your Discord webhook URL and optional Gemini API key
```

3. **Run the monitor**
```bash
python marktplaats_monitor.py
```

## Configuration

Required:
- `DISCORD_WEBHOOK_URL` - Discord webhook for notifications
- `SEARCH_URL` - Marktplaats search URL for the items you want to monitor

Optional:
- `ITEM_NAME` - Friendly name for the items being monitored (default: "items")
- `GEMINI_API_KEY` - Google Gemini API key for AI analysis
- `CHECK_INTERVAL` - Monitoring interval in seconds (default: 60)
- `MAX_PAGES` - Maximum pages to scrape (default: 3)

## Project Structure

```
├── marktplaats_monitor.py       # Main application
├── scraper_core.py              # Core scraping logic
├── requirements.txt             # Dependencies
├── env.example                  # Environment template
└── Procfile                     # Deployment configuration
```

## Discord Setup

1. Go to your Discord server settings
2. Navigate to Integrations → Webhooks
3. Create a new webhook and copy the URL
4. Add the URL to your `.env` file

## AI Analysis (Optional)

To enable AI-powered deal analysis:
1. Get an API key from [Google AI Studio](https://aistudio.google.com)
2. Add `GEMINI_API_KEY=your_key_here` to your `.env` file

The AI will analyze each listing and provide deal scores, market comparison, and negotiation advice.

## Examples

### Monitor Apple TV 4K listings:
```bash
export SEARCH_URL="https://www.marktplaats.nl/q/apple%2btv%2b4k/"
export ITEM_NAME="Apple TV 4K"
export DISCORD_WEBHOOK_URL="your-webhook-url"
python marktplaats_monitor.py
```

### Monitor iPhone listings:
```bash
export SEARCH_URL="https://www.marktplaats.nl/q/iphone/"
export ITEM_NAME="iPhone"
export DISCORD_WEBHOOK_URL="your-webhook-url"
python marktplaats_monitor.py
```

### Monitor Nintendo Switch listings:
```bash
export SEARCH_URL="https://www.marktplaats.nl/q/nintendo%2bswitch/"
export ITEM_NAME="Nintendo Switch"
export DISCORD_WEBHOOK_URL="your-webhook-url"
python marktplaats_monitor.py
```

## Finding Search URLs

1. Go to [Marktplaats.nl](https://www.marktplaats.nl)
2. Search for the item you want to monitor
3. Apply any filters you want (price range, location, category, etc.)
4. Copy the URL from your browser's address bar
5. Use this URL as your `SEARCH_URL` environment variable

## License

This project is open source. Feel free to use and modify as needed.