# OpenClaw 模拟策略看板

这是一个轻量静态网页版本，适合部署到小型 Linux 服务器。

当前版本只做模拟策略展示：

- 不连接真实券商 API
- 不保存 API Key
- 不发送真实订单
- 不需要 Node.js
- 不需要 Python 常驻进程
- 不需要数据库
- 推荐用 Nginx 直接托管静态文件

## 文件说明

核心运行文件：

- `index.html`：网页主体
- `status.json`：策略状态演示数据
- `trades.json`：模拟成交记录
- `thinking.json`：模拟思考日志
- `strategy_v2.json`：策略参数

部署辅助文件：

- `deploy.sh`：服务器拉取 GitHub 最新代码并部署
- `nginx-openclaw.conf`：Nginx 配置模板，已开启 gzip
- `make-release.sh`：生成压缩包，方便手动上传
- `tools/sync-binance-readonly.py`：从币安只读 API 同步历史成交到本地 JSON

## 第一次部署到 Linux 服务器

以下以 Ubuntu / Debian 为例。

### 1. 安装 Nginx 和 Git

```bash
sudo apt update
sudo apt install -y nginx git
```

### 2. 拉取项目

```bash
sudo mkdir -p /var/www/openclaw-trading-bot
sudo chown -R "$USER":"$USER" /var/www/openclaw-trading-bot

git clone https://github.com/YOUR_NAME/openclaw-trading-bot.git /var/www/openclaw-trading-bot
cd /var/www/openclaw-trading-bot
```

如果你使用的是自己的仓库，请把上面的 GitHub 地址改成你的仓库地址。

### 3. 安装 Nginx 配置

```bash
sudo cp nginx-openclaw.conf /etc/nginx/sites-available/openclaw-trading-bot
sudo ln -sf /etc/nginx/sites-available/openclaw-trading-bot /etc/nginx/sites-enabled/openclaw-trading-bot
sudo nginx -t
sudo systemctl reload nginx
```

默认监听端口是 `8080`。

访问：

```text
http://服务器IP:8080/
```

## 后续更新部署

以后你在 GitHub 更新代码后，服务器执行：

```bash
cd /var/www/openclaw-trading-bot
./deploy.sh
```

脚本会自动：

1. 拉取 `origin/main`
2. 重置到最新代码
3. 删除发布目录里的旧文件
4. 复制静态网页和 JSON 数据
5. 测试 Nginx 配置
6. 重载 Nginx

## 币安只读 API 同步真实交易记录

这个功能只读取历史成交记录，不会下单、撤单、转账或提现。

### 1. 在币安创建只读 API

请在币安 API 管理里创建 API Key，并确认：

- 只开启读取权限
- 不开启现货交易
- 不开启合约交易
- 不开启提现
- 不开启划转
- 建议绑定小龙虾服务器公网 IP

### 2. 在服务器配置 `.env`

```bash
cd /var/www/openclaw-trading-bot
cp .env.example .env
nano .env
```

示例：

```env
BINANCE_API_KEY=你的只读API_KEY
BINANCE_API_SECRET=你的只读API_SECRET
BINANCE_MARKETS=BTCUSDT,ETHUSDT,SOLUSDT
BINANCE_SYNC_DAYS=30
OPENCLAW_INITIAL_BALANCE=0
BINANCE_STRICT_PERMISSION_CHECK=0
```

说明：

- `.env` 已经被 `.gitignore` 忽略，不能上传 GitHub。
- 如果 `BINANCE_STRICT_PERMISSION_CHECK=1`，权限检查失败也会停止同步。
- 如果币安返回 API 开了交易或提现等危险权限，脚本会直接停止。

### 3. 测试脚本

```bash
python3 tools/sync-binance-readonly.py --self-test
python3 tools/sync-binance-readonly.py --check-config
```

### 4. 开始同步

```bash
python3 tools/sync-binance-readonly.py
```

同步成功后会更新：

- `trades.json`
- `status.json`

旧文件会自动备份到：

```text
backups/
```

### 5. 定时同步，可选

如果你希望每 10 分钟同步一次：

```bash
crontab -e
```

加入：

```cron
*/10 * * * * cd /var/www/openclaw-trading-bot && python3 tools/sync-binance-readonly.py >> sync.log 2>&1
```

网页仍然是静态页面，Nginx 不需要重启。

## 手动压缩发布

如果你不想让服务器 git clone，也可以在本地生成压缩包：

```bash
./make-release.sh
```

生成文件：

```text
release/openclaw-trading-bot-lite.tar.gz
```

上传到服务器后解压到：

```text
/var/www/openclaw-trading-bot
```

## 体积优化

本版本已移除：

- 预览 PNG 大图
- Cloudflare Pages 备份目录
- 实盘交易 Python 脚本
- Binance API Key 示例

网页只依赖几个静态文件，服务器压力很小。

## 安全提醒

这个项目只是模拟看板。不要在仓库里提交：

- `.env`
- API Key
- 真实交易日志
- 数据库文件
