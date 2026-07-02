"""OKX USDT swap order parameter builder."""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import OKX_DEFAULT_TD_MODE, OKX_SWAP_INST_ID


def build_open_swap_order(
    symbol: str,
    direction: str,
    size: float,
    order_type: str = "market",
    price: Optional[float] = None,
) -> Dict[str, Any]:
    side = "buy" if direction == "LONG" else "sell"
    pos_side = "long" if direction == "LONG" else "short"
    order = {
        "exchange": "OKX_SWAP",
        "endpoint": "POST /api/v5/trade/order",
        "instId": OKX_SWAP_INST_ID[symbol],
        "tdMode": OKX_DEFAULT_TD_MODE,
        "side": side,
        "posSide": pos_side,
        "ordType": order_type,
        "sz": str(size),
    }
    if price is not None:
        order["px"] = str(price)
    return order


def build_close_swap_order(
    symbol: str,
    direction: str,
    size: float,
    order_type: str = "market",
    price: Optional[float] = None,
) -> Dict[str, Any]:
    side = "sell" if direction == "LONG" else "buy"
    pos_side = "long" if direction == "LONG" else "short"
    order = {
        "exchange": "OKX_SWAP",
        "endpoint": "POST /api/v5/trade/order",
        "instId": OKX_SWAP_INST_ID[symbol],
        "tdMode": OKX_DEFAULT_TD_MODE,
        "side": side,
        "posSide": pos_side,
        "ordType": order_type,
        "sz": str(size),
        "reduceOnly": "true",
    }
    if price is not None:
        order["px"] = str(price)
    return order

