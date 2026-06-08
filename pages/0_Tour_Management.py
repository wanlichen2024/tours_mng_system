import streamlit as st
import pandas as pd
import time
from utils.db import supabase
from datetime import datetime

st.set_page_config(page_title="团队管理", layout="wide")
st.title("📋 团队管理")

# ==================================================
# GET TOURS
# ==================================================
def get_tours(include_deleted=False):
    if include_deleted:
        response = (
            supabase.table("tours")
            .select("*")
            .order("start_date")
            .execute()
        )
    else:
        response = (
            supabase.table("tours")
            .select("*")
            .eq("is_deleted", False)
            .order("start_date")
            .execute()
        )

    return pd.DataFrame(response.data)


# ==================================================
# UPSERT TOUR
# ==================================================
def upsert_tour(record):
    record.pop("is_deleted", None)  # 防止覆盖删除状态

    supabase.table("tours")\
        .upsert(record, on_conflict="tour_code")\
        .execute()


# ==================================================
# SOFT DELETE (FIXED)
# ==================================================
def soft_delete_tour(tour_code):
    try:
        tour_code = tour_code.strip()

        supabase.table("tours")\
            .update({"is_deleted": True})\
            .eq("tour_code", tour_code)\
            .execute()

        return True

    except Exception as e:
        st.error(f"删除失败: {e}")
        return False


# ==================================================
# RESTORE TOUR
# ==================================================
def restore_tour(tour_code):
    try:
        tour_code = tour_code.strip()

        supabase.table("tours")\
            .update({"is_deleted": False})\
            .eq("tour_code", tour_code)\
            .execute()

        return True

    except Exception as e:
        st.error(f"恢复失败: {e}")
        return False


# ==================================================
# SIDEBAR
# ==================================================
action = st.sidebar.radio(
    "操作",
    ["查看团队列表", "新增/编辑团队", "回收站"]
)

# ==================================================
# VIEW ACTIVE TOURS
# ==================================================
if action == "查看团队列表":

    st.subheader("🗂️ 当前团队")

    df = get_tours(include_deleted=False)

    if df.empty:
        st.info("暂无团队数据")
        st.stop()

    st.dataframe(df, use_container_width=True)

    st.divider()

    st.subheader("⚠️ 删除团队（软删除）")

    tour_to_del = st.selectbox(
        "选择团队",
        df["tour_code"].tolist()
    )

    confirm = st.checkbox("确认删除该团队（不可见但可恢复）")

    if st.button("删除团队", type="primary"):

        if not confirm:
            st.warning("请先确认删除")
        else:
            success = soft_delete_tour(tour_to_del)

            if success:
                st.success(f"{tour_to_del} 已删除")
                time.sleep(1)
                st.rerun()


# ==================================================
# ADD / EDIT
# ==================================================
elif action == "新增/编辑团队":

    st.subheader("✏️ 新增 / 编辑团队")

    tours_df = get_tours(include_deleted=False)
    existing_codes = (
        tours_df["tour_code"].tolist()
        if not tours_df.empty else []
    )

    mode = st.radio("模式", ["新建", "编辑"])

    if mode == "编辑":

        if not existing_codes:
            st.warning("暂无团队")
            st.stop()

        tour_code = st.selectbox(
            "选择团队",
            existing_codes
        )

        tour_data = (
            tours_df[
                tours_df["tour_code"] == tour_code
            ].iloc[0].to_dict()
        )

    else:
        tour_code = st.text_input("团号*")
        tour_data = {}

    with st.form("form"):

        col1, col2 = st.columns(2)

        with col1:

            start_date = st.date_input(
                "开始日期",
                value=pd.to_datetime(
                    tour_data.get("start_date")
                ).date() if tour_data.get("start_date") else None
            )

            end_date = st.date_input(
                "结束日期",
                value=pd.to_datetime(
                    tour_data.get("end_date")
                ).date() if tour_data.get("end_date") else None
            )

            adult_pax = st.number_input(
                "成人数",
                value=int(tour_data.get("adult_pax", 0) or 0)
            )

            child_pax = st.number_input(
                "儿童数",
                value=int(tour_data.get("child_pax", 0) or 0)
            )

            rooms = st.number_input(
                "房间数",
                value=int(tour_data.get("rooms", 0) or 0)
            )

        with col2:

            tour_leader = st.text_input(
                "领队",
                value=tour_data.get("tour_leader", "") or ""
            )

            guide_name = st.text_input(
                "导游",
                value=tour_data.get("guide_name", "") or ""
            )

            driver_name = st.text_input(
                "司机",
                value=tour_data.get("driver_name", "") or ""
            )

            route_type = st.selectbox(
                "线路类型",
                ["系列团", "单团"],
                index=0
                if tour_data.get("route_type") != "单团"
                else 1
            )

        submitted = st.form_submit_button("保存")

        if submitted:

            if not tour_code:
                st.error("团号不能为空")
                st.stop()

            record = {
                "tour_code": tour_code.strip(),
                "start_date": start_date,
                "end_date": end_date,
                "adult_pax": adult_pax,
                "child_pax": child_pax,
                "rooms": rooms,
                "tour_leader": tour_leader,
                "guide_name": guide_name,
                "driver_name": driver_name,
                "route_type": route_type,
            }

            upsert_tour(record)

            st.success("保存成功")
            st.rerun()


# ==================================================
# TRASH
# ==================================================
elif action == "回收站":

    st.subheader("🗑️ 回收站")

    df_deleted = get_tours(include_deleted=True)
    df_deleted = df_deleted[
        df_deleted["is_deleted"] == True
    ]

    if df_deleted.empty:
        st.info("回收站为空")
        st.stop()

    st.dataframe(df_deleted, use_container_width=True)

    st.divider()

    tour_to_restore = st.selectbox(
        "恢复团队",
        df_deleted["tour_code"].tolist()
    )

    if st.button("恢复"):

        success = restore_tour(tour_to_restore)

        if success:
            st.success("恢复成功")
            time.sleep(1)
            st.rerun()