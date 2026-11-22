# -*- coding: utf-8 -*-
"""邮件助手：上传导出的未读邮件 → 归类摘要 → 对话追问。

不连 IMAP，不上传服务器：邮件只在本次会话内存里解析。
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd
import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import mail as M  # noqa: E402

st.markdown("""
<style>
  .stTabs [data-baseweb="tab"] {font-size: 0.95rem;}
  div[data-testid="stMetricValue"] {font-size: 1.5rem;}
</style>
""", unsafe_allow_html=True)


def secret(key: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(key, default))
    except Exception:
        return default


with st.sidebar:
    st.markdown("### 🤖 AI 设置")
    api_key = st.text_input("API Key", value=secret("DEEPSEEK_API_KEY"), type="password",
                            key="ma_key")
    base_url = st.text_input("Base URL", value=secret("AI_BASE_URL", "https://api.deepseek.com"),
                             key="ma_base")
    model = st.text_input("模型", value=secret("AI_MODEL", "deepseek-chat"), key="ma_model")
    st.caption("没有 Key 也能看邮件列表，但摘要和对话需要 AI。")

st.title("📥 邮件助手")
st.caption("把网易企业邮箱里「未读邮件」导出后上传，先归类摘要，再直接问。"
           "（网页版：勾选邮件 → 更多 → 导出选中邮件，得到 zip）")

files = st.file_uploader(
    "上传导出的邮件（.eml 或 .zip，可多选）",
    type=["eml", "zip"], accept_multiple_files=True, key="ma_files",
)

sig = tuple(sorted((f.name, f.size) for f in files)) if files else ()
if files and sig != st.session_state.get("ma_sig"):
    parsed: list[M.Mail] = []
    for f in files:
        parsed.extend(M.parse_upload(f.name, f.getvalue(), start=len(parsed) + 1))
    seen, unique = set(), []
    for m in parsed:
        if m.msgid in seen:
            continue
        seen.add(m.msgid)
        unique.append(m)
    M.relabel(unique)
    st.session_state["ma_sig"] = sig
    st.session_state["ma_mails"] = unique
    st.session_state["ma_digest"] = ""
    st.session_state["ma_todos"] = []
    st.session_state["ma_chat"] = []

mails: list[M.Mail] = st.session_state.get("ma_mails", [])

if not mails:
    st.info("还没有邮件。先上传导出的 .zip 或 .eml。")
    with st.expander("没有导出功能？"):
        st.markdown(
            "1. 登录企业邮箱网页版 → 收件箱 → 筛选「未读」\n"
            "2. 全选 → 更多 → 导出选中邮件（得到 zip）\n"
            "3. 直接把这个 zip 拖进来，不用解压"
        )
    st.stop()

c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
c1.metric("邮件", len(mails))
c2.metric("发件人", len({m.sender for m in mails}))
c3.metric("时间跨度", (mails[0].date[:10] + " 起") if mails[0].date else "—")

if not api_key:
    st.warning("未配置 AI Key：可以浏览邮件，但摘要与对话不可用。")

if c4.button("🧠 生成 / 重新生成摘要", type="primary", use_container_width=True):
    with st.spinner("正在归类…"):
        try:
            res = M.analyze(mails, api_key, base_url, model)
            st.session_state["ma_digest"] = res.get("digest", "")
            st.session_state["ma_todos"] = res.get("todos", [])
            st.session_state["ma_mails"] = mails
            st.session_state["ma_chat"] = []
        except Exception as e:  # noqa: BLE001
            st.error(str(e))

digest = st.session_state.get("ma_digest", "")
todos = st.session_state.get("ma_todos", [])

tab1, tab2, tab3 = st.tabs(["📋 摘要", "📧 邮件", "💬 对话"])

# ---------------------------------------------------------------- 摘要
with tab1:
    if not digest and not any(m.priority for m in mails):
        st.info("点右上角「生成摘要」，AI 会按优先级归类并给出一句话结论。")
    else:
        if digest:
            st.success("**今天：** " + digest)
        groups = M.group_by_priority(mails)
        cols = st.columns(4)
        for col, p in zip(cols, M.PRIORITIES):
            col.metric(p, len(groups.get(p, [])), help=M.PRIORITY_LABEL[p])

        for p in M.PRIORITIES:
            group = groups.get(p) or []
            if not group:
                continue
            st.markdown(f"#### {p} · {M.PRIORITY_LABEL[p]}（{len(group)}）")
            for m in group:
                with st.container(border=True):
                    st.markdown(f"**{m.action or m.summary or m.subject}**")
                    meta = f"{m.sender}"
                    if m.date:
                        meta += f"　·　{m.date}"
                    if m.deadline:
                        meta += f"　·　截止 {m.deadline}"
                    st.caption(meta)
                    if m.summary and m.action:
                        st.caption(m.summary)
                    with st.expander("查看原文"):
                        st.text(m.body[:2000])

        if todos:
            st.markdown("#### 今日待办")
            for i, t in enumerate(todos, 1):
                st.markdown(f"{i}. {t}")

# ---------------------------------------------------------------- 邮件
with tab2:
    df = pd.DataFrame([{
        "ID": m.id, "日期": m.date, "发件人": m.sender, "主题": m.subject,
        "类别": m.category, "优先级": m.priority, "摘要": m.summary, "动作": m.action,
    } for m in mails])
    st.dataframe(
        df, hide_index=True, use_container_width=True, height=min(560, 60 + 36 * len(df)),
        column_config={
            "ID": st.column_config.TextColumn(width=48),
            "日期": st.column_config.TextColumn(width=110),
            "发件人": st.column_config.TextColumn(width=180),
            "主题": st.column_config.TextColumn(width=260),
            "类别": st.column_config.TextColumn(width=70),
            "优先级": st.column_config.TextColumn(width=56),
            "摘要": st.column_config.TextColumn(width=280),
            "动作": st.column_config.TextColumn(width=220),
        },
    )
    pick = st.selectbox("查看某封原文", [m.id for m in mails],
                        format_func=lambda i: next(m.label for m in mails if m.id == i))
    m = next(m for m in mails if m.id == pick)
    st.caption(f"{m.sender}　·　{m.date}")
    st.text(m.body[:4000] or "(正文为空或只有附件)")

# ---------------------------------------------------------------- 对话
with tab3:
    chat = st.session_state.setdefault("ma_chat", [])
    st.caption("可以问：直升机那封确认了什么？Sudima 晚餐改几份？帮我起草回复 Annie 的邮件。")

    for msg in chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    q = st.chat_input("基于这些邮件提问…")
    if q:
        chat.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("查询邮件…"):
                try:
                    a = M.answer(q, mails, chat[:-1], api_key, base_url, model)
                except Exception as e:  # noqa: BLE001
                    a = f"出错了：{e}"
            st.markdown(a)
        chat.append({"role": "assistant", "content": a})

    if chat and st.button("清空对话"):
        st.session_state["ma_chat"] = []
        st.rerun()
