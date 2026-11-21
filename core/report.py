# -*- coding: utf-8 -*-
"""结果合并与导出。"""
from __future__ import annotations

import io
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import LEVEL_ORDER, Finding, norm_name

NAVY = "1F3864"
THIN = Side(style="thin", color="BFCADB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FONT = "微软雅黑"


def merge_findings(rule_findings: list[Finding], ai_findings: list[Finding]) -> list[Finding]:
    merged: list[Finding] = list(rule_findings)
    for a in ai_findings:
        dup = False
        for m in merged:
            if m.category == a.category and m.target == a.target:
                if norm_name(m.where)[:12] == norm_name(a.where)[:12] or \
                        norm_name(m.current)[:16] == norm_name(a.current)[:16]:
                    dup = True
                    break
        if not dup:
            merged.append(a)
    unique, seen = [], set()
    for f in merged:
        k = (f.category, f.target, f.where, f.current, f.expected)
        if k in seen:
            continue
        seen.add(k)
        unique.append(f)
    unique.sort(key=lambda f: (LEVEL_ORDER.get(f.level, 9), f.category, f.where))
    return unique


def counts(findings: list[Finding]) -> dict[str, int]:
    c = {"必改": 0, "建议": 0, "提示": 0}
    for f in findings:
        c[f.level] = c.get(f.level, 0) + 1
    return c


def build_excel(findings: list[Finding], meta: dict, hotels: list[dict] | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "核对总览"
    ws.sheet_view.showGridLines = False
    for i, w in enumerate([2, 16, 14, 62], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.merge_cells("A1:D1")
    c = ws["A1"]
    c.value = "FINAL 校对报告　" + meta.get("tour_code", "")
    c.font = Font(name=FONT, size=16, bold=True, color=NAVY)
    ws.row_dimensions[1].height = 30

    ws.merge_cells("A2:D2")
    c = ws["A2"]
    c.value = "生成时间 " + datetime.now().strftime("%Y-%m-%d %H:%M") + "　" + meta.get("subtitle", "")
    c.font = Font(name=FONT, size=8.5, color="595959")

    r = 4
    for k, v in meta.get("kv", []):
        ws.cell(row=r, column=2, value=k).font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
        ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor="2E5C9A")
        ws.cell(row=r, column=2).alignment = Alignment(vertical="center")
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        cell = ws.cell(row=r, column=3, value=v)
        cell.font = Font(name=FONT, size=9)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[r].height = max(18, 14 * (len(str(v)) // 48 + 1))
        r += 1

    r += 1
    cnt = counts(findings)
    for lvl, color, desc in (
        ("必改", "C00000", "会导致住错酒店、吃不上饭、进不了景点、误机或结算错误"),
        ("建议", "BF8F00", "需向供应商书面确认或补齐信息"),
        ("提示", "7F7F7F", "同级替换、表述、格式类，可选处理"),
    ):
        ws.cell(row=r, column=2, value=lvl).font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=color)
        ws.cell(row=r, column=2).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=r, column=3, value=str(cnt.get(lvl, 0)) + " 项").font = Font(
            name=FONT, size=13, bold=True, color=color)
        ws.cell(row=r, column=3).alignment = Alignment(horizontal="center", vertical="center")
        cell = ws.cell(row=r, column=4, value=desc)
        cell.font = Font(name=FONT, size=9)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[r].height = 26
        r += 1

    if meta.get("summary"):
        r += 1
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        cell = ws.cell(row=r, column=2, value="结论：" + meta["summary"])
        cell.font = Font(name=FONT, size=9.5, bold=True, color="7F0000")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.fill = PatternFill("solid", fgColor="FFF2F2")
        ws.row_dimensions[r].height = 46

    # 明细
    ws2 = wb.create_sheet("问题清单")
    ws2.sheet_view.showGridLines = False
    widths = [5, 7, 9, 11, 24, 34, 34, 40, 6]
    for i, w in enumerate(widths, start=1):
        ws2.column_dimensions[get_column_letter(i)].width = w
    ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=9)
    ws2["A1"].value = "问题清单（共 %d 项）" % len(findings)
    ws2["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
    ws2.row_dimensions[1].height = 26

    heads = ["#", "级别", "类别", "对象", "位置", "现状", "应改为", "依据 / 说明", "来源"]
    for i, h in enumerate(heads, start=1):
        cell = ws2.cell(row=3, column=i, value=h)
        cell.font = Font(name=FONT, size=9.5, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws2.row_dimensions[3].height = 26
    ws2.freeze_panes = "A4"

    r = 4
    for i, f in enumerate(findings, start=1):
        vals = [i, f.level, f.category, f.target, f.where, f.current, f.expected, f.reason, f.source]
        lines = 1
        for j, v in enumerate(vals, start=1):
            cell = ws2.cell(row=r, column=j, value=v)
            cell.font = Font(name=FONT, size=9)
            cell.alignment = Alignment(vertical="center", wrap_text=True,
                                       horizontal="center" if j in (1, 2, 3, 9) else "left")
            cell.border = BORDER
            if j <= len(widths):
                n = sum(2 if ord(ch) > 127 else 1 for ch in str(v))
                lines = max(lines, -(-n // max(widths[j - 1], 4)))
        color = {"必改": "C00000", "建议": "BF8F00", "提示": "7F7F7F"}.get(f.level, "7F7F7F")
        c = ws2.cell(row=r, column=2)
        c.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=color)
        ws2.row_dimensions[r].height = max(20, 13.5 * min(lines, 8) + 6)
        r += 1

    if hotels:
        ws3 = wb.create_sheet("酒店档次")
        ws3.sheet_view.showGridLines = False
        for i, w in enumerate([10, 36, 36, 14, 40], start=1):
            ws3.column_dimensions[get_column_letter(i)].width = w
        ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
        ws3["A1"].value = "酒店：参考 vs 实订（同级/升级可接受）"
        ws3["A1"].font = Font(name=FONT, size=14, bold=True, color=NAVY)
        heads = ["日期", "中文参考酒店", "实际预订", "结论", "说明"]
        for i, h in enumerate(heads, start=1):
            cell = ws3.cell(row=3, column=i, value=h)
            cell.font = Font(name=FONT, size=9.5, bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=NAVY)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = BORDER
        r = 4
        for row in hotels:
            vals = [row.get("day", ""), row.get("cn", ""), row.get("actual", ""),
                    row.get("verdict", ""), row.get("note", "")]
            for j, v in enumerate(vals, start=1):
                cell = ws3.cell(row=r, column=j, value=v)
                cell.font = Font(name=FONT, size=9)
                cell.alignment = Alignment(vertical="center", wrap_text=True,
                                           horizontal="center" if j in (1, 4) else "left")
                cell.border = BORDER
            ws3.row_dimensions[r].height = 26
            r += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_checklist(findings: list[Finding], meta: dict) -> str:
    """生成可直接贴到微信/邮件的修改清单。"""
    lines = []
    title = f"【{meta.get('tour_code', '')}】FINAL 校对修改清单"
    lines.append(title)
    if meta.get("subtitle"):
        lines.append(meta["subtitle"])
    lines.append("")
    groups = {"必改": [], "建议": [], "提示": []}
    for f in findings:
        groups.setdefault(f.level, []).append(f)
    for lvl, mark in (("必改", "■"), ("建议", "▲"), ("提示", "·")):
        items = groups.get(lvl) or []
        if not items:
            continue
        lines.append(f"{mark} {lvl}（{len(items)} 项）")
        for i, f in enumerate(items, start=1):
            lines.append(f"{i}. [{f.target}] {f.where}")
            if f.current:
                lines.append(f"   现状：{f.current}")
            if f.expected:
                lines.append(f"   改为：{f.expected}")
            if f.reason:
                lines.append(f"   说明：{f.reason}")
        lines.append("")
    return "\n".join(lines)
