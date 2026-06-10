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
import cache_manager
from logger_config import logger
from batch_processor import print_file


def load_user_mapping():
    mapping_path = Path(__file__).parent / "user_mapping.json"
    if mapping_path.exists():
        with open(mapping_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_settings():
    settings_path = Path(__file__).parent / "settings.json"
    if settings_path.exists():
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"download_path": "./downloads"}


def save_settings(settings):
    settings_path = Path(__file__).parent / "settings.json"
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


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

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

download_path = st.session_state.settings.get("download_path", "./downloads")
Path(download_path).mkdir(parents=True, exist_ok=True)

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
    st.header("⚙️ 下载设置")

    current_path = st.session_state.settings.get("download_path", "./downloads")
    new_path = st.text_input("下载路径", value=current_path)
    if new_path != current_path:
        st.session_state.settings["download_path"] = new_path
        save_settings(st.session_state.settings)
        Path(new_path).mkdir(parents=True, exist_ok=True)
        st.success(f"✓ 下载路径已更新: {new_path}")

    st.divider()
    st.header("📋 审批查询")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=datetime.now())
    with col2:
        end_date = st.date_input("结束日期", value=datetime.now())

    # DingTalk API requires millisecond timestamps
    start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
    end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)

    status_options = {
        "已完结": ["COMPLETED"],
        "已完结未打印": ["COMPLETED"],
        "审批中": ["RUNNING"],
        "已撤销": ["TERMINATED"],
        "全部": None,
    }
    selected_status = st.selectbox("审批状态", list(status_options.keys()), index=0)
    statuses = status_options[selected_status]
    filter_unprinted = selected_status == "已完结未打印"

    col1, col2 = st.columns(2)
    with col1:
        force_refresh = st.checkbox("🔄 强制刷新（绕过本地缓存）", value=False)
    with col2:
        if st.button("🔄 刷新列表", use_container_width=True):
            st.session_state.force_refresh_list = True
            st.rerun()

    if st.button("🔍 查询", type="primary", use_container_width=True):
        with st.spinner("正在查询审批列表..."):
            try:
                env = st.session_state.env
                token = st.session_state.access_token

                cached_ids = None if force_refresh else cache_manager.get_cached_instance_list(
                    start_timestamp, end_timestamp, statuses
                )

                if cached_ids is not None:
                    ids = cached_ids
                    st.info(f"📦 已命中本地缓存，共 {len(ids)} 条审批")
                else:
                    ids = get_instance_id_list(
                        token,
                        env["process_code"],
                        start_timestamp,
                        end_timestamp,
                        statuses,
                    )
                    cache_manager.cache_instance_list(
                        start_timestamp, end_timestamp, statuses, ids
                    )

                st.session_state.instance_ids = ids
                if ids:
                    instance_info = {}
                    progress_text = st.empty()
                    api_call_count = 0
                    cache_hit_count = 0
                    for i, inst_id in enumerate(ids):
                        progress_text.write(f"⏳ 正在加载审批信息... ({i+1}/{len(ids)})")
                        try:
                            if not force_refresh:
                                inst_details = cache_manager.get_cached_instance_details(inst_id)
                                if inst_details:
                                    cache_hit_count += 1
                            else:
                                inst_details = None

                            if inst_details is None:
                                inst_details = get_instance_details(inst_id, token)
                                cache_manager.cache_instance_details(inst_id, inst_details)
                                api_call_count += 1

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
                    if api_call_count > 0:
                        st.success(f"✓ 查询成功，共 {len(ids)} 条审批（API调用 {api_call_count} 次，缓存命中 {cache_hit_count} 次）")
                    else:
                        st.success(f"✓ 查询成功，共 {len(ids)} 条审批（全部来自缓存）")
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

    stats = cache_manager.get_stats()
    total = stats["hits"] + stats["misses"]
    if total > 0:
        hit_rate = stats["hits"] / total * 100
        st.caption(f"💾 缓存命中率: {hit_rate:.1f}% ({stats['hits']}/{total})  |  文件: {cache_manager.cache_file_path().name}")

    if "instance_ids" in st.session_state and st.session_state.instance_ids:
        st.divider()
        st.subheader("审批列表")

        instance_info = st.session_state.get("instance_info", {})
        all_ids = st.session_state.instance_ids

        printed_status = cache_manager.get_printed_status(all_ids)
        if filter_unprinted:
            all_ids = [iid for iid in all_ids if not printed_status.get(iid, False)]
            instance_info = {k: v for k, v in instance_info.items() if k in all_ids}

        if not all_ids:
            st.info("没有未打印的已完结审批")
        else:
            all_selected = st.session_state.get("select_all_approvals", False)
            if st.checkbox("全选", value=all_selected, key="select_all_master"):
                st.session_state.select_all_approvals = True
                for idx in range(len(all_ids)):
                    st.session_state[f"chk_{idx}"] = True
            else:
                st.session_state.select_all_approvals = False
                for idx in range(len(all_ids)):
                    st.session_state[f"chk_{idx}"] = False

            selected_for_batch = []

            for idx, instance_id in enumerate(all_ids):
                info = instance_info.get(instance_id, {})
                business_id = info.get("business_id", instance_id[:20])
                status = info.get("status", "UNKNOWN")
                status_emoji = {"COMPLETED": "✅", "RUNNING": "🔄", "TERMINATED": "❌"}.get(status, "📋")
                is_printed = printed_status.get(instance_id, False)
                print_mark = "✓" if is_printed else ""

                is_selected = instance_id == st.session_state.get("selected_instance_id")

                cols = st.columns([0.5, 4])
                with cols[0]:
                    is_checked = st.checkbox("选择", key=f"chk_{idx}", label_visibility="collapsed")
                    if is_checked:
                        selected_for_batch.append(instance_id)
                with cols[1]:
                    if is_selected:
                        button_label = f"🔍 {business_id} {print_mark}"
                        btn_type = "primary"
                    else:
                        button_label = f"{status_emoji} {business_id} {print_mark}"
                        btn_type = "secondary"
                    if st.button(
                        button_label,
                        key=f"btn_{idx}",
                        type=btn_type,
                        use_container_width=True,
                    ):
                        for key in ["batch_action", "batch_instances"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.session_state.selected_instance_id = instance_id
                        st.rerun()

            if selected_for_batch:
                st.divider()
                st.write(f"已选择 {len(selected_for_batch)} 条审批")
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("📥 批量下载", use_container_width=True):
                        st.session_state.batch_action = "download"
                        st.session_state.batch_instances = selected_for_batch
                        st.rerun()
                with bcol2:
                    if st.button("✓ 标记已打印", use_container_width=True):
                        for iid in selected_for_batch:
                            info = instance_info.get(iid, {})
                            cache_manager.mark_printed_without_download(
                                iid, info.get("business_id", iid[:20]), info.get("title", "")
                            )
                        st.success(f"✓ 已标记 {len(selected_for_batch)} 条审批为已打印")
                        st.rerun()

    if "print_queue" in st.session_state and st.session_state.print_queue:
        st.divider()
        st.header("📂 已下载文件")
        queue = st.session_state.print_queue
        total_files = sum(len(b.get("files", [])) for b in queue.values())
        total_selected = sum(sum(1 for f in b.get("files", []) if f["selected"]) for b in queue.values())
        st.write(f"共 {len(queue)} 个批次，{total_files} 个文件（{total_selected} 个待打印）")

        sorted_items = sorted(queue.items(), key=lambda x: x[1].get("batch_order", 1))
        for business_id, batch_data in sorted_items:
            files = batch_data.get("files", [])
            with st.expander(f"📋 {business_id} ({len(files)} 个文件)"):
                for f in files:
                    st.write(f"  - {Path(f['path']).name}")

        if st.button("🖨️ 继续打印", type="primary", use_container_width=True):
            st.session_state.show_print_ui = True
            st.rerun()

        if st.button("🗑️ 清除记录", use_container_width=True):
            del st.session_state.print_queue
            st.rerun()

# --- Batch Processing ---
if "batch_action" in st.session_state and st.session_state.batch_action:
    action = st.session_state.batch_action
    instances = st.session_state.get("batch_instances", [])

    st.header("🔄 批量处理")
    st.write(f"正在处理 {len(instances)} 条审批...")

    progress_bar = st.progress(0)

    signatures_dir = Path("./signatures")
    output_dir = Path(st.session_state.settings.get("download_path", "./downloads"))

    import importlib
    import dingtalk_api
    importlib.reload(dingtalk_api)

    from batch_processor import process_single_approval

    success_count = 0
    skip_count = 0
    fail_count = 0
    all_signed_files_by_business = {}

    for i, inst_id in enumerate(instances):
        progress = (i + 1) / len(instances)
        progress_bar.progress(min(progress, 0.99))

        logger.info(f"[UI] Processing instance {i+1}/{len(instances)}: {inst_id[:20]}...")

        result = process_single_approval(
            inst_id,
            st.session_state.access_token,
            signatures_dir,
            output_dir,
            dingtalk_api,
        )

        display_id = result.get("business_id", inst_id[:20])
        if result["skipped"]:
            logger.info(f"[UI] Skipped {display_id}: {result['message']}")
            st.warning(f"⏭️ {display_id}: {result['message']}")
            skip_count += 1
        elif result["success"]:
            logger.info(f"[UI] Success {display_id}: {result['message']}")
            st.success(f"✅ {display_id}: {result['message']}")
            success_count += 1
            signed_files = result.get("signed_files", [])
            if signed_files:
                if display_id not in all_signed_files_by_business:
                    all_signed_files_by_business[display_id] = []
                all_signed_files_by_business[display_id].extend(signed_files)
        else:
            logger.error(f"[UI] Failed {display_id}: {result['message']}")
            st.error(f"❌ {display_id}: {result['message']}")
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

    if all_signed_files_by_business:
        if "print_queue" not in st.session_state:
            st.session_state.print_queue = {}

        max_batch_order = max(
            (b.get("batch_order", 0) for b in st.session_state.print_queue.values()),
            default=0,
        )

        for business_id, files in all_signed_files_by_business.items():
            if business_id in st.session_state.print_queue:
                existing = st.session_state.print_queue[business_id].get("files", [])
                start_order = len(existing) + 1
                for i, f in enumerate(files):
                    existing.append({"path": f, "order": start_order + i, "selected": True})
            else:
                max_batch_order += 1
                st.session_state.print_queue[business_id] = {
                    "batch_order": max_batch_order,
                    "files": [
                        {"path": f, "order": i + 1, "selected": True}
                        for i, f in enumerate(files)
                    ],
                }

        st.session_state.show_print_ui = True

        for iid in instances:
            info = st.session_state.get("instance_info", {}).get(iid, {})
            cache_manager.mark_as_printed(iid, info.get("business_id", iid[:20]))

    if "batch_action" in st.session_state:
        del st.session_state.batch_action

# --- Print Settings (shown after batch processing or on rerun) ---
if st.session_state.get("show_print_ui", False) and "print_queue" in st.session_state and st.session_state.print_queue:
    st.divider()
    st.subheader("🖨️ 打印设置")

    print_queue = st.session_state.print_queue
    all_files = []
    for business_id, batch_data in print_queue.items():
        for f in batch_data.get("files", []):
            all_files.append({**f, "business_id": business_id})

    st.write(f"共 {len(all_files)} 个已签名文件可打印")

    with st.form("print_settings"):
        st.write("调整批次顺序和文件勾选后，点击'应用设置'确认：")
        new_queue = {}
        idx = 0
        sorted_batches = sorted(print_queue.items(), key=lambda x: x[1].get("batch_order", 1))
        for business_id, batch_data in sorted_batches:
            files = batch_data.get("files", [])
            previous_all_selected = all(f["selected"] for f in files) if files else False

            header_cols = st.columns([1, 2, 1, 1])
            with header_cols[0]:
                batch_order = st.number_input(
                    f"批次_{business_id}",
                    min_value=1,
                    value=batch_data.get("batch_order", 1),
                    label_visibility="collapsed",
                )
            with header_cols[1]:
                st.write(f"📋 {business_id}")
            with header_cols[2]:
                select_all = st.checkbox(
                    f"全选_{business_id}",
                    value=previous_all_selected,
                    label_visibility="collapsed",
                )
            with header_cols[3]:
                st.write("全选")

            new_files = []
            for item in files:
                file_path = Path(item["path"])
                cols = st.columns([0.5, 0.5, 3])
                with cols[0]:
                    order = st.number_input(
                        f"序号_{idx}",
                        min_value=1,
                        value=item["order"],
                        label_visibility="collapsed",
                    )
                with cols[1]:
                    file_selected = item["selected"]
                    if select_all != previous_all_selected:
                        file_selected = select_all
                    selected = st.checkbox(
                        f"打印_{idx}",
                        value=file_selected,
                        label_visibility="collapsed",
                    )
                with cols[2]:
                    st.write(f"{Path(file_path).name}")
                new_files.append({"path": item["path"], "order": order, "selected": selected})
                idx += 1
            new_queue[business_id] = {
                "batch_order": batch_order,
                "files": new_files,
            }

        apply_clicked = st.form_submit_button("应用设置", use_container_width=True)

    if apply_clicked:
        st.session_state.print_queue = new_queue
        st.rerun()

    all_selected = []
    sorted_batches = sorted(print_queue.items(), key=lambda x: x[1].get("batch_order", 1))
    for business_id, batch_data in sorted_batches:
        for f in sorted(batch_data.get("files", []), key=lambda x: x["order"]):
            if f["selected"]:
                all_selected.append(f)

    if all_selected:
        st.write(f"将按顺序打印 {len(all_selected)} 个文件：")
        for i, item in enumerate(all_selected):
            st.write(f"  {i+1}. {Path(item['path']).name}")

        if st.button("🖨️ 开始打印", type="primary", use_container_width=True):
            print_progress = st.progress(0)
            printed_count = 0
            for i, item in enumerate(all_selected):
                file_path = Path(item["path"])
                st.write(f"⏳ 正在打印 {file_path.name}...")
                if print_file(file_path):
                    st.write(f"✅ 打印成功: {file_path.name}")
                    printed_count += 1
                else:
                    st.error(f"❌ 打印失败: {file_path.name}")
                print_progress.progress((i + 1) / len(all_selected))
            print_progress.empty()
            st.success(f"🎉 打印完成！成功 {printed_count}/{len(all_selected)} 个")
            if printed_count > 0:
                for iid in st.session_state.get("batch_instances", []):
                    info = st.session_state.get("instance_info", {}).get(iid, {})
                    cache_manager.mark_as_printed(iid, info.get("business_id", iid[:20]))
    else:
        st.info("未选择任何文件打印")

    if st.button("返回"):
        for key in ["batch_action", "batch_instances"]:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.show_print_ui = False
        st.rerun()

elif not st.session_state.get("show_print_ui", False) and "selected_instance_id" not in st.session_state:
    if st.session_state.get("show_summary_ui", False):
        st.subheader("📊 汇总统计")
        printed_records = cache_manager.get_printed_records()
        if printed_records:
            st.write(f"已打印记录: {len(printed_records)} 条")
            for iid, rec in printed_records.items():
                bid = rec.get("business_id", iid[:20])
                ts = rec.get("printed_at", 0)
                dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
                st.write(f"  ✓ {bid}  ({dt})")
        else:
            st.info("暂无打印记录")
        if st.button("返回"):
            st.session_state.show_summary_ui = False
            st.rerun()
    else:
        st.info("👈 请从左侧选择一个审批实例查看详情")
        if st.button("📊 查看汇总"):
            st.session_state.show_summary_ui = True
            st.rerun()
else:
    instance_id = st.session_state.selected_instance_id

    with st.spinner("正在获取审批详情..."):
        try:
            token = st.session_state.access_token
            details = cache_manager.get_cached_instance_details(instance_id)
            if details is None:
                details = get_instance_details(instance_id, token)
                cache_manager.cache_instance_details(instance_id, details)
            else:
                st.toast("📦 已命中本地缓存")
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
                dl_key = f"dl_{instance_id}_{file_id}"
                if dl_key not in st.session_state:
                    if st.button("📥 下载", key=f"btn_dl_{idx}"):
                        st.session_state[dl_key] = True
                        st.rerun()
                else:
                    try:
                        download_url = cache_manager.get_cached_download_url(instance_id, file_id)
                        if download_url is None:
                            download_url, _ = get_download_url(instance_id, file_id, token)
                            cache_manager.cache_download_url(instance_id, file_id, download_url)
                        file_bytes = download_file_bytes(download_url)
                        st.download_button(
                            label="📥 点击下载",
                            data=file_bytes,
                            file_name=file_name,
                            mime="application/octet-stream",
                            key=f"dl_btn_{idx}",
                        )
                    except Exception as e:
                        st.error(f"下载失败: {e}")
                    if dl_key in st.session_state:
                        del st.session_state[dl_key]