import streamlit as st
from supabase import create_client
import pandas as pd

# 从 secrets 中读取 Supabase 配置（注意键名必须与 secrets.toml 完全一致）
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_bookings(tour_code=None):
    query = supabase.table("bookings").select("*")
    if tour_code:
        query = query.eq("tour_code", tour_code)
    response = query.execute()
    return pd.DataFrame(response.data)