import pandas as pd
import re
from datetime import datetime
from utils.db import supabase  # 导入数据库连接

def fix_time_format(time_str):
    if not isinstance(time_str, str):
        return time_str
    return time_str.replace('：', ':').strip()

def clean_display_value(val, default=''):
    if pd.isna(val) or val is None:
        return default
    if isinstance(val, str):
        if val == 'MISSING_SUPPLIER' or val == 'MISSING_CODE':
            return default
        return val
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    return str(val)

def ensure_tour_exists(tour_code, start_date=None, end_date=None):
    """确保 tours 表中存在该团号，如果没有则创建记录（至少包含团号和起止日期）"""
    existing = supabase.table("tours").select("tour_code").eq("tour_code", tour_code).execute()
    if not existing.data:
        data = {"tour_code": tour_code}
        if start_date:
            data["start_date"] = start_date
        if end_date:
            data["end_date"] = end_date
        supabase.table("tours").insert(data).execute()
        print(f"Created tour record for {tour_code}")
    else:
        # 可选：更新起止日期（如果新日期范围更大或更小）
        if start_date and end_date:
            # 查询现有日期
            existing_tour = supabase.table("tours").select("start_date", "end_date").eq("tour_code", tour_code).execute()
            if existing_tour.data:
                old_start = existing_tour.data[0].get("start_date")
                old_end = existing_tour.data[0].get("end_date")
                # 如果新开始日期更早，则更新；如果新结束日期更晚，则更新
                update_data = {}
                if old_start is None or start_date < old_start:
                    update_data["start_date"] = start_date
                if old_end is None or end_date > old_end:
                    update_data["end_date"] = end_date
                if update_data:
                    supabase.table("tours").update(update_data).eq("tour_code", tour_code).execute()

def insert_bookings_batch(df, st):
    df = df.copy()
    required_cols = ['tour_code', 'category', 'business_name', 'check_in_date', 'reference']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    key_cols = ['tour_code', 'category', 'business_name', 'check_in_date']
    original_len = len(df)
    df = df.drop_duplicates(subset=key_cols, keep='last')
    if len(df) < original_len:
        st.warning(f"⚠️ Found {original_len - len(df)} duplicate records, kept last one.")

    df = df.replace({pd.NA: None, float('nan'): None, '': None})
    df['tour_code'] = df['tour_code'].fillna('MISSING_CODE')
    df['business_name'] = df['business_name'].fillna('MISSING_SUPPLIER')
    df['check_in_date'] = df['check_in_date'].fillna('1900-01-01')
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
        df['time'] = df['time'].astype(str).apply(lambda x: fix_time_format(x) if x != 'None' else None)
        pattern = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')
        df.loc[~df['time'].apply(lambda x: bool(pattern.match(str(x))) if x else True), 'time'] = None

    if 'days_advance_notice' not in df.columns:
        df['days_advance_notice'] = 32
    else:
        df['days_advance_notice'] = pd.to_numeric(df['days_advance_notice'], errors='coerce').fillna(32).astype(int)

    # ========== 关键：在插入 bookings 前，确保 tours 表中有对应团号 ==========
    for tour_code, group in df.groupby('tour_code'):
        # 计算该团的最早和最晚 check_in_date
        valid_dates = pd.to_datetime(group['check_in_date'], errors='coerce').dropna()
        if not valid_dates.empty:
            start_date = valid_dates.min().strftime('%Y-%m-%d')
            end_date = valid_dates.max().strftime('%Y-%m-%d')
        else:
            start_date = end_date = None
        ensure_tour_exists(tour_code, start_date, end_date)

    records = df.to_dict(orient='records')
    for rec in records:
        for k, v in rec.items():
            if pd.isna(v):
                rec[k] = None
            elif isinstance(v, (pd.Timestamp, datetime)):
                rec[k] = v.strftime('%Y-%m-%d')

    for rec in records:
        if rec.get('tour_code') is None:
            rec['tour_code'] = 'MISSING_CODE'
        if rec.get('business_name') is None:
            rec['business_name'] = 'MISSING_SUPPLIER'
        if rec.get('check_in_date') is None:
            rec['check_in_date'] = '1900-01-01'
        if rec.get('days_advance_notice') is None:
            rec['days_advance_notice'] = 32

    if not records:
        st.warning("No valid data to import.")
        return 0

    result = supabase.table("bookings").upsert(records, on_conflict=','.join(key_cols)).execute()
    return len(result.data)