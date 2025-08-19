# 📺 Marktplaats TV Monitor

An intelligent monitoring system that tracks Marktplaats for new TV listings and sends real-time Discord notifications with AI-powered deal analysis using Google Gemini.

## ✨ Key Features

- 🚨 **Real-time monitoring** of Marktplaats TV listings with intelligent deduplication
- 💬 **Rich Discord notifications** with embedded listing details and images
- 🤖 **AI-powered deal analysis** using Google Gemini with web search grounding
- 📊 **Smart scoring system** (1-100) evaluating deals based on market value, condition, and desirability
- 🎯 **Advanced filtering** by price ranges, keywords, and custom criteria
- 📈 **Comprehensive logging** with debug information and performance metrics
- 🔄 **Robust error handling** with automatic retries and graceful fallbacks
- ⚡ **High-performance scraping** with modern web parsing techniques

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher [[memory:6442355]]
- Virtual environment (recommended: `myenv`)

### 1. Setup Environment

```bash
# Activate your virtual environment
source myenv/bin/activate  # or: myenv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run setup script (optional but recommended)
python setup.py
```

### 2. Discord Webhook Setup

1. Go to your Discord server settings
2. Navigate to: `Integrations` > `Webhooks`
3. Create a new webhook and copy the URL

### 3. Google Gemini AI Setup (Optional)

1. Visit [Google AI Studio](https://aistudio.google.com)
2. Create an API key
3. Copy the key for configuration

### 4. Configuration

Create a `.env` file in the project directory:

```bash
# Copy the example file
cp env.example .env

# Edit the .env file with your settings
nano .env
```

The `.env` file will be automatically loaded - no need to export environment variables!

Example `.env` content:
```bash
# Required: Discord webhook for notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN

# Optional but recommended: AI analysis
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Monitoring settings
CHECK_INTERVAL=60
MAX_PAGES=3
SEND_STARTUP_NOTIFICATION=true
```

### 5. Run the Monitor

```bash
# Start monitoring (with AI analysis if configured)
python marktplaats_scraper.py

# Or run in background
nohup python marktplaats_scraper.py &
```

## 📁 Project Structure

```
marktplaats/
├── 📜 Core Application
│   ├── marktplaats_scraper.py       # Main monitor application with AI integration
│   ├── marktplaats_tv_scraper.py    # Core web scraping engine
│   └── config.py                    # Configuration management system
├── 🧪 Testing & Validation
│   ├── test_functionality.py        # Comprehensive end-to-end test suite
│   ├── test_extraction.py          # Data extraction validation tests
│   └── test_gemini_fix.py          # AI integration error handling tests
├── ⚙️ Setup & Configuration
│   ├── setup.py                     # Automated installation and setup
│   ├── requirements.txt             # Python dependencies
│   └── README.md                    # This documentation
├── 📊 Data & Logs
│   ├── seen_tv_listings.json       # Deduplication database (auto-generated)
│   ├── tv_monitor.log              # Application logs (auto-generated)
│   ├── test_functionality.log      # Test execution logs
│   └── test_extraction.log         # Extraction test logs
└── 🔧 Environment
    ├── myenv/                       # Python virtual environment
    └── __pycache__/                 # Python cache files
```

## 🤖 AI Analysis Features

When Google Gemini is enabled, each listing receives intelligent analysis:

### Analysis Components
- **📊 Deal Score (1-100)**: Comprehensive quality assessment
- **💰 Market Comparison**: Real-time price research via Google Search
- **✅ Pros Analysis**: Key advantages and selling points
- **❌ Cons Analysis**: Potential issues and drawbacks
- **🤝 Negotiation Advice**: Recommended offer prices and tactics

### Example AI Output
```
🔍 **Samsung 65" QLED Q80B**
📊 **78/100** - Excellent price for this premium model
✅ **PROS:** • Premium QLED panel • Gaming features • Recent model
❌ **CONS:** • No mention of remote • High energy usage • Size limitations
💰 **MARKET:** €1299/€800-950/€750
🤝 **OFFER: €700** - Good starting point, room for negotiation
```

### AI Technical Details
- **Model**: Gemini 2.5 Flash (latest available)
- **Grounding**: Google Search integration for real-time market data
- **Safety**: Robust error handling for API failures and content filtering
- **Performance**: Optimized prompts for sub-3-second analysis

## 📊 Discord Integration

### Rich Notification System
- 🔥 **Color-coded embeds** based on AI deal scores:
  - 🟢 Green (80-100): Excellent deals
  - 🟠 Orange (60-79): Good deals  
  - 🟡 Yellow (40-59): Average deals
  - 🔴 Red (<40): Questionable deals

### Notification Content
- **📱 Title & Description**: TV model and key details
- **💰 Price Information**: Listed price and numeric conversion
- **📍 Location**: Seller location and posting date
- **📝 Full Description**: Complete listing text (truncated to fit)
- **🔗 Direct Link**: One-click access to the listing
- **🤖 AI Analysis**: Complete deal assessment (when enabled)

### Discord Optimization
- Character limit validation (6000 char max)
- Field limit compliance (25 fields max)
- Rate limiting protection with delays
- Graceful fallback for webhook failures

## ⚙️ Configuration System

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | ✅ Yes | - | Discord webhook URL for notifications |
| `GEMINI_API_KEY` | ❌ No | - | Google Gemini API key for AI analysis |
| `CHECK_INTERVAL` | ❌ No | `60` | Monitoring interval in seconds |
| `MAX_PAGES` | ❌ No | `3` | Maximum pages to scrape per check |
| `SEND_STARTUP_NOTIFICATION` | ❌ No | `true` | Send notification when bot starts |

### Simple Usage

```bash
# 1. Copy the example configuration
cp env.example .env

# 2. Edit .env with your Discord webhook URL (required)
# Add your Gemini API key for AI analysis (optional)

# 3. Run the monitor - it automatically loads your .env settings
python marktplaats_scraper.py
```

### Advanced Configuration (config.py)

```python
from config import Config, ProductionConfig

# Use predefined configurations
Config = ProductionConfig  # or DevelopmentConfig, DemoConfig

# Custom price filtering
Config.MIN_PRICE = 100.0
Config.MAX_PRICE = 2000.0

# Keyword filtering
Config.INCLUDE_KEYWORDS = ['Samsung', 'LG', 'OLED', 'QLED']
Config.EXCLUDE_KEYWORDS = ['defect', 'kapot', 'reparatie', 'onderdelen']

# Performance tuning
Config.REQUEST_TIMEOUT = 10
Config.DELAY_BETWEEN_REQUESTS = 2.0
Config.DELAY_BETWEEN_NOTIFICATIONS = 3
```

## 🧪 Testing Suite

### Comprehensive Test Coverage

#### 1. Functionality Testing (`test_functionality.py`)
```bash
python test_functionality.py
```
Tests:
- ✅ AI analysis functionality and error handling
- ✅ Discord message formatting and validation
- ✅ Character limits and payload size compliance
- ✅ Error recovery and graceful degradation

#### 2. Data Extraction Testing (`test_extraction.py`)
```bash
python test_extraction.py
```
Tests:
- ✅ Web scraping accuracy and reliability
- ✅ Data parsing for titles, prices, locations, dates
- ✅ Success rate analysis and reporting
- ✅ HTML structure adaptation

#### 3. AI Integration Testing (`test_gemini_fix.py`)
```bash
python test_gemini_fix.py
```
Tests:
- ✅ Gemini API integration and authentication
- ✅ Response handling and validation
- ✅ Error scenarios and safety filters
- ✅ Grounding functionality verification

### Test Results Analysis
- **Extraction Success Rates**: Detailed reporting of data capture efficiency
- **Error Coverage**: Comprehensive validation of failure scenarios
- **Performance Metrics**: Response times and resource usage analysis

## 🔧 Core Components

### 1. MarktplaatsTVScraper (`marktplaats_tv_scraper.py`)
**Purpose**: Core web scraping engine
**Features**:
- Advanced HTML parsing with multiple fallback patterns
- Intelligent data extraction for titles, prices, locations, dates
- Robust error handling for website structure changes
- Brand and screen size detection from titles
- Session management with proper headers

**Key Classes**:
- `TVListing`: Data model for listings with auto-extraction features
- `MarktplaatsTVScraper`: Main scraping engine with adaptive parsing

### 2. TVMonitor (`marktplaats_scraper.py`)
**Purpose**: Main monitoring application with AI integration
**Features**:
- Real-time listing detection with deduplication
- Google Gemini AI integration with search grounding
- Discord webhook management with rich embeds
- Comprehensive logging and error recovery
- Performance monitoring and adaptive delays

**Key Methods**:
- `run_monitor()`: Continuous monitoring loop
- `run_single_check()`: One-time check for testing
- `_analyze_tv_listing()`: AI-powered deal analysis
- `_send_discord_notification()`: Rich notification system

### 3. Configuration Management (`config.py`)
**Purpose**: Centralized configuration with validation
**Features**:
- Environment variable loading with defaults
- Multiple configuration profiles (Development, Production, Demo)
- Validation and error checking
- Extensible filtering and customization options

## 🚨 Monitoring & Alerts

### Intelligent Deduplication
- **Hash-based tracking**: Unique IDs generated from title + price + location
- **Persistent storage**: `seen_tv_listings.json` maintains state across restarts
- **Collision handling**: Robust duplicate detection even with minor variations

### Alert Prioritization
- **Deal Quality**: Color-coded notifications based on AI assessment
- **Content Richness**: Complete listing information in single notification
- **Action-oriented**: Direct links and negotiation advice

### Performance Monitoring
- **Check intervals**: Configurable timing with failure adaptation
- **Success metrics**: Tracking of API calls, scraping success, notification delivery
- **Error recovery**: Automatic retries with exponential backoff

## 🛠️ Troubleshooting

### Common Issues & Solutions

#### No Notifications Received
```bash
# 1. Verify Discord webhook
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"Test message"}' \
  YOUR_WEBHOOK_URL

# 2. Check logs for errors
tail -f tv_monitor.log | grep "📨 Discord"

# 3. Run functionality tests
python test_functionality.py
```

#### AI Analysis Not Working
```bash
# 1. Verify API key in .env file
# Add GEMINI_API_KEY=your_key to .env
python test_gemini_fix.py

# 2. Check quota and permissions
# Visit: https://aistudio.google.com/app/apikey

# 3. Review AI-specific logs
tail -f tv_monitor.log | grep "🤖"
```

#### Scraping Issues
```bash
# 1. Test extraction directly
python test_extraction.py

# 2. Check for website changes
# Compare logs with successful runs

# 3. Review scraping patterns
# Check if Marktplaats changed their HTML structure
```

### Debug Mode
```bash
# Add LOG_LEVEL=DEBUG to your .env file
# Or run with environment override:
LOG_LEVEL=DEBUG python marktplaats_scraper.py
```

### Log Analysis
Key log patterns to monitor:
- `🎉 Found X new TV listings!` - Successful discovery
- `🤖 Successfully used model: gemini-2.5-flash` - AI working
- `✅ Discord notification sent` - Successful delivery
- `❌` - Any errors requiring attention

## 🔒 Privacy & Ethics

### Data Handling
- **Public data only**: Only accesses publicly listed items
- **Minimal storage**: Only listing IDs stored for deduplication
- **No personal data**: No user information collected or stored
- **Temporary processing**: Listing details processed in memory only

### Rate Limiting & Respect
- **Configurable delays**: Respects server resources with built-in delays
- **Error backing off**: Automatic slowdown during issues
- **Session management**: Proper connection handling

### Security
- **Webhook protection**: Discord URLs should be kept secure
- **API key safety**: Gemini keys stored in environment variables only
- **No data transmission**: All processing local except API calls

## 📄 Dependencies

### Core Requirements
- **requests**: HTTP requests and session management
- **beautifulsoup4**: HTML parsing and data extraction
- **google-genai**: Modern Gemini AI integration
- **python-dotenv**: Environment variable management

### Development Requirements
- **pytest**: Test framework and coverage
- **black**: Code formatting
- **flake8**: Code linting

### Version Compatibility
- **Python**: 3.8+ required, 3.10+ recommended
- **Google Gemini**: Latest API version with grounding support
- **Discord**: Webhook API v10 compatible

## 🚀 Performance

### Optimization Features
- **Concurrent processing**: Parallel handling where possible
- **Intelligent caching**: Session reuse and connection pooling
- **Adaptive timing**: Dynamic intervals based on success rates
- **Memory efficiency**: Streaming processing for large datasets

### Typical Performance
- **Scan duration**: 3-8 seconds per page
- **AI analysis**: 2-5 seconds per listing
- **Discord delivery**: <1 second per notification
- **Memory usage**: ~50MB during operation

## 🔮 Future Enhancements

### Planned Features
- **Multi-category support**: Beyond just TVs
- **Price history tracking**: Deal trend analysis
- **Advanced filtering**: Machine learning-based relevance
- **Mobile notifications**: Push notifications via apps
- **Database integration**: PostgreSQL/SQLite storage options

### Community Contributions
- **Issue reporting**: GitHub issues for bugs and features
- **Pull requests**: Code contributions welcome
- **Documentation**: Help improve this guide

## ❓ FAQ

**Q: How often should I check for new listings?**
A: 60 seconds is optimal for TVs. Faster may cause rate limiting, slower may miss time-sensitive deals.

**Q: Can I monitor other categories?**
A: Yes! Edit `TARGET_URL` in `config.py` to any Marktplaats category URL.

**Q: How accurate is the AI analysis?**
A: The AI uses real-time Google Search data for pricing. Accuracy depends on current market data availability.

**Q: What if Marktplaats changes their website?**
A: The scraper uses multiple fallback patterns. Run `test_extraction.py` to check compatibility.

**Q: How much does Gemini AI cost?**
A: Gemini has a generous free tier. Check current pricing at [Google AI Studio](https://aistudio.google.com).

**Q: Can I run this on a server?**
A: Yes! Use `nohup python marktplaats_scraper.py &` or set up as a systemd service.

**Q: Why are some seller names missing?**
A: Marktplaats doesn't show seller info in search results - this is expected behavior.

---

## 🎉 Happy Deal Hunting!

This monitor will help you catch the best TV deals on Marktplaats with intelligent analysis and instant notifications. The AI analysis feature provides valuable insights to help you make informed purchasing decisions and negotiate better prices.

For support, check the logs first, then run the test suite to identify any issues. The comprehensive error handling should keep the monitor running smoothly even during temporary network issues or API outages.