# Momcozy Google Play 评分看板 · 云端每日更新（GitHub Actions 版）

把原本跑在本机的每日抓取管线搬到 GitHub Actions，**电脑关机也会自动更新看板**。

## 工作原理

每天北京时间 09:00（UTC 01:00，GitHub 可能有 0~30 分钟延迟）自动执行：

1. 用服务账号下载 GCS 官方批量报告（全量评论 CSV + 每日评分统计）
2. 调官方评论 API 抓近 7 天评论增量
3. 抓美国区商店评论 + 页面快照
4. 更新 SQLite → 重新生成看板 HTML → 通过 MCP 更新已发布看板
5. 把更新后的数据库提交回仓库（持久化，下次运行接着累积）

## 手把手部署步骤

### 第 1 步：建私有仓库
1. 打开 https://github.com/new
2. Repository name 随意（如 `gplay-dashboard`），选 **Private**
3. **不要**勾选 "Add a README"，直接点 Create repository

### 第 2 步：上传本项目所有文件
把本文件夹里的内容（包括 `.github` 文件夹，需开启显示隐藏文件夹）上传到仓库：
- **方式 A（推荐，装了 Git）**：
  ```
  git init
  git add .
  git commit -m "init gplay cloud pipeline"
  git branch -M main
  git remote add origin https://github.com/<你的用户名>/gplay-dashboard.git
  git push -u origin main
  ```
- **方式 B（纯网页）**：仓库页 → Add file → Upload files → 把全部文件拖进去 → Commit。
  注意 `.github/workflows/daily-update.yml` 必须在 `.github/workflows/` 目录下。

### 第 3 步：配置 2 个 Secrets
仓库页 → Settings → Secrets and variables → Actions → New repository secret

| Secret 名称 | 值 |
|---|---|
| `GCP_SA_KEY` | 服务账号 JSON 的**完整内容**（本地文件 `C:\Users\Administrator\Downloads\momcozy-b5415-dd6e1d40c8e4.json`，用记事本打开全选复制粘贴进去） |
| `MCP_TOKEN` | app-data 平台 token：`appdata_P9hYVE-RPS_IpURYinP0_f35B9k5_UC-_CmTk28EabM`（若不填，脚本会用内置兜底 token，但该 token 可能过期，建议填上） |

### 第 4 步：手动跑一次验证
仓库页 → **Actions** 标签 → 左侧 `daily-update` → Run workflow → 运行。
看到绿色对勾、且最后日志出现 `[每日更新完成]` 即部署成功。

之后每天北京时间 09:00 左右自动运行，无需电脑开机。

## 文件说明

| 文件 | 作用 |
|---|---|
| `.github/workflows/daily-update.yml` | 定时触发 + 环境准备 + 执行 + 数据回传 |
| `fetch_daily.py` | 抓取与建库（密钥从环境变量 `GCP_SA_KEY` 读取） |
| `build_dashboard.py` | 生成看板 HTML（与本地版相同） |
| `publish.py` | 更新平台看板（token 优先从 `MCP_TOKEN` 读取） |
| `update_all.py` | 编排入口 |
| `state.json` | 已发布看板的 id/版本（**别删**，更新看板靠它） |
| `console_anchor.json` | 全球默认评分锚定值（用户从后台同步） |
| `requirements.txt` | Python 依赖 |

## 注意事项

- **网页抓取风控**：GitHub 的数据中心 IP 访问 Play 商店页面（美国评论 RPC、快照）偶发 429/验证页。
  官方 API 与 GCS 报告不受影响。若某天因此失败，看板数据仍保留上次结果，第二天会重试。
- **仓库不活跃停用**：GitHub 会把连续 60 天无活动的仓库定时任务停掉并发邮件提醒；
  本管线每天自动提交一次数据，天然保持活跃，无需担心。
- **改时间**：编辑 `.github/workflows/daily-update.yml` 里的 cron（注意是 UTC，北京 = UTC+8）。
- **本地版共存**：本机原管线保持不变，两边跑的是同一个看板（幂等更新，互不冲突）；
  若云端稳定后想停掉本机 09:00 自动化，在 WorkBuddy 里把该定时任务停用即可。
