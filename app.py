import streamlit as st
import time
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

from dingtalk_api import (
    load_env, get_access_token, get_instance_id_list,
    get_instance_details, extract_attachments, get_download_url, download_file, download_file_bytes
)


def load_user_mapping():
    mapping_path = Path(__file__).parent / "user_mapping.json"
    if mapping_path.exists():
        with open(mapping_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_user_name(user_id):
    if not user_id:
        return "未知"
    mapping = st.session_state.get("user_mapping", {})
    return mapping.get(str(user_id), str(user_id))


def process_contacts_excel(uploaded_file):
    import pandas as pd
    try:
        df = pd.read_excel(uploaded_file, header=1)
        df = df.iloc[1:].reset_index(drop=True)
        mapping = {}
        for _, row in df.iterrows():
            user_id = str(row.iloc[0]).strip()
            name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
            if user_id and name and user_id != "nan":
                mapping[user_id] = name
        return mapping
    except Exception as e:
        st.error(f"解析Excel失败: {e}")
        return None


st.set_page_config(page_title="钉钉审批Demo", layout="wide")

Path("./signatures").mkdir(exist_ok=True)
# Ensure downloads directory exists
Path("./downloads").mkdir(exist_ok=True)

if "access_token" not in st.session_state:
    with st.spinner("正在获取访问令牌..."):
        try:
            env = load_env()
            token = get_access_token(env["app_key"], env["app_secret"])
            st.session_state.access_token = token
            st.session_state.env = env
            st.session_state.token_time = time.time()
            st.success("✓ 访问令牌获取成功")
        except SystemExit as e:
            st.error(str(e))
            st.stop()
else:
    if time.time() - st.session_state.get("token_time", 0) > 7000:
        with st.spinner("访问令牌即将过期，正在刷新..."):
            try:
                env = st.session_state.env
                token = get_access_token(env["app_key"], env["app_secret"])
                st.session_state.access_token = token
                st.session_state.token_time = time.time()
                st.success("✓ 访问令牌已刷新")
            except SystemExit as e:
                st.error(str(e))
                st.stop()


with st.sidebar:
    st.header("👥 通讯录导入")

    uploaded_file = st.file_uploader(
        "上传通讯录Excel",
        type=["xlsx", "xls"],
        help="支持钉钉导出的通讯录模板",
    )

    if "user_mapping" not in st.session_state:
        st.session_state.user_mapping = load_user_mapping()

    if uploaded_file is not None:
        mapping = process_contacts_excel(uploaded_file)
        if mapping:
            mapping_path = Path(__file__).parent / "user_mapping.json"
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
            st.session_state.user_mapping = mapping
            st.success(f"✓ 导入成功，共 {len(mapping)} 条记录")
            st.info("刷新页面后生效")

    current_count = len(st.session_state.get("user_mapping", {}))
    if current_count > 0:
        st.caption(f"当前通讯录：{current_count} 人")

    st.divider()
    st.header("📋 审批查询")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("结束日期", value=datetime.now())

    # DingTalk API requires millisecond timestamps
    start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
    end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)

    status_options = {
        "已完结": ["COMPLETED"],
        "审批中": ["RUNNING"],
        "已撤销": ["TERMINATED"],
        "全部": None,
    }
    selected_status = st.selectbox("审批状态", list(status_options.keys()), index=0)
    statuses = status_options[selected_status]

    if st.button("🔍 查询", type="primary", use_container_width=True):
        with st.spinner("正在查询审批列表..."):
            try:
                env = st.session_state.env
                token = st.session_state.access_token
                ids = get_instance_id_list(
                    token,
                    env["process_code"],
                    start_timestamp,
                    end_timestamp,
                    statuses,
                )
                st.session_state.instance_ids = ids
                if ids:
                    instance_info = {}
                    progress_text = st.empty()
                    for i, inst_id in enumerate(ids):
                        progress_text.write(f"⏳ 正在加载审批信息... ({i+1}/{len(ids)})")
                        try:
                            inst_details = get_instance_details(inst_id, token)
                            originator_id = inst_details.get("originatorUserId", "未知")
                            instance_info[inst_id] = {
                                "business_id": inst_details.get("businessId", inst_id[:20]),
                                "title": inst_details.get("title", "未知标题"),
                                "status": inst_details.get("status", "UNKNOWN"),
                                "originator": get_user_name(originator_id),
                                "create_time": inst_details.get("createTime", ""),
                            }
                        except Exception:
                            instance_info[inst_id] = {
                                "business_id": inst_id[:20],
                                "title": "加载失败",
                                "status": "UNKNOWN",
                                "originator": "未知",
                                "create_time": "",
                            }
                    progress_text.empty()
                    st.session_state.instance_info = instance_info
                    st.success(f"✓ 查询成功，共 {len(ids)} 条审批")
                else:
                    st.info("未查询到符合条件的审批")
            except requests.exceptions.Timeout:
                st.error("⏱️ 请求超时，请检查网络连接")
            except requests.exceptions.ConnectionError:
                st.error("🔌 网络连接失败，请检查网络")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    st.error("🔑 访问令牌无效或已过期")
                elif e.response.status_code == 400:
                    error_data = e.response.json()
                    error_msg = error_data.get("errmsg", "请求参数错误")
                    st.error(f"❌ {error_msg}")
                else:
                    st.error(f"❌ HTTP错误: {e}")
            except Exception as e:
                st.error(f"❌ 查询失败: {e}")

    if "instance_ids" in st.session_state and st.session_state.instance_ids:
        st.divider()
        st.subheader("审批列表")

        instance_info = st.session_state.get("instance_info", {})
        selected_for_batch = []

        for idx, instance_id in enumerate(st.session_state.instance_ids):
            info = instance_info.get(instance_id, {})
            business_id = info.get("business_id", instance_id[:20])
            status = info.get("status", "UNKNOWN")
            status_emoji = {"COMPLETED": "✅", "RUNNING": "🔄", "TERMINATED": "❌"}.get(status, "📋")

            cols = st.columns([0.5, 4])
            with cols[0]:
                is_checked = st.checkbox("", key=f"chk_{idx}", label_visibility="collapsed")
            with cols[1]:
                button_label = f"{status_emoji} {business_id}"
                if st.button(
                    button_label,
                    key=f"btn_{idx}",
                    use_container_width=True,
                ):
                    st.session_state.selected_instance_id = instance_id
                    st.rerun()

            if is_checked:
                selected_for_batch.append(instance_id)

        if selected_for_batch:
            st.divider()
            st.write(f"已选择 {len(selected_for_batch)} 条审批")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 批量下载", use_container_width=True):
                    st.session_state.batch_action = "download"
                    st.session_state.batch_instances = selected_for_batch
                    st.rerun()
            with col2:
                if st.button("🖨️ 批量签名并打印", type="primary", use_container_width=True):
                    st.session_state.batch_action = "sign_and_print"
                    st.session_state.batch_instances = selected_for_batch
                    st.rerun()

if "batch_action" in st.session_state and st.session_state.batch_action:
    action = st.session_state.batch_action
    instances = st.session_state.get("batch_instances", [])

    st.header("🔄 批量处理")
    st.write(f"正在处理 {len(instances)} 条审批...")

    progress_bar = st.progress(0)
    results_container = st.container()

    signatures_dir = Path("./signatures")
    output_dir = Path("./downloads")

    import importlib
    import dingtalk_api
    importlib.reload(dingtalk_api)

    from batch_processor import process_single_approval

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, inst_id in enumerate(instances):
        progress = (i + 1) / len(instances)
        progress_bar.progress(min(progress, 0.99))

        result = process_single_approval(
            inst_id,
            st.session_state.access_token,
            signatures_dir,
            output_dir,
            dingtalk_api,
        )

        with results_container:
            if result["skipped"]:
                st.warning(f"⏭️ {inst_id[:20]}...: {result['message']}")
                skip_count += 1
            elif result["success"]:
                st.success(f"✅ {inst_id[:20]}...: {result['message']}")
                success_count += 1
            else:
                st.error(f"❌ {inst_id[:20]}...: {result['message']}")
                fail_count += 1

    progress_bar.empty()
    st.divider()
    st.subheader("📊 处理结果")
    cols = st.columns(3)
    with cols[0]:
        st.metric("成功", success_count)
    with cols[1]:
        st.metric("跳过", skip_count)
    with cols[2]:
        st.metric("失败", fail_count)

    if st.button("返回"):
        del st.session_state.batch_action
        del st.session_state.batch_instances
        st.rerun()

elif "selected_instance_id" not in st.session_state:
    st.info("👈 请从左侧选择一个审批实例查看详情")
else:
    instance_id = st.session_state.selected_instance_id

    with st.spinner("正在获取审批详情..."):
        try:
            token = st.session_state.access_token
            details = get_instance_details(instance_id, token)
        except requests.exceptions.Timeout:
            st.error("⏱️ 请求超时，请检查网络连接")
            st.stop()
        except requests.exceptions.ConnectionError:
            st.error("🔌 网络连接失败，请检查网络")
            st.stop()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                st.error("🔑 访问令牌无效或已过期")
            elif e.response.status_code == 400:
                error_data = e.response.json()
                error_msg = error_data.get("errmsg", "请求参数错误")
                st.error(f"❌ {error_msg}")
            else:
                st.error(f"❌ HTTP错误: {e}")
            st.stop()
        except Exception as e:
            st.error(f"❌ 获取详情失败: {e}")
            st.stop()

    # Title
    title = details.get("title", "未知标题")
    st.header(f"📋 {title}")

    # Two-column layout
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("基本信息")
        status = details.get("status", "未知")
        status_emoji = {"COMPLETED": "✅", "RUNNING": "🔄", "TERMINATED": "❌"}.get(status, "❓")
        st.write(f"**状态:** {status_emoji} {status}")
        originator_id = details.get('originatorUserId', '未知')
        st.write(f"**发起人:** {get_user_name(originator_id)}")
        st.write(f"**部门:** {details.get('originatorDeptName', '未知')}")
        st.write(f"**创建时间:** {details.get('createTime', '未知')}")
        st.write(f"**完成时间:** {details.get('finishTime', '未知')}")

    with col2:
        st.subheader("表单数据")
        form_values = details.get("formComponentValues", [])
        for item in form_values:
            if item.get("componentType") != "DDAttachment":
                name = item.get("name", "未知字段")
                value = item.get("value", "")
                st.write(f"**{name}:** {value}")

    st.divider()
    st.subheader("📋 审批流程")

    operation_records = details.get("operationRecords", [])
    if operation_records:
        for record in operation_records:
            record_type = record.get("type", "")
            if record_type == "START_PROCESS_INSTANCE":
                continue

            show_name = record.get("showName", "未知")
            user_id = record.get("userId", "")
            user_name = get_user_name(user_id) if user_id else "系统"
            result = record.get("result", "NONE")
            date = record.get("date", "")
            remark = record.get("remark", "")

            result_emoji = {
                "AGREE": "✅ 同意",
                "REFUSE": "❌ 拒绝",
                "NONE": "➡️ 转交/抄送",
                "BACK": "↩️ 退回",
            }.get(result, f"❓ {result}")

            with st.container():
                cols = st.columns([2, 2, 2, 2])
                with cols[0]:
                    st.write(f"**{show_name}**")
                with cols[1]:
                    st.write(f"👤 {user_name}")
                with cols[2]:
                    st.write(result_emoji)
                with cols[3]:
                    if remark:
                        st.write(f"💬 {remark}")
                    else:
                        st.write("—")
                if date:
                    st.caption(f"🕐 {date}")
    else:
        st.info("暂无审批记录")

    # Attachments section
    st.divider()
    st.subheader("📎 附件列表")

    attachments = extract_attachments(form_values)

    if not attachments:
        st.info("该审批无附件")
    else:
        # Display attachment list
        for idx, att in enumerate(attachments):
            file_name = att.get("fileName", "未知文件")
            file_type = att.get("fileType", "")
            file_size = att.get("fileSize", 0)
            size_str = f"({file_size / 1024:.1f}KB)" if file_size else ""
            st.write(f"{idx+1}. **{file_name}** {size_str}")

        for idx, att in enumerate(attachments):
            file_name = att.get("fileName", "未知文件")
            file_id = att.get("fileId")

            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{idx+1}. **{file_name}**")
            with cols[1]:
                try:
                    download_url, _ = get_download_url(instance_id, file_id, token)
                    file_bytes = download_file_bytes(download_url)
                    st.download_button(
                        label="📥 下载",
                        data=file_bytes,
                        file_name=file_name,
                        mime="application/octet-stream",
                        key=f"dl_{idx}",
                    )
                except Exception as e:
                    st.error(f"下载失败: {e}")