"""Operations Toolkit — 入口页（只负责导航，不放业务逻辑）。

替换你原来的 app.py（那个日历页）。
日历代码建议移到 archive/calendar.py，不要放在 pages/ 下，否则会被多页框架当成页面。
"""
import streamlit as st

st.set_page_config(
    page_title="Operations Toolkit",
    page_icon="🧭",
    layout="wide",
)

pages = [
    st.Page("pages/email_draft.py", title="Email Draft", icon="📧", default=True),
    st.Page("pages/final_check.py", title="Final Check", icon="🧭"),
]

st.navigation(pages).run()