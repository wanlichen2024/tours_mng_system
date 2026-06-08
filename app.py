import streamlit as st
import pandas as pd
from utils.db import supabase
from datetime import date, timedelta
import calendar
import plotly.graph_objects as go

# =====================================
# PAGE CONFIG
# =====================================
st.set_page_config(
    page_title="团队运行日历",
    page_icon="📅",
    layout="wide"
)

st.title("📅 Team Operations Calendar")

# =====================================
# LOAD DATA
# =====================================
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

# =====================================
# CLEAN DATA
# =====================================
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

today = date.today()

# =====================================
# BUILD DAILY COUNTS
# =====================================
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

date_range = pd.date_range(
    start_display,
    end_display,
    freq="D"
)

daily_counts = []

for d in date_range:

    d = d.date()

    count = (
        (
            tours_df["start_date"] <= d
        ) &
        (
            tours_df["end_date"] >= d
        )
    ).sum()

    daily_counts.append(count)

daily_df = pd.DataFrame({
    "Date": date_range,
    "Tours": daily_counts
})

# =====================================
# KPI CARDS
# =====================================
today_count = (
    (
        tours_df["start_date"] <= today
    ) &
    (
        tours_df["end_date"] >= today
    )
).sum()

future_30_count = (
    (
        tours_df["start_date"] <= today + timedelta(days=30)
    ) &
    (
        tours_df["end_date"] >= today
    )
).sum()

peak_row = daily_df.loc[
    daily_df["Tours"].idxmax()
]

peak_day = peak_row["Date"].date()
peak_count = peak_row["Tours"]

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "总团队数",
    len(tours_df)
)

col2.metric(
    "今日运行",
    today_count
)

col3.metric(
    "未来30天运行",
    future_30_count
)

col4.metric(
    "峰值",
    f"{peak_count}团"
)

st.divider()

# =====================================
# TREND CHART
# =====================================
st.subheader("📈 Tour Activity Trend")

st.line_chart(
    daily_df.set_index("Date")["Tours"],
    use_container_width=True
)

st.divider()

# =====================================
# MONTH SELECTOR
# =====================================
month_options = sorted(
    list(
        set(
            daily_df["Date"]
            .dt.strftime("%Y-%m")
        )
    )
)

default_month = today.strftime("%Y-%m")

selected_month = st.selectbox(
    "📅 Select Month",
    month_options,
    index=month_options.index(default_month)
    if default_month in month_options
    else 0
)

selected_year = int(
    selected_month.split("-")[0]
)

selected_month_num = int(
    selected_month.split("-")[1]
)

# =====================================
# MONTH COUNTS
# =====================================
_, num_days = calendar.monthrange(
    selected_year,
    selected_month_num
)

month_days = []

for day in range(1, num_days + 1):

    current_day = date(
        selected_year,
        selected_month_num,
        day
    )

    count = (
        (
            tours_df["start_date"] <= current_day
        ) &
        (
            tours_df["end_date"] >= current_day
        )
    ).sum()

    month_days.append({
        "day": day,
        "count": count,
        "weekday": current_day.weekday()
    })

month_df = pd.DataFrame(month_days)

# =====================================
# CALENDAR MATRIX
# =====================================
weeks = []

week = [None] * 7

for _, row in month_df.iterrows():

    weekday = row["weekday"]

    week[weekday] = row["count"]

    if weekday == 6:
        weeks.append(week)
        week = [None] * 7

if any(x is not None for x in week):
    weeks.append(week)

heatmap_df = pd.DataFrame(weeks)

# =====================================
# HEATMAP
# =====================================
st.subheader(
    f"📅 {selected_month} Calendar Heatmap"
)

fig = go.Figure(
    data=go.Heatmap(
        z=heatmap_df.values,
        x=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],
        y=[
            f"Week {i+1}"
            for i in range(len(heatmap_df))
        ],
        hoverongaps=False,
        colorscale="Blues",
        colorbar=dict(
            title="Tours"
        )
    )
)

fig.update_layout(
    height=450,
    margin=dict(
        l=20,
        r=20,
        t=30,
        b=20
    )
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# =====================================
# BUSIEST DAYS
# =====================================
st.divider()

st.subheader("🔥 Busiest Days")

busy_df = daily_df.sort_values(
    "Tours",
    ascending=False
).head(10)

busy_df["Date"] = busy_df["Date"].dt.strftime(
    "%d %b %Y"
)

st.dataframe(
    busy_df,
    use_container_width=True,
    hide_index=True
)