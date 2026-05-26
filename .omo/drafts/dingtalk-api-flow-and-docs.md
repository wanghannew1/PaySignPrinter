# 钉钉审批附件下载流程 & 接口文档

## 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                     钉钉审批附件下载流程                          │
│                  (Streamlit Web Demo)                           │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  启动         │
    │  Streamlit    │
    │  Web App      │
    └──────┬───────┘
           │
           ▼
    ┌──────────────────────────────────┐
    │ ① 获取 Access Token               │
    │ POST /v1.0/oauth2/accessToken     │
    │ 用 AppKey + AppSecret 换 Token     │
    │ (缓存到 session_state)             │
    └──────────────┬───────────────────┘
                   │
                   ▼
            ┌──────────────────────────────┐
            │ 左侧边栏 (Sidebar)            │
            │                              │
            │ [日期范围选择器]               │
            │ [状态筛选: 已完结/全部/...]     │
            │ [🔍 查询] 按钮                │
            └──────────────┬───────────────┘
                           │ 点击"查询"
                           ▼
    ┌──────────────────────────────────┐
    │ ② 获取审批实例ID列表               │
    │ POST /v1.0/workflow/             │
    │     processes/instanceIds/query   │
    │ processCode=PROC-D868A57B-...     │
    │ statuses=["COMPLETED"]            │
    │ startTime=选择的起始时间戳(ms)      │
    │ nextToken=0(首页) → 循环分页      │
    └──────────────┬───────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────┐
    │ 左侧边栏显示审批列表               │
    │ ┌──────────────────────────────┐ │
    │ │ 📋 付款审批-张三-202401       │ │
    │ │    状态: 已完结 | 发起人: 张三  │ │
    │ ├──────────────────────────────┤ │
    │ │ 📋 付款审批-李四-202402       │ │
    │ │    状态: 已完结 | 发起人: 李四  │ │
    │ └──────────────────────────────┘ │
    └──────────────┬───────────────────┘
                   │ 点击某个审批
                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │ 主区域 - 审批详情                                             │
    │                                                              │
    │ ┌────────────────────────┐ ┌──────────────────────────┐    │
    │ │ 📋 审批基本信息          │ │ 📝 表单数据               │    │
    │ │ 标题: 付款审批-张三     │ │ 付款事由: 供应商货款       │    │
    │ │ 状态: ✅ 已完结         │ │ 付款金额: ¥50,000.00     │    │
    │ │ 发起人: 张三            │ │ 付款日期: 2024-01-15      │    │
    │ │ 部门: 财务部            │ │ ...                       │    │
    │ │ 发起时间: 2024-01-15    │ │                           │    │
    │ │ 完结时间: 2024-01-16    │ │                           │    │
    │ └────────────────────────┘ └──────────────────────────────┘    │
    │                                                              │
    │ ③ 获取审批实例详情 (GET /v1.0/workflow/processInstances)       │
    │                                                              │
    │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
    │                                                              │
    │ 📎 附件列表                                                   │
    │ ┌──────────────────────────────────────────────────────────┐ │
    │ │ 付款凭证.pdf (123KB)                      ⬇️ 下载中...  │ │
    │ │ 发票扫描件.jpg (89KB)                     ⏳ 等待中      │ │
    │ │                                                            │ │
    │ │ [📥 下载所有附件]                                          │ │
    │ └──────────────────────────────────────────────────────────┘ │
    │                                                              │
    │ ④ 提取附件信息 (DDAttachment → fileId)                        │
    │ ⑤ 获取下载链接 (POST download → downloadUri, 15min有效)      │
    │ ⑥ 下载文件到本地 (./downloads/{instanceId}/)                    │
    └──────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────┐
    │ ① 获取 Access Token               │
    │ POST /v1.0/oauth2/accessToken     │
    │ 用 AppKey + AppSecret 换 Token     │
    └──────────────┬───────────────────┘
                   │
                   ▼
            ┌────────────┐
            │ Token 获取   │
            │ 是否成功？   │
            └──┬───────┬──┘
          否   │       │  是
               ▼       ▼
        ┌─────────┐  ┌──────────────────────────────────┐
        │ 报错退出 │  │ ② 获取审批实例ID列表               │
        └─────────┘  │ POST /v1.0/workflow/               │
                      │     processes/instanceIds/query     │
                      │ processCode=固定值(付款审批模板)    │
                      │ statuses=["COMPLETED"]             │
                      │ startTime=查询起始时间戳(ms)        │
                      │ nextToken=0(首页)                  │
                      │ maxResults=20                     │
                      └──────────────┬───────────────────┘
                                     │
                                     ▼
                            ┌────────────────┐
                            │ ID列表查询       │
                            │ 是否成功？       │
                            └──┬──────────┬──┘
                          否   │          │  是
                               ▼          ▼
                         ┌─────────┐  ┌──────────────────────┐
                         │ 报错退出 │  │ 返回 instanceId 列表  │
                         └─────────┘  │ list: [id1, id2, ...] │
                                      │ nextToken: "xxx"       │
                                      └──────────┬───────────┘
                                                 │
                                                 ▼
                                      ┌───────────────────┐
                                      │ ③ 遍历每个         │
                                      │ processInstanceId  │
                                      │ 获取审批实例详情    │
                                      └─────────┬─────────┘
                                                │
                                                ▼
                            ┌──────────────────────────────┐
                            │ ③ 获取审批实例详情              │
                            │ GET /v1.0/workflow/             │
                            │     processInstances            │
                            │     ?processInstanceId={id}     │
                            │ Header: x-acs-dingtalk-         │
                            │         access-token={token}     │
                            └──────────────┬─────────────────┘
                                           │
                                           ▼
                                  ┌────────────────┐
                                  │ 实例查询         │
                                  │ 是否成功？       │
                                  └──┬──────────┬───┘
                                否   │          │  是
                                     ▼          ▼
                               ┌─────────┐  ┌──────────────────────┐
                               │ 跳过此ID │  │ ④ 从 formComponent   │
                               │ 记录错误 │  │    Values 中提取       │
                               └─────────┘  │    附件 fileId 列表     │
                                            │ (遍历 componentType    │
                                            │  = "DDAttachment")     │
                                            └──────────┬───────────┘
                                                       │
                                                       ▼
                                            ┌────────────────┐
                                            │ 附件数量        │
                                            │ 是否 > 0 ？     │
                                            └──┬─────────┬───┘
                                          否   │         │  是
                                               ▼         ▼
                                        ┌──────────┐  ┌─────────────────────────┐
                                        │ 跳过此ID   │  │ ⑤ 遍历每个附件 fileId    │
                                        │ 记录无附件 │  │    ↓                     │
                                        └──────────┘  │ ⑤a 获取附件下载链接       │
                                                      │ POST /v1.0/workflow/     │
                                                      │   processInstances/      │
                                                      │   spaces/files/urls/     │
                                                      │   download               │
                                                      └──────────┬──────────────┘
                                                                 │
                                                                 ▼
                                                        ┌──────────────────┐
                                                        │ 下载链接获取       │
                                                        │ 是否成功？         │
                                                        └──┬────────────┬──┘
                                                      否   │            │  是
                                                           ▼            ▼
                                                    ┌──────────┐  ┌──────────────────────┐
                                                    │ 跳过此附件 │  │ ⑤b 判断 downloadUri  │
                                                    │ 记录错误   │  │    格式                │
                                                    └──────────┘  └──────────┬───────────┘
                                                                           │
                                                                  ┌────────┴────────┐
                                                                  │                 │
                                                           downloadUri        downloadUri
                                                           以 http 开头       以 # 开头
                                                           (标准URL)          (钉钉特殊格式)
                                                                  │                 │
                                                                  ▼                 ▼
                                                           ┌────────────┐  ┌────────────────────┐
                                                           │ ⑥ 直接下载  │  │ ⑥ 用 fileName +     │
                                                           │ 文件到本地   │  │   fileType 重命名     │
                                                           └──────┬─────┘  │   后下载到本地        │
                                                                  │        └─────────┬──────────┘
                                                                  │                  │
                                                                  └────────┬─────────┘
                                                                           │
                                                                           ▼
                                                                  ┌──────────────────┐
                                                                  │ ⑥ 保存到          │
                                                                  │ ./downloads/      │
                                                                  │   {instanceId}/   │
                                                                  │   {filename}      │
                                                                  └────────┬─────────┘
                                                                           │
                                                                           ▼
                                                                  ┌──────────────────┐
                                                                  │ 所有附件处理完？  │
                                                                  └──┬────────────┬──┘
                                                                否   │            │  是
                                                                     │            ▼
                                                                     │   ┌──────────────┐
                                                                     │   │ 所有ID处理完？│
                                                                     │   └──┬────────┬──┘
                                                                     │   否       │  是
                                                                     │    │       ▼
                                                                     │    │  ┌──────────┐
                                                                     │    │  │ 完成！    │
                                                                     │    │  │ 打印汇总  │
                                                                     │    └──┘  └──────────┘
                                                                     │
                                                                     └──→ 回到 5a 处理下一个附件
                                                                      │
                                                                      └──→ 回到 ③ 处理下一个 instanceId


═══════════════════════════════════════════════════════════════════

  简化流程 (6步):

  ① 获取Token
      │
      ▼
  ② 获取审批实例ID列表 (processCode=PROC-D868A57B-..., statuses=["COMPLETED"])
      │  ← ⭐ 新增环节！processCode是固定值，从.env读取
      ▼
  ③ 遍历每个 processInstanceId → 获取审批实例详情
      │
      ▼
  ④ 从 formComponentValues 提取附件信息 (DDAttachment → fileId)
      │
      ▼
  ⑤ 获取附件下载链接 (downloadUri, 15分钟有效)
      │
      ▼
  ⑥ 下载文件到本地 ./downloads/{instanceId}/
```

---

## 关键注意事项

```
⚠️ processCode 是固定值！
    → 它是付款审批模板的唯一码，在 .env 中配置
    → 获取方式：钉钉管理后台 → OA审批 → 审批模板 → processCode
    → 或通过"创建或更新审批表单模板"接口获取

⚠️ startTime 距当前时间不能超过 120 天！
    → endTime 不传则默认取当前时间
    → startTime 和 endTime 范围不能超过 120 天

⚠️ nextToken 分页！
    → 首次传 0
    → 后续传上一次返回的 nextToken
    → 返回的 nextToken 不为空表示有更多数据
    → maxResults 最多 20

⚠️ downloadUri 有效期仅 15 分钟！
    → 获取后必须立即下载
    → 不要提前获取所有链接再逐个下载

⚠️ formComponentValues.value 是 JSON 字符串！
    → 需要 json.loads() 二次解析
    → 示例: "[{\"fileId\":\"xxx\",\"fileName\":\"发票.pdf\",\"fileType\":\"pdf\"}]"

⚠️ 钉钉客户端发起的审批附件 downloadUri 格式特殊！
    → 标准格式: "https://xxx.oss-cn-xxx.aliyuncs.com/xxx"
    → 特殊格式: "#zifgs09xxxxx.file"
    → 特殊格式需用详情接口的 fileName/fileType 重命名

⚠️ Token 有效期 2 小时！
    → Demo 中每次运行重新获取即可
    → 生产环境建议缓存 7000 秒
```

---

## 接口文档

### 接口 1: 获取 Access Token

| 项目 | 值 |
|------|-----|
| **名称** | 获取企业内部应用 access_token |
| **接口地址** | `https://api.dingtalk.com/v1.0/oauth2/accessToken` |
| **HTTP方法** | POST |
| **Content-Type** | application/json |

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| appKey | string | 是 | 应用的 AppKey（即 Client ID） |
| appSecret | string | 是 | 应用的 AppSecret（即 Client Secret） |

#### 请求示例

```json
{
  "appKey": "dingwtlvjdradsgnn53l",
  "appSecret": "fpMNocxcJLDckYv3T_a27n4yCXtmCtOoLJt9-ZW6BVknE8TTd0sHQtfTsVggpxoD"
}
```

#### 响应参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| accessToken | string | 访问令牌，有效期 7200 秒 |
| expireIn | int | 过期时间，单位秒，默认 7200 |

#### 响应示例

```json
{
  "accessToken": "fw8ef8we8f76e6f7s8dxxxx",
  "expireIn": 7200
}
```

#### 错误码

| 错误码 | 说明 |
|--------|------|
| invalidParameter | 参数错误 |
| 401 | AppKey 或 AppSecret 无效 |

---

### 接口 2: 获取审批实例ID列表 ⭐ 新增

| 项目 | 值 |
|------|-----|
| **名称** | 获取审批实例ID列表 |
| **接口地址** | `https://api.dingtalk.com/v1.0/workflow/processes/instanceIds/query` |
| **HTTP方法** | POST |
| **Content-Type** | application/json |

#### 请求头

| Header | 类型 | 必填 | 说明 |
|--------|------|------|------|
| x-acs-dingtalk-access-token | string | 是 | 通过接口1获取的 accessToken |

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| processCode | string | ⭐**是** | 审批流的唯一码（固定值，付款审批模板的 processCode） |
| startTime | Long | 是 | 审批实例开始时间，Unix时间戳，单位**毫秒**。距离当前不能超过120天 |
| endTime | Long | 否 | 审批实例结束时间，Unix时间戳，单位毫秒。不传则默认取当前时间 |
| nextToken | Long | 是 | 分页游标。首次调用传 **0**，后续传上次返回的 nextToken |
| maxResults | Long | 是 | 分页大小，最多 **20** |
| userIds | Array\<String\> | 否 | 发起人userId列表，最大长度10 |
| statuses | Array\<String\> | 否 | 流程状态：RUNNING / TERMINATED / COMPLETED / CANCELED。**不传查所有** |

#### 请求示例

```json
{
  "processCode": "PROC-FF6Y2xxxx",
  "startTime": 1704067200000,
  "endTime": 1706745600000,
  "nextToken": 0,
  "maxResults": 20,
  "statuses": ["COMPLETED"]
}
```

#### 响应参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| result | object | 返回结果 |
| result.list | Array\<String\> | ⭐ **审批实例ID列表** |
| result.nextToken | String | 分页游标。**不为空表示有更多数据** |
| success | Boolean | 请求是否成功 |

#### 响应示例

```json
{
  "result": {
    "list": [
      "a171de6c-8bxxxx",
      "b282ef7d-9cyyyy",
      "c393fg8e-0dzzzz"
    ],
    "nextToken": "1706745600000_3"
  },
  "success": true
}
```

#### 分页逻辑

```
首次请求: nextToken = 0
         ↓
返回 nextToken = "1706745600000_3" (不为空，有更多数据)
         ↓
再次请求: nextToken = "1706745600000_3"
         ↓
返回 nextToken = "" (为空，没有更多数据了)
         ↓
结束分页
```

#### 错误码

| HTTP状态码 | 错误码 | 说明 |
|-----------|--------|------|
| 400 | invalidProcessCode | 审批模版 processCode 不能为空 |
| 400 | invalidInstanceListIdsStartTime | 审批实例开始时间不能为空 |
| 400 | invalidNextToken | 分页查询的游标不能为空 |
| 400 | invalidMaxResults | 分页参数非法，每页大小最多20 |
| 400 | invalidEndTime | 结束时间不能小于开始时间；时间范围不能超过120天 |
| 400 | invalidUserIds | 发起人userid列表参数非法，最大长度10 |

#### ⭐ processCode 获取方式

| 方式 | 操作 |
|------|------|
| **方式一：钉钉管理后台** | 登录钉钉管理后台 → OA审批 → 审批模板管理 → 找到付款审批模板 → processCode |
| **方式二：名词解释页面** | OA审批概述 → 名词解释 → processCode |
| **方式三：API获取** | 调用"创建或更新审批表单模板"接口获取 |

---

### 接口 3: 获取单个审批实例详情

| 项目 | 值 |
|------|-----|
| **名称** | 获取单个审批实例详情 |
| **接口地址** | `https://api.dingtalk.com/v1.0/workflow/processInstances` |
| **HTTP方法** | GET |
| **Content-Type** | application/json |

#### 请求头

| Header | 类型 | 必填 | 说明 |
|--------|------|------|------|
| x-acs-dingtalk-access-token | string | 是 | 通过接口1获取的 accessToken |

#### 查询参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| processInstanceId | string | 是 | 审批实例 ID（从接口2的 list 中获取） |

#### 请求示例

```
GET https://api.dingtalk.com/v1.0/workflow/processInstances?processInstanceId=a171de6c-8bxxxx
Host: api.dingtalk.com
x-acs-dingtalk-access-token: fw8ef8we8f76e6f7s8dxxxx
Content-Type: application/json
```

#### 响应参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| result | object | 返回结果 |
| result.title | string | 审批实例标题 |
| result.status | string | 审批状态：NEW / RUNNING / TERMINATED / COMPLETED / CANCELED |
| result.originatorUserId | string | 发起人的 userId |
| result.originatorDeptId | string | 发起人部门 ID，-1 表示根部门 |
| result.originatorDeptName | string | 发起人部门名称 |
| result.createTime | string | 创建时间 |
| result.finishTime | string | 结束时间 |
| result.processInstanceId | string | 实例 ID |
| result.bizAction | string | 业务动作：MODIFY / REVOKE / NONE |
| result.formComponentValues | array | ⭐ **表单数据列表（含附件信息）** |
| result.formComponentValues[].id | string | 组件 ID |
| result.formComponentValues[].name | string | 组件名称 |
| result.formComponentValues[].componentType | string | 组件类型，附件类为 `"DDAttachment"` |
| result.formComponentValues[].value | string | ⭐ **组件值（JSON字符串，需二次解析！）** |

#### ⭐ formComponentValues.value 附件字段解析

当 `componentType` 为 `"DDAttachment"` 时，`value` 是如下 JSON 字符串（需 `json.loads()` 解析）：

```json
[
  {
    "fileId": "68xxxx11",
    "fileName": "付款凭证.pdf",
    "fileType": "pdf",
    "fileSize": 12345
  },
  {
    "fileId": "72yyyy22",
    "fileName": "发票扫描件.jpg",
    "fileType": "jpg",
    "fileSize": 89010
  }
]
```

#### 付款审批常见表单字段

| componentType | name 示例 | 说明 |
|---------------|-----------|------|
| DDAttachment | 附件 / 凭证 / 发票 | ⭐ **附件字段，含 fileId** |
| TextField | 付款事由 | 文本字段 |
| MoneyField | 付款金额 | 金额字段 |
| DDDateField | 付款日期 | 日期字段 |
| DDSelectField | 付款方式 | 下拉选择 |
| DDContactField | 收款人 | 联系人 |

#### 响应示例

```json
{
  "result": {
    "title": "付款审批-张三-202401",
    "status": "COMPLETED",
    "originatorUserId": "zhangsan001",
    "originatorDeptId": "1",
    "originatorDeptName": "财务部",
    "createTime": "2024-01-15 10:30:00",
    "finishTime": "2024-01-16 14:20:00",
    "processInstanceId": "a171de6c-8bxxxx",
    "bizAction": "NONE",
    "formComponentValues": [
      {
        "id": "textField_001",
        "name": "付款事由",
        "componentType": "TextField",
        "value": "供应商货款结算"
      },
      {
        "id": "moneyField_001",
        "name": "付款金额",
        "componentType": "MoneyField",
        "value": "50000.00"
      },
      {
        "id": "DDAttachment_001",
        "name": "附件",
        "componentType": "DDAttachment",
        "value": "[{\"fileId\":\"68xxxx11\",\"fileName\":\"付款凭证.pdf\",\"fileType\":\"pdf\",\"fileSize\":12345}]"
      }
    ]
  }
}
```

#### 错误码

| HTTP状态码 | 错误码 | 说明 |
|-----------|--------|------|
| 400 | invalidParameter | 获取单个审批实例详情参数错误 |
| 400 | processInstanceIdError | processInstanceId 参数无效 |
| 400 | processInstanceNotExist | 审批实例不存在 |
| 400 | needAuth | 没有发起审批的权限 |
| 400 | processFormDataIsNull | 流程表单数据为空 |

---

### 接口 4: 下载审批附件（获取下载链接）

| 项目 | 值 |
|------|-----|
| **名称** | 下载审批附件 |
| **接口地址** | `https://api.dingtalk.com/v1.0/workflow/processInstances/spaces/files/urls/download` |
| **HTTP方法** | POST |
| **Content-Type** | application/json |

#### 请求头

| Header | 类型 | 必填 | 说明 |
|--------|------|------|------|
| x-acs-dingtalk-access-token | string | 是 | 通过接口1获取的 accessToken |

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| processInstanceId | string | 是 | 审批实例 ID（从接口2获取、接口3使用） |
| fileId | string | 是 | 文件 ID（从接口3的 formComponentValues 中提取） |
| withCommentAttatchment | boolean | 否 | 是否包含评论中的附件，默认 false |

#### 请求示例

```json
{
  "processInstanceId": "a171de6c-8bxxxx",
  "fileId": "68xxxx11",
  "withCommentAttatchment": false
}
```

#### 响应参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| result | object | 返回结果 |
| result.spaceId | long | 钉盘空间 ID |
| result.fileId | string | 文件 ID |
| result.downloadUri | string | ⭐ **文件下载地址（有效期 15 分钟！）** |

#### ⚠️ downloadUri 两种格式

| 格式 | 示例 | 说明 |
|------|------|------|
| **标准 URL** | `https://lippi-space-zjk.oss-cn-zhangjiakou.aliyuncs.com/xxxxx` | 直接可用，GET 请求即可下载 |
| **钉钉特殊格式** | `#zifgs09xxxxx.file` | 钉钉客户端手动发起的审批特有。⚠️ **必须用接口3返回的 fileName + fileType 拼接真实文件名后保存** |

#### 响应示例

```json
{
  "result": {
    "spaceId": 2748422566,
    "fileId": "2",
    "downloadUri": "https://lippi-space-zjk.oss-cn-zhangjiakou.aliyuncs.com/xxxxx"
  },
  "success": true
}
```

#### 错误码

| HTTP状态码 | 错误码 | 说明 |
|-----------|--------|------|
| 400 | invalidParameter | 下载审批附件参数错误 |
| 400 | userNotExist | 用户不存在 |
| 400 | invalidProcessInstanceId | 实例 id 不能为空 |
| 400 | invalidFileId | 审批附件 fileId 不能为空 |
| 400 | processInstNotExist | 审批实例不存在 |
| 400 | noPermission | 无访问权限 |
| 400 | hsfIntegrationErrorCspaceDentryServiceGrant | 授权访问钉盘失败 |

---

### 接口 5: 下载文件到本地（标准HTTP下载）

| 项目 | 值 |
|------|-----|
| **名称** | 下载文件到本地 |
| **接口地址** | 接口4返回的 downloadUri |
| **HTTP方法** | GET |
| **注意事项** | 15分钟有效，需立即下载 |

#### 下载流程

```
1. GET downloadUri（无需额外 Auth Header，URL 本身是预签名链接）
2. 以二进制流写入本地文件
3. 如果 downloadUri 以 "#" 开头，文件名使用接口3中的 fileName.fileType
4. 保存路径: ./downloads/{processInstanceId}/{safe_filename}
```

---

## 完整调用时序图

```
  客户端 (demo.py)                    钉钉 API                          本地文件系统
       │                                │                                   │
       │ ① POST /oauth2/accessToken     │                                   │
       │ {appKey, appSecret}             │                                   │
       │──────────────────────────────► │                                   │
       │                                │                                   │
       │ ◄─── {accessToken} ─────────── │                                   │
       │                                │                                   │
       │ ② POST /processes/instanceIds/query                                │
       │ {processCode, startTime,       │                                   │
       │  statuses:["COMPLETED"],        │                                   │
       │  nextToken:0, maxResults:20}   │                                   │
       │──────────────────────────────► │                                   │
       │                                │                                   │
       │ ◄─── {list:[id1,id2,...],      │                                   │
       │        nextToken:"xxx"} ────── │                                   │
       │                                │                                   │
       │ 如果 nextToken 不为空:          │                                   │
       │ 继续请求下一页 ────────────────► │                                   │
       │ ◄─── {list:[id3,...],           │                                   │
       │        nextToken:""} ────────── │                                   │
       │                                │                                   │
       │ ③ 遍历每个 processInstanceId    │                                   │
       │ GET /workflow/processInstances  │                                   │
       │   ?processInstanceId=xxx       │                                   │
       │──────────────────────────────► │                                   │
       │                                │                                   │
       │ ◄─── {title, status,           │                                   │
       │   formComponentValues:[...]} ─ │                                   │
       │                                │                                   │
       │ 解析 formComponentValues        │                                   │
       │ 找 DDAttachment → fileId       │                                   │
       │                                │                                   │
       │ ④ POST /spaces/files/urls/download                              │
       │ {processInstanceId, fileId}     │                                   │
       │──────────────────────────────► │                                   │
       │                                │                                   │
       │ ◄─── {downloadUri: "https://..."│                                  │
       │       } ─────────────────────  │                                   │
       │                                │                                   │
       │ ⑤ GET downloadUri (预签名URL)   │                                   │
       │──────────────────────────────► │                                   │
       │                                │                                   │
       │ ◄─── (binary file data) ────── │  │                                   │
       │                                │                                   │
       │ ⑥ 写入文件                                                          │
       │──────────────────────────────────────────────────────────────►    │
       │                                                                    │
       │ ./downloads/{instanceId}/{fileName}                                │
       │                                                                    │
       │ ✅ 完成（处理下一个审批或下一个附件）

═══════════════════════════════════════════════════════════════════

  简化流程 (6步，Streamlit Web界面):

  ① 启动Streamlit → 获取Token (缓存到session_state)
      │
      ▼
  ② 左侧边栏: 选择日期范围+状态 → 点击"查询" → 获取审批实例ID列表
      │
      ▼
  ③ 左侧边栏显示审批列表 → 用户点击选择
      │
      ▼
  ④ 主区域: 获取审批实例详情 → 展示基本信息+表单数据
      │
      ▼
  ⑤ 提取附件信息 → 展示附件列表+下载进度
      │
      ▼
  ⑥ 点击"下载所有附件" → 获取下载链接 → 下载到本地

  项目文件结构:
  ├── app.py              # Streamlit Web界面
  ├── dingtalk_api.py     # 钉钉API调用模块 (纯逻辑，无UI)
  ├── .env                # 凭证配置 (AppKey, AppSecret, ProcessCode)
  ├── .env.example        # 凭证模板
  ├── requirements.txt    # 依赖: requests, python-dotenv, streamlit
  ├── downloads/          # 附件下载目录
  └── .gitignore                                    │
```

---

## 凭证信息

| 参数 | 值 | 来源 |
|------|-----|------|
| AppKey | `dingwtlvjdradsgnn53l` | AppID.md |
| AppSecret | `fpMNocxcJLDckYv3T_a27n4yCXtmCtOoLJt9-ZW6BVknE8TTd0sHQtfTsVggpxoD` | AppID.md |
| AgentId | `4592859090` | AppID.md |
| processCode | `PROC-D868A57B-7939-4857-AAAB-0C8437487F7E` | ⭐ 用户提供的测试值，正式系统再调整 |

> ⚠️ processCode 当前为测试值，正式系统需在钉钉管理后台 → OA审批 → 审批模板管理中获取后更新 .env
> ⚠️ 凭证应存放在 `.env` 文件中，**不要硬编码到源码**