import os
import csv
import time
import hmac
import hashlib
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
BASE_URL = "https://api.bybit.com"


def sign_request(params: dict) -> dict:
    """Generate HMAC-SHA256 signature for Bybit API."""
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"

    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sign_str = f"{timestamp}{API_KEY}{recv_window}{sorted_params}"

    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": signature,
        "Content-Type": "application/json",
    }
    return headers


def get_all_funding_rates() -> list[dict]:
    """Fetch current funding rates for all USDT perpetual contracts."""
    url = f"{BASE_URL}/v5/market/tickers"
    params = {"category": "linear"}

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit API error: {data.get('retMsg')}")

    results = []
    for item in data["result"]["list"]:
        symbol = item.get("symbol", "")
        funding_rate = item.get("fundingRate")

        # Only keep USDT perpetuals with valid funding rate
        if not symbol.endswith("USDT") or funding_rate is None:
            continue

        try:
            rate = float(funding_rate)
        except (ValueError, TypeError):
            continue

        results.append({
            "symbol": symbol,
            "funding_rate": rate,
            "funding_rate_pct": round(rate * 100, 6),
            "last_price": item.get("lastPrice", "N/A"),
            "next_funding_time": item.get("nextFundingTime", "N/A"),
        })

    return results


def save_to_csv(data: list[dict], filepath: str, top_n: int = 50) -> None:
    """Sort by absolute funding rate and save top N to CSV."""
    sorted_data = sorted(data, key=lambda x: abs(x["funding_rate"]), reverse=True)
    top_data = sorted_data[:top_n]

    fieldnames = [
        "rank",
        "symbol",
        "funding_rate_pct",
        "funding_rate_raw",
        "last_price",
        "next_funding_time",
        "fetched_at",
    ]

    fetched_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for rank, row in enumerate(top_data, start=1):
            # Convert next_funding_time from ms timestamp if available
            nft = row["next_funding_time"]
            if nft and nft != "N/A" and str(nft).isdigit():
                nft = datetime.utcfromtimestamp(int(nft) / 1000).strftime("%Y-%m-%d %H:%M:%S UTC")

            writer.writerow({
                "rank": rank,
                "symbol": row["symbol"],
                "funding_rate_pct": f"{row['funding_rate_pct']:+.6f}%",
                "funding_rate_raw": row["funding_rate"],
                "last_price": row["last_price"],
                "next_funding_time": nft,
                "fetched_at": fetched_at,
            })

    print(f"✅ Saved top {top_n} funding rates to: {filepath}")
    print(f"\n{'Rank':<6} {'Symbol':<20} {'Funding Rate':>15}")
    print("-" * 45)
    for rank, row in enumerate(top_data[:10], start=1):
        print(f"{rank:<6} {row['symbol']:<20} {row['funding_rate_pct']:>+.6f}%")
    print(f"\n  ... and {max(0, top_n - 10)} more rows in the CSV.")


def main():
    print("📡 Fetching funding rates from Bybit...")

    if not API_KEY or not API_SECRET:
        print("⚠️  Warning: BYBIT_API_KEY / BYBIT_API_SECRET not set in .env")
        print("   Proceeding with public endpoint (no auth required for market data).\n")

    rates = get_all_funding_rates()
    print(f"   Retrieved {len(rates)} USDT perpetual symbols.\n")

    output_file = "funding_rates.csv"
    save_to_csv(rates, output_file, top_n=50)


if __name__ == "__main__":
    main()