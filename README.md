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
