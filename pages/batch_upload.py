import streamlit as st
import pandas as pd
import time
from utils.helpers import insert_bookings_batch

st.subheader("📤 Batch Upload Bookings")
template_cols = ['tour_code', 'city', 'check_in_date', 'end_date', 'time', 'pax', 'rooms',
                 'product_type', 'reference', 'business_name', 'note', 'category', 'contact', 'email', 'days_advance_notice']
template_df = pd.DataFrame(columns=template_cols)
template_df.loc[0] = ['JCE2401', 'Rotorua', '03/07/2026', '04/07/2026', '13:30', '20', '10',
                      'BB', '', 'Sudima Hotel', '', 'hotel', 'wechat123', 'hotel@example.com', 32]
csv_data = template_df.to_csv(index=False).encode('utf-8')
st.download_button("📥 Download CSV Template", csv_data, "bookings_template.csv", "text/csv")
st.markdown("---")

uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["xlsx", "xls", "csv"])
if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(uploaded_file, dtype=str)
    st.write("Preview (first 5 rows):")
    st.dataframe(df.head())
    if st.button("Confirm Import"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        try:
            status_text.text("Processing data...")
            progress_bar.progress(30)
            count = insert_bookings_batch(df, st)
            progress_bar.progress(100)
            status_text.text("Import completed!")
            st.success(f"✅ Successfully imported/updated {count} records")
            st.balloons()
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"❌ Import failed: {e}")
        finally:
            # 无论成功或失败，都清空进度条和状态文本
            if 'progress_bar' in locals():
                progress_bar.empty()
            if 'status_text' in locals():
                status_text.empty()