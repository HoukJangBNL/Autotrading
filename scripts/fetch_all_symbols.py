"""Fetch all US stock symbols from various sources."""

import json
import pandas as pd
import requests
from pathlib import Path
from typing import List, Set
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_nasdaq_symbols() -> Set[str]:
    """Fetch all NASDAQ and NYSE symbols from NASDAQ FTP."""
    symbols = set()
    
    try:
        # NASDAQ listed
        nasdaq_url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.nasdaq.com',
            'Referer': 'https://www.nasdaq.com/'
        }
        
        response = requests.get(nasdaq_url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            for row in data['data']['rows']:
                symbol = row['symbol']
                # Filter out special symbols
                if symbol and not any(c in symbol for c in ['.', '/', '^', '~']):
                    symbols.add(symbol)
            logger.info(f"Fetched {len(symbols)} symbols from NASDAQ API")
    except Exception as e:
        logger.error(f"Error fetching NASDAQ symbols: {e}")
    
    # Alternative: FTP download
    try:
        nasdaq_listed = pd.read_csv(
            "ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt", 
            sep="|"
        )
        other_listed = pd.read_csv(
            "ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt", 
            sep="|"
        )
        
        # Add NASDAQ symbols
        for symbol in nasdaq_listed['Symbol']:
            if pd.notna(symbol) and symbol != 'Symbol':
                symbols.add(symbol.strip())
        
        # Add NYSE and other symbols  
        for symbol in other_listed['NASDAQ Symbol']:
            if pd.notna(symbol) and symbol != 'NASDAQ Symbol':
                symbols.add(symbol.strip())
                
        logger.info(f"Total symbols from FTP: {len(symbols)}")
    except Exception as e:
        logger.error(f"Error fetching from FTP: {e}")
    
    return symbols


def fetch_popular_symbols() -> Set[str]:
    """Fetch popular/liquid symbols from various sources."""
    symbols = set()
    
    # Load existing symbol files if available
    config_dir = Path(__file__).parent.parent / "config"
    
    # Load SP100 if exists
    sp100_file = config_dir / "sp100_symbols.json"
    if sp100_file.exists():
        with open(sp100_file) as f:
            sp100_data = json.load(f)
            symbols.update(sp100_data)
            logger.info(f"Added {len(sp100_data)} S&P 100 symbols from file")
    
    # Load NASDAQ100 if exists
    nasdaq100_file = config_dir / "nasdaq100_symbols.json" 
    if nasdaq100_file.exists():
        with open(nasdaq100_file) as f:
            nasdaq100_data = json.load(f)
            symbols.update(nasdaq100_data)
            logger.info(f"Added {len(nasdaq100_data)} NASDAQ 100 symbols from file")
    
    # Try to fetch from datahub.io (alternative source)
    try:
        sp500_url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
        sp500_df = pd.read_csv(sp500_url)
        if 'Symbol' in sp500_df.columns:
            symbols.update(sp500_df['Symbol'].tolist())
            logger.info(f"Added {len(sp500_df)} S&P 500 symbols from datahub.io")
    except Exception as e:
        logger.error(f"Error fetching from datahub.io: {e}")
    
    # Add some manually curated popular symbols
    popular_manual = [
        'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'GOOG', 'NVDA', 'META', 'TSLA', 'BRK.B',
        'JPM', 'JNJ', 'V', 'WMT', 'UNH', 'MA', 'HD', 'PG', 'DIS', 'BAC', 'XOM',
        'NFLX', 'ADBE', 'CRM', 'TMO', 'CMCSA', 'PFE', 'ABBV', 'KO', 'PEP', 'NKE',
        'MRK', 'CVX', 'LLY', 'AVGO', 'COST', 'VZ', 'WFC', 'ABT', 'MCD', 'ACN',
        'AMD', 'INTC', 'ORCL', 'TXN', 'MDT', 'UPS', 'HON', 'NEE', 'DHR', 'QCOM',
        'SPY', 'QQQ', 'IWM', 'DIA', 'VOO', 'VTI', 'EEM', 'GLD', 'TLT', 'XLF'
    ]
    symbols.update(popular_manual)
    logger.info(f"Added {len(popular_manual)} manually curated popular symbols")
    
    return symbols


def filter_symbols(symbols: Set[str]) -> List[str]:
    """Filter and clean symbols."""
    filtered = []
    
    for symbol in symbols:
        # Skip if empty or too long
        if not symbol or len(symbol) > 5:
            continue
            
        # Skip special characters
        if any(c in symbol for c in ['.', '/', '^', '~', '$', ' ']):
            continue
            
        # Skip test symbols
        if symbol in ['TEST', 'DUMMY', 'N/A']:
            continue
            
        filtered.append(symbol.upper())
    
    return sorted(list(set(filtered)))


def save_symbols(symbols: List[str], category: str = "all"):
    """Save symbols to JSON file."""
    config_dir = Path(__file__).parent.parent / "config"
    config_dir.mkdir(exist_ok=True)
    
    filename = config_dir / f"{category}_symbols.json"
    
    data = {
        "symbols": symbols,
        "count": len(symbols),
        "category": category,
        "updated": pd.Timestamp.now().isoformat()
    }
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved {len(symbols)} symbols to {filename}")


def main():
    """Main function to fetch and save all symbols."""
    
    # Fetch all symbols
    all_symbols = fetch_nasdaq_symbols()
    logger.info(f"Total unique symbols: {len(all_symbols)}")
    
    # Filter and clean
    filtered_all = filter_symbols(all_symbols)
    logger.info(f"Filtered symbols: {len(filtered_all)}")
    
    # Save all symbols
    save_symbols(filtered_all, "all_us_stocks")
    
    # Fetch and save popular symbols separately
    popular = fetch_popular_symbols()
    filtered_popular = filter_symbols(popular)
    save_symbols(filtered_popular, "popular_stocks")
    
    # Create categories
    categories = {
        "mega_cap": [],  # > $200B
        "large_cap": [], # $10B - $200B  
        "mid_cap": [],   # $2B - $10B
        "small_cap": [], # < $2B
        "penny_stocks": [] # < $1 price
    }
    
    # Save categorized lists
    for category, symbols in categories.items():
        if symbols:
            save_symbols(symbols, category)
    
    print(f"\n✅ Successfully fetched and saved {len(filtered_all)} US stock symbols")
    print(f"📁 Files saved in config/ directory")
    print(f"   - all_us_stocks.json: {len(filtered_all)} symbols")
    print(f"   - popular_stocks.json: {len(filtered_popular)} symbols")


if __name__ == "__main__":
    main()