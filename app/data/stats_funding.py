import time
import pytz
from datetime import datetime, timezone
from dotenv import load_dotenv
from app.core.logic import initialize_client
from app.data.database import DATABASE_FILE, FUNDING_HEADERS, fetch_rows, insert_rows

# Constants
KYIV_TZ = pytz.timezone("Europe/Kyiv")
STATS_DB_FILE = DATABASE_FILE
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
    "price_at_funding",
    "price_5s",  "price_5s_%",
    "price_15s", "price_15s_%",
    "price_30s", "price_30s_%",
    "mfe_1m_%",
    "mae_1m_%",
    "price_1m",  "price_1m_%",
    "price_5m",  "price_5m_%",
    "price_10m", "price_10m_%",
]


def read_funding_stats():
    return fetch_rows("funding_stats", FIELDNAMES)


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
            price_1h_ago = float(latest[1])  # Open of latest 1h candle
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
                if pf >= l_bound:
                    depth_usdt += pf * float(q)
                else:
                    break
            for p, q in asks:
                pf = float(p)
                if pf <= u_bound:
                    depth_usdt += pf * float(q)
                else:
                    break
            stats["liquidity"] = depth_usdt

    except Exception as e:
        print(f"Error fetching stats for {symbol}: {e}")

    return stats


class FundingBatch:
    """Tracks a group of coins sharing the same funding time."""

    def __init__(self, funding_time_ms):
        self.funding_time_ms = funding_time_ms
        self.funding_time_dt = datetime.fromtimestamp(
            funding_time_ms / 1000, tz=timezone.utc
        ).astimezone(KYIV_TZ)
        self.records = {}           # symbol -> {all pre-funding stats}

        # Price snapshots (symbol -> float)
        self.price_pre5s      = {}
        self.price_at_funding = {}  # exact price at/just before funding tick — reference for % calcs
        self.price_5s         = {}  # 5 s after funding
        self.price_15s        = {}  # 15 s after funding
        self.price_30s        = {}  # 30 s after funding
        self.price_1m         = {}  # 60 s after funding
        self.price_5m         = {}  # 5 min after funding
        self.price_10m        = {}  # 10 min after funding

        # MFE / MAE tracking during the first 60 s (symbol -> float %)
        # MFE = Maximum Favorable Excursion (highest positive % from reference)
        # MAE = Maximum Adverse Excursion (lowest negative % from reference, stored as negative)
        self.mfe_1m = {}
        self.mae_1m = {}

        self.captured_stages = set()
        self.is_completed = False

    def add_coin(self, symbol, rate, vol24h, price, change24h, adv_stats):
        self.records[symbol] = {
            "rate": rate,
            "vol24h": vol24h,
            "price": price,
            "change24h": change24h,
            **adv_stats,
        }

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    _STAGE_ATTR = {
        "pre5s":      "price_pre5s",
        "at_funding": "price_at_funding",
        "5s":         "price_5s",
        "15s":        "price_15s",
        "30s":        "price_30s",
        "1m":         "price_1m",
        "5m":         "price_5m",
        "10m":        "price_10m",
    }

    def update_prices(self, tickers, stage):
        """Write lastPrice for every tracked symbol into the appropriate dict."""
        attr = self._STAGE_ATTR.get(stage)
        if attr is None:
            return
        target_dict = getattr(self, attr)
        for item in tickers:
            symbol = item["symbol"]
            if symbol in self.records:
                try:
                    target_dict[symbol] = float(item["lastPrice"])
                except (ValueError, TypeError):
                    continue
        self.captured_stages.add(stage)
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"Captured {stage} prices for batch "
            f"{self.funding_time_dt.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def track_mfe_mae(self, tickers):
        """
        Call on every ticker fetch while elapsed_sec is in (0, 60].
        Updates running MFE and MAE for each symbol.
        """
        for item in tickers:
            symbol = item["symbol"]
            if symbol not in self.records:
                continue
            ref = self.price_at_funding.get(symbol) or self.price_pre5s.get(symbol) or self.records[symbol].get("price")
            if not ref or ref <= 0:
                continue
            try:
                price = float(item["lastPrice"])
            except (ValueError, TypeError):
                continue
            pct = (price - ref) / ref * 100
            # MFE: highest positive %
            if pct > self.mfe_1m.get(symbol, 0.0):
                self.mfe_1m[symbol] = pct
            # MAE: lowest negative % (most adverse)
            if pct < self.mae_1m.get(symbol, 0.0):
                self.mae_1m[symbol] = pct

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _pct(self, price, ref):
        """Return % change from ref to price, or 0 if data missing."""
        if ref and ref > 0 and price and price > 0:
            return (price - ref) / ref * 100
        return 0.0

    def save_to_database(self):
        try:
            ts_str = self.funding_time_dt.strftime("%Y-%m-%d %H:%M:%S")
            rows = []
            for symbol, d in self.records.items():
                price_pre = self.price_pre5s.get(symbol, d["price"])
                # price_at_funding is the reference for all second-level % columns
                price_ref = self.price_at_funding.get(symbol) or price_pre

                p5s   = self.price_5s.get(symbol, 0)
                p15s  = self.price_15s.get(symbol, 0)
                p30s  = self.price_30s.get(symbol, 0)
                p1m   = self.price_1m.get(symbol, 0)
                p5m   = self.price_5m.get(symbol, 0)
                p10m  = self.price_10m.get(symbol, 0)

                ch5s   = self._pct(p5s,  price_ref)
                ch15s  = self._pct(p15s, price_ref)
                ch30s  = self._pct(p30s, price_ref)
                ch1m   = self._pct(p1m,  price_ref)
                ch5m   = self._pct(p5m,  price_ref)
                ch10m  = self._pct(p10m, price_ref)

                mfe = self.mfe_1m.get(symbol, 0.0)
                mae = self.mae_1m.get(symbol, 0.0)

                rows.append([
                    ts_str, symbol,
                    f"{d['rate']:.6f}",       f"{d['vol24h']:.2f}",
                    f"{d['rvol']:.4f}",        f"{d['oi_value']:.2f}",
                    f"{d['spread']:.4f}",      f"{d['liquidity']:.2f}",
                    f"{d['volatility']:.4f}",  f"{d['change1h']:.4f}",
                    f"{d['change12h']:.4f}",   f"{d['change24h']:.4f}",
                    f"{price_pre:.6f}",        f"{price_ref:.6f}",
                    # second-level snapshots
                    f"{p5s:.6f}",   f"{ch5s:+.4f}",
                    f"{p15s:.6f}",  f"{ch15s:+.4f}",
                    f"{p30s:.6f}",  f"{ch30s:+.4f}",
                    # MFE / MAE
                    f"{mfe:+.4f}",  f"{mae:+.4f}",
                    # minute-level snapshots
                    f"{p1m:.6f}",   f"{ch1m:+.4f}",
                    f"{p5m:.6f}",   f"{ch5m:+.4f}",
                    f"{p10m:.6f}",  f"{ch10m:+.4f}",
                ])

            insert_rows("funding_stats", FIELDNAMES, rows)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"Batch {ts_str} saved to {STATS_DB_FILE}"
            )
        except Exception as e:
            print(f"Error saving batch to SQLite: {e}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    load_dotenv()
    print("=== Professional Funding Stats Recorder Started ===")

    MIN_FUNDING_THRESHOLD = 0.100  # Minimum absolute funding rate in %

    try:
        session = initialize_client("Bybit", testnet=False)
        print("Bybit client initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize Bybit client: {e}")
        return

    # Startup scan
    print("\n" + "=" * 50)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] INITIAL SCAN (|Rate| >= {MIN_FUNDING_THRESHOLD}%, Time <= 1h)")
    print("=" * 50)
    try:
        res = session.get_tickers(category="linear")
        if res.get("retCode") == 0:
            tickers = res["result"]["list"]
            now_ms = int(time.time() * 1000)
            opportunities = []

            for it in tickers:
                symbol = it.get("symbol", "")
                if not symbol.endswith("USDT"):
                    continue
                try:
                    rate = float(it.get("fundingRate") or 0)
                    rate_pct = rate * 100
                    next_ft_ms = int(it.get("nextFundingTime") or 0)
                except (ValueError, TypeError):
                    continue
                if next_ft_ms == 0:
                    continue
                secs_to_funding = (next_ft_ms - now_ms) / 1000.0
                if abs(rate_pct) >= MIN_FUNDING_THRESHOLD and 0 <= secs_to_funding <= 3600:
                    opportunities.append({"symbol": symbol, "rate": rate_pct, "secs": secs_to_funding})

            if opportunities:
                opportunities.sort(key=lambda x: abs(x["rate"]), reverse=True)
                print(f"{'SYMBOL':<15} | {'RATE (%)':<12} | {'TIME LEFT':<15}")
                print("-" * 50)
                for opt in opportunities:
                    total = int(opt["secs"])
                    h = total // 3600
                    m = (total % 3600) // 60
                    s = total % 60
                    time_str = f"{h}h {m:02d}m {s:02d}s" if h > 0 else f"{m}m {s:02d}s"
                    print(f"{opt['symbol']:<15} | {opt['rate']:+.4f}%  | {time_str:<15}")
                print("-" * 50)
                print(f"Total opportunities found: {len(opportunities)}")
            else:
                print(f"No coins found with |rate| >= {MIN_FUNDING_THRESHOLD}%")
        else:
            print(f"Warning: Could not fetch initial tickers: {res.get('retMsg')}")
    except Exception as e:
        print(f"Error during initial scan: {e}")
    print("=" * 50 + "\n")

    active_batches = {}
    last_trigger_hour = -1

    while True:
        try:
            now = datetime.now(KYIV_TZ)

            # ------------------------------------------------------------------
            # 1. Trigger Check (Minute 59, second >= 5)
            # ------------------------------------------------------------------
            if now.minute == 59 and now.hour != last_trigger_hour and now.second >= 5:
                last_trigger_hour = now.hour
                print(f"\n[{now.strftime('%H:%M:%S')}] Minute 59 Trigger: Scanning for upcoming funding events...")

                response = session.get_tickers(category="linear")
                if response.get("retCode") == 0:
                    tickers = response["result"]["list"]
                    now_ms = int(time.time() * 1000)

                    upcoming = []
                    for it in tickers:
                        if not it.get("symbol", "").endswith("USDT"):
                            continue
                        rate_pct = float(it.get("fundingRate") or 0) * 100
                        if abs(rate_pct) < MIN_FUNDING_THRESHOLD:
                            continue
                        ft = int(it.get("nextFundingTime") or 0)
                        if 0 < (ft - now_ms) <= 120000:
                            upcoming.append(it)

                    if upcoming:
                        ft_groups = {}
                        for it in upcoming:
                            ft = int(it["nextFundingTime"])
                            ft_key = (ft // 10000) * 10000
                            ft_groups.setdefault(ft_key, []).append(it)

                        for ft_ms, items in ft_groups.items():
                            if ft_ms in active_batches:
                                continue

                            batch = FundingBatch(ft_ms)
                            print(
                                f"[{now.strftime('%H:%M:%S')}] Event detected for "
                                f"{batch.funding_time_dt.strftime('%Y-%m-%d %H:%M:%S')}. "
                                f"Processing {len(items)} symbols."
                            )

                            items.sort(key=lambda x: abs(float(x.get("fundingRate") or 0)), reverse=True)
                            target_items = items[:150]
                            seen_symbols = set()

                            for idx, it in enumerate(target_items):
                                symbol = it["symbol"]
                                if symbol in seen_symbols:
                                    continue
                                seen_symbols.add(symbol)
                                try:
                                    price  = float(it.get("lastPrice") or 0)
                                    rate   = float(it.get("fundingRate") or 0) * 100
                                    vol24h = float(it.get("volume24h") or 0)
                                    ch24h  = float(it.get("price24hPcnt") or 0) * 100
                                    adv = get_advanced_stats(session, symbol, price, it)
                                    batch.add_coin(symbol, rate, vol24h, price, ch24h, adv)
                                    time.sleep(0.15)
                                    if (idx + 1) % 20 == 0:
                                        print(f"  Processed {idx + 1}/{len(target_items)} coins...")
                                except Exception as e:
                                    print(f"Error gathering stats for {symbol}: {e}")

                            active_batches[ft_ms] = batch
                            print(
                                f"[{datetime.now(KYIV_TZ).strftime('%H:%M:%S')}] "
                                f"Batch {batch.funding_time_dt.strftime('%Y-%m-%d %H:%M:%S')} "
                                f"initialization complete."
                            )
                    else:
                        print(f"[{now.strftime('%H:%M:%S')}] No coins found with funding in the next 2 minutes.")
                else:
                    print(f"API Error fetching tickers: {response.get('retMsg')}")
                    last_trigger_hour = -1  # Retry

            # ------------------------------------------------------------------
            # 2. Update Prices for Active Batches
            # ------------------------------------------------------------------
            sleep_interval = 2.0
            if active_batches:
                now_ms = int(time.time() * 1000)

                needs_update = False
                for ft_ms, batch in active_batches.items():
                    elapsed_sec     = (now_ms - ft_ms) / 1000.0
                    time_to_funding = (ft_ms - now_ms) / 1000.0

                    # 1. Close to funding (within 10s before or right around 0): fast polling
                    if -2.0 <= time_to_funding <= 10.0:
                        needs_update = True
                        sleep_interval = min(sleep_interval, 0.3)
                    # 2. First 62s post-funding (5s, 15s, 30s, 1m, MFE/MAE tracking): fast polling
                    elif 0 < elapsed_sec <= 62.0:
                        needs_update = True
                        sleep_interval = min(sleep_interval, 0.5)
                    # 3. Later post-funding snapshots: 5m, 10m
                    elif (elapsed_sec >= 300.0 and "5m" not in batch.captured_stages) or \
                         (elapsed_sec >= 600.0 and "10m" not in batch.captured_stages):
                        needs_update = True
                        sleep_interval = min(sleep_interval, 2.0)

                if needs_update:
                    response = session.get_tickers(category="linear")
                    if response.get("retCode") == 0:
                        tickers = response["result"]["list"]

                        completed_keys = []
                        for ft_ms, batch in active_batches.items():
                            elapsed_sec     = (now_ms - ft_ms) / 1000.0
                            time_to_funding = (ft_ms - now_ms) / 1000.0

                            # --- pre-funding snapshots ---
                            if 0 <= time_to_funding <= 6.0 and "pre5s" not in batch.captured_stages:
                                batch.update_prices(tickers, "pre5s")

                            # exact funding moment (<= 1.2s before tick or first instant <= 2.5s after 0)
                            if (time_to_funding <= 1.2 or elapsed_sec >= 0) and "at_funding" not in batch.captured_stages:
                                batch.update_prices(tickers, "at_funding")

                            # --- post-funding second-level snapshots ---
                            if elapsed_sec >= 5.0   and "5s"  not in batch.captured_stages:
                                batch.update_prices(tickers, "5s")
                            if elapsed_sec >= 15.0  and "15s" not in batch.captured_stages:
                                batch.update_prices(tickers, "15s")
                            if elapsed_sec >= 30.0  and "30s" not in batch.captured_stages:
                                batch.update_prices(tickers, "30s")

                            # --- MFE / MAE tracking during first 60 s ---
                            if 0 < elapsed_sec <= 60.0:
                                batch.track_mfe_mae(tickers)

                            # --- minute-level snapshots ---
                            if elapsed_sec >= 60.0  and "1m"  not in batch.captured_stages:
                                batch.update_prices(tickers, "1m")
                            if elapsed_sec >= 300.0 and "5m"  not in batch.captured_stages:
                                batch.update_prices(tickers, "5m")
                            if elapsed_sec >= 600.0 and "10m" not in batch.captured_stages:
                                batch.update_prices(tickers, "10m")
                                batch.save_to_database()
                                completed_keys.append(ft_ms)

                        for k in completed_keys:
                            del active_batches[k]

            time.sleep(sleep_interval)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
