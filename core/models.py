# -*- coding: utf-8 -*-
"""数据模型与通用工具。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
          "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12, "十三": 13,
          "十四": 14, "十五": 15}


def cn_day_to_int(s: str) -> int | None:
    s = s.strip()
    if s.isdigit():
        return int(s)
    return CN_NUM.get(s)


def parse_date(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"(\d{1,2})[/-](\d{1,2})", s)
    if m:
        return date(date.today().year, int(m.group(1)), int(m.group(2)))
    return None


def norm_time(v: str) -> str:
    """18：00 / 18:00:00 / 18.00 -> 18:00"""
    if v is None:
        return ""
    s = str(v).strip()
    m = re.search(r"(\d{1,2})\s*[:：.．]\s*(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.search(r"\b(\d{1,2})\s*点\b", s)
    if m:
        return f"{int(m.group(1)):02d}:00"
    return s


def norm_key(s: str) -> str:
    """确认号/编号归一化：去掉 #、空格、连字符、大小写。"""
    return re.sub(r"[^0-9A-Za-z]", "", str(s or "")).upper()


def norm_name(s: str) -> str:
    s = str(s or "").lower()
    s = re.sub(r"[（(].*?[）)]", "", s)
    s = re.sub(r"\b(hotel|restaurant|cafe|the|ltd|limited|partnership|&)\b", " ", s)
    s = re.sub(r"[\s\-_.,'’·]+", "", s)
    return s


RE_ROOM = re.compile(r"(\d+)\s*(TWN|Twin|双床|DBL|Double|大床|SGL|Single|单房|TSU|Triple)", re.I)


def parse_rooms(text: str) -> dict[str, int]:
    """'6 TWN +4 DBL +1 SGL' -> {'TWN':6,'DBL':4,'SGL':1}"""
    out: dict[str, int] = {}
    for n, t in RE_ROOM.findall(str(text or "")):
        t = t.upper()
        t = {"TWIN": "TWN", "双床": "TWN", "DOUBLE": "DBL", "大床": "DBL",
             "SINGLE": "SGL", "单房": "SGL", "TRIPLE": "TSU"}.get(t, t)
        out[t] = out.get(t, 0) + int(n)
    return out


def room_total(rooms: dict[str, int]) -> int:
    return sum(rooms.values())


def parse_pax(text: str) -> dict[str, int]:
    """'19ADT+2TL' / '19 ADT + 1 TL' / '19 Adults, 1 Guide' -> {'ADT':19,'TL':2,'GUIDE':0}"""
    s = str(text or "").upper().replace("，", "+")
    out = {"ADT": 0, "TL": 0, "GUIDE": 0}
    for n, label in re.findall(r"(\d+)\s*(ADT|ADULTS?|TL|T/L|GUIDE|T/G|TG)", s):
        k = {"ADT": "ADT", "ADULT": "ADT", "ADULTS": "ADT",
             "TL": "TL", "T/L": "TL", "GUIDE": "GUIDE", "T/G": "GUIDE", "TG": "GUIDE"}[label]
        out[k] += int(n)
    if out["ADT"] == 0 and out["TL"] == 0:
        m = re.search(r"(\d+)\s*(?:ADULTS?|成人)", s)
        if m:
            out["ADT"] = int(m.group(1))
        if "GUIDE" in s:
            out["GUIDE"] = 1
    return out


def pax_text(p: dict[str, int]) -> str:
    parts = []
    if p.get("ADT"):
        parts.append(f"{p['ADT']} ADT")
    if p.get("TL"):
        parts.append(f"{p['TL']} TL")
    if p.get("GUIDE"):
        parts.append(f"{p['GUIDE']} GUIDE")
    return " + ".join(parts) if parts else "—"


@dataclass
class Booking:
    kind: str                      # hotel / meal / attraction
    date: date | None = None
    route: str = ""
    supplier: str = ""
    product: str = ""
    time: str = ""
    pax: str = ""
    rooms: str = ""
    ref: str = ""
    note: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        d = self.date.strftime("%m/%d") if self.date else "—"
        return f"{d} {self.supplier} {self.product}".strip()


@dataclass
class OpsSheet:
    tour_code: str = ""
    pax_header: str = ""
    tour_leader: str = ""
    flights_raw: str = ""
    bookings: list[Booking] = field(default_factory=list)
    sheets: dict[str, list[list]] = field(default_factory=dict)

    def of(self, kind: str) -> list[Booking]:
        return [b for b in self.bookings if b.kind == kind]


@dataclass
class DayPlan:
    no: int
    date: date | None
    title: str = ""
    detail: str = ""
    meals: dict[str, str] = field(default_factory=dict)
    hotel: str = ""

    @property
    def label(self) -> str:
        d = self.date.strftime("%m/%d") if self.date else ""
        return f"D{self.no} {d}".strip()


@dataclass
class CnItinerary:
    tour_name: str = ""
    days: list[DayPlan] = field(default_factory=list)
    flights: list[dict] = field(default_factory=list)
    raw_text: str = ""
    date_column_note: str = ""


@dataclass
class Voucher:
    vno: str = ""
    date: date | None = None
    date_text: str = ""
    supplier: str = ""
    item: str = ""
    time: str = ""
    adt: int = 0
    tl: int = 0
    tg: int = 0
    sgl: int = 0
    twn: int = 0
    dbl: int = 0
    kk: str = ""
    note: str = ""
    raw: str = ""

    @property
    def pax_dict(self) -> dict[str, int]:
        return {"ADT": self.adt, "TL": self.tl, "GUIDE": self.tg}

    @property
    def rooms_text(self) -> str:
        parts = []
        for k, v in (("SGL", self.sgl), ("TWN", self.twn), ("DBL", self.dbl)):
            if v:
                parts.append(f"{v} {k}")
        return " + ".join(parts)

    @property
    def label(self) -> str:
        return f"{self.supplier} {self.item}".strip()


@dataclass
class Finding:
    level: str          # 必改 / 建议 / 提示
    category: str       # 酒店/餐饮/景点/航班/人数/确认号/行程/单号
    target: str         # 中文行程 / 路书 / Voucher / 操作表
    where: str
    current: str
    expected: str
    reason: str = ""
    source: str = "规则"
    confidence: float = 1.0
    refs: str = ""

    @property
    def key(self) -> tuple:
        return (self.category, self.target, self.where.strip()[:40], norm_name(self.current)[:30])


LEVEL_ORDER = {"必改": 0, "建议": 1, "提示": 2}
