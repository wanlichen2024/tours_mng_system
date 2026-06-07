# pages/email_draft.py
import streamlit as st
import pandas as pd
import pyperclip


st.subheader("📧 Generate Email Drafts from CSV")
st.markdown("""
    **Select email type and upload a CSV file.**  
    The CSV should follow the required column structure for each type.
    """)

email_type = st.selectbox("Email Type", [
        "Chinese Meal (订中餐)",
        "Western Meal (订西餐)",
        "Attraction New Booking (景点新预定)",
        "Attraction Amendment (景点Amend)",
        "Hotel Room List (酒店名单)",
        "Hotel Amendment (酒店Amendment)",
        "Attraction Reconfirm (景点Reconfirm)"
    ])

uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])

if uploaded_file is not None:
        df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
        st.write("Preview (first 5 rows):")
        st.dataframe(df.head())
        
        # 调试：显示列名
        st.caption(f"Detected columns: {list(df.columns)}")
        
        # 自动从文件名提取 tour_code（取第一个空格前的部分）
        tour_code = uploaded_file.name.replace(".csv", "").split(" ")[0]
        st.info(f"Tour Code extracted: {tour_code}")
        
        year = 2026
        emails = []
        success = True

        try:
            if email_type == "Chinese Meal (订中餐)":
                required = ['Restaurant', 'Date', 'Time', 'Product', 'No. of Pax']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing columns: {missing}")
                    success = False
                else:
                    for _, row in df.iterrows():
                        time_str = str(row['Time']).replace('#', '').strip()
                        date_clean = str(row['Date']).strip()
                        if "2026" in date_clean:
                            date_str = f"{time_str} at {date_clean}"
                        else:
                            date_str = f"{time_str} at {date_clean} {year}"
                        pax = str(row['No. of Pax']).strip() if pd.notna(row['No. of Pax']) else "N/A"
                        email = f"""
Restaurant: ********{row['Restaurant']}*******

Hello, 请订餐:

Tour code: {tour_code}
Date: {date_str}
Product: {row['Product']}
Pax: {pax}

"""
                        emails.append(email)

            elif email_type == "Western Meal (订西餐)":
                required = ['Restaurant', 'Date', 'Time', 'Product', 'No. of Pax']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing columns: {missing}")
                    success = False
                else:
                    for _, row in df.iterrows():
                        time_str = str(row['Time']).replace('#', '').strip()
                        date_clean = str(row['Date']).strip()
                        if str(year) in date_clean:
                            date_time_str = f"{time_str} at {date_clean}"
                        else:
                            date_time_str = f"{time_str} at {date_clean} {year}"
                        pax = str(row['No. of Pax']).strip() if pd.notna(row['No. of Pax']) else "N/A"
                        email = f"""
Restaurant: ********{row['Restaurant']}*******

Subject: {tour_code} New Booking - {row['Restaurant']}

Dear reservation,

Please kindly process the below new booking.
I look forward to your confirmation.

Tour code: {tour_code}
Date and Time: {date_time_str}
Product: {row['Product']}
Pax: {pax}

Best regards

"""
                        emails.append(email)

            elif email_type == "Attraction New Booking (景点新预定)":
                required = ['Attraction', 'Date', 'Time', 'Product', 'No. of Pax']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing columns: {missing}")
                    success = False
                else:
                    for _, row in df.iterrows():
                        time_str = str(row['Time']).replace('#', '').strip()
                        date_clean = str(row['Date']).strip()
                        if str(year) in date_clean:
                            date_time_str = f"{time_str} at {date_clean}"
                        else:
                            date_time_str = f"{time_str} at {date_clean} {year}"
                        pax = str(row['No. of Pax']).strip() if pd.notna(row['No. of Pax']) else "N/A"
                        email = f"""
Company: ********{row['Attraction']}*******

Subject: {tour_code} New Booking - {row['Attraction']}

Dear reservation,

Please kindly process the below new booking.
I look forward to your confirmation.

Tour code: {tour_code}
Date and Time: {date_time_str}
Product: {row['Product']}
Pax: {pax}

Best regards

"""
                        emails.append(email)

            elif email_type == "Attraction Amendment (景点Amend)":
                required = ['Attraction', 'Date', 'Time', 'Product', 'No. of Pax', 'Reference']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing columns: {missing}")
                    success = False
                else:
                    for _, row in df.iterrows():
                        time_str = str(row['Time']).replace('#', '').strip()
                        date_clean = str(row['Date']).strip()
                        if str(year) in date_clean:
                            date_time_str = f"{time_str} at {date_clean}"
                        else:
                            date_time_str = f"{time_str} at {date_clean} {year}"
                        pax = str(row['No. of Pax']).strip() if pd.notna(row['No. of Pax']) else "N/A"
                        email = f"""
Company: ********{row['Attraction']}*******

Subject: {tour_code} Amendment - {row['Attraction']}

Dear reservation,

Please kindly amend the below booking.
I look forward to your confirmation.

Tour code: {tour_code}
Reference: {row['Reference']}
Date and Time: {date_time_str}
Product: {row['Product']}
Pax: {pax}

Best regards

"""
                        emails.append(email)

            elif email_type == "Hotel Room List (酒店名单)":
                required = ['Hotel', 'Date', 'No. of Room', 'Product', 'Reference']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing columns: {missing}")
                    success = False
                else:
                    # 处理日期列
                    df['Date_full'] = df['Date'].astype(str).apply(lambda x: x if str(year) in x else f"{x} {year}")
                    df['Date_dt'] = pd.to_datetime(df['Date_full'], dayfirst=True, errors='coerce')
                    df = df.sort_values('Date_dt')
                    df['Ref_tmp'] = df['Reference'].fillna('')
                    df.loc[df['Ref_tmp'] == '', 'Ref_tmp'] = df['Hotel'] + "_" + df['No. of Room'].astype(str)
                    grouped = df.groupby('Ref_tmp')
                    for ref, group in grouped:
                        group_sorted = group.sort_values('Date_dt')
                        check_in = group_sorted['Date_dt'].iloc[0]
                        check_out = group_sorted['Date_dt'].iloc[-1] + pd.Timedelta(days=1)
                        room_type = " + ".join(group_sorted['No. of Room'].dropna().astype(str).unique())
                        reference = group_sorted['Reference'].iloc[0] if pd.notna(group_sorted['Reference'].iloc[0]) else "N/A"
                        hotel_name = group_sorted['Hotel'].iloc[0]
                        product = group_sorted['Product'].iloc[0]
                        email = f"""
Subject: {tour_code} Room list - {hotel_name}

Dear reservation,

Please kindly find the below room list.
I look forward to your confirmation.

Tour code: {tour_code}
Check in: {check_in.strftime('%d %B %Y')}
Check out: {check_out.strftime('%d %B %Y')}
Item : {product}
Reference: {reference}
Room Type: {room_type}

"""
                        emails.append(email)

            elif email_type == "Hotel Amendment (酒店Amendment)":
                required = ['Hotel', 'Date', 'No. of Room', 'Product', 'Reference']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing columns: {missing}")
                    success = False
                else:
                    df['Date_full'] = df['Date'].astype(str).apply(lambda x: x if str(year) in x else f"{x} {year}")
                    df['Date_dt'] = pd.to_datetime(df['Date_full'], dayfirst=True, errors='coerce')
                    df = df.sort_values('Date_dt')
                    df['Ref_tmp'] = df['Reference'].fillna('')
                    df.loc[df['Ref_tmp'] == '', 'Ref_tmp'] = df['Hotel'] + "_" + df['No. of Room'].astype(str)
                    grouped = df.groupby('Ref_tmp')
                    for ref, group in grouped:
                        group_sorted = group.sort_values('Date_dt')
                        check_in = group_sorted['Date_dt'].iloc[0]
                        check_out = group_sorted['Date_dt'].iloc[-1] + pd.Timedelta(days=1)
                        room_type = " + ".join(group_sorted['No. of Room'].dropna().astype(str).unique())
                        reference = group_sorted['Reference'].iloc[0] if pd.notna(group_sorted['Reference'].iloc[0]) else "N/A"
                        hotel_name = group_sorted['Hotel'].iloc[0]
                        product = group_sorted['Product'].iloc[0]
                        email = f"""
Subject: {tour_code} Amendment - {hotel_name}

Dear reservation:

Please kindly amend the below booking.
I look forward to your confirmation.

Tour code: {tour_code}
Check in: {check_in.strftime('%d %B %Y')}
Check out: {check_out.strftime('%d %B %Y')}
Reference: {reference}
Room Type: {room_type}

Best regards

"""
                        emails.append(email)

            elif email_type == "Attraction Reconfirm (景点Reconfirm)":
                required = ['Attraction', 'Date', 'Time', 'Product', 'No. of Pax', 'Reference']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing columns: {missing}")
                    success = False
                else:
                    for _, row in df.iterrows():
                        time_str = str(row['Time']).replace('#', '').strip()
                        date_clean = str(row['Date']).strip()
                        if str(year) in date_clean:
                            date_time_str = f"{time_str} at {date_clean}"
                        else:
                            date_time_str = f"{time_str} at {date_clean} {year}"
                        pax = str(row['No. of Pax']).strip() if pd.notna(row['No. of Pax']) else "N/A"
                        email = f"""
Company: ********{row['Attraction']}*******

Subject: {tour_code} Reconfirm - {row['Attraction']}

Dear reservation,

Please kindly reconfirm the below booking detail.
I look forward to your confirmation.

Tour code: {tour_code}
Reference: {row['Reference']}
Date and Time: {date_time_str}
Product: {row['Product']}
Pax: {pax}

Best regards

"""
                        emails.append(email)

        except Exception as e:
            st.error(f"Error processing file: {e}")
            success = False

        if success and emails:
            st.success(f"Generated {len(emails)} email(s).")
            with st.expander("View generated emails"):
                for i, email in enumerate(emails):
                    st.code(email, language='text')
                    if st.button(f"Copy email {i+1}", key=f"copy_{i}"):
                        pyperclip.copy(email)
                        st.success(f"Email {i+1} copied to clipboard")
            all_emails_text = "\n" + "="*50 + "\n".join(emails)
            st.download_button(
                label="📥 Download all emails as .txt",
                data=all_emails_text,
                file_name=f"{email_type.replace(' ', '_')}_{tour_code}.txt",
                mime="text/plain"
            )
        elif success and not emails:
            st.warning("No valid data found in CSV. Check column names or data content.")