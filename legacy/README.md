# Stock Scanner

A quantitative stock screening tool for swing trading and options strategies. Scans hundreds of stocks to find high-probability setups based on technical indicators, volatility metrics, and price action.

## Features

- **Multi-Universe Scanning**: Quick scan (50 stocks), S&P 500 sample (100), or full market (550+)
- **Smart Caching**: Results cached daily to reduce API calls
- **Technical Analysis**: RSI, moving averages, trend classification, support/resistance
- **Volatility Metrics**: IV Rank proxy for options strategies
- **Volume Analysis**: Time-adjusted volume pace (accounts for time of day)
- **Opportunity Scoring**: Ranks stocks by multiple factors

## What It Finds

- High IV opportunities for premium selling (puts/calls)
- Pullback patterns in established uptrends
- Oversold bounce plays
- Stocks at key support levels with unusual volume

## Setup

### 1. Get an API Key

You'll need a free API key from [Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs):

1. Create a free account
2. Copy your API key from the dashboard

### 2. Install Dependencies

```bash
# Clone the repo
git clone https://github.com/yourusername/danecast-trades.git
cd danecast-trades

# Create virtual environment
python -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your API key
# FMP_API_KEY=your_actual_key_here
```

### 4. Run the App

```bash
streamlit run app.py
```

The scanner will open in your browser at `http://localhost:8501`

## Usage

### Scanner Tab

1. **Select Universe Size**:
   - Quick Scan (50 stocks) - Fast daily screening, ~30-60 seconds
   - S&P 500 Sample (100 stocks) - Broader coverage, ~1-2 minutes
   - Full Universe (550+ stocks) - Comprehensive scan, ~5-8 minutes

2. **Set Filters**:
   - Minimum IV Rank (default 20%) - Higher = better for options selling
   - Maximum Price - Filter out expensive stocks

3. **Execute Scan**: Results are cached for the day, so subsequent scans are instant

4. **Review Results**: Stocks ranked by opportunity score with detailed metrics

### Ticker Lookup Tab

Enter any stock symbol for a detailed technical breakdown including:
- Current price and daily change
- 52-week position and range
- Moving average distances
- RSI and momentum
- Support/resistance levels
- Strategy suggestions

## Understanding the Metrics

| Metric | What It Means |
|--------|---------------|
| **IV Rank** | Where current volatility sits in its 52-week range. 60%+ = good for selling options |
| **52W Position** | Where price sits between yearly high/low. Below 40% = potential value |
| **Volume Pace** | Current volume vs expected for time of day. 1.5x+ = unusual activity |
| **RSI** | Momentum indicator. Below 30 = oversold, above 70 = overbought |
| **Trend** | Algorithmic classification based on MA slope and price position |

## Scoring System

Stocks are scored (0-100) based on:
- High IV Rank (60%+): +20 points
- Pullback in uptrend at MA support: +25 points
- Oversold RSI (<35): +15 points
- Low in 52-week range (<40%): +20 points
- High volume pace (>1.5x): +15 points
- Large cap ($10B+): +10 points

## Project Structure

```
danecast-trades/
├── app.py              # Streamlit UI
├── src/
│   ├── __init__.py
│   ├── api.py          # FMP API client
│   ├── indicators.py   # Technical calculations
│   ├── scanner.py      # Scanner engine
│   └── universes.py    # Stock ticker lists
├── static/
│   └── styles.css      # UI styling
├── scanner_cache/      # Daily cache (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

## Tips

- **Best Times to Scan**: Before market open (get fresh ideas) or after close (review the day)
- **Large Scans**: Run full universe scans on weekends - results cache for the day
- **Options Focus**: Filter for IV Rank > 50% to find premium selling opportunities
- **Swing Trades**: Look for "Pullback in Uptrend" with RSI < 40

## License

MIT
