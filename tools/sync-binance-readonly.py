#!/usr/bin/env python3
"""
Sync Binance USD-M Futures read-only trade history into OpenClaw JSON files.

Safety model:
- Uses signed GET endpoints only.
- Does not contain order, cancel, transfer, or withdraw endpoints.
- API keys are read from a local .env file that must never be committed.
- Frontend continues to read local JSON only.
"""

import argparse
import hashlib
import hmac
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
TRADES_FILE = ROOT / "trades.json"
STATUS_FILE = ROOT / "status.json"
BACKUP_DIR = ROOT / "backups"

FAPI_BASE = "https://fapi.binance.com"
SAPI_BASE = "https://api.binance.com"
SPOT_BASE = "https://api.binance.com"
DAPI_BASE = "https://dapi.binance.com"
EAPI_BASE = "https://eapi.binance.com"

SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
STABLE_USD_ASSETS = {"USDT", "USDC", "FDUSD", "BUSD", "TUSD", "USDP", "DAI"}


class SyncError(RuntimeError):
    pass


class Config:
    def __init__(
        self,
        api_key,
        api_secret,
        markets,
        sync_days,
        initial_balance,
        strict_permission_check,
        auto_discover,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.markets = markets
        self.sync_days = sync_days
        self.initial_balance = initial_balance
        self.strict_permission_check = strict_permission_check
        self.auto_discover = auto_discover


def load_dotenv(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def getenv(name: str, env_file_values: Dict[str, str], default: str = "") -> str:
    return os.environ.get(name, env_file_values.get(name, default)).strip()


def read_config() -> Config:
    env_values = load_dotenv(ENV_FILE)
    api_key = getenv("BINANCE_API_KEY", env_values)
    api_secret = getenv("BINANCE_API_SECRET", env_values)
    markets_raw = getenv("BINANCE_MARKETS", env_values, "BTCUSDT,ETHUSDT,SOLUSDT")
    markets = [item.strip().upper() for item in markets_raw.split(",") if item.strip()]
    sync_days = int(getenv("BINANCE_SYNC_DAYS", env_values, "30"))
    initial_balance = float(getenv("OPENCLAW_INITIAL_BALANCE", env_values, "0") or 0)
    strict_permission_check = getenv("BINANCE_STRICT_PERMISSION_CHECK", env_values, "0") == "1"
    auto_discover = getenv("BINANCE_AUTO_DISCOVER", env_values, "1") != "0"

    if not api_key or not api_secret:
        raise SyncError("Missing BINANCE_API_KEY or BINANCE_API_SECRET in .env")
    if not markets:
        raise SyncError("BINANCE_MARKETS is empty")
    if sync_days < 1 or sync_days > 180:
        raise SyncError("BINANCE_SYNC_DAYS must be between 1 and 180")

    return Config(
        api_key=api_key,
        api_secret=api_secret,
        markets=markets,
        sync_days=sync_days,
        initial_balance=initial_balance,
        strict_permission_check=strict_permission_check,
        auto_discover=auto_discover,
    )


def now_ms() -> int:
    return int(time.time() * 1000)


def sign_query(params: Dict[str, Any], api_secret: str) -> str:
    query = urllib.parse.urlencode(params, doseq=True)
    signature = hmac.new(api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{query}&signature={signature}"


def signed_get(base_url: str, path: str, params: Dict[str, Any], config: Config) -> Any:
    payload = dict(params)
    payload.setdefault("recvWindow", 5000)
    payload["timestamp"] = now_ms()
    query = sign_query(payload, config.api_secret)
    url = f"{base_url}{path}?{query}"
    request = urllib.request.Request(url, headers={"X-MBX-APIKEY": config.api_key})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise SyncError(f"Binance HTTP {error.code} for {path}: {body}") from error
    except urllib.error.URLError as error:
        raise SyncError(f"Network error for {path}: {error}") from error


def public_get(base_url: str, path: str, params: Dict[str, Any]) -> Any:
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{base_url}{path}?{query}" if query else f"{base_url}{path}"
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise SyncError(f"Binance HTTP {error.code} for {path}: {body}") from error
    except urllib.error.URLError as error:
        raise SyncError(f"Network error for {path}: {error}") from error


def check_permissions(config: Config) -> None:
    try:
        restrictions = signed_get(SAPI_BASE, "/sapi/v1/account/apiRestrictions", {}, config)
    except SyncError as error:
        message = f"Permission check unavailable: {error}"
        if config.strict_permission_check:
            raise SyncError(message) from error
        print(f"[WARN] {message}")
        print("[WARN] Continuing because BINANCE_STRICT_PERMISSION_CHECK=0.")
        return

    risky_keys = [
        "enableSpotAndMarginTrading",
        "enableMargin",
        "enableWithdrawals",
        "enableInternalTransfer",
        "permitsUniversalTransfer",
        "enableVanillaOptions",
    ]
    risky_enabled = [key for key in risky_keys if bool(restrictions.get(key))]
    if risky_enabled:
        joined = ", ".join(risky_enabled)
        raise SyncError(f"API key is not read-only. Risky permissions enabled: {joined}")

    if restrictions.get("enableReading") is False:
        raise SyncError("API key does not have reading permission enabled")


def discover_symbols_from_income(config: Config) -> List[str]:
    end = now_ms()
    start = end - config.sync_days * 24 * 60 * 60 * 1000
    symbols = set()

    print("[INFO] Discovering traded symbols from Binance income history")
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + SEVEN_DAYS_MS - 1, end)
        page = 1
        while True:
            params = {
                "startTime": chunk_start,
                "endTime": chunk_end,
                "page": page,
                "limit": 1000,
            }
            rows = signed_get(FAPI_BASE, "/fapi/v1/income", params, config)
            if not isinstance(rows, list):
                raise SyncError(f"Unexpected income response: {rows}")
            for row in rows:
                symbol = str(row.get("symbol") or "").upper().strip()
                if symbol.endswith("USDT"):
                    symbols.add(symbol)
            if len(rows) < 1000:
                break
            page += 1
            time.sleep(0.08)
        print(f"[INFO] Income {datetime_from_ms(chunk_start)} -> {datetime_from_ms(chunk_end)}: {len(symbols)} symbols so far")
        chunk_start = chunk_end + 1
        time.sleep(0.08)

    return sorted(symbols)


def resolve_markets(config: Config) -> List[str]:
    if not config.auto_discover:
        return config.markets

    discovered = discover_symbols_from_income(config)
    if discovered:
        print(f"[INFO] Auto-discovered symbols: {', '.join(discovered)}")
        return discovered

    print(f"[WARN] No symbols discovered from income history. Falling back to BINANCE_MARKETS: {', '.join(config.markets)}")
    return config.markets


def fetch_user_trades(config: Config, markets: List[str]) -> List[Dict[str, Any]]:
    end = now_ms()
    start = end - config.sync_days * 24 * 60 * 60 * 1000
    all_trades: List[Dict[str, Any]] = []

    for symbol in markets:
        chunk_start = start
        print(f"[INFO] Syncing {symbol}")
        while chunk_start < end:
            chunk_end = min(chunk_start + SEVEN_DAYS_MS - 1, end)
            params = {
                "symbol": symbol,
                "startTime": chunk_start,
                "endTime": chunk_end,
                "limit": 1000,
            }
            rows = signed_get(FAPI_BASE, "/fapi/v1/userTrades", params, config)
            if isinstance(rows, list):
                all_trades.extend(rows)
                print(f"[INFO] {symbol} {datetime_from_ms(chunk_start)} -> {datetime_from_ms(chunk_end)}: {len(rows)} fills")
            else:
                raise SyncError(f"Unexpected response for {symbol}: {rows}")
            chunk_start = chunk_end + 1
            time.sleep(0.08)

    all_trades.sort(key=lambda item: int(item.get("time", 0)))
    deduped: Dict[str, Dict[str, Any]] = {}
    for row in all_trades:
        trade_id = f"{row.get('symbol')}:{row.get('id')}:{row.get('orderId')}:{row.get('time')}"
        deduped[trade_id] = row
    return list(deduped.values())


def fetch_usdm_balances(config: Config) -> List[Dict[str, Any]]:
    try:
        balances = signed_get(FAPI_BASE, "/fapi/v2/balance", {}, config)
    except SyncError as error:
        print(f"[WARN] USD-M futures balance unavailable: {error}")
        return []
    return balances if isinstance(balances, list) else []


def fetch_coinm_balances(config: Config) -> List[Dict[str, Any]]:
    try:
        balances = signed_get(DAPI_BASE, "/dapi/v1/balance", {}, config)
    except SyncError as error:
        print(f"[WARN] COIN-M futures balance unavailable: {error}")
        return []
    return balances if isinstance(balances, list) else []


def fetch_spot_balances(config: Config) -> List[Dict[str, Any]]:
    try:
        account = signed_get(SPOT_BASE, "/api/v3/account", {}, config)
    except SyncError as error:
        print(f"[WARN] Spot account balance unavailable: {error}")
        return []
    balances = account.get("balances") if isinstance(account, dict) else []
    return balances if isinstance(balances, list) else []


def fetch_options_balances(config: Config) -> List[Dict[str, Any]]:
    try:
        account = signed_get(EAPI_BASE, "/eapi/v1/account", {}, config)
    except SyncError as error:
        print(f"[WARN] Options account balance unavailable: {error}")
        return []
    if isinstance(account, dict):
        for key in ("asset", "assets", "balances"):
            rows = account.get(key)
            if isinstance(rows, list):
                return rows
    return account if isinstance(account, list) else []


def first_float(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        try:
            return float(row.get(key))
        except (TypeError, ValueError):
            continue
    return None


def price_asset_in_usdt(asset: str, price_cache: Dict[str, Optional[float]]) -> Optional[float]:
    asset = asset.upper()
    if asset in STABLE_USD_ASSETS:
        return 1.0
    if asset in price_cache:
        return price_cache[asset]

    symbol = f"{asset}USDT"
    try:
        ticker = public_get(SPOT_BASE, "/api/v3/ticker/price", {"symbol": symbol})
        price = float(ticker.get("price"))
        price_cache[asset] = price
        return price
    except Exception:
        price_cache[asset] = None
        return None


def add_asset_value(
    breakdown: Dict[str, Any],
    account: str,
    asset: str,
    amount: float,
    price_cache: Dict[str, Optional[float]],
) -> None:
    if abs(amount) <= 0:
        return
    price = price_asset_in_usdt(asset, price_cache)
    row = breakdown.setdefault(
        account,
        {
            "total_usdt": 0.0,
            "assets": [],
            "unpriced_assets": [],
        },
    )
    if price is None:
        row["unpriced_assets"].append({"asset": asset, "amount": amount})
        return
    value = amount * price
    row["total_usdt"] += value
    row["assets"].append(
        {
            "asset": asset,
            "amount": round(amount, 12),
            "price_usdt": round(price, 8),
            "value_usdt": round(value, 8),
        }
    )


def fetch_total_assets(config: Config) -> Dict[str, Any]:
    price_cache: Dict[str, Optional[float]] = {}
    breakdown: Dict[str, Any] = {}

    for row in fetch_spot_balances(config):
        asset = str(row.get("asset") or "").upper()
        free = first_float(row, ["free"]) or 0.0
        locked = first_float(row, ["locked"]) or 0.0
        add_asset_value(breakdown, "spot", asset, free + locked, price_cache)

    for row in fetch_usdm_balances(config):
        asset = str(row.get("asset") or "").upper()
        amount = first_float(row, ["balance", "crossWalletBalance", "availableBalance"]) or 0.0
        add_asset_value(breakdown, "usdm_futures", asset, amount, price_cache)

    for row in fetch_coinm_balances(config):
        asset = str(row.get("asset") or "").upper()
        amount = first_float(row, ["balance", "walletBalance", "crossWalletBalance", "availableBalance"]) or 0.0
        add_asset_value(breakdown, "coinm_futures", asset, amount, price_cache)

    for row in fetch_options_balances(config):
        asset = str(row.get("asset") or row.get("currency") or "").upper()
        amount = first_float(row, ["equity", "marginBalance", "walletBalance", "available", "balance"]) or 0.0
        add_asset_value(breakdown, "options", asset, amount, price_cache)

    total = sum(float(item.get("total_usdt", 0.0)) for item in breakdown.values())
    for item in breakdown.values():
        item["total_usdt"] = round(float(item.get("total_usdt", 0.0)), 8)
    return {
        "total_usdt": round(total, 8),
        "breakdown": breakdown,
    }


def fetch_usdt_balance(config: Config) -> Optional[float]:
    total_assets = fetch_total_assets(config)
    return float(total_assets.get("total_usdt", 0.0))



def datetime_from_ms(value: Any) -> str:
    timestamp = int(value) / 1000
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def infer_direction(row: Dict[str, Any], realized_pnl: float) -> str:
    position_side = str(row.get("positionSide") or "").upper()
    side = str(row.get("side") or "").upper()
    if position_side == "SHORT":
        return "short"
    if position_side == "LONG":
        return "long"
    if abs(realized_pnl) > 0:
        return "short" if side == "BUY" else "long"
    return "long" if side == "BUY" else "short"


def normalize_trades(raw_trades: List[Dict[str, Any]], initial_balance: float) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    running_balance = float(initial_balance)

    for row in raw_trades:
        side = str(row.get("side") or "").upper()
        realized_pnl = float(row.get("realizedPnl") or 0)
        commission = abs(float(row.get("commission") or 0))
        net_pnl = realized_pnl - commission
        if abs(realized_pnl) > 0 or commission > 0:
            running_balance += net_pnl

        direction = infer_direction(row, realized_pnl)
        trade_action = "CLOSE" if abs(realized_pnl) > 0 else "OPEN"
        normalized.append(
            {
                "time": datetime_from_ms(row.get("time", now_ms())),
                "type": "BUY" if side == "BUY" else "SELL",
                "symbol": str(row.get("symbol") or "").upper(),
                "amount": float(row.get("qty") or 0),
                "price": float(row.get("price") or 0),
                "pnl": round(net_pnl, 8),
                "reason": "Binance read-only sync",
                "direction": direction,
                "leverage": None,
                "balance": round(running_balance, 8),
                "tradeAction": trade_action,
                "fee": commission,
                "commissionAsset": row.get("commissionAsset"),
                "binanceOrderId": row.get("orderId"),
                "binanceTradeId": row.get("id"),
            }
        )

    return normalized


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def backup_existing_files() -> None:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(exist_ok=True)
    for path in (TRADES_FILE, STATUS_FILE):
        if path.exists():
            shutil.copy2(path, BACKUP_DIR / f"{path.stem}-{timestamp}.json")


def build_status(trades: List[Dict[str, Any]], total_assets: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    existing = load_json(STATUS_FILE, {})
    final_balance = None
    account_breakdown = {}
    if isinstance(total_assets, dict):
        final_balance = total_assets.get("total_usdt")
        account_breakdown = total_assets.get("breakdown") or {}
    if final_balance is None:
        final_balance = float(trades[-1]["balance"]) if trades else 0.0

    watchlist = sorted({str(item.get("symbol", "")).replace("USDT", "") for item in trades if item.get("symbol")})
    recent_events = [
        f"Binance read-only sync {datetime.now().strftime('%H:%M:%S')}",
        f"Imported {len(trades)} fills",
        f"Estimated total assets: {round(float(final_balance), 4)} USDT",
        f"Watchlist: {', '.join(watchlist[:8]) if watchlist else '--'}",
        "No order, cancel, transfer, or withdraw code executed",
    ]

    strategy_v2 = existing.get("strategy_v2") or load_json(ROOT / "strategy_v2.json", {})
    if isinstance(strategy_v2, dict):
        strategy_v2.setdefault("version", "Binance read-only history")
        strategy_v2["coins"] = [f"{coin}USDT" for coin in watchlist[:5]]
        strategy_v2["topN"] = min(len(watchlist), 5)

    return {
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "balance": round(float(final_balance), 8),
        "equity": round(float(final_balance), 8),
        "unrealized_pnl": 0.0,
        "positions": 0,
        "open_positions": [],
        "mode": "binance-readonly-sync",
        "account_total_usdt": round(float(final_balance), 8),
        "account_breakdown": account_breakdown,
        "watchlist": watchlist,
        "top_signal": {"symbol": None, "direction": None, "score": None},
        "strategy_changes": [],
        "events": recent_events,
        "strategy_v2": strategy_v2,
    }


def write_outputs(trades: List[Dict[str, Any]], status: Dict[str, Any]) -> None:
    backup_existing_files()
    TRADES_FILE.write_text(json.dumps(trades, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def self_test() -> None:
    sample = [
        {
            "symbol": "BTCUSDT",
            "id": 1,
            "orderId": 11,
            "side": "BUY",
            "price": "65000",
            "qty": "0.01",
            "realizedPnl": "0",
            "commission": "0.02",
            "commissionAsset": "USDT",
            "time": 1710000000000,
            "positionSide": "BOTH",
        },
        {
            "symbol": "BTCUSDT",
            "id": 2,
            "orderId": 12,
            "side": "SELL",
            "price": "66000",
            "qty": "0.01",
            "realizedPnl": "10",
            "commission": "0.02",
            "commissionAsset": "USDT",
            "time": 1710003600000,
            "positionSide": "BOTH",
        },
    ]
    trades = normalize_trades(sample, 100)
    assert len(trades) == 2
    assert trades[0]["tradeAction"] == "OPEN"
    assert trades[1]["tradeAction"] == "CLOSE"
    assert trades[1]["direction"] == "long"
    status = build_status(trades, None)
    assert status["mode"] == "binance-readonly-sync"
    print("self-test-ok")


def check_api(config: Config) -> None:
    check_permissions(config)
    symbols = resolve_markets(config)
    total_assets = fetch_total_assets(config)
    print("api-ok")
    print(f"auto-discover={'on' if config.auto_discover else 'off'}")
    print(f"symbols={','.join(symbols) if symbols else '--'}")
    print(f"total-assets-usdt={total_assets.get('total_usdt', 0)}")
    for account, detail in sorted((total_assets.get("breakdown") or {}).items()):
        print(f"{account}={detail.get('total_usdt', 0)} USDT")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Binance read-only trade history into local OpenClaw JSON files.")
    parser.add_argument("--check-config", action="store_true", help="Validate local .env and exit without network sync.")
    parser.add_argument("--check-api", action="store_true", help="Test Binance read-only API access without writing files.")
    parser.add_argument("--self-test", action="store_true", help="Run offline converter tests and exit.")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        config = read_config()
        if args.check_config:
            print("config-ok")
            return 0
        if args.check_api:
            check_api(config)
            return 0
        check_permissions(config)
        markets = resolve_markets(config)
        raw_trades = fetch_user_trades(config, markets)
        total_assets = fetch_total_assets(config)
        final_balance = float(total_assets.get("total_usdt", 0.0))
        initial = final_balance if final_balance and not raw_trades else config.initial_balance
        trades = normalize_trades(raw_trades, initial)
        status = build_status(trades, total_assets)
        write_outputs(trades, status)
        print(f"[OK] Synced {len(trades)} fills into {TRADES_FILE.name} and {STATUS_FILE.name}")
        return 0
    except SyncError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
