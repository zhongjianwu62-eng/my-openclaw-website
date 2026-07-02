"""Dense-zone breakout signal and exit logic."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from config import (
    CONTRACT_HARD_STOP,
    CONTRACT_TAKE_PROFIT,
    COOLDOWN_MINUTES,
    DENSE_REQUIRED_BARS,
    DENSE_THRESHOLDS,
    DIVERGE_MULTIPLIER,
    OPTION_EFFECTIVE_LEVERAGE,
    OPTION_FORCE_EXIT_DAYS,
    OPTION_SYMBOLS,
    OPTION_THETA_DECAY_PER_DAY,
    OPTION_TP_MULTIPLE,
    OPTION_TREND_PROFIT_MULTIPLE,
)
from indicators import prepare_live_frame
from order_models import AccountState, PositionState, StrategyMemory, TradeAction
from risk_guard import build_risk_pause_action, risk_pause_reason


def base_symbol(symbol: str) -> str:
    return symbol.upper().replace("USDT", "")


def threshold_for(symbol: str) -> float:
    return DENSE_THRESHOLDS[base_symbol(symbol)]


def direction_filter_ok(row: pd.Series, direction: str) -> bool:
    needed = ["EMA60", "EMA120", "H1_EMA60", "H1_EMA120"]
    if any(pd.isna(row.get(col)) for col in needed):
        return False
    if direction == "LONG":
        return row["EMA60"] > row["EMA120"] and row["H1_EMA60"] > row["H1_EMA120"]
    return row["EMA60"] < row["EMA120"] and row["H1_EMA60"] < row["H1_EMA120"]


def option_side(direction: str) -> str:
    return "CALL" if direction == "LONG" else "PUT"


def estimate_option_multiple(position: PositionState, close_price: float, now: datetime) -> float:
    side = option_side(position.direction)
    leverage = OPTION_EFFECTIVE_LEVERAGE.get(position.symbol, {}).get(side, 18.0)
    theta = OPTION_THETA_DECAY_PER_DAY.get(position.symbol, {}).get(side, 0.08)
    if position.direction == "LONG":
        underlying_return = (close_price - position.entry_price) / position.entry_price
    else:
        underlying_return = (position.entry_price - close_price) / position.entry_price
    elapsed_days = max((now - position.entry_time).total_seconds() / 86400, 0.0)
    return max(0.0, 1.0 + leverage * underlying_return - theta * elapsed_days)


def actual_or_estimated_option_multiple(
    position: PositionState,
    close_price: float,
    now: datetime,
    option_marks: Optional[Dict[str, float]] = None,
) -> float:
    option_marks = option_marks or {}
    if position.option_symbol and position.option_entry_premium:
        current_mark = option_marks.get(position.option_symbol)
        if current_mark and current_mark > 0:
            return current_mark / position.option_entry_premium
    return estimate_option_multiple(position, close_price, now)


def update_dense_memory(symbol: str, row: pd.Series, memory: StrategyMemory) -> None:
    threshold = threshold_for(symbol)
    key = symbol
    dense_gap = row["Dense_Gap"]
    high = float(row["high"])
    low = float(row["low"])

    if pd.notna(dense_gap) and dense_gap <= threshold:
        memory.dense_count[key] = memory.dense_count.get(key, 0) + 1
        memory.dense_high[key] = high if key not in memory.dense_high else max(memory.dense_high[key], high)
        memory.dense_low[key] = low if key not in memory.dense_low else min(memory.dense_low[key], low)
        if memory.dense_count[key] >= DENSE_REQUIRED_BARS and key not in memory.dense_breakout_direction:
            memory.dense_breakout_direction[key] = None
    else:
        if key not in memory.dense_breakout_direction:
            memory.dense_count[key] = 0
            memory.dense_high.pop(key, None)
            memory.dense_low.pop(key, None)


def get_entry_signal(symbol: str, row: pd.Series, memory: StrategyMemory) -> Optional[str]:
    key = symbol
    if key not in memory.dense_breakout_direction:
        return None

    high = memory.dense_high[key]
    low = memory.dense_low[key]
    close = float(row["close"])
    threshold = threshold_for(symbol)

    if memory.dense_breakout_direction[key] is None:
        if close > high and direction_filter_ok(row, "LONG"):
            memory.dense_breakout_direction[key] = "LONG"
        elif close < low and direction_filter_ok(row, "SHORT"):
            memory.dense_breakout_direction[key] = "SHORT"

    direction = memory.dense_breakout_direction[key]
    if direction is None:
        return None

    if direction == "LONG":
        failed_opposite = close < low
        still_breakout = close > high
    else:
        failed_opposite = close > high
        still_breakout = close < low

    if failed_opposite:
        clear_dense_zone(symbol, memory)
        return None

    gap_confirmed = pd.notna(row["Dense_Gap"]) and row["Dense_Gap"] >= threshold * DIVERGE_MULTIPLIER
    if gap_confirmed and still_breakout and direction_filter_ok(row, direction):
        last_exit = memory.last_exit_time.get(f"{symbol}:{direction}")
        now = pd.to_datetime(row["close_time"]).to_pydatetime()
        cooldown_ok = last_exit is None or now >= last_exit + timedelta(minutes=COOLDOWN_MINUTES)
        clear_dense_zone(symbol, memory)
        return direction if cooldown_ok else None

    return None


def clear_dense_zone(symbol: str, memory: StrategyMemory) -> None:
    memory.dense_count.pop(symbol, None)
    memory.dense_high.pop(symbol, None)
    memory.dense_low.pop(symbol, None)
    memory.dense_breakout_direction.pop(symbol, None)


def evaluate_contract_exit(position: PositionState, row: pd.Series) -> Optional[str]:
    threshold = threshold_for(position.symbol)
    close = float(row["close"])
    high = float(row["high"])
    low = float(row["low"])
    gap = row["Dense_Gap"]

    if pd.notna(gap) and gap > threshold * DIVERGE_MULTIPLIER:
        position.has_diverged = True

    if position.direction == "LONG":
        if low <= position.entry_price * (1 - CONTRACT_HARD_STOP):
            return "HARD_SL"
        if high >= position.entry_price * (1 + CONTRACT_TAKE_PROFIT):
            return "TP"
        current_pnl = (close - position.entry_price) / position.entry_price
        if pd.notna(gap) and gap >= threshold and current_pnl < 0 and row["EMA20"] < row["EMA60"] < row["EMA120"]:
            return "EMA_REV"
    else:
        if high >= position.entry_price * (1 + CONTRACT_HARD_STOP):
            return "HARD_SL"
        if low <= position.entry_price * (1 - CONTRACT_TAKE_PROFIT):
            return "TP"
        current_pnl = (position.entry_price - close) / position.entry_price
        if pd.notna(gap) and gap >= threshold and current_pnl < 0 and row["EMA20"] > row["EMA60"] > row["EMA120"]:
            return "EMA_REV"

    if position.has_diverged and pd.notna(gap) and gap <= threshold:
        return "RE_DENSE"
    return None


def evaluate_option_exit(
    position: PositionState,
    row: pd.Series,
    option_marks: Optional[Dict[str, float]] = None,
) -> Optional[tuple[str, float]]:
    now = pd.to_datetime(row["close_time"]).to_pydatetime()
    close = float(row["close"])
    threshold = threshold_for(position.symbol)
    gap = row["Dense_Gap"]

    if pd.notna(gap) and gap > threshold * DIVERGE_MULTIPLIER:
        position.has_diverged = True

    multiple = actual_or_estimated_option_multiple(position, close, now, option_marks)
    if multiple >= OPTION_TP_MULTIPLE:
        return "OPTION_TP_3X", multiple
    if position.has_diverged and pd.notna(gap) and gap <= threshold and multiple > 1.0:
        return "RE_DENSE_PROFIT", multiple
    if multiple >= OPTION_TREND_PROFIT_MULTIPLE:
        if position.direction == "LONG" and row["EMA20"] < row["EMA60"]:
            return "EMA_PROFIT_EXIT", multiple
        if position.direction == "SHORT" and row["EMA20"] > row["EMA60"]:
            return "EMA_PROFIT_EXIT", multiple
    if now >= position.entry_time + timedelta(days=OPTION_FORCE_EXIT_DAYS):
        return "TIME_EXIT", multiple
    return None


def build_no_trade(symbol: str, market: str, reason: str, debug: Optional[Dict[str, Any]] = None) -> TradeAction:
    return TradeAction(action="NO_TRADE", symbol=symbol, market=market, reason=reason, debug=debug or {})


def evaluate_symbol_signal(
    symbol: str,
    m15_df: pd.DataFrame,
    h1_df: pd.DataFrame,
    memory: StrategyMemory,
    account: AccountState,
) -> Optional[str]:
    frame = prepare_live_frame(m15_df, h1_df)
    if len(frame) < 130:
        return None
    row = frame.iloc[-1]
    update_dense_memory(symbol, row, memory)
    return get_entry_signal(symbol, row, memory)

