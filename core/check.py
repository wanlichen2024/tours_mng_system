# -*- coding: utf-8 -*-
"""确定性核对规则：人数、房数、时间、确认号、缺失项、航班。

语义类判断（菜品是否等价、酒店档次、项目描述）交给 AI，这里只处理
可以硬比对的事实，保证不出错报。
"""
from __future__ import annotations

import difflib
import re
from datetime import timedelta

from .models import (Booking, CnItinerary, Finding, OpsSheet, Voucher,
                     norm_key, norm_name, norm_time, parse_pax, parse_rooms,
                     pax_text, room_total)


def _sim(a: str, b: str) -> float:
    a, b = norm_name(a), norm_name(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


_MEAL_WORDS = ("lunch", "dinner", "breakfast", "dish", "soup", "course", "burger",
               "pot", "steak", "buffet", "fish", "chips", "combo", "便当", "火锅",
               "菜", "餐", "汉堡", "自助")
_ATTR_WORDS = ("flight", "tour", "experience", "admission", "watch", "penguin",
               "farm", "movie", "helicopter")
_ROOM_WORDS = ("room", "bbt", "standard", "suite", "twin", "double")


def _guess_kind(item: str) -> str:
    t = (item or "").lower()
    if any(w in t for w in _ROOM_WORDS):
        return "hotel"
    if any(w in t for w in _MEAL_WORDS):
        return "meal"
    if any(w in t for w in _ATTR_WORDS):
        return "attraction"
    return ""


def _match_one(v: Voucher, bookings: list[Booking]) -> Booking | None:
    best, score = None, 0.0
    kind = _guess_kind(v.item)
    for b in bookings:
        if b.date and v.date:
            delta = abs((b.date - v.date).days)
            if delta > 1:
                continue
        base = _sim(v.supplier, b.supplier)
        if base < 0.45:
            continue
        sc = base
        if kind and b.kind == kind:
            sc += 0.35
        elif kind and b.kind != kind:
            sc -= 0.25
        if sc > score:
            best, score = b, sc
    return best if score >= 0.55 else None


def _fmt_rooms(d: dict[str, int]) -> str:
    return " + ".join(f"{v} {k}" for k, v in d.items()) or "—"


def run_rules(ops: OpsSheet, cn: CnItinerary | None,
              vouchers: list[Voucher]) -> list[Finding]:
    out: list[Finding] = []
    add = out.append

    # ---------------- 人数口径 ----------------
    header = parse_pax(ops.pax_header)
    meal_pax: dict[str, int] = {}
    for b in ops.of("meal"):
        p = parse_pax(b.pax)
        for k, v in p.items():
            meal_pax[k] = max(meal_pax.get(k, 0), v)
    att_pax: dict[str, int] = {}
    for b in ops.of("attraction"):
        p = parse_pax(b.pax)
        for k, v in p.items():
            att_pax[k] = max(att_pax.get(k, 0), v)

    if header and meal_pax and (header.get("TL", 0) != meal_pax.get("TL", 0)):
        add(Finding("建议", "人数", "操作表",
                    "操作表抬头 Number of Pax",
                    f"抬头：{pax_text(header)}；餐饮预订：{pax_text(meal_pax)}",
                    f"统一为 {pax_text(meal_pax)}（含领队与导游）",
                    "同一团两套人数口径，会导致景点按 1 人出票、餐按 2 人备餐。", "规则"))
    if header and att_pax and header.get("ADT", 0) != att_pax.get("ADT", 0):
        add(Finding("必改", "人数", "操作表", "操作表抬头 vs 景点预订",
                    f"抬头 ADT {header.get('ADT')}／景点 ADT {att_pax.get('ADT')}",
                    "核实际成人数", "成人票数不一致，直接影响门票与结算。", "规则"))

    # ---------------- 酒店房数 ----------------
    hotel_rows = ops.sheets.get("hotel", [])
    sheet_rooms: dict[str, str] = {}
    for r in hotel_rows:
        if not r or len(r) < 5:
            continue
        name = str(r[2] or "")
        rooms = str(r[3] or "")
        if name and rooms:
            sheet_rooms[norm_name(name)] = rooms
    seen_hotel: set[str] = set()
    for b in ops.of("hotel"):
        if not b.rooms or norm_name(b.supplier) in seen_hotel:
            continue
        for k, v in sheet_rooms.items():
            if _sim(b.supplier, k) > 0.7 and parse_rooms(v) != parse_rooms(b.rooms):
                seen_hotel.add(norm_name(b.supplier))
                add(Finding("必改", "酒店", "操作表", f"{b.date:%m/%d} {b.supplier}".strip(),
                            f"操作表酒店段：{b.rooms}；hotel 表：{v}",
                            "两者统一为同一房数并更新 hotel 表",
                            "内部两套房数并存，按少的订会少房。", "规则"))

    # ---------------- Voucher ↔ 操作表 ----------------
    all_bookings = [b for b in ops.bookings if b.kind in ("hotel", "meal", "attraction")]
    used: set[int] = set()
    for v in vouchers:
        b = _match_one(v, all_bookings)
        if not b:
            add(Finding("建议", "单号", "Voucher", f"{v.vno} {v.supplier}",
                        f"{v.supplier} / {v.item}",
                        "在操作表中补录该预订", "Voucher 找不到对应的操作表条目，无法对账。", "规则"))
            continue
        used.add(id(b))
        # 同一家酒店连住多晚共用一个 voucher，避免误报「漏发券」
        if b.kind == "hotel" and b.date:
            for other in all_bookings:
                if other.kind == "hotel" and other.date and _sim(b.supplier, other.supplier) > 0.75 \
                        and abs((other.date - b.date).days) <= 3:
                    used.add(id(other))

        if b.time and v.time and norm_time(b.time) != norm_time(v.time):
            add(Finding("必改", "餐饮" if b.kind == "meal" else "景点", "Voucher",
                        f"{v.vno} {v.supplier}",
                        f"券面 {v.time}；操作表 {norm_time(b.time)}",
                        f"以 {norm_time(b.time)} 为准并重发券",
                        "时间不一致，餐厅会按不同时间备餐。", "规则"))

        bp, vp = parse_pax(b.pax), v.pax_dict
        if bp.get("ADT") and vp.get("ADT") and bp["ADT"] != vp["ADT"]:
            add(Finding("必改", "人数", "Voucher", f"{v.vno} {v.supplier}",
                        f"券面 ADT {vp['ADT']}；操作表 {pax_text(bp)}",
                        f"改为 {pax_text(bp)}", "用餐/门票人数与预订不符。", "规则"))
        if bp.get("TL") and vp.get("TL") and bp["TL"] != vp["TL"]:
            add(Finding("建议", "人数", "Voucher", f"{v.vno} {v.supplier}",
                        f"券面 T/L {vp['TL']}；操作表 {pax_text(bp)}",
                        f"改为 {pax_text(bp)}", "陪同人数不一致。", "规则"))

        if b.rooms and v.rooms_text and parse_rooms(b.rooms) != parse_rooms(v.rooms_text):
            add(Finding("必改", "酒店", "Voucher", f"{v.vno} {v.supplier}",
                        f"券面 {v.rooms_text}；操作表 {b.rooms}",
                        f"改为 {b.rooms}", "房型/房数不一致，前台会按券面排房。", "规则"))

        if b.ref and v.kk:
            nk_b, nk_v = norm_key(b.ref), norm_key(v.kk)
            if nk_b != nk_v:
                if nk_b.endswith(nk_v) or nk_v.endswith(nk_b) or nk_v in nk_b:
                    add(Finding("提示", "确认号", "Voucher", f"{v.vno} {v.supplier}",
                                f"券面 {v.kk}；操作表 {b.ref}",
                                f"补全为 {b.ref}", "确认号不完整，酒店/景点对账时可能查不到单。", "规则"))
                else:
                    add(Finding("必改", "确认号", "Voucher", f"{v.vno} {v.supplier}",
                                f"券面 {v.kk}；操作表 {b.ref}",
                                f"核对并改为 {b.ref}", "确认号不同，属于两张不同订单。", "规则"))
        elif not v.kk and b.ref:
            add(Finding("提示", "确认号", "Voucher", f"{v.vno} {v.supplier}",
                        "券面无确认号", f"补 {b.ref}", "无确认号无法向供应商证明已预订。", "规则"))
        elif not b.ref:
            add(Finding("提示", "确认号", "操作表", f"{b.supplier}",
                        "操作表无 Reference", "补录供应商确认号",
                        "餐厅/景点若无确认号，出问题时无法追溯。", "规则"))

    # 有预订但无券
    for b in all_bookings:
        if id(b) in used:
            continue
        if not (b.time or b.pax or b.ref):
            continue
        add(Finding("建议", "单号", "Voucher", b.label,
                    "操作表有此预订，Voucher 中未找到",
                    "补发 Voucher", "漏发券，供应商可能未收到预订。", "规则"))

    # 券号复用
    seen: dict[str, list[str]] = {}
    for v in vouchers:
        seen.setdefault(v.vno, []).append(v.item or v.supplier)
    for vno, items in seen.items():
        if len(items) > 1:
            add(Finding("提示", "单号", "Voucher", vno,
                        "同一券号含 " + " / ".join(items),
                        "注明「合并结算」", "同号多券属正常，但需在券面注明避免重复计费。", "规则"))

    # ---------------- 航班 ----------------
    ops_flights = _parse_ops_flights(ops.flights_raw)
    if cn and ops_flights:
        cn_map = {f["flight"]: f for f in cn.flights}
        for f in ops_flights:
            c = cn_map.get(f["flight"])
            if not c:
                continue
            if c.get("arr") and f["arr"] and norm_time(c["arr"]) != norm_time(f["arr"]):
                add(Finding("必改", "航班", "中文行程", f"{f['flight']} 抵达时间",
                            f"中文：{c['arr']}；操作表：{f['arr']}",
                            f"以 {f['arr']} 为准", "落地时间差会影响接机与首日行程。", "规则"))
            if c.get("dep") and f["dep"] and norm_time(c["dep"]) != norm_time(f["dep"]):
                add(Finding("必改", "航班", "中文行程", f"{f['flight']} 起飞时间",
                            f"中文：{c['dep']}；操作表：{f['dep']}",
                            f"以 {f['dep']} 为准", "起飞时间不一致。", "规则"))

    # 中文参考酒店 vs 实订：允许同级/升级，档次判断交给 AI（见 hotel_review）
    return out


def _parse_ops_flights(raw: str) -> list[dict]:
    out = []
    for m in re.finditer(r"([A-Z]{2}\d{2,4})\s+([A-Z]{6})\s+(\d{3,4})\s*/\s*(\d{3,4})", raw or ""):
        def t(x):
            x = x.zfill(4)
            return f"{x[:2]}:{x[2:]}"
        out.append({"flight": m.group(1), "route": m.group(2), "dep": t(m.group(3)), "arr": t(m.group(4))})
    return out
