"""
Batch processing module for DingTalk approval attachments.
Handles: download, signature insertion, and printing.
"""

import json
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage

import cache_manager


# Mapping from approval role showName to Excel signature position keyword
ROLE_TO_SIGNATURE_KEYWORD = {
    "五险一金": "业务审核",
    "部门负责人": "部长签字",
    "财务": "财务审核",
    "总经理": "总经理签字",
}


def get_approver_role(show_name: str) -> Optional[str]:
    """Map approver showName to signature keyword."""
    show_name_lower = show_name.lower()
    for role_keyword, sig_keyword in ROLE_TO_SIGNATURE_KEYWORD.items():
        if role_keyword in show_name_lower:
            return sig_keyword
    return None


def is_approval_passed(details: dict) -> Tuple[bool, str]:
    """Check if approval is passed (all required approvers agreed)."""
    records = details.get("operationRecords", [])
    for record in records:
        if record.get("type") in ("EXECUTE_TASK_NORMAL", "EXECUTE_TASK_TRANSFER"):
            result = record.get("result", "NONE")
            if result == "REFUSE":
                return False, f"审批被拒绝: {record.get('showName', '')}"
            elif result == "BACK":
                return False, f"审批被退回: {record.get('showName', '')}"
    return True, "审批通过"


def get_approvers_with_roles(details: dict) -> List[Dict]:
    """Get all approvers who agreed, with their roles."""
    records = details.get("operationRecords", [])
    approvers = []
    for record in records:
        if record.get("type") in ("EXECUTE_TASK_NORMAL", "EXECUTE_TASK_TRANSFER"):
            if record.get("result") == "AGREE":
                show_name = record.get("showName", "")
                role = get_approver_role(show_name)
                if role:
                    approvers.append({
                        "userId": record.get("userId"),
                        "showName": show_name,
                        "role": role,
                    })
    return approvers


def find_signature_image(user_id: str, signatures_dir: Path) -> Optional[Path]:
    """Find signature image for a user."""
    if not user_id:
        return None
    sig_path = signatures_dir / f"{user_id}.png"
    if sig_path.exists():
        return sig_path
    for f in signatures_dir.glob("*.png"):
        if user_id in f.name:
            return f
    return None


def _is_cell_in_merged_range(ws, row, col):
    for merged_range in ws.merged_cells.ranges:
        if (merged_range.min_row <= row <= merged_range.max_row and
                merged_range.min_col <= col <= merged_range.max_col):
            return merged_range
    return None


def _estimate_text_span(text, col_width):
    if not col_width or col_width == 0:
        col_width = 8.43
    width = sum(2 if '\u4e00' <= c <= '\u9fff' else 1 for c in str(text))
    return width / col_width


def _split_merged_for_text(ws, row, col):
    from openpyxl.utils import get_column_letter

    merged = _is_cell_in_merged_range(ws, row, col)
    if not merged:
        return col + 2

    text = str(ws.cell(row=row, column=col).value) if ws.cell(row=row, column=col).value else ""

    def get_width(c):
        letter = get_column_letter(c)
        dim = ws.column_dimensions.get(letter)
        return dim.width if dim and dim.width else 8.43

    total_cols = merged.max_col - merged.min_col + 1
    total_width = sum(get_width(c) for c in range(merged.min_col, merged.max_col + 1))
    text_span = _estimate_text_span(text, total_width)
    needed_cols = min(max(1, int(text_span) + 1), total_cols)

    if needed_cols >= total_cols:
        return merged.max_col + 1

    merged_str = str(merged)
    ws.unmerge_cells(merged_str)

    new_end = merged.min_col + needed_cols - 1
    if new_end > merged.min_col:
        ws.merge_cells(start_row=row, start_column=merged.min_col,
                       end_row=row, end_column=new_end)

    for c in range(new_end + 1, merged.max_col + 1):
        ws.cell(row=row, column=c).value = None

    return new_end + 1


def find_all_signature_positions(ws) -> Dict[str, Tuple[int, int]]:
    """Find all signature positions in the worksheet."""
    positions = {}
    keyword_groups = [
        (["总经理签字"], "总经理签字"),
        (["部长签字", "部长、分管副总签字", "分管副总签字"], "部长签字"),
        (["财务审核"], "财务审核"),
        (["业务审核"], "业务审核"),
    ]

    for row in range(1, ws.max_row + 1):
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=row, column=col)
            if cell.value:
                value = str(cell.value).strip()
                for texts, role_key in keyword_groups:
                    if role_key not in positions:
                        for text in texts:
                            if text in value:
                                positions[role_key] = (row, col)
                                break
    return positions


def _insert_signature_to_excel_openpyxl(
    excel_path: Path,
    approvers: List[Dict],
    signatures_dir: Path,
    output_path: Path,
) -> Tuple[bool, List[str]]:
    inserted_roles = []
    try:
        wb = load_workbook(str(excel_path))
        ws = wb.active

        positions = find_all_signature_positions(ws)
        if not positions:
            return False, []

        for approver in approvers:
            role = approver.get("role")
            user_id = approver.get("userId")
            if not role or not user_id:
                continue

            if role not in positions:
                continue

            sig_path = find_signature_image(user_id, signatures_dir)
            if not sig_path:
                continue

            row, col = positions[role]
            target_col = _split_merged_for_text(ws, row, col)

            img = XLImage(str(sig_path))
            img.width = 120
            img.height = 60
            cell_addr = f"{ws.cell(row=row, column=target_col).coordinate}"
            ws.add_image(img, cell_addr)
            inserted_roles.append(role)

        wb.save(str(output_path))
        return len(inserted_roles) > 0, inserted_roles
    except Exception as e:
        print(f"插入签名失败: {e}")
        return False, []


def _convert_xls_to_xlsx_windows(xls_path: Path) -> Optional[Path]:
    try:
        import pythoncom
        import win32com.client
        from win32com.client import constants
    except ImportError:
        print("转换xls需要 pywin32: pip install pywin32")
        return None

    pythoncom.CoInitialize()
    excel = None
    wb = None

    try:
        xlsx_path = xls_path.with_suffix(".xlsx")
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        wb = excel.Workbooks.Open(str(xls_path.resolve()))
        wb.SaveAs(str(xlsx_path.resolve()), FileFormat=constants.xlOpenXMLWorkbook)
        wb.Close(SaveChanges=False)
        excel.Quit()

        return xlsx_path
    except Exception as e:
        print(f"xls转换失败: {e}")
        return None
    finally:
        try:
            if wb:
                wb.Close(SaveChanges=False)
            if excel:
                excel.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def _insert_signature_to_excel_windows(
    excel_path: Path,
    approvers: List[Dict],
    signatures_dir: Path,
    output_path: Path,
) -> Tuple[bool, List[str]]:
    xlsx_path = _convert_xls_to_xlsx_windows(excel_path)
    if xlsx_path is None:
        return False, []

    try:
        result = _insert_signature_to_excel_openpyxl(
            xlsx_path, approvers, signatures_dir, output_path
        )
        return result
    finally:
        try:
            xlsx_path.unlink()
        except Exception:
            pass


def insert_signature_to_excel(
    excel_path: Path,
    approvers: List[Dict],
    signatures_dir: Path,
    output_path: Path,
) -> Tuple[bool, List[str]]:
    ext = excel_path.suffix.lower()
    if platform.system() == "Windows" and ext == ".xls":
        return _insert_signature_to_excel_windows(
            excel_path, approvers, signatures_dir, output_path
        )
    return _insert_signature_to_excel_openpyxl(
        excel_path, approvers, signatures_dir, output_path
    )


def print_file(file_path: Path, printer_name: Optional[str] = None) -> bool:
    """Print file using LibreOffice."""
    try:
        if file_path.suffix.lower() in (".xlsx", ".xls", ".docx", ".doc"):
            cmd = [
                "libreoffice",
                "--headless",
                "--print",
                str(file_path),
            ]
            if printer_name:
                cmd.extend(["--printer", printer_name])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        elif file_path.suffix.lower() == ".pdf":
            cmd = ["lpr", str(file_path)]
            if printer_name:
                cmd.extend(["-P", printer_name])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        return False
    except Exception as e:
        print(f"打印失败: {e}")
        return False


def sanitize_dir_name(name: str) -> str:
    """Sanitize string for use as directory name."""
    invalid_chars = '\\/:*?"<>|'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip()


def process_single_approval(
    instance_id: str,
    token: str,
    signatures_dir: Path,
    output_base_dir: Path,
    dingtalk_api_module,
) -> dict:
    """Process a single approval: download, sign, print."""
    result = {
        "instance_id": instance_id,
        "success": False,
        "message": "",
        "downloaded": [],
        "signed": [],
        "printed": [],
        "skipped": False,
        "title": "",
    }

    try:
        details = cache_manager.get_cached_instance_details(instance_id)
        if details is None:
            details = dingtalk_api_module.get_instance_details(instance_id, token)
            cache_manager.cache_instance_details(instance_id, details)
    except Exception as e:
        result["message"] = f"获取详情失败: {e}"
        return result

    business_id = details.get("businessId", instance_id[:20])
    result["business_id"] = business_id

    passed, msg = is_approval_passed(details)
    if not passed:
        result["skipped"] = True
        result["message"] = msg
        return result

    approvers = get_approvers_with_roles(details)
    if not approvers:
        result["message"] = "未找到可签名的审批角色"
        return result

    form_values = details.get("formComponentValues", [])
    attachments = dingtalk_api_module.extract_attachments(form_values)

    if not attachments:
        result["message"] = "无附件"
        return result

    instance_dir = output_base_dir / sanitize_dir_name(business_id)
    instance_dir.mkdir(parents=True, exist_ok=True)

    for att in attachments:
        file_id = att.get("fileId")
        file_name = att.get("fileName", "unknown")
        file_type = att.get("fileType", "")

        try:
            download_url = cache_manager.get_cached_download_url(instance_id, file_id)
            if download_url is None:
                download_url, needs_rename = dingtalk_api_module.get_download_url(
                    instance_id, file_id, token
                )
                cache_manager.cache_download_url(instance_id, file_id, download_url)
            file_bytes = dingtalk_api_module.download_file_bytes(download_url)

            # Save to instance dir directly (no nested subdir)
            safe_name = sanitize_dir_name(file_name)
            file_path = instance_dir / safe_name
            counter = 1
            while file_path.exists():
                stem = Path(safe_name).stem
                suffix = Path(safe_name).suffix
                file_path = instance_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            with open(file_path, "wb") as f:
                f.write(file_bytes)

            result["downloaded"].append(file_name)

            # If Excel, insert signatures
            if file_type in ("xlsx", "xls") or file_path.suffix in (".xlsx", ".xls"):
                signed_name = f"signed_{file_path.stem}.xlsx"
                signed_path = instance_dir / signed_name
                success, inserted = insert_signature_to_excel(
                    file_path, approvers, signatures_dir, signed_path
                )
                if success:
                    result["signed"].extend(inserted)
                    # Print disabled - uncomment when needed
                    # if print_file(signed_path):
                    #     result["printed"].append(file_name)
                else:
                    pass
                    # Print disabled - uncomment when needed
                    # if print_file(file_path):
                    #     result["printed"].append(file_name)
            else:
                pass
                # Print disabled - uncomment when needed
                # if print_file(file_path):
                #     result["printed"].append(file_name)

        except Exception:
            continue

    result["success"] = True
    result["message"] = (
        f"下载 {len(result['downloaded'])} 个, "
        f"签名 {len(result['signed'])} 处"
    )
    return result
