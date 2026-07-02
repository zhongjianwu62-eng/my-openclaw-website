# 自动交易核心：合约期权双版本

这个包是给服务器上的小龙虾接入用的“核心决策层”。

它不保存 API Key，不签名，不主动真实下单。小龙虾每 15 分钟把已经收盘的 K 线、持仓、账户风控状态喂进来，本包返回标准化交易动作和订单参数。

## 交易版本

### 币安期权版

- 不做 BTC，资金太小暂时跳过。
- 做 `BNB/ETH/SOL/DOGE/XRP`。
- 做多买 Call，做空买 Put。
- 每次买入 `0.01` 张期权。
- 优先选择接近 7 天到期、delta 合适的期权。
- 权利金 3 倍止盈。
- `RE_DENSE` 盈利时止盈。
- EMA 盈利保护止盈。
- 到第 6 天还没出场则时间退出。
- 不设价格止损，最大亏损为权利金。

### 欧易合约版

- 做 `BTC/BNB/ETH/SOL/DOGE/XRP` 永续合约。
- BTC 每笔名义金额 `6U`。
- 其他币每笔名义金额 `5U`。
- 默认逐仓。
- 退出规则：`TP`、`RE_DENSE`、`EMA_REV`、`HARD_SL`。
- 硬止损默认 `4.5%`，在 `config.py` 里可以改。

## 入场逻辑

两个版本共用同一个方向信号：

1. 连续 8 根 M15 `Dense_Gap <= 阈值`，形成密集区。
2. 记录密集区高点和低点。
3. 只交易该密集区第一次有效突破。
4. 做多：M15 收盘价突破密集区高点。
5. 做空：M15 收盘价跌破密集区低点。
6. 不立刻进场。
7. 等 `Dense_Gap >= 阈值 * 1.2`。
8. M15 EMA60/120 与 H1 EMA60/120 方向一致。
9. 输出订单，标记为下一根 M15 开盘执行。

## 风控

默认风控写在 `config.py`：

- 当日亏损达到 `15U`，停止当天开新仓。
- 当日亏损达到权益 `20%`，停止当天开新仓。
- 连续亏损达到 3 笔，暂停开新仓。
- 最大同时持仓 6 笔。
- 单币种最多 1 笔持仓。
- API 连续错误达到 3 次，暂停开新仓。

触发风控时，返回：

```json
{
  "action": "RISK_PAUSE",
  "risk_blocked": true
}
```

## 小龙虾需要喂入的数据

每个币种：

- `15m`：至少 130 根已经收盘的 M15 K 线。
- `1h`：至少 130 根已经收盘的 H1 K 线。
- K 线字段：`open_time, close_time, open, high, low, close, volume`。

账户状态：

- 当前权益。
- 今日已实现盈亏。
- 连续亏损次数。
- 当前持仓。

期权版还需要：

- 当前可交易期权链。
- 已持仓期权的当前 mark 价格，方便判断权利金倍数。

## 核心调用

```python
from trading_engine import evaluate_live_cycle
from order_models import AccountState, StrategyMemory

memory = StrategyMemory()
account = AccountState(equity_usdt=100)

actions = evaluate_live_cycle(
    candles_by_symbol=candles_by_symbol,
    account=account,
    memory=memory,
    option_chain=option_chain,
    option_marks=option_marks,
    enable_options=True,
    enable_contracts=True,
)
```

返回值是动作列表。小龙虾只需要识别 `action` 字段。

## 订单动作

可能返回：

- `NO_TRADE`
- `OPEN_BINANCE_OPTION`
- `CLOSE_BINANCE_OPTION`
- `OPEN_OKX_SWAP`
- `CLOSE_OKX_SWAP`
- `RISK_PAUSE`

## API 参数说明

### 币安期权

订单参数生成器会返回：

```json
{
  "exchange": "BINANCE_OPTIONS",
  "endpoint": "POST /eapi/v1/order",
  "symbol": "ETH-260710-3600-C",
  "side": "BUY",
  "type": "MARKET",
  "quantity": "0.01"
}
```

小龙虾负责补充：

- `timestamp`
- `signature`
- API Key Header
- 真实请求发送

### 欧易合约

订单参数生成器会返回：

```json
{
  "exchange": "OKX_SWAP",
  "endpoint": "POST /api/v5/trade/order",
  "instId": "ETH-USDT-SWAP",
  "tdMode": "isolated",
  "side": "buy",
  "posSide": "long",
  "ordType": "market",
  "sz": "0.00142857"
}
```

小龙虾负责补充：

- OKX API 签名请求头
- 真实请求发送
- 合约最小下单数量和张数换算

## 实盘提醒

上线前建议先让小龙虾跑 1 到 3 天模拟盘，只记录动作，不真实下单。

重点检查：

- M15/H1 是否只传已收盘 K 线。
- H1 是否严格用 `H1 close_time <= M15 close_time` 的最新完整 K 线。
- OKX 的 `sz` 是否符合该币种最小张数。
- 币安期权是否确实选到了可交易合约。
- 风控触发后是否只平仓，不再开新仓。

