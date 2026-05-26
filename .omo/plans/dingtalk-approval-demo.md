# 钉钉审批打印工具 - Web Demo

## TL;DR

> **Quick Summary**: 用Python + Streamlit做一个Web验证Demo，端到端验证钉钉OA审批API：获取accessToken → 获取审批实例ID列表 → 展示审批列表 → 查看详情 → 下载附件到本地。
> 
> **Deliverables**:
> - `app.py` - Streamlit Web界面（审批列表 + 详情 + 下载进度）
> - `dingtalk_api.py` - 钉钉API调用模块（6个函数）
> - `.env.example` - 凭证配置模板（含PROCESS_CODE）
> - `requirements.txt` - Python依赖
> - `.gitignore` - 排除.env和downloads
> 
> **Estimated Effort**: Medium (3-5小时)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 5

---

## Context

### Original Request
设计一个工具，用来调取钉钉OA审批完结的流程的单个审批实例详情和附件到本地，然后经过加签名输出打印材料支持一键批量打印。先将最主要的获取单个审批实例详情和下载审批附件做成测试demo验证可行性。

### Interview Summary
**Key Discussions**:
- 编程语言: Python
- 审批类型: 付款审批
- processCode: `PROC-D868A57B-7939-4857-AAAB-0C8437487F7E`（测试值，正式系统再调）
- 权限: OA审批接口权限已开通
- **UI: Streamlit Web界面**，包含审批列表展示、审批详情展示、下载进度指示
- 不做附件在线预览

**Research Findings**:
- 钉钉v2 API: accessToken通过POST获取，7200秒有效期
- 审批实例ID列表: POST instanceIds/query, 需processCode+startTime, 支持分页
- 审批实例详情: GET processInstances, 返回formComponentValues含附件fileId
- 附件下载: POST下载授权接口获取downloadUri，15分钟有效
- formComponentValues的value是JSON字符串需二次解析
- Streamlit: pip install streamlit, 最快Python Web框架，适合demo验证

### Metis Review
**Identified Gaps** (addressed):
- formComponentValues可能含嵌套JSON需json.loads()二次解析
- downloadUri有两种格式（标准URL vs #zifgs09格式）
- 安全：AppSecret不能硬编码 → .env文件方案
- 附件可能为0 → 优雅处理
- 中文文件名处理 → UTF-8编码+文件名净化
- processCode需从审批模板获取 → 用户已提供测试值

---

## Work Objectives

### Core Objective
验证钉钉OA审批API的可行性：通过Web界面展示已完结审批列表、查看详情、下载附件。

### Concrete Deliverables
- `app.py` - Streamlit Web应用（左侧审批列表、右侧详情+下载进度）
- `dingtalk_api.py` - API调用模块（6个函数独立可测）
- `.env.example` + `.env` - 凭证配置
- `requirements.txt` + `.gitignore`

### Definition of Done
- [ ] `streamlit run app.py` 启动Web界面
- [ ] 左侧面板显示已完结审批列表（ID、标题、状态、发起人）
- [ ] 点击审批项，右侧展示详情（表单数据、附件列表）
- [ ] 附件逐个下载，显示下载进度（等待/下载中/完成/失败）
- [ ] 附件保存到 `./downloads/<processInstanceId>/` 目录
- [ ] 错误场景（无效processCode、缺少凭证）界面显示错误提示

### Must Have
- 获取accessToken功能
- 获取审批实例ID列表（通过processCode+statuses=COMPLETED+分页）
- 遍历每个ID获取审批实例详情
- 从formComponentValues中提取附件fileId
- 下载附件到本地
- Streamlit Web界面：审批列表展示
- Streamlit Web界面：审批详情展示（表单字段）
- Streamlit Web界面：附件下载进度指示
- .env凭证管理（含PROCESS_CODE）
- 分页支持（nextToken循环直到为空）
- 中文文件名支持
- 零附件的优雅处理

### Must NOT Have (Guardrails)
- 不实现签名功能（将来工具）
- 不实现打印功能（将来工具）
- 不实现批量打印功能
- 不使用钉钉SDK（纯HTTP请求验证API）
- 不使用日志框架（st.error/st.warning即可）
- 不添加重试逻辑（简单错误处理）
- 不添加"预留抽象"（YAGNI）
- 不实现数据库存储
- 不实现webhook/回调
- 不硬编码AppSecret到源码
- 不实现附件在线预览

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO
- **Automated tests**: None (this IS the verification)
- **Framework**: N/A
- **Strategy**: Agent-executed smoke test via Streamlit + curl verification

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Web UI**: Use Bash - Start streamlit, curl endpoints, check responses
- **API Module**: Use Bash (python -c) - Import module, call functions, verify output
- **Downloads**: Use Bash - Check file existence, size > 0

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - foundation):
├── Task 1: Project scaffolding + .env + gitignore + streamlit config [quick]
└── Task 2: DingTalk API module (6 functions) [deep]

Wave 2 (After Wave 1 - UI + integration):
├── Task 3: Streamlit app - sidebar (审批列表) [visual-engineering]
├── Task 4: Streamlit app - main area (审批详情 + 附件下载) [visual-engineering]
└── Task 5: End-to-end integration + error handling [quick]

Wave FINAL (After ALL tasks — review):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA - streamlit + API (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 3 → Task 5 → F3
Parallel Speedup: ~40% faster than sequential
Max Concurrent: 2 (Wave 1), 3 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | - | 2, 3, 4, 5 | 1 |
| 2 | 1 | 3, 4, 5 | 1 |
| 3 | 1, 2 | 5 | 2 |
| 4 | 1, 2 | 5 | 2 |
| 5 | 3, 4 | F1-F4 | 2 |

### Agent Dispatch Summary

- **Wave 1**: **2** - T1 → `quick`, T2 → `deep`
- **Wave 2**: **3** - T3 → `visual-engineering`, T4 → `visual-engineering`, T5 → `quick`
- **FINAL**: **4** - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Project Scaffolding + Streamlit Config

  **What to do**:
  - Create project directory structure (all files in project root)
  - Create `.env.example` with template: `DINGTALK_APP_KEY=your_app_key_here`, `DINGTALK_APP_SECRET=your_app_secret_here`, `DINGTALK_AGENT_ID=your_agent_id_here`, `DINGTALK_PROCESS_CODE=your_process_code_here`
  - Create actual `.env` file with real credentials from AppID.md AND processCode `PROC-D868A57B-7939-4857-AAAB-0C8437487F7E`
  - Create `.gitignore` with entries: `.env`, `downloads/`, `__pycache__/`, `*.pyc`
  - Create `requirements.txt` with: `requests`, `python-dotenv`, `streamlit`
  - Create empty `app.py` with just `import streamlit as st` and `st.title("钉钉审批Demo")` to verify streamlit works
  - Create empty `dingtalk_api.py` with just a docstring
  - Verify `pip install -r requirements.txt` works
  - Verify `streamlit run app.py` starts without error

  **Must NOT do**:
  - Do NOT hardcode any credentials in Python source files
  - Do NOT commit .env to git

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file creation, no complex logic
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 2, but T2 needs .env)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 2 (needs .env), Task 3, 4, 5
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `AppID.md` - Contains credentials (AppKey, AppSecret, AgentId) and processCode

  **External References**:
  - Streamlit docs: https://docs.streamlit.io/ - Installation and hello world
  - python-dotenv: https://pypi.org/project/python-dotenv/ - .env file loading

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Project files created correctly
    Tool: Bash
    Preconditions: Project directory exists at /home/ubuntu/coding/PaySignPrinter
    Steps:
      1. Run `ls /home/ubuntu/coding/PaySignPrinter/.env.example .env .gitignore requirements.txt app.py dingtalk_api.py`
      2. Run `cat /home/ubuntu/coding/PaySignPrinter/.env.example` → contains DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID, DINGTALK_PROCESS_CODE
      3. Run `cat /home/ubuntu/coding/PaySignPrinter/.env` → contains real AppKey and processCode "PROC-D868A57B-7939-4857-AAAB-0C8437487F7E"
      4. Run `cat /home/ubuntu/coding/PaySignPrinter/requirements.txt` → contains requests, python-dotenv, streamlit
    Expected Result: All files exist with correct content
    Evidence: .omo/evidence/task-1-scaffolding.txt

  Scenario: Streamlit starts successfully
    Tool: Bash
    Preconditions: requirements installed, app.py exists
    Steps:
      1. Run `cd /home/ubuntu/coding/PaySignPrinter && timeout 10 streamlit run app.py --server.headless true 2>&1 | head -5`
    Expected Result: Streamlit starts without import errors
    Evidence: .omo/evidence/task-1-streamlit-start.txt
  ```

  **Commit**: YES
  - Message: `feat(demo): add project scaffolding and streamlit config`
  - Files: `.env.example`, `.env`, `.gitignore`, `requirements.txt`, `app.py`, `dingtalk_api.py`
  - Pre-commit: `pip install -r requirements.txt`

- [x] 2. DingTalk API Module (6 Functions)

  **What to do**:
  - Implement `dingtalk_api.py` with 6 functions:
  
  1. `load_env()` - Load `.env`, read `DINGTALK_APP_KEY`, `DINGTALK_APP_SECRET`, `DINGTALK_PROCESS_CODE`, raise SystemExit if missing
  
  2. `get_access_token(app_key, app_secret)` - POST `/v1.0/oauth2/accessToken`, return accessToken string
  
  3. `get_instance_id_list(access_token, process_code, start_time, end_time=None, statuses=["COMPLETED"])` - POST `/v1.0/workflow/processes/instanceIds/query`, handle pagination (nextToken loop), return list of process instance IDs
  
  4. `get_instance_details(process_instance_id, access_token)` - GET `/v1.0/workflow/processInstances?processInstanceId={id}`, return full response dict
  
  5. `extract_attachments(form_component_values)` - Parse formComponentValues, find DDAttachment items, json.loads() the value field, return list of `{fileId, fileName, fileType}`
  
  6. `get_download_url(process_instance_id, file_id, access_token)` - POST download URL endpoint, return `(download_uri, needs_rename)` tuple
  
  7. `download_file(download_url, file_name, output_dir, process_instance_id, needs_rename=False, original_file_type=None)` - Download file to local, sanitize filename, handle duplicates, return filepath

  - Each function should print step info (for debugging) and return structured data
  - Handle all API errors gracefully: HTTP errors, network timeout, missing fields
  - Use `requests` library with 30s timeout for all calls
  - ProcessCode default from .env but overridable via parameter

  **Must NOT do**:
  - Do NOT use DingTalk SDK
  - Do NOT add retry logic
  - Do NOT add token caching to disk
  - Do NOT include any Streamlit code in this module (pure API logic only)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 7 functions with various API calls, pagination logic, error handling - requires careful implementation
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 1's .env)
  - **Parallel Group**: Wave 1 (sequential after Task 1)
  - **Blocks**: Task 3, 4, 5
  - **Blocked By**: Task 1

  **References**:

  **API/Type References**:
  - Token: `POST https://api.dingtalk.com/v1.0/oauth2/accessToken` → `{accessToken, expireIn}`
  - ID List: `POST https://api.dingtalk.com/v1.0/workflow/processes/instanceIds/query` → `{result: {list: [string], nextToken: string}}`
    - ⚠️ startTime距当前不能超过120天, maxResults最大20, nextToken首次传0
  - Details: `GET https://api.dingtalk.com/v1.0/workflow/processInstances?processInstanceId={id}` → `{result: {title, status, formComponentValues, ...}}`
  - Download URL: `POST https://api.dingtalk.com/v1.0/workflow/processInstances/spaces/files/urls/download` → `{result: {downloadUri, spaceId, fileId}}`
    - ⚠️ downloadUri 15分钟有效, ⚠️ #zifgs09xxxxx.file 格式需重命名
  - formComponentValues.value: JSON string requiring json.loads()
  - processCode: `PROC-D868A57B-7939-4857-AAAB-0C8437487F7E`

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: API module imports without errors
    Tool: Bash
    Preconditions: dingtalk_api.py exists
    Steps:
      1. Run `cd /home/ubuntu/coding/PaySignPrinter && python -c "from dingtalk_api import load_env, get_access_token, get_instance_id_list, get_instance_details, extract_attachments, get_download_url, download_file; print('All functions imported')"`
    Expected Result: "All functions imported" printed without errors
    Evidence: .omo/evidence/task-2-imports.txt

  Scenario: Token retrieval works
    Tool: Bash
    Preconditions: .env with valid credentials
    Steps:
      1. Run `cd /home/ubuntu/coding/PaySignPrinter && python -c "from dingtalk_api import load_env, get_access_token; env = load_env(); token = get_access_token(env['app_key'], env['app_secret']); print('Token:', token[:10] + '...')"`
    Expected Result: Token prefix printed (non-empty)
    Failure Indicators: 401 error, empty token
    Evidence: .omo/evidence/task-2-token.txt

  Scenario: Instance ID list retrieval works
    Tool: Bash
    Preconditions: Valid token, valid processCode
    Steps:
      1. Run `cd /home/ubuntu/coding/PaySignPrinter && python -c "from dingtalk_api import load_env, get_access_token, get_instance_id_list; import time; env = load_env(); token = get_access_token(env['app_key'], env['app_secret']); start = int((time.time() - 86400*30)*1000); ids = get_instance_id_list(token, env['process_code'], start); print(f'Found {len(ids)} instances')"`
    Expected Result: Number of instances printed (>0 if approvals exist)
    Evidence: .omo/evidence/task-2-instance-ids.txt

  Scenario: Missing credentials error
    Tool: Bash
    Preconditions: Environment variables unset
    Steps:
      1. Run `cd /home/ubuntu/coding/PaySignPrinter && DINGTALK_APP_KEY="" python -c "from dingtalk_api import load_env; load_env()" 2>&1`
    Expected Result: Clear error message, exit code != 0
    Evidence: .omo/evidence/task-2-missing-creds.txt
  ```

  **Commit**: YES
  - Message: `feat(demo): add DingTalk API module with 7 functions`
  - Files: `dingtalk_api.py`
  - Pre-commit: `python -c "from dingtalk_api import load_env, get_access_token, get_instance_id_list, get_instance_details, extract_attachments, get_download_url, download_file"`

- [x] 3. Streamlit App - Sidebar (审批列表)

  **What to do**:
  - Implement `app.py` Streamlit application sidebar:
    - Page config: `st.set_page_config(page_title="钉钉审批Demo", layout="wide")`
    - Load env and get access token on app start (with st.spinner)
    - Sidebar with:
      - Date range picker (st.date_input): startTime and endTime, default last 30 days
      - Status filter (st.selectbox): "已完结" (COMPLETED) / "全部" / "审批中" (RUNNING) / "已撤销" (TERMINATED)
      - "查询" button (st.button): triggers `get_instance_id_list()` call
      - Results: st.dataframe or st.expander showing list of approvals with columns: 标题, 状态, 发起人, 发起时间
      - Each row clickable → sets st.session_state.selected_instance_id
    - Handle errors: display st.error() for API failures (token, processCode, network)
    - Handle empty results: st.info("未查询到已完结的审批")
    - Cache access token in st.session_state to avoid re-fetching on every interaction

  **Must NOT do**:
  - Do NOT put API logic in app.py (use dingtalk_api module)
  - Do NOT add attachment download in sidebar (that's Task 4)
  - Do NOT add logging framework

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Streamlit UI layout and interaction design
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 4, but they share app.py so need coordination)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 5
  - **Blocked By**: Task 1, Task 2

  **References**:

  **External References**:
  - Streamlit docs: https://docs.streamlit.io/ - st.sidebar, st.dataframe, st.selectbox, st.date_input, st.button
  - Streamlit session state: https://docs.streamlit.io/ - st.session_state for caching token and selected ID

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Streamlit app starts and shows sidebar
    Tool: Bash
    Preconditions: app.py exists, .env configured
    Steps:
      1. Run `cd /home/ubuntu/coding/PaySignPrinter && timeout 15 streamlit run app.py --server.headless true 2>&1 | head -10`
    Expected Result: Streamlit starts without errors
    Evidence: .omo/evidence/task-3-streamlit-start.txt

  Scenario: Sidebar shows date picker and status filter
    Tool: Bash
    Preconditions: App is running
    Steps:
      1. Check app.py source contains st.sidebar, st.date_input, st.selectbox, st.button
      2. Check date picker defaults to last 30 days
      3. Check status filter defaults to "已完结" (COMPLETED)
    Expected Result: UI elements present in source code, correct defaults
    Evidence: .omo/evidence/task-3-sidebar-ui.txt
  ```

  **Commit**: YES
  - Message: `feat(demo): add Streamlit sidebar with approval list`
  - Files: `app.py`
  - Pre-commit: `python -m py_compile app.py`

- [x] 4. Streamlit App - Main Area (审批详情 + 附件下载)

  **What to do**:
  - Implement main area of `app.py`:
    - When an instance is selected (from st.session_state.selected_instance_id):
      - Call `get_instance_details()` to fetch details
      - Display in st.columns layout:
        - Left column: 审批详情 (title, status badge, originator, department, create/finish time)
        - Right column: 表单数据 (iterate formComponentValues, display non-attachment fields as key-value pairs)
      - Below details: 附件列表 section
        - If attachments found: list each with fileName, fileType, fileSize
        - "下载所有附件" button: triggers download loop with progress
        - For each attachment: st.progress bar showing download status
          - "⏳ 等待中" → "⬇️ 下载中..." → "✅ 已下载" or "❌ 下载失败"
        - Download location shown: `./downloads/<processInstanceId>/`
      - If no attachments: st.info("该审批无附件")
    - When no instance selected:
      - st.info("请从左侧选择一个审批实例")
    - Error handling: st.error for API failures, st.warning for partial failures

  **Must NOT do**:
  - Do NOT implement attachment preview/previewer (not in scope)
  - Do NOT add batch download across multiple instances (only single instance)
  - Do NOT put API logic in app.py (use dingtalk_api module)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Streamlit UI for detail display and progress indicators
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 3, but share app.py)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 5
  - **Blocked By**: Task 1, Task 2

  **References**:

  **External References**:
  - Streamlit columns: https://docs.streamlit.io/ - st.columns for side-by-side layout
  - Streamlit progress: https://docs.streamlit.io/ - st.progress for download indication
  - Streamlit status elements: st.success, st.error, st.warning, st.info

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Detail view shows approval info
    Tool: Bash
    Preconditions: app.py has main area implementation
    Steps:
      1. Check app.py source contains st.columns, st.success, st.info
      2. Check for "下载所有附件" button
      3. Check for attachment progress indicators (st.progress or status text)
    Expected Result: UI structure present in source code
    Evidence: .omo/evidence/task-4-detail-view.txt
  ```

  **Commit**: YES
  - Message: `feat(demo): add approval detail view and attachment download with progress`
  - Files: `app.py`
  - Pre-commit: `python -m py_compile app.py`

- [x] 5. End-to-End Integration + Error Handling

  **What to do**:
  - Wire up the complete flow in `app.py`:
    - On app start: load_env(), get_access_token(), cache in session_state
    - On "查询" click: get_instance_id_list() → populate sidebar list
    - On instance selection: get_instance_details() → display in main area
    - On "下载所有附件" click: loop through attachments, get_download_url() + download_file() per file, update progress per file
    - Handle all edge cases:
      - Token expired mid-session → show error, refresh token on next action
      - No approvals found for date range → st.info message
      - Instance has 0 attachments → st.info message
      - Download fails for single file → st.error for that file, continue others
      - Network timeout → st.error with timeout message
      - Invalid processCode → st.sidebar.error
  - Make sure `streamlit run app.py` shows full working UI
  - Verify download directory is created: `./downloads/<processInstanceId>/`

  **Must NOT do**:
  - Do NOT add progress bars with percentage (use simple status text)
  - Do NOT add file type detection
  - Do NOT add config file support

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Integration work, wiring existing functions together
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Task 3 and Task 4)
  - **Blocks**: F1, F2, F3, F4
  - **Blocked By**: Task 3, Task 4

  **References**:

  **Pattern References**:
  - `dingtalk_api.py` functions: `load_env()`, `get_access_token()`, `get_instance_id_list()`, `get_instance_details()`, `extract_attachments()`, `get_download_url()`, `download_file()`

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full streamlit app starts and renders
    Tool: Bash
    Preconditions: All files exist, .env configured
    Steps:
      1. Run `cd /home/ubuntu/coding/PaySignPrinter && timeout 15 streamlit run app.py --server.headless true 2>&1 | head -10`
    Expected Result: Streamlit starts without import or runtime errors
    Evidence: .omo/evidence/task-5-app-start.txt

  Scenario: Help text / placeholder visible when no instance selected
    Tool: Bash
    Preconditions: App running
    Steps:
      1. Check app.py contains st.info with placeholder message for when no instance is selected
    Expected Result: Placeholder message present in source
    Evidence: .omo/evidence/task-5-placeholder.txt

  Scenario: Error handling for missing credentials
    Tool: Bash
    Preconditions: .env temporarily renamed
    Steps:
      1. Run `cd /home/ubuntu/coding/PaySignPrinter && mv .env .env.bak && streamlit run app.py --server.headless true 2>&1 | head -20; mv .env.bak .env`
    Expected Result: App shows error message about missing credentials (not crash)
    Evidence: .omo/evidence/task-5-env-error.txt
  ```

  **Commit**: YES
  - Message: `feat(demo): add end-to-end integration and error handling`
  - Files: `app.py`, `dingtalk_api.py`
  - Pre-commit: `python -m py_compile app.py && python -m py_compile dingtalk_api.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search for forbidden patterns. Check evidence files. Compare deliverables.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `python -m py_compile` on both files. Review for: hardcoded credentials, missing error handling, unclear names, excessive abstraction. Check .env.example has all vars. Check .gitignore. Verify dingtalk_api.py has no Streamlit imports (should be pure API).
  Output: `Build [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start: `streamlit run app.py`. Verify: sidebar shows date picker + status filter. Click query → approval list appears. Select an approval → details + attachments shown. Click download → progress updates → files in ./downloads/. Test error: invalid processCode → error shown. Test: missing .env → error shown.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  Verify 1:1 plan-to-code: everything in spec built, nothing beyond. Check: no SDK import, no logging framework, no attachment preview, no batch across instances. Verify dingtalk_api.py is pure API logic (no st.* calls).
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Single Commit**: `feat(demo): add DingTalk approval Web demo with Streamlit`
  - `app.py`, `dingtalk_api.py`, `.env.example`, `.env`, `requirements.txt`, `.gitignore`
  - Pre-commit: `python -m py_compile app.py && python -m py_compile dingtalk_api.py`

---

## Success Criteria

### Verification Commands
```bash
pip install -r requirements.txt                                    # Expected: no errors
python -c "from dingtalk_api import load_env, get_access_token, get_instance_id_list, get_instance_details, extract_attachments, get_download_url, download_file"  # Expected: no import errors
streamlit run app.py                                                # Expected: Web UI opens
# In browser: select date range → click 查询 → select approval → click 下载
ls ./downloads/                                                     # Expected: directories with downloaded files
```

### Final Checklist
- [ ] All "Must Have" present (including instance ID list function and Web UI)
- [ ] All "Must NOT Have" absent (no SDK, no preview, no logging)
- [ ] streamlit run app.py starts without errors
- [ ] Token retrieval works against real DingTalk API
- [ ] Instance ID list retrieval works with processCode
- [ ] Sidebar shows approval list
- [ ] Detail view shows approval form data
- [ ] Attachment download produces real files
- [ ] Error cases handled gracefully in UI