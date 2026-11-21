# -*- coding: utf-8 -*-
"""Final 路书 / Voucher 校对工具。

上传：① 国内中文行程　② 操作表　③ Voucher（及已发路书）
输出：必改 / 建议 / 提示 三级问题清单，可导出 Excel 与文本清单。
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

import pandas as pd
import streamlit as st

# pages/ 子目录里的脚本默认不在根目录的 sys.path 上，这里补一下
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import pipeline, report          # noqa: E402
from core.models import Finding           # noqa: E402

CSS = """
<style>
  .stTabs [data-baseweb="tab"] {font-size: 0.95rem;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def secret(key: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(key, default))
    except Exception:
        return default


# --------------------------------------------------------------------------
# 侧边栏
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🤖 AI 设置")
    api_key_default = secret("DEEPSEEK_API_KEY") or secret("OPENAI_API_KEY")
    use_ai = st.toggle("启用 AI 语义核对", value=bool(api_key_default),
                       help="关闭时只做规则核对（人数/房数/时间/确认号/航班），仍可发现大部分硬错。")
    api_key = st.text_input("API Key", value=api_key_default, type="password",
                            help="也可在 Streamlit secrets 里配置 DEEPSEEK_API_KEY")
    base_url = st.text_input("Base URL", value=secret("AI_BASE_URL", "https://api.deepseek.com/v1"))
    model = st.text_input("模型", value=secret("AI_MODEL", "deepseek-chat"))

    st.divider()
    st.markdown("### 📅 行程参数")
    auto_depart = st.toggle("自动识别出发日期", value=True,
                            help="从操作表航班行的日期码（如 1.1119）推断，用于挑选中文行程里的日期列。")
    manual_depart = None
    if not auto_depart:
        manual_depart = st.date_input("出发日期", value=dt.date.today())

    st.divider()
    with st.expander("判断标准（可修改 core/ai.py）"):
        st.markdown(
            "- **参考酒店**允许同级或升级替换，不要求字面一致\n"
            "- **餐食按总道数**合并计算：7菜1汤+鹿肉 = 8菜1汤含鹿肉\n"
            "- 别名/简称视为一致：Chopsticks 101 = 台北101小火锅\n"
            "- 全角半角、大小写、空格不算差异\n"
            "- 只报会导致落地事故或结算错误的实质差异"
        )

# --------------------------------------------------------------------------
# 上传
# --------------------------------------------------------------------------
st.title("Final 路书 / Voucher 校对")
st.caption("上传三份文件，先比对「中文行程 ↔ 操作表」，再比对「Voucher / 路书 ↔ 操作表」，输出必改清单。")

c1, c2, c3 = st.columns(3)
f_cn = c1.file_uploader("① 国内中文行程", type=["docx", "pdf"], key="cn",
                        help="组团社发来的中文行程（Word 或 PDF）")
f_ops = c2.file_uploader("② 操作表", type=["xlsx"], key="ops",
                         help="含 操作表 / 中餐 / 西餐 / 景点 / hotel 工作表")
f_extra = c3.file_uploader("③ Voucher / 已发路书", type=["pdf", "docx", "xlsx"],
                           accept_multiple_files=True, key="extra",
                           help="Voucher PDF 与 Itinerary（路书）PDF 可一起上传，自动识别")

col_a, col_b = st.columns([1, 3])
run = col_a.button("🔍 开始核对", type="primary", use_container_width=True)
col_b.caption("数据只在本次会话内解析；启用 AI 时，结构化摘要会发送到你配置的模型接口。")


def do_check():
    with st.status("解析文件…", expanded=True) as status:
        extras = [(f.name, f.getvalue()) for f in (f_extra or [])]
        res = pipeline.run(
            f_ops.getvalue(), f_cn.getvalue(), f_cn.name, extras,
            depart=manual_depart if not auto_depart else None,
            use_ai=use_ai, api_key=api_key, base_url=base_url, model=model,
            progress=status.write,
        )
        for name in res.get("skipped", []):
            status.write(f"跳过：{name}（暂只支持 Voucher / 路书 PDF）")
        status.update(label="完成", state="complete", expanded=False)
    st.session_state["fc_res"] = res


if run:
    if not f_cn or not f_ops:
        st.error("请至少上传「中文行程」与「操作表」。")
    else:
        try:
            do_check()
        except Exception as e:  # noqa: BLE001
            st.exception(e)


# --------------------------------------------------------------------------
# 结果
# --------------------------------------------------------------------------
res: dict | None = st.session_state.get("fc_res")
if not res:
    st.info("上传文件后点击「开始核对」。首次使用建议先看下方「怎么判断」。")
    with st.expander("怎么判断：三条核心规则"):
        st.markdown(
            "1. **参考酒店不必一致**：中文行程写的是参考酒店，允许同级或升级替换；只有降级才算问题。\n"
            "2. **餐食按总道数比**：`7菜1汤+鹿肉` 与 `8菜1汤含鹿肉` 是同一件事，鹿肉就是第 8 道菜。\n"
            "3. **只报实质差异**：住错酒店、吃不上饭、进不了景点、误机、结算错——其余只作提示。"
        )
    st.stop()

findings: list[Finding] = res["findings"]
cnt = report.counts(findings)

m1, m2, m3, m4 = st.columns(4)
m1.metric("必改", cnt.get("必改", 0))
m2.metric("建议", cnt.get("建议", 0))
m3.metric("提示", cnt.get("提示", 0))
m4.metric("识别", f"{len(res['cn'].days)} 天 / {len(res['vouchers'])} 券")

if res.get("ai_error"):
    st.warning(res["ai_error"])
if not res["cn"].days:
    st.error("中文行程未识别到「第X天」，请确认文件格式，或取消「自动识别出发日期」后手动选择出发日。")
if not res["vouchers"] and (f_extra or []):
    st.warning("未从上传文件中解析出 Voucher，请确认是 Toursoft 导出的 Voucher PDF。")

if res["summary"]:
    st.success("**结论：** " + res["summary"])

tour_code = res["ops"].tour_code or ""
subtitle = f"{res['ops'].pax_header}　出发 {res['depart'] or '—'}"

tab1, tab2, tab3, tab4 = st.tabs(["📋 问题清单", "🏨 酒店对照", "🔍 解析数据", "⬇️ 下载"])

with tab1:
    if not findings:
        st.success("未发现差异。")
    else:
        df = pd.DataFrame([{
            "#": i, "级别": f.level, "类别": f.category, "对象": f.target,
            "位置": f.where, "现状": f.current, "应改为": f.expected,
            "说明": f.reason, "来源": f.source,
        } for i, f in enumerate(findings, start=1)])
        st.dataframe(
            df, hide_index=True, use_container_width=True, height=min(680, 60 + 42 * len(df)),
            column_config={
                "#": st.column_config.NumberColumn(width=40),
                "级别": st.column_config.TextColumn(width=62),
                "类别": st.column_config.TextColumn(width=70),
                "对象": st.column_config.TextColumn(width=84),
                "位置": st.column_config.TextColumn(width=180),
                "现状": st.column_config.TextColumn(width=230),
                "应改为": st.column_config.TextColumn(width=230),
                "说明": st.column_config.TextColumn(width=260),
                "来源": st.column_config.TextColumn(width=56),
            },
        )

with tab2:
    hotels = res.get("hotels") or []
    if hotels:
        st.dataframe(pd.DataFrame(hotels), hide_index=True, use_container_width=True)
    elif res["cn"].days:
        rows = []
        by_date = {b.date: b for b in res["ops"].of("hotel") if b.date}
        for d in res["cn"].days:
            b = by_date.get(d.date)
            if d.hotel or b:
                rows.append({"天": d.label, "中文参考酒店": d.hotel or "—",
                             "实际预订": b.supplier if b else "—",
                             "房型": b.rooms if b else "—"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("参考酒店允许同级或升级替换；启用 AI 后会给出档次判断。")
    else:
        st.info("未识别到中文行程住宿信息。")

with tab3:
    st.markdown("**操作表预订（前 40 条）**")
    st.dataframe(pd.DataFrame([{
        "类型": b.kind, "日期": b.date, "供应商": b.supplier, "项目": b.product,
        "时间": b.time, "人数": b.pax, "房间": b.rooms, "确认号": b.ref,
    } for b in res["ops"].bookings[:40]]), hide_index=True, use_container_width=True)
    if res["vouchers"]:
        st.markdown("**Voucher**")
        st.dataframe(pd.DataFrame([{
            "券号": v.vno, "日期": v.date, "供应商": v.supplier, "项目": v.item,
            "时间": v.time, "人数": v.pax_dict, "房间": v.rooms_text, "确认号": v.kk,
        } for v in res["vouchers"]]), hide_index=True, use_container_width=True)

with tab4:
    meta = {
        "tour_code": tour_code,
        "subtitle": subtitle,
        "summary": res.get("summary", ""),
        "kv": [
            ("团号", tour_code),
            ("人数", res["ops"].pax_header),
            ("出发日期", str(res["depart"] or "—")),
            ("中文行程", f"{len(res['cn'].days)} 天"),
            ("Voucher", f"{len(res['vouchers'])} 张"),
        ],
    }
    xlsx = report.build_excel(findings, meta, res.get("hotels"))
    md = report.build_checklist(findings, meta)
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ 下载 Excel 核对报告", xlsx,
                       file_name=f"{tour_code or 'Final'}_核对报告.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    d2.download_button("⬇️ 下载修改清单（txt）", md.encode("utf-8"),
                       file_name=f"{tour_code or 'Final'}_修改清单.txt",
                       mime="text/plain", use_container_width=True)
    with st.expander("预览修改清单"):
        st.text(md)