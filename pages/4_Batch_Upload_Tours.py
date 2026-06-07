import streamlit as st
import pandas as pd
import time
from utils.db import supabase

st.set_page_config(page_title="批量上传团队信息", layout="wide")
st.title("📤 批量上传团队信息")
st.caption("上传 CSV 文件，自动创建或更新 tours 表中的团队记录（基于 tour_code 去重）")

# 模板下载
template_cols = [
    'tour_code', 'start_date', 'end_date', 'adult_pax', 'child_pax', 'rooms',
    'tour_leader', 'guide_name', 'guide_phone', 'driver_name', 'route_type', 'route_name', 'notes'
]
template_df = pd.DataFrame(columns=template_cols)
template_df.loc[0] = [
    'JCE2401', '01/07/2026', '10/07/2026', 20, 2, 11,
    'Li Wei', 'Zhang San', '+64211234567', 'Wang Wu', '系列团', '澳新13天经典', ''
]
csv_data = template_df.to_csv(index=False).encode('utf-8')
st.download_button("📥 下载 CSV 模板", csv_data, "tours_template.csv", "text/csv")
st.markdown("---")

uploaded_file = st.file_uploader("选择 CSV 文件", type=["csv"])
if uploaded_file:
    # 读取时将所有列作为字符串，避免自动转换
    df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
    st.write("预览前5行：")
    st.dataframe(df.head())

    required_cols = ['tour_code', 'start_date', 'end_date']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"缺少必要列：{missing}")
    else:
        df_clean = df.copy()
        # 替换空字符串为 None
        df_clean = df_clean.replace({pd.NA: None, '': None})
        
        # 强制按 DD/MM/YYYY 解析日期，无效则设为 None
        for col in ['start_date', 'end_date']:
            # 先转为字符串，去除前后空格
            date_series = df_clean[col].astype(str).str.strip()
            # 尝试解析，dayfirst=True
            parsed = pd.to_datetime(date_series, dayfirst=True, errors='coerce')
            # 将有效日期格式化为 YYYY-MM-DD
            df_clean[col] = parsed.dt.strftime('%Y-%m-%d')
            df_clean.loc[parsed.isna(), col] = None
        
        # 数字列
        for col in ['adult_pax', 'child_pax', 'rooms']:
            if col in df_clean.columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').astype('Int64')
        
        # 文本列清理
        text_cols = ['tour_leader', 'guide_name', 'guide_phone', 'driver_name', 'route_type', 'route_name', 'notes']
        for col in text_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(str).replace('nan', None).replace('None', None)
        
        # 去重（保留最后一条）
        df_clean = df_clean.drop_duplicates(subset=['tour_code'], keep='last')
        records = df_clean.to_dict(orient='records')
        
        # 最终清理NaN
        for rec in records:
            for k, v in rec.items():
                if isinstance(v, float) and pd.isna(v):
                    rec[k] = None
        
        if st.button("确认导入"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            try:
                inserted = 0
                updated = 0
                for i, rec in enumerate(records):
                    existing = supabase.table("tours").select("tour_code").eq("tour_code", rec['tour_code']).execute()
                    if existing.data:
                        supabase.table("tours").update(rec).eq("tour_code", rec['tour_code']).execute()
                        updated += 1
                    else:
                        supabase.table("tours").insert(rec).execute()
                        inserted += 1
                    progress_bar.progress((i+1)/len(records))
                status_text.text("导入完成！")
                st.success(f"✅ 新增 {inserted} 个团队，更新 {updated} 个团队")
                st.balloons()
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ 导入失败：{e}")
                progress_bar.empty()
                status_text.empty()