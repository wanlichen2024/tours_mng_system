import streamlit as st
import pandas as pd
import time
from utils.db import supabase, get_bookings
from utils.helpers import clean_display_value
from utils.excel_export import generate_itinerary_excel

st.subheader("🔍 View Bookings by Tour")

# 获取所有团号（从 bookings 表中提取）
all_tours_resp = supabase.table("bookings").select("tour_code").execute()
tour_list = sorted(set([t['tour_code'] for t in all_tours_resp.data])) if all_tours_resp.data else []
if not tour_list:
    st.info("No tour data yet.")
    st.stop()

selected_tour = st.selectbox("Select Tour Code", tour_list)

# 查询团队主信息（tours 表）
tour_info = supabase.table("tours").select("*").eq("tour_code", selected_tour).execute()
if tour_info.data:
    info = tour_info.data[0]
    st.write(f"**行程日期**: {info.get('start_date', '-')} 至 {info.get('end_date', '-')}  |  **成人数**: {info.get('adult_pax', '-')}  |  **儿童**: {info.get('child_pax', '-')}  |  **房间数**: {info.get('rooms', '-')}")
    st.write(f"**领队**: {info.get('tour_leader', '-')}  |  **导游**: {info.get('guide_name', '-')}  |  **司机**: {info.get('driver_name', '-')}  |  **线路类型**: {info.get('route_type', '-')}  |  **线路名称**: {info.get('route_name', '-')}")
else:
    st.info("该团尚未在团队主表中录入信息，请前往「团队管理」页面补充。")

# 获取该团的预订数据
df = get_bookings(selected_tour)
if df.empty:
    st.info(f"No bookings found for tour {selected_tour}.")
    st.stop()

hotels = df[df['category'] == 'hotel'].copy()
attractions = df[df['category'] == 'attraction'].copy()
meals = df[df['category'] == 'restaurant'].copy()

# 酒店部分（可编辑提前通知天数）
if not hotels.empty:
    st.subheader("🏨 Hotel Bookings")
    hotels_display = hotels.sort_values('check_in_date')
    hotels_display['check_in_date'] = pd.to_datetime(hotels_display['check_in_date']).dt.strftime('%d/%m/%Y')
    if 'end_date' in hotels_display.columns:
        hotels_display['end_date'] = pd.to_datetime(hotels_display['end_date']).dt.strftime('%d/%m/%Y')
    
    if 'id' not in hotels_display.columns:
        st.error("Hotel data missing 'id' column. Please check database.")
    else:
        hotels_display['id'] = hotels_display['id'].astype(str)
        display_hotels = hotels_display[['id', 'city', 'business_name', 'check_in_date', 'end_date', 'rooms', 'product_type', 'reference', 'days_advance_notice']].copy()
        display_hotels.columns = ['ID', 'City', 'Supplier', 'Check-in', 'Check-out', 'Rooms', 'Product', 'Reference', 'Advance Notice (days)']
        display_hotels = display_hotels.fillna('')
        display_hotels.insert(0, '#', range(1, len(display_hotels)+1))
        
        column_config = {
            "#": st.column_config.NumberColumn("#", disabled=True),
            "ID": st.column_config.TextColumn("ID", disabled=True),
            "City": st.column_config.TextColumn("City", disabled=True),
            "Supplier": st.column_config.TextColumn("Supplier", disabled=True),
            "Check-in": st.column_config.TextColumn("Check-in", disabled=True),
            "Check-out": st.column_config.TextColumn("Check-out", disabled=True),
            "Rooms": st.column_config.TextColumn("Rooms", disabled=True),
            "Product": st.column_config.TextColumn("Product", disabled=True),
            "Reference": st.column_config.TextColumn("Reference", disabled=True),
            "Advance Notice (days)": st.column_config.NumberColumn("Advance Notice (days)", min_value=1, step=1),
        }
        
        edited_hotels = st.data_editor(
            display_hotels,
            use_container_width=True,
            key="hotel_editor",
            column_config=column_config,
            hide_index=True,
        )
        
        for _, row in edited_hotels.iterrows():
            hotel_id = row['ID']
            new_days = row['Advance Notice (days)']
            orig_row = display_hotels[display_hotels['ID'] == hotel_id]
            if not orig_row.empty:
                orig_days = orig_row.iloc[0]['Advance Notice (days)']
                if new_days != orig_days:
                    supabase.table("bookings").update({"days_advance_notice": int(new_days)}).eq("id", int(hotel_id)).execute()
                    st.success(f"Updated advance notice for {row['Supplier']} to {new_days} days")
                    time.sleep(0.5)
                    st.rerun()

# 景点部分
if not attractions.empty:
    st.subheader("🎯 Attraction Bookings")
    att_display = attractions.sort_values('check_in_date')
    att_display['check_in_date'] = pd.to_datetime(att_display['check_in_date']).dt.strftime('%d/%m/%Y')
    if 'time' in att_display.columns:
        att_display['time'] = att_display['time'].fillna('')
    display_att = att_display[['city', 'business_name', 'check_in_date', 'time', 'pax', 'product_type', 'reference']].copy()
    display_att.columns = ['City', 'Supplier', 'Date', 'Time', 'Pax', 'Product', 'Reference']
    display_att = display_att.fillna('')
    display_att.reset_index(drop=True, inplace=True)
    display_att.index = display_att.index + 1
    st.dataframe(display_att, use_container_width=True)

# 餐厅部分
if not meals.empty:
    st.subheader("🍽️ Restaurant Bookings")
    meals_display = meals.sort_values('check_in_date')
    meals_display['check_in_date'] = pd.to_datetime(meals_display['check_in_date']).dt.strftime('%d/%m/%Y')
    if 'time' in meals_display.columns:
        meals_display['time'] = meals_display['time'].fillna('')
    display_meals = meals_display[['city', 'business_name', 'check_in_date', 'time', 'pax', 'product_type', 'reference']].copy()
    display_meals.columns = ['City', 'Supplier', 'Date', 'Time', 'Pax', 'Product', 'Reference']
    display_meals = display_meals.fillna('')
    display_meals.reset_index(drop=True, inplace=True)
    display_meals.index = display_meals.index + 1
    st.dataframe(display_meals, use_container_width=True)

# 下载 Excel 行程单
st.markdown("---")
excel_file = generate_itinerary_excel(selected_tour, hotels, attractions, meals)
st.download_button(
    label="📥 Download Excel Itinerary (Printable & Editable)",
    data=excel_file,
    file_name=f"tour_{selected_tour}_itinerary.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help="Download as Excel. Open file, then use Page Layout > Scale to Fit for A4 printing."
)