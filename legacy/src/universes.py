"""
Stock Universe Definitions
Curated lists of tickers for different scanning strategies
"""

# Quick scan - High volume, popular stocks for fast daily screening
QUICK_SCAN = [
    # High volume tech
    'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD', 'GOOGL', 'AMZN', 'META',
    # High IV options plays
    'NFLX', 'COIN', 'PLTR', 'RIVN', 'SOFI', 'RBLX', 'HOOD',
    # Stable dividend payers
    'KO', 'PG', 'JNJ', 'PFE', 'XOM', 'CVX',
    # Banks
    'JPM', 'BAC', 'WFC', 'C', 'GS',
    # Popular retail
    'DIS', 'NKE', 'SBUX', 'MCD', 'WMT', 'TGT', 'COST',
    # Semiconductors
    'INTC', 'QCOM', 'MU', 'AVGO', 'LRCX', 'AMAT',
    # Healthcare
    'UNH', 'LLY', 'ABBV', 'TMO', 'ABT',
    # Finance
    'V', 'MA', 'PYPL', 'SQ'
]

# Robinhood 100 - Most popular retail trading stocks
ROBINHOOD_100 = [
    'TSLA', 'NVDA', 'AAPL', 'AMD', 'PLTR', 'SOFI', 'F', 'NIO', 'RIVN', 'LCID',
    'MARA', 'RIOT', 'COIN', 'HOOD', 'RBLX', 'DKNG', 'UBER', 'LYFT', 'DASH', 'ABNB',
    'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'DIS', 'PYPL', 'SQ', 'SHOP', 'SNAP',
    'PINS', 'SPOT', 'ZM', 'DOCU', 'TWLO', 'SNOW', 'CRWD', 'NET', 'DDOG', 'OKTA',
    'MRNA', 'BNTX', 'PFE', 'JNJ', 'ABBV', 'GILD', 'BIIB', 'VRTX', 'REGN', 'AMGN',
    'FSR', 'CHPT', 'BLNK', 'PLUG', 'FCEL', 'ENPH', 'SEDG', 'RUN',
    'AFRM', 'UPST', 'V', 'MA', 'JPM',
    'WMT', 'TGT', 'COST', 'HD', 'LOW', 'ETSY', 'W', 'CHWY', 'CVNA',
    'EA', 'TTWO', 'ATVI', 'U', 'PENN', 'MGM',
    'INTC', 'TSM', 'QCOM', 'MU', 'AVGO', 'ARM', 'MRVL', 'ON',
    'AAL', 'DAL', 'UAL', 'LUV', 'SAVE', 'JBLU', 'BKNG', 'EXPE'
]

# S&P 500 Sample - 100 representative large caps
SP500_SAMPLE = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B',
    'UNH', 'JNJ', 'V', 'WMT', 'JPM', 'MA', 'PG', 'HD',
    'CVX', 'XOM', 'ABBV', 'MRK', 'KO', 'PEP', 'COST', 'AVGO',
    'LLY', 'BAC', 'PFE', 'TMO', 'CSCO', 'ORCL', 'ACN', 'MCD',
    'ABT', 'DHR', 'ADBE', 'CRM', 'VZ', 'CMCSA', 'DIS', 'NKE',
    'WFC', 'BMY', 'TXN', 'PM', 'UPS', 'RTX', 'QCOM', 'INTC',
    'HON', 'NEE', 'UNP', 'AMGN', 'LOW', 'SPGI', 'AMD', 'BA',
    'GS', 'CAT', 'MS', 'SBUX', 'LMT', 'AXP', 'DE', 'ISRG',
    'BLK', 'PLD', 'MDT', 'ADI', 'TJX', 'GILD', 'MMC', 'CI',
    'C', 'SYK', 'REGN', 'NOW', 'ZTS', 'CB', 'SCHW', 'PGR',
    'VRTX', 'ETN', 'MO', 'TMUS', 'BSX', 'LRCX', 'AMAT', 'SO',
    'DUK', 'EOG', 'SLB', 'ADP', 'CME', 'ITW', 'GE', 'MMM',
    'APD', 'CL', 'USB', 'PNC', 'ICE', 'NSC', 'EQIX', 'WM'
]

# Full S&P 500 components
SP500_FULL = [
    # Mega Cap Tech
    'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL',
    'CRM', 'ADBE', 'CSCO', 'ACN', 'AMD', 'INTC', 'IBM', 'QCOM', 'TXN', 'INTU',
    # Finance
    'BRK.B', 'JPM', 'V', 'MA', 'BAC', 'WFC', 'GS', 'MS', 'C', 'SPGI',
    'AXP', 'BLK', 'SCHW', 'USB', 'PNC', 'TFC', 'COF', 'CB', 'MMC', 'PGR',
    'AON', 'AIG', 'MET', 'PRU', 'ALL', 'TRV', 'AFL', 'HIG', 'CINF', 'L',
    # Healthcare
    'UNH', 'LLY', 'JNJ', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'PFE', 'AMGN',
    'CVS', 'MDT', 'BMY', 'GILD', 'CI', 'ISRG', 'REGN', 'VRTX', 'ZTS', 'HCA',
    'BSX', 'ELV', 'MCK', 'COR', 'SYK', 'BDX', 'HUM', 'IDXX', 'A',
    # Consumer Discretionary
    'HD', 'MCD', 'NKE', 'SBUX', 'TJX', 'BKNG', 'CMG', 'MAR',
    'LOW', 'TGT', 'ABNB', 'GM', 'F', 'ORLY', 'AZO', 'YUM', 'DHI', 'LEN',
    'RCL', 'CCL', 'NCLH', 'LVS', 'WYNN', 'MGM', 'EXPE', 'EBAY', 'ETSY', 'W',
    # Consumer Staples
    'WMT', 'PG', 'KO', 'PEP', 'COST', 'PM', 'MO', 'MDLZ', 'CL', 'GIS',
    'KMB', 'STZ', 'KHC', 'HSY', 'K', 'CAG', 'SJM', 'CPB', 'MKC', 'TSN',
    # Industrials
    'CAT', 'BA', 'RTX', 'UNP', 'HON', 'UPS', 'GE', 'MMM', 'DE', 'LMT',
    'ADP', 'ITW', 'ETN', 'NSC', 'EMR', 'GD', 'TT', 'PCAR', 'CMI', 'FDX',
    'CSX', 'NOC', 'WM', 'RSG', 'CARR', 'OTIS', 'IR', 'FAST', 'PAYX', 'CHRW',
    # Energy
    'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'MPC', 'PSX', 'VLO', 'OXY', 'KMI',
    'WMB', 'HES', 'DVN', 'HAL', 'BKR', 'FANG', 'MRO', 'APA', 'TRGP', 'EQT',
    # Technology
    'NOW', 'AMAT', 'LRCX', 'KLAC', 'SNPS', 'CDNS', 'MCHP', 'ADI', 'NXPI',
    'TEAM', 'ZS', 'FTNT', 'PANW', 'WDAY', 'DDOG',
    # Communication Services
    'NFLX', 'DIS', 'CMCSA', 'T', 'VZ', 'TMUS', 'CHTR',
    'EA', 'TTWO', 'WBD', 'FOXA', 'FOX', 'NWSA', 'NWS', 'OMC', 'IPG',
    # Utilities
    'NEE', 'SO', 'DUK', 'D', 'AEP', 'EXC', 'SRE', 'XEL', 'WEC', 'PCG',
    'ED', 'PEG', 'ES', 'FE', 'ETR', 'AWK', 'DTE', 'PPL', 'CMS', 'CNP',
    # Real Estate
    'PLD', 'AMT', 'EQIX', 'CCI', 'PSA', 'WELL', 'SPG', 'O', 'DLR', 'VICI',
    'AVB', 'EQR', 'SBAC', 'MAA', 'ESS', 'VTR', 'ARE', 'INVH', 'EXR', 'UDR',
    # Materials
    'LIN', 'APD', 'SHW', 'ECL', 'NEM', 'FCX', 'NUE', 'DD', 'DOW', 'VMC',
    'MLM', 'CTVA', 'ALB', 'CF', 'MOS', 'PPG', 'EMN', 'IFF', 'CE', 'FMC',
    # Additional Semiconductors
    'MRVL', 'MPWR', 'ON', 'TER', 'SWKS', 'QRVO',
    # Healthcare Equipment
    'EW', 'BAX', 'RMD', 'DXCM', 'HOLX', 'ALGN', 'MTD', 'GEHC', 'RVTY', 'ZBH',
    # Biotech
    'BIIB', 'MRNA', 'ALNY', 'NBIX', 'EXAS', 'TECH', 'INCY', 'VTRS', 'JAZZ',
    # Software & Cloud
    'OKTA', 'CRWD', 'NET', 'SNOW', 'MDB', 'ESTC', 'CFLT', 'DBX',
    # Retail
    'ROST', 'DG', 'DLTR', 'CHWY', 'CVNA', 'KSS', 'M', 'JWN', 'BBY', 'GPS',
    # Regional Banks
    'BK', 'STT', 'NTRS', 'CFG', 'KEY', 'FITB', 'HBAN', 'RF', 'MTB', 'ZION',
    # Insurance
    'GL', 'AJG', 'WRB', 'RLI', 'JKHY', 'BRO', 'AIZ', 'AFG',
    # Transportation
    'DAL', 'UAL', 'AAL', 'LUV', 'EXPD', 'KNX', 'ODFL', 'XPO', 'JBHT', 'LSTR', 'SAIA',
    # Restaurants & Hotels
    'QSR', 'DRI', 'DPZ', 'HLT', 'IHG', 'H',
    # Auto
    'APTV', 'BWA', 'ALV',
    # Other
    'BRK.A'
]


def get_combined_universe() -> list[str]:
    """
    Combine S&P 500 + Robinhood 100, remove duplicates.
    Returns ~550-600 unique tickers sorted alphabetically.
    """
    combined = set(SP500_FULL + ROBINHOOD_100)
    return sorted(list(combined))
