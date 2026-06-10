# openpyxl 的一个隐蔽陷阱：为什么隐藏 D 列，G 列也跟着消失了？

> 用 openpyxl 处理 Excel 的打印功能时，隐藏了三列，结果第四列也"凭空消失"了——WPS 里怎么拖动都找不到。排查了一下午，最终在 raw XML 里发现了 openpyxl 自动合并列定义的"设计行为"。

---

## 问题：藏三列，丢四列

需求很简单：处理工资表时，把"部门"、"岗位"、"职工号"三列隐藏，不参与打印。

代码写得很直接：

```python
def _hide_columns(ws):
    headers_to_hide = {"部门", "岗位", "职工号"}
    header_row = 3
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=header_row, column=col)
        if cell.value and str(cell.value).strip() in headers_to_hide:
            ws.column_dimensions[cell.column_letter].hidden = True
```

逻辑没有任何问题：找到第 3 行列头匹配的三个字符串，对应的 D、E、F 列设 `hidden=True`，保存。

然后用 WPS 打开处理后的文件，傻眼了：

| 列 | 预期 | 实际 |
|---|---|---|
| D（部门） | 隐藏 ✅ | 隐藏 ✅ |
| E（岗位） | 隐藏 ✅ | 隐藏 ✅ |
| F（职工号） | 隐藏 ✅ | 隐藏 ✅ |
| G（基本工资） | **显示** | **看不见了** ❌ |
| H（交通补贴） | 隐藏 ✅ | 隐藏 ✅ |

G 列（基本工资）——直接"蒸发了"。列宽写着 13.0，不是 0；`hidden` 属性是 `False`，不是 `True`。但 WPS 里从 C 列直接跳到 I 列，中间没有 G 列的任何痕迹。拖动水平滚动条也找不到。

## 排查：openpyxl 说 G 没隐藏，那谁藏了？

先确认 openpyxl 读取到的属性：

```python
ws.column_dimensions['G'].hidden   # → False
ws.column_dimensions['G'].width    # → 13.0
```

openpyxl 说 G 列没隐藏。那问题一定在**保存后的文件**里。

再用 Python 直接读 raw XML（.xlsx 本质上是一个 zip 包）：

```python
import zipfile
from lxml import etree

with zipfile.ZipFile('signed_xxx.xlsx') as z:
    with z.open('xl/worksheets/sheet1.xml') as sheet:
        tree = etree.parse(sheet)
        root = tree.getroot()

for col in root.findall('.//{http://schemas.openxmlformats.org/...}col'):
    if col.get('hidden') == '1':
        print(f"HIDDEN: min={col.get('min')} max={col.get('max')}")
```

输出：

```
HIDDEN: min=4 max=7 width=11.140625
HIDDEN: min=5 max=5 width=13
HIDDEN: min=6 max=6 width=13
HIDDEN: min=8 max=8 width=default
```

**破案了**：`min=4 max=7` 意思是**第 4 列到第 7 列（D-G）全部隐藏**。

这不是我的代码写的！我明确只设了 D、E、F 的 `hidden=True`，但保存后的 XML 里出现了一个 `col 4-7 hidden=1` 的节点，把 G 列也打包带走了。

## 根因：openpyxl 的"列节点合并"

在 OOXML 规范中，连续且属性相同的列可以合并成一个 `<col>` 节点，用 `min` 和 `max` 来表示范围。openpyxl 的 `ColumnDimensionHolder` 在保存时会自动执行这个合并逻辑。

**合并的条件**：连续列中，只要某一列没有**独立的** `<col>` 节点定义，它就会**继承并扩展相邻节点的范围**。

具体到这个场景：
1. 原始文件中 D 列（第 4 列）已经是 `hidden=True`（模板自带）
2. 我的代码把 E（第 5 列）设为 `hidden=True`
3. 我的代码把 F（第 6 列）设为 `hidden=True`
4. G 列（第 7 列）——**没有显式写入任何 `hidden` 属性**
5. openpyxl 保存时：4、5、6 三列都是 `hidden=True`，属性相同，合并为 `col 4-6 hidden=1`
6. G 列（第 7 列）没有独立节点，被"顺延"进了合并范围，变成 `col 4-7 hidden=1`

**本质**：不是 openpyxl 把 G 列设成了隐藏，而是 openpyxl 在生成 XML 时，因为 G 没有独立节点而把 D-G 作为一个组，整个组被标为 `hidden=1`。

## 修复：给每一列"身份证"

解决方法非常直接：**所有列都显式写一次 `hidden`**，不管它是 True 还是 False。这样每一列都会生成独立的 `<col>` 节点，openpyxl 就不会合并了。

```python
def _hide_columns(ws):
    headers_to_hide = {"部门", "岗位", "职工号"}
    header_row = 3
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=header_row, column=col)
        col_letter = cell.column_letter
        hidden = ws.column_dimensions[col_letter].hidden  # 先读原始状态
        if cell.value and str(cell.value).strip() in headers_to_hide:
            hidden = True   # 需要隐藏的列
        ws.column_dimensions[col_letter].hidden = hidden   # 显式写回
```

改之前的逻辑是"只写匹配的列"（3 个赋值），改之后是"每列都写"（30 个赋值）。差别就在这一行：`ws.column_dimensions[col_letter].hidden = hidden` 哪怕 `hidden=False` 也写。这迫使 openpyxl 为 G 列生成 `<col min=7 max=7 hidden=0/>`，从而拆散了 4-7 的合并组。

修复后的 XML：

```xml
<col min=4 max=4 hidden=1/>   <!-- D: 部门，隐藏 -->
<col min=5 max=5 hidden=1/>   <!-- E: 岗位，隐藏 -->
<col min=6 max=6 hidden=1/>   <!-- F: 职工号，隐藏 -->
<col min=7 max=7 hidden=0/>   <!-- G: 基本工资，显示 ✅ -->
<col min=8 max=8 hidden=1/>   <!-- H: 交通补贴，隐藏 -->
```

每一列都独立存在，不再有合并范围的连带隐藏。

## 启示

1. **openpyxl 读取的属性 ≠ XML 中实际存储的值**。openpyxl 会做很多"智能"处理——合并节点、继承属性、默认值填充——导致你在 Python 里看到的值和文件中存的可能根本不是同一件事。

2. **出问题时，直接读 raw XML**。别只看 `ws.column_dimensions['G'].hidden`，去解压 .xlsx 看 `sheet1.xml`，真相永远在那里。

3. **"不写"不等于"默认值"**。在 openpyxl 的列定义中，不写 `hidden` 属性可能意味着"继承相邻组的属性"，而不是"默认为 False"。防御性编程在这儿很管用——该显式写的属性都写上。

4. **这其实是 OOXML 规范的设计行为**，不是 openpyxl 的 bug。openpyxl 仓库的 Issue #1988（"hides two columns instead of 1"）和 #1711 都讨论过相关问题，根源在于 Excel 本身也这样合并列节点。

---

*如果你也遇到过 openpyxl 各种"反直觉"的列操作问题，欢迎去 [Heptapod Issue #1988](https://foss.heptapod.net/openpyxl/openpyxl/-/issues/1988) 追加案例。*
