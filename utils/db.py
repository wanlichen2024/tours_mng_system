import streamlit as st
from supabase import create_client
import pandas as pd

SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_bookings(tour_code=None):
    query = supabase.table("bookings").select("*")
    if tour_code:
        query = query.eq("tour_code", tour_code)
    response = query.execute()
    return pd.DataFrame(response.data)