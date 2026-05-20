# 钉钉审批打印工具 - 项目上下文

> 生成时间：2026-05-20
> 用途：供后续 OpenCode 会话快速读取，避免重复分析

---

## 1. 项目概述

**项目名称**：钉钉审批打印工具（PaySignPrinter）
**当前阶段**：Demo 验证阶段（已完成）
**技术栈**：Python 3.12 + Streamlit + Requests + python-dotenv
**部署状态**：已推送到 GitHub（https://github.com/wanghannew1/PaySignPrinter）

### 核心目标
验证钉钉 OA 审批 API 可行性：获取 Token → 查询审批实例 → 查看详情 → 下载附件。

### 未来完整功能
- [x] 获取审批详情和下载附件（Demo 已完成）
- [ ] 审批详情自动加签名
- [ ] 输出打印材料（PDF 生成）
- [ ] 一键批量打印
- [ ] 用户登录与权限管理

---

## 2. 关键文件清单

| 文件 | 作用 | 行数 | 状态 |
|------|------|------|------|
| `app.py` | Streamlit Web 界面 | 224 | ✅ 稳定 |
| `dingtalk_api.py` | 钉钉 API 封装模块 | 233 | ✅ 稳定 |
| `README.md` | 部署文档 | 297 | ✅ 完整 |
| `requirements.txt` | Python 依赖 | 3 | ✅ 稳定 |
| `.env.example` | 配置模板 | 5 | ✅ 稳定 |
| `.gitignore` | Git 忽略规则 | 25 | ✅ 完整 |

### 敏感文件（已加入 .gitignore，不提交）
- `.env` - 包含真实 AppKey/AppSecret
- `AppID.md` - 原始凭证记录
- `downloads/` - 下载的附件目录

---

## 3. 钉钉 API 调用链

```
POST /v1.0/oauth2/accessToken
    ↓ 获取 accessToken（有效期 7200s）
POST /v1.0/workflow/processes/instanceIds/query
    ↓ 获取审批实例 ID 列表（分页，maxResults=20）
GET /v1.0/workflow/processInstances
    ↓ 获取单个审批实例详情
POST /v1.0/workflow/processInstances/spaces/files/urls/download
    ↓ 获取附件下载链接（有效期 15 分钟）
GET <downloadUri>
    ↓ 下载文件到本地
```

### 关键参数
- **processCode**: `PROC-D868A57B-7939-4857-AAAB-0C8437487F7E`（测试用，固定值）
- **时间格式**: 毫秒时间戳（如 `1776614400000`）
- **日期限制**: 查询范围不超过 120 天
- **分页**: nextToken 机制，每页最多 20 条

---

## 4. 核心代码结构

### dingtalk_api.py（7 个函数）

```python
load_env()                    # 加载 .env 配置
get_access_token()            # 获取/刷新 Token
get_instance_id_list()        # 分页获取实例 ID 列表
get_instance_details()        # 获取单个实例详情
extract_attachments()         # 从表单中提取附件信息
get_download_url()            # 获取附件下载链接
download_file()               # 下载文件到本地
```

### app.py（Streamlit 界面）

```
侧边栏 (st.sidebar)
├── 📋 审批查询
│   ├── 开始日期 / 结束日期（date_input）
│   ├── 审批状态（selectbox：已完结/审批中/已撤销/全部）
│   └── 🔍 查询按钮
│
└── 审批列表（动态生成按钮）

主区域
├── 访问令牌状态提示
├── 审批详情（两栏布局）
│   ├── 基本信息（状态、发起人、部门、时间）
│   └── 表单数据（动态渲染所有字段）
│
└── 📎 附件列表
    ├── 附件清单（文件名、大小）
    └── 📥 下载所有附件按钮
```

---

## 5. 关键决策记录

### 5.1 技术选型
- **选择 Streamlit 而非 Flask/Django**：快速验证、无需前端知识、适合内部工具
- **纯文件存储，无数据库**：部署简单、零配置、适合 Demo 阶段
- **.env 管理凭证**：安全、不硬编码、易于切换环境

### 5.2 API 设计
- **processInstanceId 通过列表接口获取**：不手动传入，确保流程完整
- **Token 自动刷新**：7000 秒时自动重新获取，避免过期
- **异常处理**：网络超时、HTTP 401/400、下载失败均有优雅处理

### 5.3 界面设计
- **侧边栏 + 主区域**：经典管理后台布局
- **审批列表用按钮而非表格**：点击即查看，交互简单
- **两栏详情**：左栏基本信息，右栏表单数据

---

## 6. 已知问题与注意事项

### 6.1 当前限制
1. **无持久化存储**：服务器重启后 session 数据丢失
2. **单用户模式**：无并发隔离，不适合多用户同时使用
3. **无用户认证**：任何人访问都能操作
4. **附件下载无断点续传**：大文件可能失败

### 6.2 钉钉 API 限制
1. **Token 有效期**：7200 秒，需自动刷新
2. **下载链接有效期**：15 分钟，过期需重新获取
3. **查询时间范围**：不超过 120 天
4. **分页限制**：每页最多 20 条

### 6.3 特殊处理
- **formComponentValues.value 是 JSON 字符串**：需要 `json.loads()` 解析
- **特殊 downloadUri 格式**：以 `#` 开头的需要 `fileName+fileType` 重命名
- **文件名中的冒号**：需要替换为下划线避免 Windows 不兼容

---

## 7. 测试记录

### 7.1 API 测试（2026-05-20）
- ✅ 获取 Token：成功（有效期 7200s）
- ✅ 查询列表：28 条记录（30 天范围）
- ✅ 查看详情："张鑫提交的公告发布"等审批正常显示
- ✅ 提取附件：2 个附件（docx + xlsx）
- ✅ 下载文件：成功保存到 `./downloads/`

### 7.2 Web 界面测试（Headless 截图）
- ✅ 首页：侧边栏查询面板正常
- ✅ 查询后：显示 28 条审批列表
- ✅ 详情页：两栏布局、表单数据、附件列表正常

### 7.3 部署测试
- ✅ Ubuntu 22.04 无图形界面环境
- ✅ Python 3.12
- ✅ 后台启动（tmux + nohup）
- ✅ Playwright Headless 截图验证

---

## 8. 环境配置

### 8.1 当前环境变量（.env）
> ⚠️ **注意**：真实凭证已从本文件移除，请查看本地 `.env` 文件

```env
DINGTALK_APP_KEY=your_app_key_here
DINGTALK_APP_SECRET=your_app_secret_here
DINGTALK_AGENT_ID=your_agent_id_here
DINGTALK_PROCESS_CODE=PROC-D868A57B-7939-4857-AAAB-0C8437487F7E
```

### 8.2 依赖版本
```
requests>=2.31.0
python-dotenv>=1.0.0
streamlit>=1.28.0
```

---

## 9. Git 信息

- **仓库地址**：https://github.com/wanghannew1/PaySignPrinter
- **SSH 地址**：`git@github.com:wanghannew1/PaySignPrinter.git`
- **分支**：master
- **提交数**：4 个
- **Git 用户**：wanghannew1 / 224199843@qq.com

### 提交历史
```
e8321e5 docs: add comprehensive README with deployment guide
0176663 feat: add Streamlit web UI for approval management
734b20b feat: add DingTalk API module with 7 functions
6196978 chore: add project configuration files
```

---

## 10. 后续开发建议

### 10.1 优先级 1：用户系统
- 添加简单的 session-based 登录
- 角色：admin / operator / viewer
- 控制功能权限（查询/下载/打印/设置）

### 10.2 优先级 2：PDF 生成
- 将审批详情渲染为打印友好的 HTML
- 使用 weasyprint 或 pdfkit 生成 PDF
- 支持自定义页眉页脚

### 10.3 优先级 3：电子签名
- 上传签名图片（PNG 透明背景）
- 在 PDF 指定位置叠加签名
- 支持手写板输入（可选）

### 10.4 优先级 4：批量打印
- 多选审批实例（checkbox）
- 批量下载附件
- 合并为一个 PDF 或分别打印

### 10.5 技术债务
- [ ] 添加单元测试（pytest）
- [ ] 添加类型注解
- [ ] 日志记录（替代 print）
- [ ] 配置文件验证（pydantic）
- [ ] 数据库持久化（SQLite）

---

## 11. 快速启动命令

```bash
# 克隆
git clone git@github.com:wanghannew1/PaySignPrinter.git
cd PaySignPrinter

# 安装依赖
pip install -r requirements.txt

# 配置
cp .env.example .env
# 编辑 .env 填入凭证

# 启动
streamlit run app.py

# 后台启动
tmux new -s dingtalk
streamlit run app.py --server.headless true --server.port 8501
# Ctrl+B, D 分离
```

---

## 12. 相关文档链接

- [钉钉开放平台](https://open.dingtalk.com/)
- [Streamlit 文档](https://docs.streamlit.io/)
- [获取访问令牌 API](https://open.dingtalk.com/document/isv/serverapi/get-access-token)
- [获取审批实例 ID 列表](https://open.dingtalk.com/document/isv/serverapi/obtain-the-approval-instance-id)
- [获取审批实例详情](https://open.dingtalk.com/document/isv/serverapi/obtain-a-single-approval-instance)
- [下载附件](https://open.dingtalk.com/document/isv/serverapi/download-attachments)

---

*此文件由 Atlas (OhMyOpenCode) 于 2026-05-20 生成*
*用于后续会话快速恢复上下文，避免重复分析*
