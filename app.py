import streamlit as st
import pandas as pd
from utils.db import supabase
from datetime import date, timedelta
import calendar

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="团队运行日历",
    page_icon="📅",
    layout="wide"
)

st.title("📅 Team Operations Calendar")

# ==========================================
# LOAD DATA
# ==========================================
tours_resp = (
    supabase
    .table("tours")
    .select("tour_code,start_date,end_date")
    .execute()
)

tours_df = pd.DataFrame(tours_resp.data)

if tours_df.empty:
    st.info("暂无团队数据")
    st.stop()

# ==========================================
# CLEAN DATA
# ==========================================
tours_df["start_date"] = pd.to_datetime(
    tours_df["start_date"]
).dt.date

tours_df["end_date"] = pd.to_datetime(
    tours_df["end_date"]
).dt.date

tours_df = tours_df.dropna(
    subset=["start_date", "end_date"]
)

if tours_df.empty:
    st.info("暂无有效团队数据")
    st.stop()

# ==========================================
# DATE RANGE
# ==========================================
today = date.today()

min_date = min(tours_df["start_date"])
max_date = max(tours_df["end_date"])

start_display = min(
    min_date,
    today - timedelta(days=30)
)

end_display = max(
    max_date,
    today + timedelta(days=180)
)

# ==========================================
# DAILY COUNTS
# ==========================================
date_list = pd.date_range(
    start_display,
    end_display,
    freq="D"
)

daily_counts = []

for d in date_list:
    current_date = d.date()

    count = (
        (
            tours_df["start_date"] <= current_date
        ) &
        (
            tours_df["end_date"] >= current_date
        )
    ).sum()

    daily_counts.append(count)

daily_df = pd.DataFrame({
    "Date": date_list,
    "Tours": daily_counts
})

# ==========================================
# KPI SECTION
# ==========================================
today_count = (
    (
        tours_df["start_date"] <= today
    ) &
    (
        tours_df["end_date"] >= today
    )
).sum()

future_30 = (
    (
        tours_df["start_date"] <= today + timedelta(days=30)
    ) &
    (
        tours_df["end_date"] >= today
    )
).sum()

peak_idx = daily_df["Tours"].idxmax()

peak_day = daily_df.loc[peak_idx, "Date"].date()
peak_count = daily_df.loc[peak_idx, "Tours"]

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "总团队数",
        len(tours_df)
    )

with col2:
    st.metric(
        "今日运行",
        today_count
    )

with col3:
    st.metric(
        "未来30天运行",
        future_30
    )

with col4:
    st.metric(
        "峰值",
        f"{peak_count}团"
    )

# ==========================================
# TREND CHART
# ==========================================
st.markdown("### 📈 Team Activity Trend")

chart_df = daily_df.copy()
chart_df = chart_df.set_index("Date")

st.line_chart(
    chart_df["Tours"],
    use_container_width=True
)

st.divider()

# ==========================================
# MONTH SELECTOR
# ==========================================
months = sorted(
    list(
        set(
            (
                d.year,
                d.month
            )
            for d in date_list
        )
    )
)

month_options = [
    f"{y}-{m:02d}"
    for y, m in months
]

selected_month = st.selectbox(
    "📅 Select Month",
    month_options,
    index=max(
        0,
        month_options.index(
            f"{today.year}-{today.month:02d}"
        )
        if f"{today.year}-{today.month:02d}"
        in month_options
        else 0
    )
)

selected_year = int(
    selected_month.split("-")[0]
)

selected_month_num = int(
    selected_month.split("-")[1]
)

# ==========================================
# BUILD MONTH DATA
# ==========================================
month_counts = {}

month_dates = pd.date_range(
    date(selected_year, selected_month_num, 1),
    date(
        selected_year,
        selected_month_num,
        calendar.monthrange(
            selected_year,
            selected_month_num
        )[1]
    )
)

for d in month_dates:

    current_date = d.date()

    count = (
        (
            tours_df["start_date"] <= current_date
        ) &
        (
            tours_df["end_date"] >= current_date
        )
    ).sum()

    month_counts[current_date.day] = count

# ==========================================
# LEGEND
# ==========================================
st.markdown("""
<div style="display:flex; gap:20px; margin-bottom:15px;">
<div>⚪ 0团</div>
<div>🔹 1-2团</div>
<div>🔷 3-5团</div>
<div>🔵 6+团</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# CALENDAR CSS
# ==========================================
st.markdown("""
<style>

.calendar-grid {
    display:grid;
    grid-template-columns:repeat(7,1fr);
    gap:8px;
}

.weekday {
    text-align:center;
    font-weight:600;
    padding:8px;
}

.day-card {
    min-height:90px;
    border-radius:12px;
    padding:10px;
    text-align:center;
    box-shadow:0 1px 4px rgba(0,0,0,0.08);
    transition:0.2s;
}

.day-card:hover {
    transform:translateY(-2px);
}

.today {
    border:3px solid #2563eb;
}

.empty {
    min-height:90px;
}

</style>
""", unsafe_allow_html=True)

# ==========================================
# CALENDAR HEADER
# ==========================================
weekdays = [
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun"
]

html = '<div class="calendar-grid">'

for day in weekdays:
    html += f"""
    <div class="weekday">
        {day}
    </div>
    """

# ==========================================
# BLANK DAYS
# ==========================================
first_day_weekday = date(
    selected_year,
    selected_month_num,
    1
).weekday()

for _ in range(first_day_weekday):
    html += '<div class="empty"></div>'

# ==========================================
# DAY CARDS
# ==========================================
_, num_days = calendar.monthrange(
    selected_year,
    selected_month_num
)

for day in range(1, num_days + 1):

    cnt = month_counts.get(day, 0)

    current_day = date(
        selected_year,
        selected_month_num,
        day
    )

    if cnt == 0:
        bg = "#f3f4f6"

    elif cnt <= 2:
        bg = "#dbeafe"

    elif cnt <= 5:
        bg = "#93c5fd"

    else:
        bg = "#2563eb"

    today_class = ""

    if current_day == today:
        today_class = "today"

    html += f"""
    <div
        class="day-card {today_class}"
        style="background:{bg};"
        title="{current_day} | {cnt} Tours"
    >
        <div style="
            font-size:20px;
            font-weight:700;
        ">
            {day}
        </div>

        <div style="
            margin-top:8px;
            font-size:14px;
        ">
            {cnt}团
        </div>
    </div>
    """

html += "</div>"

st.markdown(
    html,
    unsafe_allow_html=True
)