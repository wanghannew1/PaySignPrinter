"""DingTalk API module for PaySignPrinter."""
import os
import json
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load .env on module import
load_dotenv()

DINGTALK_BASE_URL = "https://api.dingtalk.com/v1.0"


def load_env():
    """Load credentials from .env file."""
    app_key = os.getenv("DINGTALK_APP_KEY")
    app_secret = os.getenv("DINGTALK_APP_SECRET")
    agent_id = os.getenv("DINGTALK_AGENT_ID")
    process_code = os.getenv("DINGTALK_PROCESS_CODE")

    if not all([app_key, app_secret, agent_id, process_code]):
        raise SystemExit("缺少钉钉应用凭证，请检查 .env 文件")

    return {
        "app_key": app_key,
        "app_secret": app_secret,
        "agent_id": agent_id,
        "process_code": process_code,
    }


def get_access_token(app_key, app_secret):
    """Get access token from DingTalk."""
    url = f"{DINGTALK_BASE_URL}/oauth2/accessToken"
    payload = {"appKey": app_key, "appSecret": app_secret}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(
            f"Token response: {json.dumps(data, indent=2, ensure_ascii=False)}"
        )

        access_token = data.get("accessToken")
        if not access_token:
            raise ValueError("Response missing accessToken")

        print("✓ 获取访问令牌成功")
        return access_token
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"获取访问令牌失败: {e}")


def get_instance_id_list(
    access_token, process_code, start_time, end_time=None, statuses=None
):
    """Get list of approval instance IDs with pagination."""
    if statuses is None:
        statuses = ["COMPLETED"]

    url = f"{DINGTALK_BASE_URL}/workflow/processes/instanceIds/query"
    headers = {
        "x-acs-dingtalk-access-token": access_token,
        "Content-Type": "application/json",
    }

    all_ids = []
    next_token = 0

    while True:
        payload = {
            "processCode": process_code,
            "startTime": start_time,
            "endTime": end_time,
            "nextToken": next_token,
            "maxResults": 20,
            "statuses": statuses,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            result = data.get("result", {})
            ids = result.get("list", [])
            all_ids.extend(ids)

            next_token = result.get("nextToken")
            if not next_token:
                break
        except requests.exceptions.RequestException as e:
            print(f"获取审批实例ID列表失败: {e}")
            raise

    print(f"✓ 获取审批实例ID列表成功，共 {len(all_ids)} 条")
    return all_ids


def get_instance_details(process_instance_id, access_token):
    """Get details of a single approval instance."""
    url = f"{DINGTALK_BASE_URL}/workflow/processInstances"
    params = {"processInstanceId": process_instance_id}
    headers = {"x-acs-dingtalk-access-token": access_token}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(
            f"Instance details: {json.dumps(data, indent=2, ensure_ascii=False)}"
        )

        print("✓ 审批实例详情获取成功")
        return data.get("result", {})
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"获取审批实例详情失败: {e}")


def extract_attachments(form_component_values):
    """Extract attachment file IDs from form component values."""
    attachments = []

    if not form_component_values:
        print("未发现附件")
        return attachments

    for component in form_component_values:
        if component.get("componentType") == "DDAttachment":
            value = component.get("value", "")
            if not value:
                continue

            try:
                # value might be a JSON string or already a list
                if isinstance(value, str):
                    attachment_list = json.loads(value)
                else:
                    attachment_list = value

                if isinstance(attachment_list, list):
                    attachments.extend(attachment_list)
            except json.JSONDecodeError:
                print(f"解析附件数据失败: {value}")
                continue

    if attachments:
        print(f"发现 {len(attachments)} 个附件")
    else:
        print("未发现附件")

    return attachments


def get_download_url(process_instance_id, file_id, access_token):
    """Get download URL for an attachment."""
    url = (
        f"{DINGTALK_BASE_URL}/workflow/processInstances/spaces/files/urls/download"
    )
    headers = {
        "x-acs-dingtalk-access-token": access_token,
        "Content-Type": "application/json",
    }
    payload = {
        "processInstanceId": process_instance_id,
        "fileId": file_id,
        "withCommentAttatchment": False,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        result = data.get("result", {})
        download_uri = result.get("downloadUri", "")
        needs_rename = download_uri.startswith("#")

        print("✓ 下载链接获取成功")
        return download_uri, needs_rename
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"获取下载链接失败: {e}")


def download_file(
    download_url,
    file_name,
    output_dir,
    process_instance_id,
    needs_rename=False,
    original_file_type=None,
):
    """Download file from URL to local directory."""
    # Create output directory
    download_dir = Path(output_dir) / process_instance_id
    download_dir.mkdir(parents=True, exist_ok=True)

    # Determine filename
    if needs_rename and original_file_type:
        safe_name = f"{file_name}.{original_file_type}"
    else:
        safe_name = file_name

    # Sanitize filename
    invalid_chars = '\\/:*?"<>|'
    for char in invalid_chars:
        safe_name = safe_name.replace(char, "_")

    # Handle duplicates
    file_path = download_dir / safe_name
    counter = 1
    while file_path.exists():
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        file_path = download_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    try:
        response = requests.get(download_url, timeout=60, stream=True)
        response.raise_for_status()

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        size_kb = file_path.stat().st_size / 1024
        print(f"✓ 附件下载完成: {file_path} ({size_kb:.1f}KB)")
        return str(file_path)
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"下载附件失败: {e}")
