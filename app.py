import streamlit as st
import pandas as pd
from utils.db import supabase
from datetime import date, timedelta
import calendar

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="Team Calendar",
    page_icon="📅",
    layout="wide"
)

st.title("📅 Team Operations Calendar")

# ==================================================
# LOAD DATA
# ==================================================
response = (
    supabase
    .table("tours")
    .select("tour_code,start_date,end_date")
    .execute()
)

tours_df = pd.DataFrame(response.data)

if tours_df.empty:
    st.info("No tour data found.")
    st.stop()

tours_df["start_date"] = pd.to_datetime(
    tours_df["start_date"]
).dt.date

tours_df["end_date"] = pd.to_datetime(
    tours_df["end_date"]
).dt.date

tours_df = tours_df.dropna(
    subset=["start_date", "end_date"]
)

today = date.today()

# ==================================================
# KPI SECTION
# ==================================================
today_running = (
    (
        tours_df["start_date"] <= today
    ) &
    (
        tours_df["end_date"] >= today
    )
).sum()

next_30_days = (
    (
        tours_df["start_date"] <= today + timedelta(days=30)
    ) &
    (
        tours_df["end_date"] >= today
    )
).sum()

# calculate daily counts
date_range = pd.date_range(
    tours_df["start_date"].min(),
    tours_df["end_date"].max(),
    freq="D"
)

daily_counts = []

for d in date_range:

    current_day = d.date()

    count = (
        (
            tours_df["start_date"] <= current_day
        ) &
        (
            tours_df["end_date"] >= current_day
        )
    ).sum()

    daily_counts.append(count)

daily_df = pd.DataFrame({
    "Date": date_range,
    "Tours": daily_counts
})

peak_row = daily_df.loc[
    daily_df["Tours"].idxmax()
]

peak_day = peak_row["Date"].strftime(
    "%d %b %Y"
)

peak_count = peak_row["Tours"]

# ==================================================
# KPI CARDS
# ==================================================
c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Tours",
    len(tours_df)
)

c2.metric(
    "Running Today",
    today_running
)

c3.metric(
    "Next 30 Days",
    next_30_days
)

c4.metric(
    "Peak Day",
    f"{peak_count} Tours"
)

st.divider()

# ==================================================
# TREND
# ==================================================
st.subheader("📈 Tour Activity Trend")

chart_df = daily_df.copy()
chart_df = chart_df.set_index("Date")

st.line_chart(
    chart_df["Tours"],
    use_container_width=True
)

st.divider()

# ==================================================
# MONTH SELECTOR
# ==================================================
available_months = sorted(
    list(
        set(
            daily_df["Date"]
            .dt.strftime("%Y-%m")
        )
    )
)

current_month = today.strftime("%Y-%m")

selected_month = st.selectbox(
    "Select Month",
    available_months,
    index=available_months.index(current_month)
    if current_month in available_months
    else 0
)

year = int(
    selected_month.split("-")[0]
)

month = int(
    selected_month.split("-")[1]
)

st.subheader(
    f"📅 {calendar.month_name[month]} {year}"
)

# ==================================================
# WEEKDAY HEADER
# ==================================================
headers = st.columns(7)

weekdays = [
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun"
]

for i, day_name in enumerate(weekdays):
    headers[i].markdown(
        f"**{day_name}**"
    )

# ==================================================
# MONTH DATA
# ==================================================
first_weekday, num_days = calendar.monthrange(
    year,
    month
)

cells = []

for _ in range(first_weekday):
    cells.append(None)

for day in range(1, num_days + 1):
    cells.append(day)

while len(cells) % 7 != 0:
    cells.append(None)

# ==================================================
# CALENDAR GRID
# ==================================================
selected_date = None

for week_start in range(
    0,
    len(cells),
    7
):

    cols = st.columns(7)

    for i in range(7):

        day = cells[
            week_start + i
        ]

        with cols[i]:

            if day is None:

                st.write("")

            else:

                current_date = date(
                    year,
                    month,
                    day
                )

                count = (
                    (
                        tours_df["start_date"]
                        <= current_date
                    ) &
                    (
                        tours_df["end_date"]
                        >= current_date
                    )
                ).sum()

                if count == 0:
                    icon = "⚪"

                elif count <= 2:
                    icon = "🟢"

                elif count <= 5:
                    icon = "🟡"

                else:
                    icon = "🔴"

                with st.container(
                    border=True
                ):

                    if current_date == today:
                        st.markdown(
                            f"**⭐ {day}**"
                        )
                    else:
                        st.markdown(
                            f"**{day}**"
                        )

                    st.caption(
                        f"{icon} {count} Tours"
                    )

                    if st.button(
                        "View",
                        key=f"{current_date}"
                    ):
                        st.session_state[
                            "selected_date"
                        ] = current_date

# ==================================================
# DAY DETAILS
# ==================================================
if "selected_date" in st.session_state:

    selected_date = st.session_state[
        "selected_date"
    ]

    st.divider()

    st.subheader(
        f"📋 Tours on {selected_date}"
    )

    tours = tours_df[
        (
            tours_df["start_date"]
            <= selected_date
        ) &
        (
            tours_df["end_date"]
            >= selected_date
        )
    ]

    if tours.empty:

        st.info(
            "No tours running."
        )

    else:

        st.success(
            f"{len(tours)} tours running"
        )

        st.dataframe(
            tours[
                [
                    "tour_code",
                    "start_date",
                    "end_date"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )