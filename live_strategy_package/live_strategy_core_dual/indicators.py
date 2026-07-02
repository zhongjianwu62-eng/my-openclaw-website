"""Indicator helpers for closed M15/H1 candles."""

from __future__ import annotations

import pandas as pd


INDICATOR_COLUMNS = ["MA20", "MA60", "MA120", "EMA20", "EMA60", "EMA120"]


def prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open_time", "close_time", "open", "high", "low", "close"])
    return df.sort_values("close_time").drop_duplicates("close_time").reset_index(drop=True)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA20"] = df["close"].rolling(window=20).mean()
    df["MA60"] = df["close"].rolling(window=60).mean()
    df["MA120"] = df["close"].rolling(window=120).mean()
    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA60"] = df["close"].ewm(span=60, adjust=False).mean()
    df["EMA120"] = df["close"].ewm(span=120, adjust=False).mean()
    values = df[INDICATOR_COLUMNS]
    df["Dense_Gap"] = (values.max(axis=1) - values.min(axis=1)) / df["close"]
    df.loc[values.isna().any(axis=1) | (df["close"] <= 0), "Dense_Gap"] = float("nan")
    return df


def prepare_live_frame(m15_df: pd.DataFrame, h1_df: pd.DataFrame) -> pd.DataFrame:
    m15 = add_indicators(prepare_ohlcv(m15_df))
    h1 = add_indicators(prepare_ohlcv(h1_df))
    h1_cols = h1[["close_time", "EMA60", "EMA120"]].rename(
        columns={"EMA60": "H1_EMA60", "EMA120": "H1_EMA120"}
    )
    return pd.merge_asof(
        m15.sort_values("close_time"),
        h1_cols.sort_values("close_time"),
        on="close_time",
        direction="backward",
        allow_exact_matches=True,
    ).reset_index(drop=True)

