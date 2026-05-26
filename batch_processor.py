"""
Batch processing module for DingTalk approval attachments.
Handles: download, signature insertion, and printing.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage


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


def find_all_signature_positions(ws) -> Dict[str, Tuple[int, int]]:
    """Find all signature positions in the worksheet."""
    positions = {}
    keywords = ["总经理签字", "部长签字", "财务审核", "业务审核"]

    for row in range(1, ws.max_row + 1):
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=row, column=col)
            if cell.value:
                value = str(cell.value).strip()
                for keyword in keywords:
                    if keyword in value and keyword not in positions:
                        positions[keyword] = (row, col)
    return positions


def insert_signature_to_excel(
    excel_path: Path,
    approvers: List[Dict],
    signatures_dir: Path,
    output_path: Path,
) -> Tuple[bool, List[str]]:
    """Insert multiple signatures into Excel at correct positions."""
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
            target_col = col + 2

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
        details = dingtalk_api_module.get_instance_details(instance_id, token)
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
            download_url, needs_rename = dingtalk_api_module.get_download_url(
                instance_id, file_id, token
            )
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
                signed_path = instance_dir / f"signed_{file_path.name}"
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
