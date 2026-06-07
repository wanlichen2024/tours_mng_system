import streamlit as st
import pandas as pd
from utils.db import supabase
from datetime import datetime, timedelta, date
import calendar

st.set_page_config(page_title="团队日历", layout="wide")
st.title("📅 团队运行日历")

tours_resp = supabase.table("tours").select("tour_code", "start_date", "end_date").execute()
tours_df = pd.DataFrame(tours_resp.data)

if tours_df.empty:
    st.info("暂无团队数据。")
    st.stop()

# 转换为 date 对象
tours_df['start_date'] = pd.to_datetime(tours_df['start_date']).dt.date
tours_df['end_date'] = pd.to_datetime(tours_df['end_date']).dt.date

# 有效团队
tours_df = tours_df.dropna(subset=['start_date', 'end_date'])
st.write(f"有效团队数: {len(tours_df)}")

if tours_df.empty:
    st.stop()

min_date = min(tours_df['start_date'])
max_date = max(tours_df['end_date'])
today = date.today()
start_display = min(min_date, today - timedelta(days=30))
end_display = max(max_date, today + timedelta(days=180))

# 生成日期列表
current = start_display
date_list = []
while current <= end_display:
    date_list.append(current)
    current += timedelta(days=1)

# 计算每日团队数
counts = []
for d in date_list:
    cnt = ((tours_df['start_date'] <= d) & (tours_df['end_date'] >= d)).sum()
    counts.append(cnt)

# 构建日历数据
calendar_data = {}
for d, cnt in zip(date_list, counts):
    key = (d.year, d.month)
    if key not in calendar_data:
        calendar_data[key] = {}
    calendar_data[key][d.day] = cnt

# 显示日历
for (year, month) in sorted(calendar_data.keys()):
    st.subheader(f"{year}年{month}月")
    first_day_weekday = date(year, month, 1).weekday()
    _, num_days = calendar.monthrange(year, month)
    day_counts = calendar_data[(year, month)]
    
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    html = '<table style="width:100%; border-collapse: collapse; text-align: center;">'
    html += '<tr>' + ''.join([f'<th style="border:1px solid #ddd; padding:8px;">{day}</th>' for day in weekdays]) + '</tr>'
    
    row = []
    for _ in range(first_day_weekday):
        row.append('<td style="border:1px solid #ddd; padding:8px;"></td>')
    for day in range(1, num_days+1):
        cnt = day_counts.get(day, 0)
        if cnt == 0:
            bg = "#d4edda"
            color = "black"
        elif cnt <= 2:
            bg = "#fff3cd"
            color = "black"
        else:
            bg = "#f8d7da"
            color = "red"
        cell = f'<td style="border:1px solid #ddd; padding:8px; background-color:{bg}; color:{color};">{day}<br><small>{cnt}团</small></td>'
        row.append(cell)
        if len(row) == 7:
            html += '<tr>' + ''.join(row) + '</tr>'
            row = []
    if row:
        while len(row) < 7:
            row.append('<td style="border:1px solid #ddd; padding:8px;"></td>')
        html += '<tr>' + ''.join(row) + '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)