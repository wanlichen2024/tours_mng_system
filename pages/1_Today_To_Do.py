import streamlit as st
from utils.db import supabase
from datetime import datetime, timedelta
import pandas as pd

st.subheader("📅 Team Arrival Calendar (Next 14 Days)")

# 获取所有团队的到达日期
tours_resp = supabase.table("tours").select("tour_code", "start_date").execute()
tours = pd.DataFrame(tours_resp.data)

if not tours.empty:
    tours['start_date'] = pd.to_datetime(tours['start_date']).dt.date
    today = datetime.now().date()
    end_date = today + timedelta(days=14)
    future_tours = tours[(tours['start_date'] >= today) & (tours['start_date'] <= end_date)]

    if not future_tours.empty:
        # 构建日历数据
        cal_data = {today + timedelta(days=i): [] for i in range(15)}
        for _, row in future_tours.iterrows():
            d = row['start_date']
            if today <= d <= end_date:
                cal_data[d].append(row['tour_code'])

        st.markdown("### 📆 Calendar View")
        cols = st.columns(7)
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(weekdays):
            cols[i].markdown(f"**{day}**")

        first_day = today
        start_weekday = first_day.weekday()
        weeks = []
        current_week = [None] * 7
        for i in range(start_weekday):
            current_week[i] = None
        for d in (today + timedelta(days=i) for i in range(15)):
            wd = d.weekday()
            if wd == 0 and d != today:
                weeks.append(current_week)
                current_week = [None] * 7
            current_week[wd] = d
        weeks.append(current_week)

        for week in weeks:
            cols = st.columns(7)
            for i, d in enumerate(week):
                if d is None:
                    cols[i].markdown(" ")
                else:
                    items = cal_data.get(d, [])
                    if items:
                        tooltip = "\n".join(items)
                        cols[i].markdown(f"**{d.day}**\n\n" + "<br>".join(items), help=tooltip)
                    else:
                        cols[i].markdown(f"{d.day}")

        st.markdown("---")
        st.subheader("📋 List View (Arriving in next 14 days)")
        for _, row in future_tours.sort_values('start_date').iterrows():
            st.write(f"**{row['start_date']}** - Tour {row['tour_code']}")
    else:
        st.info("No teams arriving in the next 14 days.")
else:
    st.info("No tours found. Please add tours first.")

# ==================== 待取消酒店列表 ====================
st.markdown("---")
st.subheader("🏨 Hotels Pending Cancellation/Confirmation")

# 获取所有未确认的酒店
resp = supabase.table("bookings").select("*").eq("category", "hotel").is_("reference", "null").execute()
hotels = pd.DataFrame(resp.data)

if hotels.empty:
    st.success("No pending hotel confirmations.")
else:
    today = datetime.now().date()
    pending = []
    for _, row in hotels.iterrows():
        check_in = pd.to_datetime(row['check_in_date']).date()
        days_notice = row.get('days_advance_notice', 32)
        deadline = check_in - timedelta(days=days_notice)
        if deadline <= today:  # 已过截止日期需要处理
            task_key = f"{row['tour_code']}_{row['business_name']}_{row['check_in_date']}"
            # 检查是否已完成
            existing = supabase.table("completed_tasks").select("task_key").eq("task_key", task_key).execute()
            if not existing.data:
                pending.append({
                    'task_key': task_key,
                    'tour_code': row['tour_code'],
                    'hotel': row['business_name'],
                    'city': row.get('city', ''),
                    'check_in': check_in,
                    'deadline': deadline
                })

    if not pending:
        st.success("All pending hotels have been processed!")
    else:
        st.warning(f"Found {len(pending)} hotel(s) requiring action.")
        for item in pending:
            col1, col2, col3 = st.columns([0.8, 0.15, 0.05])
            with col1:
                st.write(f"**{item['tour_code']}** - {item['hotel']} ({item['city']}) | Check-in: {item['check_in']} | Cancel deadline: {item['deadline']}")
            with col2:
                if st.button("✅ Done", key=f"done_{item['task_key']}"):
                    supabase.table("completed_tasks").insert({"task_key": item['task_key']}).execute()
                    st.rerun()