import os
import time
import csv
from datetime import datetime
from dotenv import load_dotenv
from logic import initialize_client

# Constants
STATS_FILE = "funding_stats.csv"

def record_funding_stats(session):
    """Fetch and record funding rates for all linear USDT perpetuals."""
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching funding rates...")
        
        # Get all linear tickers from Bybit
        response = session.get_tickers(category="linear")
        if response.get("retCode") != 0:
            print(f"Error fetching tickers: {response.get('retMsg')}")
            return

        tickers = response["result"]["list"]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        file_exists = os.path.isfile(STATS_FILE)
        
        # Open CSV file in append mode
        with open(STATS_FILE, "a", newline="", encoding="utf-8") as f:
            fieldnames = ["datetime", "symbol", "funding_rate_pct"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            count = 0
            for item in tickers:
                symbol = item.get("symbol", "")
                # Only process USDT pairs as per project convention
                if not symbol.endswith("USDT"):
                    continue
                
                try:
                    # fundingRate is returned as a decimal string (e.g., "0.0001")
                    rate = float(item.get("fundingRate") or 0) * 100
                    writer.writerow({
                        "datetime": now_str,
                        "symbol": symbol,
                        "funding_rate_pct": f"{rate:.6f}"
                    })
                    count += 1
                except (ValueError, TypeError) as e:
                    print(f"Error parsing rate for {symbol}: {e}")
                    continue
            
            print(f"Successfully recorded stats for {count} coins.")
            
    except Exception as e:
        print(f"Unexpected error in record_funding_stats: {e}")

def main():
    """Main loop to monitor time and trigger recording at the 59th minute."""
    load_dotenv()
    print("=== Funding Stats Recorder Started ===")
    
    # Initialize Bybit session (Mainnet by default for stats)
    try:
        # We use testnet=False as statistics are typically gathered from production
        session = initialize_client("Bybit", testnet=False)
        print("Bybit client initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize Bybit client: {e}")
        return

    last_recorded_hour = -1

    try:
        while True:
            now = datetime.now()
            current_minute = now.minute
            current_hour = now.hour

            # Trigger at the 59th minute of every hour
            if current_minute == 59 and last_recorded_hour != current_hour:
                record_funding_stats(session)
                last_recorded_hour = current_hour
            
            # Sleep to prevent high CPU usage, check every 30 seconds
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nRecorder stopped by user.")
    except Exception as e:
        print(f"Fatal error in main loop: {e}")

if __name__ == "__main__":
    main()
