import streamlit as st
from utils.db import get_bookings

st.subheader("📋 All Booking Records")
df = get_bookings()
if df.empty:
    st.info("No data available. Please upload via Batch Upload.")
else:
    st.dataframe(df, use_container_width=True)