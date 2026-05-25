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


def get_final_approver(details: dict) -> Optional[str]:
    """Get the last approver who agreed."""
    records = details.get("operationRecords", [])
    final_approver = None
    for record in records:
        if record.get("type") in ("EXECUTE_TASK_NORMAL", "EXECUTE_TASK_TRANSFER"):
            if record.get("result") == "AGREE":
                final_approver = record.get("userId")
    return final_approver


def find_signature_image(user_id: str, signatures_dir: Path) -> Optional[Path]:
    """Find signature image for a user."""
    if not user_id:
        return None
    # Try exact match first
    sig_path = signatures_dir / f"{user_id}.png"
    if sig_path.exists():
        return sig_path
    # Try all PNG files (fallback)
    for f in signatures_dir.glob("*.png"):
        if user_id in f.name:
            return f
    return None


def download_attachment(
    instance_id: str,
    file_id: str,
    file_name: str,
    token: str,
    output_dir: Path,
    dingtalk_api_module,
) -> Optional[Path]:
    """Download a single attachment."""
    try:
        download_url, needs_rename = dingtalk_api_module.get_download_url(
            instance_id, file_id, token
        )
        saved = dingtalk_api_module.download_file(
            download_url,
            file_name,
            str(output_dir),
            instance_id,
            needs_rename=needs_rename,
            original_file_type="",
        )
        return Path(saved) if saved else None
    except Exception:
        return None


def find_signature_cell(ws) -> Optional[Tuple[int, int]]:
    signature_keywords = ["总经理签字", "负责人签字", "审批签字", "签字", "签名"]

    for row in range(1, ws.max_row + 1):
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=row, column=col)
            if cell.value:
                value = str(cell.value).strip()
                for keyword in signature_keywords:
                    if keyword in value:
                        return (row, col)
    return None


def insert_signature_to_excel(
    excel_path: Path,
    signature_path: Path,
    output_path: Path,
) -> bool:
    """Insert signature image into Excel at the signature row."""
    try:
        wb = load_workbook(str(excel_path))
        ws = wb.active

        # Find signature cell
        sig_cell = find_signature_cell(ws)

        if sig_cell:
            target_row, target_col = sig_cell
            # Place signature in the next column to the right
            target_col += 1
        else:
            # Fallback: use last row, first column
            target_row = ws.max_row
            target_col = 1

        # Insert image
        img = XLImage(str(signature_path))
        img.width = 120
        img.height = 60
        cell_addr = f"{ws.cell(row=target_row, column=target_col).coordinate}"
        ws.add_image(img, cell_addr)

        wb.save(str(output_path))
        return True
    except Exception as e:
        print(f"插入签名失败: {e}")
        return False


def print_file(file_path: Path, printer_name: Optional[str] = None) -> bool:
    """Print file using LibreOffice."""
    try:
        if file_path.suffix.lower() in (".xlsx", ".xls", ".docx", ".doc"):
            # Use LibreOffice to print
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
            # Use lpr for PDF
            cmd = ["lpr", str(file_path)]
            if printer_name:
                cmd.extend(["-P", printer_name])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        return False
    except Exception as e:
        print(f"打印失败: {e}")
        return False


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
    }

    try:
        details = dingtalk_api_module.get_instance_details(instance_id, token)
    except Exception as e:
        result["message"] = f"获取详情失败: {e}"
        return result

    # Check approval status
    passed, msg = is_approval_passed(details)
    if not passed:
        result["skipped"] = True
        result["message"] = msg
        return result

    # Get final approver
    approver_id = get_final_approver(details)
    if not approver_id:
        result["message"] = "无法确定审批人"
        return result

    # Find signature
    sig_path = find_signature_image(approver_id, signatures_dir)
    if not sig_path:
        result["message"] = f"未找到审批人 {approver_id} 的签名图片"
        return result

    # Get attachments
    form_values = details.get("formComponentValues", [])
    attachments = dingtalk_api_module.extract_attachments(form_values)

    if not attachments:
        result["message"] = "无附件"
        return result

    # Create output directory for this instance
    instance_dir = output_base_dir / instance_id
    instance_dir.mkdir(parents=True, exist_ok=True)

    # Process each attachment
    for att in attachments:
        file_id = att.get("fileId")
        file_name = att.get("fileName", "unknown")
        file_type = att.get("fileType", "")

        # Download
        downloaded = download_attachment(
            instance_id,
            file_id,
            file_name,
            token,
            instance_dir,
            dingtalk_api_module,
        )
        if not downloaded:
            continue

        result["downloaded"].append(file_name)

        # If Excel, insert signature
        if file_type in ("xlsx", "xls") or downloaded.suffix in (".xlsx", ".xls"):
            signed_path = instance_dir / f"signed_{file_name}"
            if insert_signature_to_excel(downloaded, sig_path, signed_path):
                result["signed"].append(file_name)
                # Print signed file
                if print_file(signed_path):
                    result["printed"].append(file_name)
            else:
                # Try printing original if signing failed
                if print_file(downloaded):
                    result["printed"].append(file_name)
        else:
            # Print non-Excel files directly
            if print_file(downloaded):
                result["printed"].append(file_name)

    result["success"] = True
    result["message"] = (
        f"下载 {len(result['downloaded'])} 个, "
        f"签名 {len(result['signed'])} 个, "
        f"打印 {len(result['printed'])} 个"
    )
    return result
