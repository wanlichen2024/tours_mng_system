import streamlit as st
from utils.db import supabase
from datetime import datetime, timedelta
import pandas as pd
import pytz  # 需要安装：pip install pytz

st.subheader("📅 Upcoming Hotel Confirmation Deadlines (Next 14 Days)")

# 获取数据
resp = supabase.table("bookings").select("*").eq("category", "hotel").is_("reference", "null").execute()
hotels = pd.DataFrame(resp.data)

if hotels.empty:
    st.success("🎉 No pending hotel confirmations. All hotels are confirmed.")
    st.stop()

# 使用本地日期（新西兰时区）
local_tz = pytz.timezone('Pacific/Auckland')
today = datetime.now(local_tz).date()

reminders = []
for _, row in hotels.iterrows():
    # 将数据库中的日期字符串转为 datetime，并本地化
    check_in_str = row['check_in_date']
    # 假设数据库存的是 UTC 日期字符串 "2026-07-02"
    # 直接解析为日期，不涉及时区
    check_in = pd.to_datetime(check_in_str).date()
    days_notice = row.get('days_advance_notice', 32)
    deadline = check_in - timedelta(days=days_notice)
    days_left = (deadline - today).days
    if 0 <= days_left <= 14:
        reminders.append({
            'date': deadline,  # 这个是纯日期
            'tour_code': row['tour_code'],
            'hotel': row['business_name'],
            'city': row.get('city', ''),
            'days_left': days_left,
            'notice_days': days_notice
        })

if not reminders:
    st.info("No deadlines in the next 14 days.")
    st.stop()

# 调试：显示实际截止日期（可注释掉）
with st.expander("Debug: Show raw deadlines"):
    for r in reminders:
        st.write(f"{r['tour_code']} - {r['hotel']} : deadline {r['date']}")

df_reminders = pd.DataFrame(reminders).sort_values('date')
st.markdown("### 📆 Calendar View")
start_date = today
cal_data = {start_date + timedelta(days=i): [] for i in range(15)}
for r in reminders:
    d = r['date']
    if start_date <= d <= start_date + timedelta(days=14):
        cal_data[d].append(r)

# 星期标题
cols = st.columns(7)
weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
for i, day in enumerate(weekdays):
    cols[i].markdown(f"**{day}**")

# 构建日历网格
first_day = start_date
start_weekday = first_day.weekday()
weeks = []
current_week = [None] * 7
for i in range(start_weekday):
    current_week[i] = None
for d in (start_date + timedelta(days=i) for i in range(15)):
    wd = d.weekday()
    if wd == 0 and d != start_date:
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
                tooltip = "\n".join([f"{it['tour_code']}: {it['hotel']}" for it in items])
                cols[i].markdown(f"**{d.day}**\n\n" + "<br>".join([f"{it['tour_code']}" for it in items]), help=tooltip)
            else:
                cols[i].markdown(f"{d.day}")

st.markdown("---")
st.subheader("📋 List View")
for _, r in df_reminders.iterrows():
    if r['days_left'] == 0:
        st.error(f"🔴 **TODAY** - Tour {r['tour_code']}: {r['hotel']} (deadline: {r['date']})")
    elif r['days_left'] <= 3:
        st.warning(f"⚠️ **{r['tour_code']}** - {r['hotel']} | Deadline in {r['days_left']} day(s) ({r['date']})")
    else:
        st.info(f"📌 **{r['tour_code']}** - {r['hotel']} | Deadline in {r['days_left']} days ({r['date']})")