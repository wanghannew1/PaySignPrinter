# 钉钉审批打印工具 - 常见问题 (FAQ)

## Q1: 批量下载卡在"正在处理"，控制台报 403 Forbidden

**现象：**
```
获取下载链接失败: 403 Client Error: Forbidden
```

**原因：** 钉钉应用缺少必需的 API 权限。

**解决：** 在钉钉开放平台 → 应用权限管理 中开通：
- `Storage.DownloadInfo.Read` — 企业存储文件下载信息读权限
- `Workflow.Instance.Write` — 工作流实例写权限（下载附件必需）

**申请链接：** https://open-dev.dingtalk.com/appscope/apply

---

## Q2: .xls 文件签名插入失败，报"无效的类字符串"

**现象：**
```
xls转换失败: (-2147221005, '无效的类字符串', None, None)
```

**原因：** Windows COM 组件权限问题。WPS/Office 的 COM 注册表在**普通用户**会话中，但程序在**管理员权限**终端中运行时无法访问。

**解决：**
1. **不要用管理员权限启动终端**
2. 用普通用户身份打开 CMD/PowerShell
3. 再执行 `streamlit run app.py`

**注意：** 如果必须用管理员运行，需要确保 WPS/Office 也在同一权限上下文中注册 COM 组件（不推荐）。

---

## Q2b: .xls 文件签名插入失败，报"xlOpenXMLWorkbook"

**现象：**
```
xls转换失败: xlOpenXMLWorkbook
```

**原因：** WPS 的 COM 接口不支持 `constants.xlOpenXMLWorkbook` 常量名。WPS 和 Microsoft Excel 的 COM 常量不完全兼容。

**解决：** 已修复。代码使用数值 `51` 代替常量名：
```python
# 修改前（WPS报错）
wb.SaveAs(..., FileFormat=constants.xlOpenXMLWorkbook)

# 修改后（WPS兼容）
wb.SaveAs(..., FileFormat=51)  # 51 = xlsx格式码
```

如果 `51` 也失败，会自动 fallback 到不带 FileFormat 参数的保存方式。

---

## Q3: 提示"未找到可签名的审批角色"

**现象：**
```
未找到可签名的审批角色
```

**原因：** 钉钉返回的审批角色 `showName` 格式变化，和代码中的映射表不匹配。

**解决：**
1. 编辑 `role_mapping.json` 配置文件
2. 添加钉钉实际返回的角色名映射

**示例：**
```json
{
  "财务审核": "财务审核",
  "总经理签字": "总经理签字",
  "部长签字": "部长签字"
}
```

---

## Q4: 签名图片和提示词重叠

**现象：** 签名图片遮挡了 Excel 中的提示文字。

**原因：** 旧版本使用固定偏移（`col + 2`），没有考虑合并单元格和文字长度。

**解决：** 已修复。程序现在会：
1. 检测合并单元格
2. 拆分合并区域为文字刚好容纳的宽度
3. 在文字右侧紧贴位置插入签名

**注意：** `.xls` 格式需转换为 `.xlsx` 后才能使用此功能。

---

## Q5: 下载路径如何修改？

**解决：** 在 Streamlit 侧边栏的"⚙️ 下载设置"中修改，修改后会自动保存到 `settings.json`。

---

## Q6: API 调用量有多少？每月 5000 次够吗？

**估算（200 条审批，每条 2 个附件）：**

| 操作 | 调用次数 |
|------|---------|
| 首次查询 | 201 次（1 列表 + 200 详情） |
| 同条件再次查询 | 0 次（全部命中缓存） |
| 下载 10 个附件 | 20 次（10 URL + 10 下载） |

**省流技巧：**
- 查询结果自动缓存，再次查询 0 API 调用
- 下载 URL 15 分钟内可复用

---

## Q7: 签名位置找到了，但签名后文件里没有签名图片

**现象：**
日志显示：
```
[SIGN] Found positions: {'总经理签字': (18, 1), ...}
[SIGN] Signature image not found for user 285843661939115798
[SIGN] Saved to signed_xxx.xlsx, inserted: []
```

**原因：** `./signatures/` 目录中没有对应的签名图片文件。

**解决：**
1. 准备审批人的签名图片（PNG 格式，透明背景最佳）
2. 将图片放入 `./signatures/` 目录
3. 图片文件名必须是 `userId.png`，例如 `285843661939115798.png`

**如何获取 userId：**
- 在审批详情页查看审批人信息
- 或者从钉钉通讯录导出获取

---

## Q8: 汇总表（xlsx）没有插入签名

**现象：**
```
[SIGN] Found positions: {}
[SIGN] No signature positions found in 汇总表.xlsx
```

**原因：** 汇总表通常没有"总经理签字"、"部长签字"等提示词，只有工资数据汇总，所以程序找不到签名位置。

**解决：** 这是预期行为。汇总表不需要签名，只有各单位的明细表才需要。如果汇总表也需要签名，请在 Excel 中手动添加提示词单元格。

---

## Q7: 列宽正常但打印时某列"不见了"，WPS 里拖滚动条也看不到

**现象：**
- 代码理论只隐藏了 D/E/F 列（部门、岗位、职工号）
- 但 G 列（基本工资）也看不见，拖动滚动条也找不到
- 实际列宽正常（13.0），`hidden=False`
- 用 raw XML 检查发现 `<col min="4" max="7" hidden="1"/>`，D-G 四列被合并隐藏

**原因：openpyxl 列节点合并 bug**

openpyxl 在保存文件时，会把**连续的、属性相同的列**合并成一个 XML 节点：

```xml
<!-- 代码意图：只隐藏 D(4)、E(5)、F(6) -->
<!-- openpyxl 保存结果：D-G(4-7) 合并成一组全部隐藏 -->
<col min="4" max="7" hidden="1"/>
```

当你隐藏 D、E、F 三列时，openpyxl 创建 `<col min=4 max=6 hidden=1/>`。但如果 G 列（7）没有**独立的** `<col>` 节点，openpyxl 会把范围扩展到 4-7，导致 G 列被**连带隐藏**。

这是 openpyxl 的一个已知设计行为：`ColumnDimensionHolder` 自动合并连续的 `col` 节点以减小 XML 体积，但不会为未显式设置属性的中间列创建独立节点。

**解决：**

在 `batch_processor.py` 的 `_hide_columns()` 中，**对所有列**都显式读写 `hidden` 属性：

```python
def _hide_columns(ws):
    headers_to_hide = {"部门", "岗位", "职工号"}
    header_row = 3
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=header_row, column=col)
        col_letter = cell.column_letter
        hidden = ws.column_dimensions[col_letter].hidden  # 读原始状态
        if cell.value and str(cell.value).strip() in headers_to_hide:
            hidden = True  # 匹配的列设为隐藏
        ws.column_dimensions[col_letter].hidden = hidden  # 显式写回
```

关键：**每列都需要显式写一次 `hidden`**——即使是 `False`。这样 openpyxl 就会为每列生成独立的 `<col>` 节点，不会合并。

**相关 Commit：** `2211216` - fix: prevent openpyxl from merging hidden columns into groups

---

*最后更新：2026-06-10*
