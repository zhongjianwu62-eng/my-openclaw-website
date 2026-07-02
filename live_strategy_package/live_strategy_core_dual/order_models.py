"""Small JSON-friendly models used by the live strategy package."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class PositionState:
    symbol: str
    market: str
    direction: str
    entry_price: float
    entry_time: datetime
    quantity: float = 0.0
    option_symbol: Optional[str] = None
    option_entry_premium: Optional[float] = None
    has_diverged: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountState:
    equity_usdt: float
    realized_pnl_today_usdt: float = 0.0
    consecutive_losses: int = 0
    open_positions: List[PositionState] = field(default_factory=list)
    pause_until: Optional[datetime] = None
    api_error_count: int = 0


@dataclass
class StrategyMemory:
    dense_count: Dict[str, int] = field(default_factory=dict)
    dense_high: Dict[str, float] = field(default_factory=dict)
    dense_low: Dict[str, float] = field(default_factory=dict)
    dense_breakout_direction: Dict[str, Optional[str]] = field(default_factory=dict)
    last_exit_time: Dict[str, datetime] = field(default_factory=dict)


@dataclass
class TradeAction:
    action: str
    symbol: str
    market: str
    direction: Optional[str] = None
    reason: str = ""
    order: Optional[Dict[str, Any]] = None
    risk_blocked: bool = False
    debug: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "symbol": self.symbol,
            "market": self.market,
            "direction": self.direction,
            "reason": self.reason,
            "order": self.order,
            "risk_blocked": self.risk_blocked,
            "debug": self.debug,
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

