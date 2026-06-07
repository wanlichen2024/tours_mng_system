import streamlit as st
from supabase import create_client
import pandas as pd

SUPABASE_URL = st.secrets["https://qhxepqgritemabnkians.supabase.co"]
SUPABASE_KEY = st.secrets["sb_publishable_xzbwJgwT5jpgYryxkDq5bA_CXBQ-XbZ"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_bookings(tour_code=None):
    query = supabase.table("bookings").select("*")
    if tour_code:
        query = query.eq("tour_code", tour_code)
    response = query.execute()
    return pd.DataFrame(response.data)