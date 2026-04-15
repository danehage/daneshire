"""
Stock Universe Definitions
Curated lists of tickers for different scanning strategies
"""

# Quick scan - High volume, popular stocks for fast daily screening
QUICK_SCAN = [
    # High volume tech
    "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "GOOGL", "AMZN", "META",
    # High IV options plays
    "NFLX", "COIN", "PLTR", "RIVN", "SOFI", "RBLX", "HOOD",
    # Stable dividend payers
    "KO", "PG", "JNJ", "PFE", "XOM", "CVX",
    # Banks
    "JPM", "BAC", "WFC", "C", "GS",
    # Popular retail
    "DIS", "NKE", "SBUX", "MCD", "WMT", "TGT", "COST",
    # Semiconductors
    "INTC", "QCOM", "MU", "AVGO", "LRCX", "AMAT",
    # Healthcare
    "UNH", "LLY", "ABBV", "TMO", "ABT",
    # Finance
    "V", "MA", "PYPL", "SQ",
]

# Robinhood 100 - Most popular retail trading stocks
ROBINHOOD_100 = [
    "TSLA", "NVDA", "AAPL", "AMD", "PLTR", "SOFI", "F", "NIO", "RIVN", "LCID",
    "MARA", "RIOT", "COIN", "HOOD", "RBLX", "DKNG", "UBER", "LYFT", "DASH", "ABNB",
    "MSFT", "GOOGL", "AMZN", "META", "NFLX", "DIS", "PYPL", "SQ", "SHOP", "SNAP",
    "PINS", "SPOT", "ZM", "DOCU", "TWLO", "SNOW", "CRWD", "NET", "DDOG", "OKTA",
    "MRNA", "BNTX", "PFE", "JNJ", "ABBV", "GILD", "BIIB", "VRTX", "REGN", "AMGN",
    "FSR", "CHPT", "BLNK", "PLUG", "FCEL", "ENPH", "SEDG", "RUN",
    "AFRM", "UPST", "V", "MA", "JPM",
    "WMT", "TGT", "COST", "HD", "LOW", "ETSY", "W", "CHWY", "CVNA",
    "EA", "TTWO", "ATVI", "U", "PENN", "MGM",
    "INTC", "TSM", "QCOM", "MU", "AVGO", "ARM", "MRVL", "ON",
    "AAL", "DAL", "UAL", "LUV", "SAVE", "JBLU", "BKNG", "EXPE",
]

# S&P 500 Sample - 100 representative large caps
SP500_SAMPLE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B",
    "UNH", "JNJ", "V", "WMT", "JPM", "MA", "PG", "HD",
    "CVX", "XOM", "ABBV", "MRK", "KO", "PEP", "COST", "AVGO",
    "LLY", "BAC", "PFE", "TMO", "CSCO", "ORCL", "ACN", "MCD",
    "ABT", "DHR", "ADBE", "CRM", "VZ", "CMCSA", "DIS", "NKE",
    "WFC", "BMY", "TXN", "PM", "UPS", "RTX", "QCOM", "INTC",
    "HON", "NEE", "UNP", "AMGN", "LOW", "SPGI", "AMD", "BA",
    "GS", "CAT", "MS", "SBUX", "LMT", "AXP", "DE", "ISRG",
    "BLK", "PLD", "MDT", "ADI", "TJX", "GILD", "MMC", "CI",
    "C", "SYK", "REGN", "NOW", "ZTS", "CB", "SCHW", "PGR",
    "VRTX", "ETN", "MO", "TMUS", "BSX", "LRCX", "AMAT", "SO",
    "DUK", "EOG", "SLB", "ADP", "CME", "ITW", "GE", "MMM",
    "APD", "CL", "USB", "PNC", "ICE", "NSC", "EQIX", "WM",
]

# Full S&P 500 components (updated April 2026)
SP500_FULL = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A",
    "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL",
    "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK",
    "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT",
    "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO",
    "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX",
    "BDX", "BRK.B", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BK", "BA",
    "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BF.B", "BLDR", "BG", "BXP",
    "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY",
    "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW",
    "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO",
    "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL",
    "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW",
    "CPAY", "CTVA", "CSGP", "COST", "CTRA", "CRH", "CRWD", "CCI", "CSX", "CMI",
    "CVS", "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN",
    "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW",
    "DHI", "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW",
    "EA", "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX",
    "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE",
    "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS",
    "FITB", "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN",
    "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS",
    "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS",
    "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST",
    "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW",
    "INCY", "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG",
    "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI",
    "JPM", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC",
    "KHC", "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY",
    "LIN", "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC",
    "MAR", "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK",
    "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP",
    "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP",
    "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS",
    "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL",
    "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY",
    "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW",
    "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG",
    "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX",
    "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL",
    "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE",
    "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV",
    "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY",
    "TMUS", "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA",
    "TXN", "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG",
    "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP",
    "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VTR", "VLTO", "VRSN", "VRSK",
    "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW",
    "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST",
    "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM",
    "ZBRA", "ZBH", "ZTS",
]


# Universe name -> ticker list mapping
UNIVERSES = {
    "quick": QUICK_SCAN,
    "robinhood": ROBINHOOD_100,
    "sp500_sample": SP500_SAMPLE,
    "sp500": SP500_FULL,
}


def get_universe(name: str) -> list[str]:
    """Get ticker list by universe name."""
    return UNIVERSES.get(name, QUICK_SCAN)


def get_combined_universe() -> list[str]:
    """
    Combine S&P 500 + Robinhood 100, remove duplicates.
    Returns ~550-600 unique tickers sorted alphabetically.
    """
    combined = set(SP500_FULL + ROBINHOOD_100)
    return sorted(list(combined))
