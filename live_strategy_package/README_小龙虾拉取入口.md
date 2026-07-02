# 小龙虾拉取入口

服务器拉取仓库后，请进入：

```text
live_strategy_package/live_strategy_core_dual/
```

优先阅读：

```text
README_小龙虾交接说明.md
README_接入说明.md
```

核心调用文件：

```text
trading_engine.py
```

核心函数：

```python
evaluate_live_cycle(...)
```

本包不会保存 API Key，不会签名，不会主动真实下单。  
小龙虾负责把返回的订单参数接到服务器已有的 Binance Options / OKX Swap 执行模块里。

也可以直接下载并解压：

```text
live_strategy_package/live_strategy_core_dual.zip
```

上线建议：

1. 先跑模拟记录模式 1 到 3 天。
2. 确认 M15/H1 都是已收盘 K 线。
3. 确认币安期权数量是 `0.01`。
4. 确认 BTC 不走期权，只走欧易合约。
5. 确认风控触发后不再开新仓。
