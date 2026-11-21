# -*- coding: utf-8 -*-
"""把「解析 → 规则 → AI → 合并」串成一条可测试的流水线。"""
from __future__ import annotations

import datetime as dt
import re
from typing import Callable

from . import ai, check, extract, report


def infer_depart(ops) -> dt.date | None:
    dates = [b.date for b in ops.bookings if b.date]
    year = dates[0].year if dates else dt.date.today().year
    m = re.search(r"\b\d\.(\d{2})(\d{2})\b", ops.flights_raw or "")
    if m:
        try:
            return dt.date(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    return min(dates) if dates else None


def run(ops_bytes: bytes,
        cn_bytes: bytes,
        cn_name: str,
        extras: list[tuple[str, bytes]] | None = None,
        depart: dt.date | None = None,
        use_ai: bool = False,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        progress: Callable[[str], None] | None = None) -> dict:
    def step(msg: str):
        if progress:
            progress(msg)

    ops = extract.parse_ops(ops_bytes)
    step(f"操作表：{len(ops.bookings)} 条预订，人数 {ops.pax_header or '未识别'}")

    depart = depart or infer_depart(ops)
    step(f"出发日期：{depart or '未识别'}")

    cn = extract.parse_cn_any(cn_bytes, cn_name, depart)
    step(f"中文行程：识别 {len(cn.days)} 天")

    vouchers, itin_text, skipped = [], "", []
    for name, data in extras or []:
        kind = extract.detect_file_kind(name, data)
        if kind == "voucher_pdf":
            vs = extract.parse_vouchers(extract.load_pdf_text(data))
            vouchers.extend(vs)
            step(f"{name}：{len(vs)} 张 Voucher")
        elif kind == "itinerary_pdf":
            itin_text += "\n" + extract.load_pdf_text(data)
            step(f"{name}：已读入路书原文")
        else:
            skipped.append(name)

    step("规则核对…")
    rules = check.run_rules(ops, cn, vouchers)

    ai_res = {"findings": [], "summary": "", "hotel_review": [], "error": None}
    if use_ai and api_key:
        step("AI 语义核对…")
        facts = ai.build_facts(ops, cn, vouchers, itin_text)
        ai_res = ai.run_ai(facts, api_key, base_url, model)
    elif use_ai and not api_key:
        ai_res["error"] = "未填写 API Key，本次仅使用规则核对。"

    findings = report.merge_findings(rules, ai_res.get("findings", []))
    step("完成")
    return {
        "findings": findings,
        "rules": rules,
        "summary": ai_res.get("summary", ""),
        "hotels": ai_res.get("hotel_review", []),
        "ai_error": ai_res.get("error"),
        "ops": ops,
        "cn": cn,
        "vouchers": vouchers,
        "depart": depart,
        "itin_len": len(itin_text),
        "skipped": skipped,
    }
