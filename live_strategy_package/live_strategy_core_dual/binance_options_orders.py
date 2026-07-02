"""Binance Options order parameter builder.

This module intentionally does not sign or send requests. Crawfish should attach
API credentials, timestamp, signature, and call the Binance endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from config import (
    OPTION_MAX_ABS_DELTA,
    OPTION_MAX_DAYS,
    OPTION_MIN_ABS_DELTA,
    OPTION_MIN_DAYS,
    OPTION_QUANTITY,
    OPTION_TARGET_DAYS,
)


def option_side_for_direction(direction: str) -> str:
    return "CALL" if direction == "LONG" else "PUT"


def select_option_contract(
    underlying: str,
    direction: str,
    option_chain: Iterable[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    wanted_side = option_side_for_direction(direction)
    candidates = []

    for row in option_chain:
        if str(row.get("underlying") or row.get("underlyingAsset") or "").upper() not in {
            underlying.upper(),
            underlying.upper().replace("USDT", ""),
        }:
            continue
        if str(row.get("side") or row.get("optionSide") or "").upper() != wanted_side:
            continue

        expiry = row.get("expiry") or row.get("expiryDate") or row.get("expiration")
        if isinstance(expiry, (int, float)):
            expiry_dt = datetime.fromtimestamp(float(expiry) / 1000, tz=timezone.utc)
        elif isinstance(expiry, str):
            expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        else:
            continue

        days = (expiry_dt - now).total_seconds() / 86400
        delta = abs(float(row.get("delta", row.get("markDelta", 0.0)) or 0.0))
        if days <= 0 or delta <= 0:
            continue

        in_window = OPTION_MIN_DAYS <= days <= OPTION_MAX_DAYS
        delta_ok = OPTION_MIN_ABS_DELTA <= delta <= OPTION_MAX_ABS_DELTA
        distance = abs(days - OPTION_TARGET_DAYS) + abs(delta - 0.45)
        if in_window and delta_ok:
            distance -= 10.0
        candidates.append((distance, row))

    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1]


def build_buy_option_order(option_symbol: str, quantity: float = OPTION_QUANTITY, price: Optional[float] = None) -> Dict[str, Any]:
    order = {
        "exchange": "BINANCE_OPTIONS",
        "endpoint": "POST /eapi/v1/order",
        "symbol": option_symbol,
        "side": "BUY",
        "type": "LIMIT" if price else "MARKET",
        "quantity": f"{quantity:.2f}",
    }
    if price is not None:
        order["price"] = str(price)
        order["timeInForce"] = "GTC"
    return order


def build_sell_option_order(option_symbol: str, quantity: float = OPTION_QUANTITY, price: Optional[float] = None) -> Dict[str, Any]:
    order = {
        "exchange": "BINANCE_OPTIONS",
        "endpoint": "POST /eapi/v1/order",
        "symbol": option_symbol,
        "side": "SELL",
        "type": "LIMIT" if price else "MARKET",
        "quantity": f"{quantity:.2f}",
    }
    if price is not None:
        order["price"] = str(price)
        order["timeInForce"] = "GTC"
    return order

