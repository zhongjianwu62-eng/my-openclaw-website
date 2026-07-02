"""Main live strategy entry point for Crawfish integration."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from binance_options_orders import build_buy_option_order, build_sell_option_order, select_option_contract
from config import CONTRACT_ORDER_NOTIONAL_USDT, CONTRACT_SYMBOLS, OPTION_QUANTITY, OPTION_SYMBOLS
from dense_breakout_strategy import (
    build_no_trade,
    evaluate_contract_exit,
    evaluate_option_exit,
    evaluate_symbol_signal,
)
from indicators import prepare_live_frame
from okx_swap_orders import build_close_swap_order, build_open_swap_order
from order_models import AccountState, PositionState, StrategyMemory, TradeAction
from risk_guard import build_risk_pause_action, risk_pause_reason


def calc_contract_size_by_notional(notional_usdt: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return round(notional_usdt / price, 8)


def _latest_row(m15_df: pd.DataFrame, h1_df: pd.DataFrame) -> Optional[pd.Series]:
    frame = prepare_live_frame(m15_df, h1_df)
    if len(frame) < 130:
        return None
    return frame.iloc[-1]


def evaluate_existing_positions(
    symbol: str,
    m15_df: pd.DataFrame,
    h1_df: pd.DataFrame,
    account: AccountState,
    option_marks: Optional[Dict[str, float]] = None,
) -> List[TradeAction]:
    row = _latest_row(m15_df, h1_df)
    if row is None:
        return []

    actions: List[TradeAction] = []
    for position in list(account.open_positions):
        if position.symbol != symbol:
            continue

        if position.market == "OKX_SWAP":
            reason = evaluate_contract_exit(position, row)
            if reason:
                actions.append(
                    TradeAction(
                        action="CLOSE_OKX_SWAP",
                        symbol=symbol,
                        market="OKX_SWAP",
                        direction=position.direction,
                        reason=reason,
                        order=build_close_swap_order(symbol, position.direction, position.quantity or 0.0),
                    )
                )
        elif position.market == "BINANCE_OPTIONS":
            exit_result = evaluate_option_exit(position, row, option_marks)
            if exit_result:
                reason, multiple = exit_result
                if position.option_symbol:
                    order = build_sell_option_order(position.option_symbol, position.quantity or OPTION_QUANTITY)
                else:
                    order = None
                actions.append(
                    TradeAction(
                        action="CLOSE_BINANCE_OPTION",
                        symbol=symbol,
                        market="BINANCE_OPTIONS",
                        direction=position.direction,
                        reason=reason,
                        order=order,
                        debug={"premium_multiple": multiple},
                    )
                )
    return actions


def evaluate_new_entries(
    symbol: str,
    m15_df: pd.DataFrame,
    h1_df: pd.DataFrame,
    memory: StrategyMemory,
    account: AccountState,
    option_chain: Optional[Iterable[Dict[str, Any]]] = None,
    enable_options: bool = True,
    enable_contracts: bool = True,
) -> List[TradeAction]:
    direction = evaluate_symbol_signal(symbol, m15_df, h1_df, memory, account)
    if not direction:
        return [build_no_trade(symbol, "DUAL", "no_entry_signal")]

    row = _latest_row(m15_df, h1_df)
    if row is None:
        return [build_no_trade(symbol, "DUAL", "not_enough_closed_candles")]

    actions: List[TradeAction] = []
    close_price = float(row["close"])

    if enable_contracts and symbol in CONTRACT_SYMBOLS:
        reason = risk_pause_reason(account, symbol)
        if reason:
            actions.append(build_risk_pause_action(symbol, "OKX_SWAP", reason))
        else:
            notional = CONTRACT_ORDER_NOTIONAL_USDT[symbol]
            size = calc_contract_size_by_notional(notional, close_price)
            actions.append(
                TradeAction(
                    action="OPEN_OKX_SWAP",
                    symbol=symbol,
                    market="OKX_SWAP",
                    direction=direction,
                    reason="dense_breakout_gap_confirmed",
                    order=build_open_swap_order(symbol, direction, size),
                    debug={
                        "timing": "execute_on_next_m15_open",
                        "notional_usdt": notional,
                        "reference_close": close_price,
                    },
                )
            )

    if enable_options and symbol in OPTION_SYMBOLS:
        reason = risk_pause_reason(account, symbol)
        if reason:
            actions.append(build_risk_pause_action(symbol, "BINANCE_OPTIONS", reason))
        else:
            contract = select_option_contract(symbol, direction, option_chain or [])
            if not contract:
                actions.append(
                    build_no_trade(
                        symbol,
                        "BINANCE_OPTIONS",
                        "no_suitable_option_contract",
                        {"direction": direction, "timing": "execute_on_next_m15_open"},
                    )
                )
            else:
                option_symbol = str(contract.get("symbol"))
                actions.append(
                    TradeAction(
                        action="OPEN_BINANCE_OPTION",
                        symbol=symbol,
                        market="BINANCE_OPTIONS",
                        direction=direction,
                        reason="dense_breakout_gap_confirmed",
                        order=build_buy_option_order(option_symbol, OPTION_QUANTITY),
                        debug={
                            "timing": "execute_on_next_m15_open",
                            "selected_contract": contract,
                        },
                    )
                )

    return actions or [build_no_trade(symbol, "DUAL", "market_disabled")]


def evaluate_live_cycle(
    candles_by_symbol: Dict[str, Dict[str, pd.DataFrame]],
    account: AccountState,
    memory: StrategyMemory,
    option_chain: Optional[Iterable[Dict[str, Any]]] = None,
    option_marks: Optional[Dict[str, float]] = None,
    enable_options: bool = True,
    enable_contracts: bool = True,
) -> List[Dict[str, Any]]:
    actions: List[TradeAction] = []
    for symbol, frames in candles_by_symbol.items():
        m15_df = frames["15m"]
        h1_df = frames["1h"]
        exits = evaluate_existing_positions(symbol, m15_df, h1_df, account, option_marks)
        if exits:
            actions.extend(exits)
            continue
        actions.extend(
            evaluate_new_entries(
                symbol,
                m15_df,
                h1_df,
                memory,
                account,
                option_chain,
                enable_options=enable_options,
                enable_contracts=enable_contracts,
            )
        )
    return [action.to_dict() for action in actions]

