# 钉钉审批打印工具 - API 接口文档

本文档列出本工具在下载审批附件流程中调用的所有钉钉 API 接口。

---

## 1. 获取 AccessToken

**接口：** `POST /v1.0/oauth2/accessToken`

**用途：** 获取访问令牌，所有后续 API 调用都需要在 Header 中携带此 token。

**代码位置：** `dingtalk_api.py:get_access_token()`

**请求参数：**
```json
{
  "appKey": "你的AppKey",
  "appSecret": "你的AppSecret"
}
```

**返回值：**
```json
{
  "expireIn": 7200,
  "accessToken": "xxx"
}
```

**调用时机：**
- 应用启动时自动获取
- Token 过期前自动刷新（有效期 7200 秒）

**缓存：** 存储在 `st.session_state.access_token` 中，有效期内复用。

**权限要求：** 无（应用级接口，不需要单独授权）

---

## 2. 查询审批实例 ID 列表

**接口：** `POST /v1.0/workflow/processes/instanceIds/query`

**用途：** 按日期范围和审批状态查询符合条件的审批实例 ID 列表。

**代码位置：** `dingtalk_api.py:get_instance_id_list()`

**请求参数：**
```json
{
  "processCode": "PROC-xxx",
  "startTime": 1700000000000,
  "endTime": 1700000000001,
  "nextToken": 0,
  "maxResults": 20,
  "statuses": ["COMPLETED"]
}
```

**返回值：**
```json
{
  "result": {
    "list": ["instanceId1", "instanceId2"],
    "nextToken": "xxx"
  }
}
```

**调用时机：**
- 用户在侧边栏点击"查询"按钮时触发
- 首次查询（冷缓存）时调用

**缓存：** 查询结果按 `(startTime, endTime, statuses)` 作为 key 缓存到 `approval_cache.json`，有效期内（直到重新查询）复用。

**权限要求：**
- `oa_approval` — OA审批权限
- `workflow` — 工作流权限

---

## 3. 获取单个审批实例详情

**接口：** `GET /v1.0/workflow/processInstances`

**用途：** 获取审批实例的完整详情，包括表单数据、附件信息、审批流程记录等。

**代码位置：** `dingtalk_api.py:get_instance_details()`

**请求参数：**
```
GET /v1.0/workflow/processInstances?processInstanceId=xxx
```

**Header：**
```
x-acs-dingtalk-access-token: xxx
```

**返回值：**
```json
{
  "result": {
    "businessId": "PAY-2025-001",
    "title": "工资审批",
    "status": "COMPLETED",
    "formComponentValues": [...],
    "operationRecords": [...]
  }
}
```

**调用时机：**
- 查询列表后，加载每条审批的基本信息（businessId, title, status 等）
- 用户点击某条审批查看详情时
- 批量下载前获取附件列表

**缓存：** 按 `instanceId` 缓存到 `approval_cache.json`，永久有效（审批一旦完结不会变化）。

**权限要求：**
- `oa_approval` — OA审批权限
- `Workflow.Instance.Read` — 工作流实例读权限

---

## 4. 获取附件下载链接

**接口：** `POST /v1.0/workflow/processInstances/spaces/files/urls/download`

**用途：** 获取审批附件的临时下载 URL（有效期 15 分钟）。

**代码位置：** `dingtalk_api.py:get_download_url()`

**请求参数：**
```json
{
  "processInstanceId": "xxx",
  "fileId": "xxx",
  "withCommentAttatchment": false
}
```

**返回值：**
```json
{
  "result": {
    "downloadUri": "https://xxx"  // 或 "#zifgs09xxxxx.file"（需重命名）
  }
}
```

**调用时机：**
- 用户点击下载按钮时
- 批量下载时逐个获取附件的下载 URL

**缓存：** 按 `(instanceId, fileId)` 缓存到 `approval_cache.json`，有效期 15 分钟。

**权限要求：**
- `Storage.DownloadInfo.Read` — 企业存储文件下载信息读权限
- `Workflow.Instance.Write` — 工作流实例写权限（必须）

---

## 5. 下载附件文件

**接口：** `GET {downloadUri}`

**用途：** 从步骤 4 获取的 URL 下载实际的文件内容。

**代码位置：** `dingtalk_api.py:download_file_bytes()`

**请求参数：**
```
GET https://xxx/download  (15分钟内有效)
```

**返回值：** 文件二进制内容

**调用时机：**
- 获取下载 URL 后立即调用
- 批量下载时逐个下载文件

**缓存：** 无（文件内容不缓存，每次都重新下载）。

**权限要求：** 无（直接 HTTP GET，不经过钉钉鉴权）。

---

## 完整调用链

```
启动应用
  └── get_access_token()           (1) POST /v1.0/oauth2/accessToken

点击"查询"
  ├── get_instance_id_list()       (2) POST /v1.0/workflow/processes/instanceIds/query
  │     └── 遍历每个 instanceId:
  │         └── get_instance_details()   (3) GET /v1.0/workflow/processInstances

查看审批详情
  └── get_instance_details()       (3) GET /v1.0/workflow/processInstances
        └── extract_attachments()  (本地解析，无API调用)

下载单个附件
  ├── get_download_url()           (4) POST /v1.0/workflow/processInstances/spaces/files/urls/download
  └── download_file_bytes()      (5) GET {downloadUri}

批量下载
  ├── get_instance_details()       (3) 缓存命中则跳过
  ├── get_download_url()           (4) 缓存命中则跳过
  └── download_file_bytes()      (5) 逐个下载文件
      └── insert_signature_to_excel()  (本地处理，无API调用)
```

---

## 缓存策略总结

| 接口 | 缓存 key | 有效期 | 说明 |
|------|---------|--------|------|
| get_access_token | session_state | 7000秒 | 自动刷新 |
| get_instance_id_list | (start, end, statuses) | 永久 | 直到重新查询 |
| get_instance_details | instanceId | 永久 | 审批完结后不变 |
| get_download_url | (instanceId, fileId) | 15分钟 | URL 本身 15 分钟过期 |
| download_file_bytes | 无 | — | 每次都下载 |

---

## 权限开通清单

在钉钉开放平台 → 应用管理 → 权限管理 中，确保已开启：

| 权限名称 | 接口对应 | 说明 |
|----------|---------|------|
| `oa_approval` | (2)(3) | OA审批权限 |
| `workflow` | (2) | 工作流权限 |
| `Workflow.Instance.Read` | (3) | 工作流实例读权限 |
| `Workflow.Instance.Write` | (4) | 工作流实例写权限（下载附件必需） |
| `Storage.DownloadInfo.Read` | (4) | 企业存储文件下载信息读权限 |

**常见问题：**
- 403 Forbidden → 缺少 `Storage.DownloadInfo.Read` 或 `Workflow.Instance.Write` 权限
- 401 Unauthorized → Token 过期或无效
- 400 Bad Request → 请求参数错误（如日期范围超过 120 天）

---

## API 调用量估算

以查询 200 条审批、每条 2 个附件为例：

| 阶段 | 调用次数 | 说明 |
|------|---------|------|
| 首次查询 | 1 + 200 = 201 次 | 1 次列表 + 200 次详情 |
| 同条件再次查询 | 0 次 | 全部命中缓存 |
| 下载 10 个附件 | 10 次 (4) + 10 次 (5) = 20 次 | 缓存有效期内 (4) 可省 |
| 合计（首次全流程） | ~221 次 | 建议控制在每月 5000 次以内 |

**省流技巧：**
- 善用本地缓存，避免重复查询
- 批量下载时复用已缓存的详情和下载 URL
- 下载 URL 15 分钟内可复用

---

*文档版本：2026-06-08*
*适用代码版本：db6afd0 及之后*
