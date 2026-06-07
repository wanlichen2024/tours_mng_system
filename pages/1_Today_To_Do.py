import streamlit as st
from utils.db import supabase
from datetime import datetime, timedelta
import pandas as pd


st.subheader("📅 Upcoming Hotel Confirmation Deadlines (Next 14 Days)")
resp = supabase.table("bookings").select("*").eq("category", "hotel").is_("reference", "null").execute()
hotels = pd.DataFrame(resp.data)
if hotels.empty:
        st.success("🎉 No pending hotel confirmations. All hotels are confirmed.")
        st.stop()

today = datetime.now().date()
reminders = []
for _, row in hotels.iterrows():
        check_in = pd.to_datetime(row['check_in_date']).date()
        days_notice = row.get('days_advance_notice', 32)
        deadline = check_in - timedelta(days=days_notice)
        days_left = (deadline - today).days
        if 0 <= days_left <= 14:
            reminders.append({
                'date': deadline,
                'tour_code': row['tour_code'],
                'hotel': row['business_name'],
                'city': row.get('city', ''),
                'days_left': days_left,
                'notice_days': days_notice
            })

if not reminders:
    st.info("No deadlines in the next 14 days.")
    st.stop()

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