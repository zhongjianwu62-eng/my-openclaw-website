"""Daily and position-level risk checks before opening new trades."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from config import RISK_CONFIG
from order_models import AccountState, TradeAction, utc_now


def risk_pause_reason(account: AccountState, symbol: str) -> Optional[str]:
    now = utc_now()
    if account.pause_until and now < account.pause_until:
        return f"paused_until_{account.pause_until.isoformat()}"

    if account.realized_pnl_today_usdt <= -float(RISK_CONFIG["daily_loss_limit_usdt"]):
        return "daily_loss_usdt_limit"

    if account.equity_usdt > 0:
        loss_pct = abs(min(account.realized_pnl_today_usdt, 0.0)) / account.equity_usdt
        if loss_pct >= float(RISK_CONFIG["daily_loss_limit_pct"]):
            return "daily_loss_pct_limit"

    if account.consecutive_losses >= int(RISK_CONFIG["max_consecutive_losses"]):
        return "consecutive_loss_limit"

    if account.api_error_count >= int(RISK_CONFIG["pause_after_api_errors"]):
        return "api_error_limit"

    if len(account.open_positions) >= int(RISK_CONFIG["max_open_positions_total"]):
        return "max_total_positions"

    per_symbol = sum(1 for position in account.open_positions if position.symbol == symbol)
    if per_symbol >= int(RISK_CONFIG["max_open_positions_per_symbol"]):
        return "max_symbol_positions"

    return None


def build_risk_pause_action(symbol: str, market: str, reason: str) -> TradeAction:
    return TradeAction(
        action="RISK_PAUSE",
        symbol=symbol,
        market=market,
        reason=reason,
        risk_blocked=True,
    )


def next_loss_pause_until():
    return utc_now() + timedelta(minutes=int(RISK_CONFIG["loss_pause_minutes"]))

