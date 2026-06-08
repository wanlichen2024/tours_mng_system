import streamlit as st
from utils.db import supabase
from datetime import datetime, timedelta
import pandas as pd

st.subheader("📅 Team Arrival Calendar (Next 14 Days)")

# 获取所有团队的到达日期
resp = supabase.table("tours").select("tour_code", "start_date").execute()
tours = pd.DataFrame(resp.data)

if tours.empty:
    st.info("No tours found. Please add tours first.")
    st.stop()

# 转换日期列
tours['start_date'] = pd.to_datetime(tours['start_date']).dt.date

# 设定显示范围：从今天开始未来14天
today = datetime.now().date()
end_date = today + timedelta(days=14)

# 筛选未来14天内到达的团队
future_tours = tours[(tours['start_date'] >= today) & (tours['start_date'] <= end_date)]

if future_tours.empty:
    st.success("🎉 No teams arriving in the next 14 days.")
    st.stop()

# 构建日历数据：每天有哪些团到达
cal_data = {today + timedelta(days=i): [] for i in range(15)}
for _, row in future_tours.iterrows():
    d = row['start_date']
    if today <= d <= end_date:
        cal_data[d].append(row['tour_code'])

# 显示日历
st.markdown("### 📆 Calendar View")
# 星期标题
cols = st.columns(7)
weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
for i, day in enumerate(weekdays):
    cols[i].markdown(f"**{day}**")

# 构建日历网格
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