# 钉钉审批打印工具 - Demo 版

一个基于 Python + Streamlit 的 Web 应用，用于验证钉钉 OA 审批 API 的可行性。支持获取审批实例列表、查看审批详情、下载审批附件到本地。

## ✨ 功能特性

- 🔐 **自动获取 AccessToken** - 启动时自动获取并缓存钉钉访问令牌
- 📋 **审批列表查询** - 支持按日期范围和审批状态筛选
- 📄 **审批详情查看** - 双栏布局展示基本信息和表单数据
- 📎 **附件下载** - 一键下载所有审批附件到本地
- 🔄 **Token 自动刷新** - 接近过期时自动刷新，无需手动干预
- 🌐 **Web 界面** - 基于 Streamlit 的响应式 Web UI

## 🛠️ 环境要求

- Python 3.8+
- pip 包管理器
- 网络连接（访问钉钉 API）

### 支持的操作系统

- ✅ Ubuntu / Debian / CentOS（无图形界面也支持）
- ✅ macOS
- ✅ Windows

## 📦 安装步骤

### 1. 克隆或下载项目

```bash
# 如果是 git 仓库
git clone <repository-url>
cd PaySignPrinter

# 或者直接下载压缩包并解压
cd PaySignPrinter
```

### 2. 创建虚拟环境（推荐）

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

依赖包：
- `requests` - HTTP 请求库
- `python-dotenv` - 环境变量管理
- `streamlit` - Web 应用框架

### 4. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，填入你的钉钉应用凭证
nano .env  # 或使用其他编辑器
```

`.env` 文件内容：

```env
# 钉钉应用凭证（从钉钉开放平台获取）
DINGTALK_APP_KEY=your_app_key_here
DINGTALK_APP_SECRET=your_app_secret_here
DINGTALK_AGENT_ID=your_agent_id_here

# 审批流程编码（固定值，测试用）
DINGTALK_PROCESS_CODE=PROC-D868A57B-7939-4857-AAAB-0C8437487F7E
```

#### 如何获取钉钉凭证

1. 登录 [钉钉开放平台](https://open.dingtalk.com/)
2. 进入你的企业内部应用
3. 在"凭证与基础信息"中获取：
   - **AppKey** (`DINGTALK_APP_KEY`)
   - **AppSecret** (`DINGTALK_APP_SECRET`)
   - **AgentId** (`DINGTALK_AGENT_ID`)
4. 在"权限管理"中确保已开启：
   - `oa_approval` - OA审批权限
   - `workflow` - 工作流权限

## 🚀 启动应用

### 方式一：直接启动（有图形界面）

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`

### 方式二：后台启动（无图形界面 / 服务器部署）

```bash
# 使用 nohup 后台运行
nohup streamlit run app.py --server.headless true --server.port 8501 > streamlit.log 2>&1 &

# 或者使用 tmux/screen
tmux new -s dingtalk-demo
streamlit run app.py --server.headless true --server.port 8501
# 按 Ctrl+B 然后 D 分离会话
```

访问地址：
- 本地：`http://localhost:8501`
- 远程：`http://<服务器IP>:8501`

### 方式三：SSH 端口转发（远程服务器 + 本地浏览器）

如果你在本地机器，通过 SSH 连接到远程服务器：

```bash
ssh -L 8501:localhost:8501 user@remote-server-ip
```

然后在本地浏览器打开 `http://localhost:8501`

## 📖 使用指南

### 1. 查询审批列表

1. 在左侧边栏选择**日期范围**
2. 选择**审批状态**（已完结 / 审批中 / 已撤销 / 全部）
3. 点击 **🔍 查询** 按钮
4. 等待查询完成，下方会显示审批列表

### 2. 查看审批详情

1. 在左侧审批列表中点击任意审批实例
2. 右侧主区域会显示：
   - **基本信息**：状态、发起人、部门、时间等
   - **表单数据**：审批表单中的所有字段
   - **附件列表**：可下载的附件清单

### 3. 下载附件

1. 在审批详情页找到"📎 附件列表"区域
2. 点击 **📥 下载所有附件** 按钮
3. 附件会下载到 `./downloads/<实例ID>/` 目录

## 📁 项目结构

```
PaySignPrinter/
├── app.py                  # Streamlit Web 应用主文件
├── dingtalk_api.py         # 钉钉 API 封装模块
├── requirements.txt        # Python 依赖
├── .env                    # 环境变量配置（需自行创建）
├── .env.example            # 环境变量示例模板
├── .gitignore             # Git 忽略规则
├── downloads/             # 下载的附件存放目录（自动创建）
└── README.md              # 本文件
```

## 🔧 核心 API 流程

```
获取 AccessToken
    ↓
获取审批实例 ID 列表（分页）
    ↓
获取单个审批实例详情
    ↓
提取附件信息
    ↓
获取下载链接
    ↓
下载文件到本地
```

### 涉及的钉钉 API

| API | 用途 | 文档 |
|-----|------|------|
| `POST /v1.0/oauth2/accessToken` | 获取访问令牌 | [链接](https://open.dingtalk.com/document/isv/serverapi/get-access-token) |
| `POST /v1.0/workflow/processes/instanceIds/query` | 获取审批实例 ID 列表 | [链接](https://open.dingtalk.com/document/isv/serverapi/obtain-the-approval-instance-id) |
| `GET /v1.0/workflow/processInstances` | 获取审批实例详情 | [链接](https://open.dingtalk.com/document/isv/serverapi/obtain-a-single-approval-instance) |
| `POST /v1.0/workflow/processInstances/spaces/files/urls/download` | 获取附件下载链接 | [链接](https://open.dingtalk.com/document/isv/serverapi/download-attachments) |

## 🐛 常见问题

### Q1: 启动时报错 `ModuleNotFoundError`

**原因**：依赖未安装或虚拟环境未激活

**解决**：
```bash
# 确认在虚拟环境中
which python  # 应该显示 venv 路径

# 重新安装依赖
pip install -r requirements.txt
```

### Q2: 查询时报错 "访问令牌无效或已过期"

**原因**：AppKey / AppSecret 配置错误

**解决**：
1. 检查 `.env` 文件中的凭证是否正确
2. 确认应用已发布（钉钉开放平台 -> 版本管理与发布）
3. 确认应用已开启 OA 审批权限

### Q3: 查询成功但列表为空

**原因**：
- 日期范围内没有符合条件的审批
- 应用没有访问该审批流程的权限

**解决**：
1. 扩大日期范围
2. 在钉钉开放平台检查应用权限范围
3. 确认 `DINGTALK_PROCESS_CODE` 正确

### Q4: 无图形界面如何查看界面效果

**方案 A - 截图查看**：
```bash
# 安装 Playwright
npm install -g playwright
npx playwright install chromium

# 截图
npx playwright screenshot --browser=chromium \
    --viewport-size=1400,900 \
    --full-page \
    http://localhost:8501 ./screenshot.png
```

**方案 B - 纯命令行测试**：
```bash
# 测试 API 是否正常工作
curl -s http://localhost:8501 | grep -i "审批查询"
# 应该返回包含"审批查询"的 HTML 内容
```

### Q5: 如何修改 processCode

编辑 `.env` 文件：
```env
DINGTALK_PROCESS_CODE=你的新流程编码
```

然后重启应用即可，无需修改代码。

## ⚠️ 注意事项

1. **凭证安全**：`.env` 文件包含敏感信息，已加入 `.gitignore`，请勿提交到版本控制
2. **Token 有效期**：AccessToken 有效期 7200 秒，应用会自动刷新
3. **下载链接有效期**：附件下载链接有效期 15 分钟，过期需重新获取
4. **日期范围限制**：钉钉 API 要求查询时间范围不超过 120 天
5. **分页限制**：每页最多返回 20 条记录，应用已自动处理分页

## 📝 测试记录

- **测试时间**：2026-05-20
- **测试环境**：Ubuntu 22.04 (无图形界面)
- **Python 版本**：3.12
- **测试结果**：✅ 全部通过
  - 获取 Token：成功
  - 查询列表：28 条记录
  - 查看详情：正常显示
  - 下载附件：2 个文件成功下载

## 🔮 未来计划

本 Demo 验证了钉钉 API 的可行性，完整工具将包含：
- [ ] 审批详情自动加签名
- [ ] 输出打印材料（PDF 生成）
- [ ] 一键批量打印

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**作者**：Atlas (OhMyOpenCode)
**日期**：2026-05-20
