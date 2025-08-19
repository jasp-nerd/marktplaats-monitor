# Marktplaats TV Monitor

A Python script that monitors Marktplaats for new TV listings and sends Discord notifications with optional AI-powered deal analysis.

## Features

- Real-time monitoring of Marktplaats TV listings
- Discord webhook notifications
- AI deal analysis with Google Gemini (optional)
- Duplicate detection to avoid spam
- Configurable price and keyword filtering

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
python marktplaats_scraper.py
```

## Configuration

Required:
- `DISCORD_WEBHOOK_URL` - Discord webhook for notifications

Optional:
- `GEMINI_API_KEY` - Google Gemini API key for AI analysis
- `CHECK_INTERVAL` - Monitoring interval in seconds (default: 60)
- `MAX_PAGES` - Maximum pages to scrape (default: 3)

## Project Structure

```
├── marktplaats_scraper.py       # Main application
├── marktplaats_tv_scraper.py    # Core scraping logic
├── config.py                    # Configuration management
├── requirements.txt             # Dependencies
└── env.example                  # Environment template
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

## License

This project is open source. Feel free to use and modify as needed.