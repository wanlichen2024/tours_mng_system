import os
import json
import gspread
import pandas as pd
from supabase import create_client
from google.oauth2.service_account import Credentials
import re
from datetime import datetime

# 从环境变量读取配置
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GDRIVE_CREDENTIALS = os.environ["GDRIVE_CREDENTIALS"]
SHEET_URL = os.environ["SHEET_URL"]

# 初始化 Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 初始化 Google Sheets
creds_dict = json.loads(GDRIVE_CREDENTIALS)
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
gc = gspread.authorize(creds)

# 打开工作表
sh = gc.open_by_url(SHEET_URL)

def clean_bookings_df(df):
    df = df.replace({pd.NA: None, float('nan'): None, '': None})
    if 'tour_code' in df.columns:
        df['tour_code'] = df['tour_code'].fillna('MISSING_CODE')
    if 'business_name' in df.columns:
        df['business_name'] = df['business_name'].fillna('MISSING_SUPPLIER')
    if 'check_in_date' in df.columns:
        df['check_in_date'] = df['check_in_date'].fillna('1900-01-01')
    if 'category' in df.columns:
        df['category'] = df['category'].astype(str).str.lower()
        valid_cats = ['hotel', 'attraction', 'restaurant']
        df.loc[~df['category'].isin(valid_cats), 'category'] = 'unknown'
    if 'pax' in df.columns:
        df['pax'] = df['pax'].astype(str).replace('nan', None).replace('None', None)
    if 'rooms' in df.columns:
        df['rooms'] = pd.to_numeric(df['rooms'], errors='coerce').astype('Int64')
    for col in ['check_in_date', 'end_date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
    if 'time' in df.columns:
        def fix_time(t):
            if not isinstance(t, str):
                return t
            return t.replace('：', ':').strip()
        df['time'] = df['time'].astype(str).apply(lambda x: fix_time(x) if x != 'None' else None)
        pattern = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')
        df.loc[~df['time'].apply(lambda x: bool(pattern.match(str(x))) if x else True), 'time'] = None
    if 'days_advance_notice' not in df.columns:
        df['days_advance_notice'] = 32
    else:
        df['days_advance_notice'] = pd.to_numeric(df['days_advance_notice'], errors='coerce').fillna(32).astype(int)
    # 移除 id, created_at 等自动字段
    for col in ['id', 'created_at']:
        if col in df.columns:
            df = df.drop(columns=[col])
    return df

def clean_tours_df(df):
    df = df.replace({pd.NA: None, float('nan'): None, '': None})
    if 'tour_code' in df.columns:
        df['tour_code'] = df['tour_code'].fillna('MISSING_CODE')
    for col in ['start_date', 'end_date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
    numeric_cols = ['adult_pax', 'child_pax', 'rooms']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    text_cols = ['tour_leader', 'guide_name', 'guide_phone', 'driver_name', 'route_type', 'route_name', 'notes']
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).replace('nan', None).replace('None', None)
    for col in ['id', 'created_at']:
        if col in df.columns:
            df = df.drop(columns=[col])
    return df

def sync_bookings():
    try:
        ws = sh.worksheet("bookings")
        data = ws.get_all_records()
        if not data:
            print("No bookings data found in sheet 'bookings'")
            return
        df = pd.DataFrame(data)
        df = clean_bookings_df(df)
        records = df.to_dict(orient='records')
        key_cols = ['tour_code', 'category', 'business_name', 'check_in_date']
        if records:
            supabase.table("bookings").upsert(records, on_conflict=','.join(key_cols)).execute()
            print(f"Synced {len(records)} bookings")
    except Exception as e:
        print(f"Error syncing bookings: {e}")

def sync_tours():
    try:
        ws = sh.worksheet("tours")
        data = ws.get_all_records()
        if not data:
            print("No tours data found in sheet 'tours'")
            return
        df = pd.DataFrame(data)
        df = clean_tours_df(df)
        records = df.to_dict(orient='records')
        if records:
            supabase.table("tours").upsert(records, on_conflict="tour_code").execute()
            print(f"Synced {len(records)} tours")
    except Exception as e:
        print(f"Error syncing tours: {e}")

if __name__ == "__main__":
    sync_bookings()
    sync_tours()
    print("Sync completed")