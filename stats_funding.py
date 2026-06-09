import os
import time
import csv
import pytz
from datetime import datetime, timezone
from dotenv import load_dotenv
from logic import initialize_client

# Constants
KYIV_TZ = pytz.timezone("Europe/Kyiv")
STATS_FILE = "funding_stats.csv"
FIELDNAMES = [
    "funding_timestamp", 
    "symbol", 
    "funding_rate_pct", 
    "volume_24h", 
    "relative_volume_1h",
    "open_interest_value",
    "spread_pct",
    "liquidity_depth_1pct_usdt",
    "volatility_1h_pct",
    "price_change_1h_pct",
    "price_change_12h_pct",
    "price_change_24h_pct",
    "price_pre_5s", 
    "price_1m", 
    "price_1m_%",
    "price_5m", 
    "price_5m_%",
    "price_10m",
    "price_10m_%"
]

def get_advanced_stats(session, symbol, current_price, ticker_item):
    """Fetch all requested advanced metrics for a coin."""
    stats = {
        "change1h": 0.0, "change12h": 0.0, "volatility": 0.0,
        "rvol": 0.0, "oi_value": 0.0, "spread": 0.0, "liquidity": 0.0
    }
    try:
        # 1. Ticker-based stats (Fast)
        bid = float(ticker_item.get("bid1Price") or 0)
        ask = float(ticker_item.get("ask1Price") or 0)
        if current_price and bid and ask:
            stats["spread"] = (ask - bid) / current_price * 100
        stats["oi_value"] = float(ticker_item.get("openInterestValue") or 0)
        vol24h = float(ticker_item.get("volume24h") or 0)

        # 2. Candle-based stats (1h, 12h, Volatility, RVOL)
        resp_k = session.get_kline(category="linear", symbol=symbol, interval="60", limit=13)
        if resp_k.get("retCode") == 0 and len(resp_k["result"]["list"]) >= 1:
            klines = resp_k["result"]["list"]
            # Bybit V5: [0] is latest. [1] is previous 1h.
            latest = klines[0]
            price_1h_ago = float(latest[1]) # Open of latest 1h candle
            vol1h = float(latest[5])
            high = float(latest[2])
            low = float(latest[3])
            
            stats["volatility"] = ((high - low) / low * 100) if low else 0
            stats["rvol"] = (vol1h / (vol24h / 24)) if vol24h > 0 else 0
            stats["change1h"] = ((current_price - price_1h_ago) / price_1h_ago * 100) if price_1h_ago else 0
            
            # 12h ago
            if len(klines) >= 13:
                price_12h_ago = float(klines[12][1])
                stats["change12h"] = ((current_price - price_12h_ago) / price_12h_ago * 100) if price_12h_ago else 0

        # 3. Liquidity (Orderbook depth within 1%)
        resp_ob = session.get_orderbook(category="linear", symbol=symbol, limit=50)
        if resp_ob.get("retCode") == 0:
            bids = resp_ob["result"]["b"]
            asks = resp_ob["result"]["a"]
            l_bound = current_price * 0.99
            u_bound = current_price * 1.01
            depth_usdt = 0
            for p, q in bids:
                pf = float(p)
                if pf >= l_bound: depth_usdt += pf * float(q)
                else: break
            for p, q in asks:
                pf = float(p)
                if pf <= u_bound: depth_usdt += pf * float(q)
                else: break
            stats["liquidity"] = depth_usdt

    except Exception as e:
        print(f"Error fetching stats for {symbol}: {e}")
    
    return stats

class FundingBatch:
    """Tracks a group of coins sharing the same funding time."""
    def __init__(self, funding_time_ms):
        self.funding_time_ms = funding_time_ms
        self.funding_time_dt = datetime.fromtimestamp(funding_time_ms / 1000, tz=timezone.utc).astimezone(KYIV_TZ)
        self.records = {} # symbol -> {all stats}
        self.price_1m = {}
        self.price_5m = {}
        self.price_10m = {}
        self.price_pre5s = {}
        self.captured_stages = set()
        self.is_completed = False

    def add_coin(self, symbol, rate, vol24h, price, change24h, adv_stats):
        self.records[symbol] = {
            "rate": rate,
            "vol24h": vol24h,
            "price": price,
            "change24h": change24h,
            **adv_stats
        }

    def update_prices(self, tickers, stage):
        target_dict = getattr(self, f"price_{stage}")
        for item in tickers:
            symbol = item["symbol"]
            if symbol in self.records:
                try:
                    target_dict[symbol] = float(item["lastPrice"])
                except (ValueError, TypeError):
                    continue
        self.captured_stages.add(stage)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Captured {stage} prices for batch {self.funding_time_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    def save_to_csv(self):
        file_exists = os.path.isfile(STATS_FILE)
        try:
            with open(STATS_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                if not file_exists:
                    writer.writeheader()
                
                ts_str = self.funding_time_dt.strftime("%Y-%m-%d %H:%M:%S")
                for symbol, d in self.records.items():
                    price_pre = d['price']
                    
                    p1m = self.price_1m.get(symbol, 0)
                    p5m = self.price_5m.get(symbol, 0)
                    p10m = self.price_10m.get(symbol, 0)
                    
                    # Calculate % changes relative to price captured 5s before funding
                    price_pre = self.price_pre5s.get(symbol, d['price'])
                    ch1m = ((p1m - price_pre) / price_pre * 100) if price_pre > 0 and p1m > 0 else 0
                    ch5m = ((p5m - price_pre) / price_pre * 100) if price_pre > 0 and p5m > 0 else 0
                    ch10m = ((p10m - price_pre) / price_pre * 100) if price_pre > 0 and p10m > 0 else 0

                    writer.writerow({
                        "funding_timestamp": ts_str,
                        "symbol": symbol,
                        "funding_rate_pct": f"{d['rate']:.6f}",
                        "volume_24h": f"{d['vol24h']:.2f}",
                        "relative_volume_1h": f"{d['rvol']:.4f}",
                        "open_interest_value": f"{d['oi_value']:.2f}",
                        "spread_pct": f"{d['spread']:.4f}",
                        "liquidity_depth_1pct_usdt": f"{d['liquidity']:.2f}",
                        "volatility_1h_pct": f"{d['volatility']:.4f}",
                        "price_change_1h_pct": f"{d['change1h']:.4f}",
                        "price_change_12h_pct": f"{d['change12h']:.4f}",
                        "price_change_24h_pct": f"{d['change24h']:.4f}",
                        "price_pre_5s": f"{price_pre:.6f}",
                        "price_1m": f"{p1m:.6f}",
                        "price_1m_%": f"{ch1m:+.4f}",
                        "price_5m": f"{p5m:.6f}",
                        "price_5m_%": f"{ch5m:+.4f}",
                        "price_10m": f"{p10m:.6f}",
                        "price_10m_%": f"{ch10m:+.4f}"
                    })
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Batch {ts_str} saved to {STATS_FILE}")
        except Exception as e:
            print(f"Error saving batch to CSV: {e}")

def main():
    load_dotenv()
    print("=== Professional Funding Stats Recorder Started ===")
    
    MIN_FUNDING_THRESHOLD = 0.100 # Minimum absolute funding rate in %

    try:
        session = initialize_client("Bybit", testnet=False)
        print("Bybit client initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize Bybit client: {e}")
        return

    # Startup: Scan for funding opportunities (replicating the main app scanner)
    print("\n" + "="*50)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] INITIAL SCAN (|Rate| >= {MIN_FUNDING_THRESHOLD}%, Time <= 1h)")
    print("="*50)
    try:
        res = session.get_tickers(category="linear")
        if res.get("retCode") == 0:
            tickers = res["result"]["list"]
            now_ms = int(time.time() * 1000)
            opportunities = []
            
            for it in tickers:
                symbol = it.get("symbol", "")
                if not symbol.endswith("USDT"): continue
                
                try:
                    rate = float(it.get("fundingRate") or 0)
                    rate_pct = rate * 100
                    next_ft_ms = int(it.get("nextFundingTime") or 0)
                except (ValueError, TypeError): continue
                
                if next_ft_ms == 0: continue
                
                secs_to_funding = (next_ft_ms - now_ms) / 1000.0
                
                # Filter by threshold AND time (only within the next 1 hour)
                if abs(rate_pct) >= MIN_FUNDING_THRESHOLD and 0 <= secs_to_funding <= 3600:
                    opportunities.append({
                        "symbol": symbol,
                        "rate": rate_pct,
                        "secs": secs_to_funding
                    })
            
            if opportunities:
                # Sort by absolute rate DESC (highest first)
                opportunities.sort(key=lambda x: abs(x["rate"]), reverse=True)
                
                print(f"{'SYMBOL':<15} | {'RATE (%)':<12} | {'TIME LEFT':<15}")
                print("-" * 50)
                for opt in opportunities:
                    # Format time like in auto_scanner.py
                    total = int(opt["secs"])
                    h = total // 3600
                    m = (total % 3600) // 60
                    s = total % 60
                    time_str = f"{h}h {m:02d}m {s:02d}s" if h > 0 else f"{m}m {s:02d}s"
                    
                    rate_str = f"{opt['rate']:+.4f}%"
                    print(f"{opt['symbol']:<15} | {rate_str:<12} | {time_str:<15}")
                print("-" * 50)
                print(f"Total opportunities found: {len(opportunities)}")
            else:
                print(f"No coins found with |rate| >= {MIN_FUNDING_THRESHOLD}%")
        else:
            print(f"Warning: Could not fetch initial tickers: {res.get('retMsg')}")
    except Exception as e:
        print(f"Error during initial scan: {e}")
    print("="*50 + "\n")

    active_batches = {}
    last_trigger_hour = -1

    while True:
        try:
            now = datetime.now(KYIV_TZ)
            
            # 1. Trigger Check (Minute 59)
            # Starting earlier (59:05) to allow more time for deep stats without hitting rate limits
            if now.minute == 59 and now.hour != last_trigger_hour and now.second >= 5:
                last_trigger_hour = now.hour
                print(f"\n[{now.strftime('%H:%M:%S')}] Minute 59 Trigger: Scanning for upcoming funding events...")
                
                response = session.get_tickers(category="linear")
                if response.get("retCode") == 0:
                    tickers = response["result"]["list"]
                    now_ms = int(time.time() * 1000)
                    
                    upcoming = []
                    for it in tickers:
                        if not it.get("symbol", "").endswith("USDT"): continue
                        
                        rate_pct = float(it.get("fundingRate") or 0) * 100
                        if abs(rate_pct) < MIN_FUNDING_THRESHOLD: continue

                        ft = int(it.get("nextFundingTime") or 0)
                        # Look for funding in the next 120 seconds
                        if 0 < (ft - now_ms) <= 120000:
                            upcoming.append(it)
                    
                    if upcoming:
                        # Group symbols by rounded funding time
                        ft_groups = {}
                        for it in upcoming:
                            ft = int(it["nextFundingTime"])
                            ft_key = (ft // 10000) * 10000
                            if ft_key not in ft_groups:
                                ft_groups[ft_key] = []
                            ft_groups[ft_key].append(it)
                        
                        for ft_ms, items in ft_groups.items():
                            if ft_ms in active_batches: continue
                            
                            batch = FundingBatch(ft_ms)
                            print(f"[{now.strftime('%H:%M:%S')}] Event detected for {batch.funding_time_dt.strftime('%Y-%m-%d %H:%M:%S')}. Processing {len(items)} symbols.")
                            
                            # Sort by funding rate magnitude
                            items.sort(key=lambda x: abs(float(x.get("fundingRate") or 0)), reverse=True)
                            target_items = items[:150]
                            
                            seen_symbols = set()
                            for idx, it in enumerate(target_items):
                                symbol = it["symbol"]
                                if symbol in seen_symbols: continue
                                seen_symbols.add(symbol)
                                
                                try:
                                    price = float(it.get("lastPrice") or 0)
                                    rate = float(it.get("fundingRate") or 0) * 100
                                    vol24h = float(it.get("volume24h") or 0)
                                    ch24h = float(it.get("price24hPcnt") or 0) * 100
                                    
                                    # Fetch deep stats
                                    adv = get_advanced_stats(session, symbol, price, it)
                                    batch.add_coin(symbol, rate, vol24h, price, ch24h, adv)
                                    
                                    # SLOW DOWN to avoid 10006 Rate Limit (Err: 10/sec for kline)
                                    # 0.15s delay allows ~6-7 requests per second, which is safer
                                    time.sleep(0.15) 
                                    
                                    if (idx + 1) % 20 == 0:
                                        print(f"  Processed {idx + 1}/{len(target_items)} coins...")
                                except Exception as e:
                                    print(f"Error gathering stats for {symbol}: {e}")
                            
                            active_batches[ft_ms] = batch
                            print(f"[{datetime.now(KYIV_TZ).strftime('%H:%M:%S')}] Batch {batch.funding_time_dt.strftime('%Y-%m-%d %H:%M:%S')} initialization complete.")
                    else:
                        print(f"[{now.strftime('%H:%M:%S')}] No coins found with funding in the next 2 minutes.")
                else:
                    print(f"API Error fetching tickers: {response.get('retMsg')}")
                    last_trigger_hour = -1 # Retry

            # 2. Update Prices for Active Batches (1m, 5m, 10m post-funding)
            if active_batches:
                # To minimize API calls, we only fetch tickers if we actually need a snapshot
                now_ms = int(time.time() * 1000)
                needs_update = False
                for ft_ms, batch in active_batches.items():
                    elapsed = (now_ms - ft_ms) / 1000.0
                    time_to_funding = (ft_ms - now_ms) / 1000.0
                    if (elapsed >= 60 and "1m" not in batch.captured_stages) or \
                       (elapsed >= 300 and "5m" not in batch.captured_stages) or \
                       (elapsed >= 600 and "10m" not in batch.captured_stages) or \
                       (0 <= time_to_funding <= 5 and "pre5s" not in batch.captured_stages):
                        needs_update = True
                        break
                
                if needs_update:
                    response = session.get_tickers(category="linear")
                    if response.get("retCode") == 0:
                        tickers = response["result"]["list"]
                        
                        completed_keys = []
                        for ft_ms, batch in active_batches.items():
                            elapsed_sec = (now_ms - ft_ms) / 1000.0
                            time_to_funding = (ft_ms - now_ms) / 1000.0
                            if 0 <= time_to_funding <= 5 and "pre5s" not in batch.captured_stages:
                                batch.update_prices(tickers, "pre5s")
                            if elapsed_sec >= 60 and "1m" not in batch.captured_stages:
                                batch.update_prices(tickers, "1m")
                            if elapsed_sec >= 300 and "5m" not in batch.captured_stages:
                                batch.update_prices(tickers, "5m")
                            if elapsed_sec >= 600 and "10m" not in batch.captured_stages:
                                batch.update_prices(tickers, "10m")
                                batch.save_to_csv()
                                completed_keys.append(ft_ms)
                        
                        for k in completed_keys:
                            del active_batches[k]

            time.sleep(2)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
