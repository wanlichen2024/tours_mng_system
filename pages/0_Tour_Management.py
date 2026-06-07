import streamlit as st
import pandas as pd
from utils.db import supabase
from datetime import datetime

st.set_page_config(page_title="团队管理", layout="wide")
st.title("📋 团队管理")

def get_tours():
    resp = supabase.table("tours").select("*").order("start_date").execute()
    return pd.DataFrame(resp.data)

def upsert_tour(record):
    supabase.table("tours").upsert(record, on_conflict="tour_code").execute()

def delete_tour(tour_code):
    supabase.table("tours").delete().eq("tour_code", tour_code).execute()

action = st.sidebar.radio("操作", ["查看团队列表", "新增/编辑团队"])

if action == "查看团队列表":
    st.subheader("🗂️ 所有团队")
    df = get_tours()
    if df.empty:
        st.info("暂无团队数据。请先添加。")
    else:
        st.dataframe(df, use_container_width=True)
        with st.expander("删除团队"):
            tour_to_del = st.selectbox("选择要删除的团号", df['tour_code'].tolist())
            if st.button("删除该团队"):
                confirm = st.checkbox("确认删除？此操作不会影响 bookings 中的预订记录。")
                if confirm:
                    delete_tour(tour_to_del)
                    st.success(f"已删除团队 {tour_to_del}")
                    st.rerun()

elif action == "新增/编辑团队":
    st.subheader("✏️ 新增或编辑团队")
    tours_df = get_tours()
    existing_codes = tours_df['tour_code'].tolist() if not tours_df.empty else []
    
    option = st.radio("选择", ["新建团队", "编辑已有团队"])
    if option == "编辑已有团队":
        if not existing_codes:
            st.warning("暂无团队，请先新建。")
            st.stop()
        tour_code = st.selectbox("选择团号", existing_codes)
        tour_data = tours_df[tours_df['tour_code'] == tour_code].iloc[0].to_dict()
    else:
        tour_code = st.text_input("团号*")
        tour_data = {}

    with st.form("tour_form"):
        col1, col2 = st.columns(2)
        with col1:
            # 安全处理日期：如果值为空或NaT，则使用None，st.date_input 会显示空
            start_val = tour_data.get('start_date')
            if start_val in (None, pd.NaT, '') or (isinstance(start_val, float) and pd.isna(start_val)):
                start_val = None
            end_val = tour_data.get('end_date')
            if end_val in (None, pd.NaT, '') or (isinstance(end_val, float) and pd.isna(end_val)):
                end_val = None
            
            start_date = st.date_input("到达日期", value=start_val if start_val else None)
            end_date = st.date_input("结束日期", value=end_val if end_val else None)
            adult_pax = st.number_input("成人数", value=int(tour_data.get('adult_pax', 0) or 0), step=1)
            child_pax = st.number_input("儿童数", value=int(tour_data.get('child_pax', 0) or 0), step=1)
            rooms = st.number_input("房间数", value=int(tour_data.get('rooms', 0) or 0), step=1)
        with col2:
            tour_leader = st.text_input("领队", value=tour_data.get('tour_leader', '') or '')
            guide_name = st.text_input("导游姓名", value=tour_data.get('guide_name', '') or '')
            guide_phone = st.text_input("导游电话", value=tour_data.get('guide_phone', '') or '')
            driver_name = st.text_input("司机姓名", value=tour_data.get('driver_name', '') or '')
            route_type = st.selectbox("线路类型", ["系列团", "单团"], index=0 if (tour_data.get('route_type', '系列团') == '系列团') else 1)
            route_name = st.text_input("线路名称", value=tour_data.get('route_name', '') or '')
        notes = st.text_area("备注", value=tour_data.get('notes', '') or '')

        submitted = st.form_submit_button("保存")
        if submitted:
            if not tour_code:
                st.error("团号不能为空")
            else:
                new_record = {
                    "tour_code": tour_code,
                    "start_date": start_date.strftime('%Y-%m-%d') if start_date else None,
                    "end_date": end_date.strftime('%Y-%m-%d') if end_date else None,
                    "adult_pax": adult_pax,
                    "child_pax": child_pax,
                    "rooms": rooms,
                    "tour_leader": tour_leader,
                    "guide_name": guide_name,
                    "guide_phone": guide_phone,
                    "driver_name": driver_name,
                    "route_type": route_type,
                    "route_name": route_name,
                    "notes": notes
                }
                upsert_tour(new_record)
                st.success(f"团队 {tour_code} 已保存")
                st.rerun()