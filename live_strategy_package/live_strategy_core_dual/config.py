"""Live strategy configuration for the dense breakout dual-market package."""

from __future__ import annotations


SYMBOLS = ["BTCUSDT", "BNBUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT"]
OPTION_SYMBOLS = ["BNBUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT"]
CONTRACT_SYMBOLS = SYMBOLS

DENSE_THRESHOLDS = {
    "BTC": 0.005,
    "BNB": 0.005,
    "ETH": 0.007,
    "SOL": 0.007,
    "DOGE": 0.015,
    "XRP": 0.005,
}

DENSE_REQUIRED_BARS = 8
DIVERGE_MULTIPLIER = 1.2
COOLDOWN_MINUTES = 60

CONTRACT_TAKE_PROFIT = 0.135
CONTRACT_HARD_STOP = 0.045
CONTRACT_ORDER_NOTIONAL_USDT = {
    "BTCUSDT": 6.0,
    "BNBUSDT": 5.0,
    "ETHUSDT": 5.0,
    "SOLUSDT": 5.0,
    "DOGEUSDT": 5.0,
    "XRPUSDT": 5.0,
}

OKX_SWAP_INST_ID = {
    "BTCUSDT": "BTC-USDT-SWAP",
    "BNBUSDT": "BNB-USDT-SWAP",
    "ETHUSDT": "ETH-USDT-SWAP",
    "SOLUSDT": "SOL-USDT-SWAP",
    "DOGEUSDT": "DOGE-USDT-SWAP",
    "XRPUSDT": "XRP-USDT-SWAP",
}

OKX_DEFAULT_TD_MODE = "isolated"
OKX_DEFAULT_LEVERAGE = 20

OPTION_QUANTITY = 0.01
OPTION_TARGET_DAYS = 7
OPTION_MIN_DAYS = 5
OPTION_MAX_DAYS = 10
OPTION_MIN_ABS_DELTA = 0.30
OPTION_MAX_ABS_DELTA = 0.65
OPTION_TP_MULTIPLE = 3.0
OPTION_TREND_PROFIT_MULTIPLE = 1.5
OPTION_FORCE_EXIT_DAYS = 6

OPTION_EFFECTIVE_LEVERAGE = {
    "BNBUSDT": {"CALL": 23.58, "PUT": 20.84},
    "ETHUSDT": {"CALL": 15.04, "PUT": 15.94},
    "SOLUSDT": {"CALL": 28.70, "PUT": 29.02},
    "DOGEUSDT": {"CALL": 30.64, "PUT": 29.24},
    "XRPUSDT": {"CALL": 35.14, "PUT": 36.14},
}

OPTION_THETA_DECAY_PER_DAY = {
    "BNBUSDT": {"CALL": 0.07, "PUT": 0.07},
    "ETHUSDT": {"CALL": 0.07, "PUT": 0.07},
    "SOLUSDT": {"CALL": 0.36, "PUT": 0.41},
    "DOGEUSDT": {"CALL": 0.08, "PUT": 0.08},
    "XRPUSDT": {"CALL": 0.08, "PUT": 0.08},
}

RISK_CONFIG = {
    "daily_loss_limit_usdt": 15.0,
    "daily_loss_limit_pct": 0.20,
    "max_consecutive_losses": 3,
    "loss_pause_minutes": 240,
    "max_open_positions_total": 6,
    "max_open_positions_per_symbol": 1,
    "pause_after_api_errors": 3,
}

