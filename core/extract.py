# -*- coding: utf-8 -*-
"""文件解析：操作表 / 中文行程 / Voucher。

所有解析都做容错，解析不到的字段留空，交给后续规则与 AI 判断。
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta

import openpyxl
from docx import Document

from .models import (Booking, CnItinerary, DayPlan, OpsSheet, Voucher,
                     cn_day_to_int, norm_time, parse_date)

# --------------------------------------------------------------------------
# 基础读取
# --------------------------------------------------------------------------


def load_docx(data: bytes):
    from docx.oxml.ns import qn
    doc = Document(io.BytesIO(data))
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    tables = []
    for t in doc.tables:
        rows = []
        for tr in t._tbl.tr_lst:
            cells = []
            for tc in tr.tc_lst:
                text = "".join(node.text or "" for node in tc.iter(qn("w:t")))
                cells.append(" ".join(text.split()))
            rows.append(cells)
        tables.append(rows)
    return paras, tables


def load_pdf_text(data: bytes) -> str:
    """优先 pdfplumber（保留版面），其次系统 pdftotext，最后 pypdf。"""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            txt = "\n".join((p.extract_text(layout=True) or "") for p in pdf.pages)
        if txt.strip():
            return txt
    except Exception:
        pass
    try:
        import shutil
        import subprocess
        import tempfile
        exe = shutil.which("pdftotext")
        if exe:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(data)
                path = f.name
            out = subprocess.run([exe, "-layout", "-enc", "UTF-8", path, "-"],
                                 capture_output=True, timeout=60)
            os.unlink(path)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.decode("utf-8", "ignore")
    except Exception:
        pass
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in r.pages)
    except Exception:
        return ""


def load_xlsx(data: bytes) -> dict[str, list[list]]:
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)]
            for ws in wb.worksheets}


def s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


# --------------------------------------------------------------------------
# 操作表
# --------------------------------------------------------------------------

_HEADER_KEYS = {
    "date": "date", "day": "day", "route": "route",
    "hotel": "supplier", "attraction": "supplier", "restaurant": "supplier",
    "product": "product", "time": "time", "reference": "ref",
    "no. of room": "rooms", "no. of pax": "pax", "note": "note",
    "confirm date": "confirm", "id": "id",
}


def _map_header(row) -> dict[str, int]:
    m: dict[str, int] = {}
    for i, cell in enumerate(row):
        k = s(cell).lower().strip()
        if not k:
            continue
        if k in _HEADER_KEYS:
            m[_HEADER_KEYS[k]] = i
        elif k.startswith("no. of") and "room" in k:
            m["rooms"] = i
        elif k.startswith("no. of") and "pax" in k:
            m["pax"] = i
        elif k.startswith("date"):
            m.setdefault("date", i)
    return m


def _is_section(row) -> bool:
    a = s(row[0]).lower() if row else ""
    return a in {"hotel", "attractions", "attraction", "meals", "meal"}


def _is_header(row) -> bool:
    vals = [s(c).lower() for c in row]
    return "date" in vals and any(v in ("hotel", "attraction", "restaurant") for v in vals)


def parse_ops(data: bytes) -> OpsSheet:
    sheets = load_xlsx(data)
    main_key = "操作表" if "操作表" in sheets else next(iter(sheets))
    rows = sheets[main_key]
    ops = OpsSheet(sheets={k: v for k, v in sheets.items() if k != main_key})

    if rows and rows[0]:
        ops.tour_code = s(rows[0][0])

    for r in rows:
        a = s(r[0]).lower() if r else ""
        if a.startswith("number of pax"):
            ops.pax_header = s(r[1]) if len(r) > 1 else ""
        elif a.startswith("tour leader"):
            ops.tour_leader = s(r[1]) if len(r) > 1 else ""
        elif a.startswith("flight"):
            ops.flights_raw = " ".join(s(c) for c in r[1:] if s(c))

    if not ops.flights_raw:
        for r in rows:
            for c in r:
                if "PVG" in s(c) and "AKL" in s(c):
                    ops.flights_raw = s(c)
                    break

    kind = ""
    cols: dict[str, int] = {}
    blank = 0
    last_date = None
    for r in rows:
        if _is_section(r):
            kind, cols, blank = "", {}, 0
            last_date = None
            continue
        if _is_header(r):
            hdr = [s(c).lower() for c in r]
            if "hotel" in hdr:
                kind = "hotel"
            elif "attraction" in hdr:
                kind = "attraction"
            else:
                kind = "meal"
            cols = _map_header(r)
            blank = 0
            last_date = None
            continue
        if not kind:
            continue
        if not any(s(c) for c in r):
            blank += 1
            if blank >= 3:
                kind, cols = "", {}
            continue
        blank = 0

        def get(key, default=""):
            i = cols.get(key)
            if i is None or i >= len(r):
                return default
            return s(r[i])

        supplier = get("supplier")
        product = get("product")
        time_ = norm_time(get("time"))
        pax = get("pax")
        rooms = get("rooms")
        ref = get("ref")
        if not supplier and not product:
            continue
        note = get("note")
        is_note_only = kind == "meal" and not time_ and not pax and not ref
        if is_note_only:
            kind_name = "meal_note"
        else:
            kind_name = kind
        row_date = parse_date(get("date")) or last_date
        if row_date:
            last_date = row_date
        ops.bookings.append(Booking(
            kind=kind_name,
            date=row_date,
            route=get("route"),
            supplier=supplier,
            product=product,
            time=time_,
            pax=pax,
            rooms=rooms,
            ref=ref,
            note=note,
            raw={"row": [s(c) for c in r]},
        ))
    return ops


# --------------------------------------------------------------------------
# 中文行程（国内发的 docx）
# --------------------------------------------------------------------------

_RE_DAY = re.compile(r"第\s*([一二三四五六七八九十\d]+)\s*天")
_RE_CODE = re.compile(r"\b(1[0-2]\d{2})\b")


def _pick_day_table(tables):
    best, score = None, 0
    for t in tables:
        txt = " ".join(" ".join(r) for r in t[:2])
        if "日期" in txt and "行程" in txt:
            return t
        sc = sum(1 for r in t if r and _RE_DAY.search(" ".join(r[:1])))
        if sc > score:
            best, score = t, sc
    return best


def parse_cn_itinerary(data: bytes, depart: date | None = None) -> CnItinerary:
    paras, tables = load_docx(data)
    it = CnItinerary(raw_text="\n".join(paras))
    it.tour_name = next((p for p in paras if len(p) < 40 and ("新西兰" in p or "NZ" in p)), "")

    # 航班表
    for t in tables:
        head = " ".join(" ".join(r) for r in t[:1])
        if "航空公司" in head or "航班" in head:
            for r in t[1:]:
                line = " ".join(r)
                fn = re.search(r"\b([A-Z]{2}\d{2,4})\b", line)
                if not fn:
                    continue
                times = re.findall(r"第?\s*(\d+)\s*天?\s*(\d{1,2}[:：]\d{2})", line)
                it.flights.append({
                    "dir": s(r[0]),
                    "flight": fn.group(1),
                    "dep": times[0][1] if times else "",
                    "arr": times[-1][1] if len(times) > 1 else "",
                    "raw": line.strip(),
                })
            break

    table = _pick_day_table(tables)
    if not table:
        return it

    # 日期码只在首日行出现一次（每天对应不同出发日），据此校验出发日是否对得上
    first_codes = []
    for r in table:
        if r and _RE_DAY.search(s(r[0])):
            first_codes = _RE_CODE.findall(s(r[0]))
            break
    it.date_column_note = ""
    if depart and first_codes:
        target = depart.strftime("%m%d")
        it.date_column_note = ("日期列匹配：" + target) if target in first_codes else \
            ("日期列未匹配（首日可选：" + "/".join(first_codes[:6]) + "…）")

    days: dict[int, DayPlan] = {}
    order: list[int] = []
    cur: int | None = None
    for r in table:
        if not r:
            continue
        first = s(r[0])
        m = _RE_DAY.search(first)
        if m:
            cur = cn_day_to_int(m.group(1))
        elif first.strip() and not first.startswith(("早餐", "午餐", "晚餐", "住宿")):
            continue
        no = cur
        if no is None:
            continue
        if no not in days:
            days[no] = DayPlan(no=no, date=(depart + timedelta(days=no - 1)) if depart else None)
            order.append(no)
        dp = days[no]
        cells = [s(c) for c in r[1:] if s(c)]
        for cell in cells:
            if cell.startswith(("早餐", "午餐", "晚餐")):
                for part in re.split(r"[|｜]", cell):
                    mm = re.match(r"(早餐|午餐|晚餐)[：:]\s*(.*)", part.strip())
                    if mm:
                        dp.meals[{"早餐": "breakfast", "午餐": "lunch", "晚餐": "dinner"}[mm.group(1)]] = mm.group(2).strip()
            elif cell.startswith("住宿"):
                dp.hotel = re.sub(r"^住宿[：:]\s*", "", cell).strip()
            elif not dp.title:
                dp.title = cell.strip()
            else:
                dp.detail += ("\n" if dp.detail else "") + cell.strip()
    it.days = [days[i] for i in order]
    return it


# --------------------------------------------------------------------------
# Voucher（PDF / 文本）
# --------------------------------------------------------------------------

_RE_VNO = re.compile(r"Voucher\s*#\s*(\d{5,})")
_RE_FIELD = {
    "adt": re.compile(r"\bADT:\s*(\d+)"),
    "tl": re.compile(r"\bT/L:\s*(\d+)"),
    "tg": re.compile(r"\bT/G:\s*(\d+)"),
    "sgl": re.compile(r"\bSGL:\s*(\d+)"),
    "twn": re.compile(r"\bTWN:\s*(\d+)"),
    "dbl": re.compile(r"\bDBL:\s*(\d+)"),
}
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def _clean_block(b: str) -> str:
    b = re.sub(r"\d{1,2}/\d{1,2}/\d{2},\s*\d{1,2}:\d{2}\s*[AP]M[^\n]*", "", b)
    b = re.sub(r"Here is Voucher Notice[^\n]*", "", b)
    b = re.sub(r"Sign On Behalf Of[^\n]*", "", b)
    return b


_FIELD_PREFIX = ("Ref:", "CheckIn:", "CheckOut:", "Nights:", "ITEM:", "KK NO:", "ID:",
                 "Tel:", "Fax:", "ADT:", "T/L:", "T/G:", "SGL:", "TWN:", "DBL:")
_ADDR_HINT = (" Rd", " Road", " Street", " Ave", " Highway", " Drive", " Crescent",
              " Place", " Terrace", "Sainsbury", "SH5", "Quay", "Cnr", "PO Box",
              "Quadrant", "Memorial", "Pakihau", "Blenheim", "Amohau", "Eruera",
              "Mayoral", "Rattray", "Humber", "Buckland", "Ngongotaha", "Western Road")


def parse_vouchers(text: str) -> list[Voucher]:
    out: list[Voucher] = []
    for raw in re.split(r"(?=Voucher\s*#\s*\d{5,})", text):
        if not _RE_VNO.search(raw):
            continue
        b = _clean_block(raw)
        v = Voucher(raw=b)
        v.vno = _RE_VNO.search(b).group(1)
        for k, rx in _RE_FIELD.items():
            m = rx.search(b)
            if m:
                setattr(v, k, int(m.group(1)))

        m = re.search(r"ITEM:[ \t]*([^\n]+)", b)
        if m:
            v.item = re.split(r"\s+KK NO:", m.group(1).strip())[0].strip()
        m = re.search(r"KK NO:[ \t]*([^\n]*)", b)
        if m:
            v.kk = re.split(r"\s+ID:", m.group(1).strip())[0].strip()

        m = re.search(r"CheckIn:\s*\w{3,4},?\s*(\d{1,2})\s+([A-Z]{3})\s+(\d{4})(?:\s*(\d{1,2}:\d{2}))?", b)
        if m:
            try:
                v.date = date(int(m.group(3)), _MONTHS.get(m.group(2).upper(), 1), int(m.group(1)))
            except Exception:
                v.date = None
            v.time = m.group(4) or ""
        m = re.search(r"DATE:\s*([\d-]+)", b)
        v.date_text = m.group(1) if m else ""

        lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
        di = next((i for i, ln in enumerate(lines) if ln.startswith("DATE:")), None)

        # 兼容两种 PDF 版面：pdfplumber（Ref 独占一行）与 pdftotext -layout（供应商与 Ref 同行）
        cand = ""
        mm = re.search(r"(?m)^[ \t]{0,20}([^\n]*?\S)[ \t]+Ref:", b)
        if mm:
            cand = mm.group(1).strip()
            if len(cand) < 3 or any(h in cand for h in _ADDR_HINT) or "CheckIn" in cand:
                cand = ""
        sup: list[str] = [cand] if cand else []
        if not sup and di is not None:
            for ln in lines[di + 1:]:
                if ln.startswith(_FIELD_PREFIX):
                    break
                if re.match(r"^\d", ln) or any(h in ln for h in _ADDR_HINT):
                    break
                if sup and ln.lower() in sup[-1].lower():
                    continue
                if len(sup) >= 3:
                    break
                sup.append(ln)
        v.supplier = " ".join(sup).strip()

        ni = next((i for i, ln in enumerate(lines) if ln.startswith("ID:")), None)
        if ni is not None:
            tail = []
            for ln in lines[ni + 1:]:
                if "Sign On Behalf Of" in ln:
                    ln = ln.split("Sign On Behalf Of")[0].strip()
                    if ln:
                        tail.append(ln)
                    break
                if ln.startswith(_FIELD_PREFIX):
                    continue
                tail.append(ln)
            v.note = " / ".join(tail)[:300]
        if v.supplier:
            out.append(v)
    return out


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def detect_file_kind(name: str, data: bytes) -> str:
    name = name.lower()
    if name.endswith(".xlsx"):
        return "ops"
    if name.endswith(".docx"):
        return "docx"
    if name.endswith(".pdf"):
        txt = load_pdf_text(data)
        if "Voucher" in txt and "Ref:" in txt:
            return "voucher_pdf"
        if re.search(r"\bItinerary\b|路书|行程单", txt, re.I):
            return "itinerary_pdf"
        return "pdf"
    return "unknown"


def parse_cn_text(text: str, depart: date | None) -> CnItinerary:
    """段落式（PDF / 纯文本）中文行程的兜底解析。"""
    it = CnItinerary(raw_text=text)
    marks = list(re.finditer(r"第\s*([一二三四五六七八九十\d]+)\s*天", text))
    for i, m in enumerate(marks):
        no = cn_day_to_int(m.group(1))
        if no is None:
            continue
        chunk = text[m.start(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        d = DayPlan(no=no, date=(depart + timedelta(days=no - 1)) if depart else None)
        d.title = chunk.split("\n", 1)[0][:120]
        for key, label in (("breakfast", "早餐"), ("lunch", "午餐"), ("dinner", "晚餐")):
            mm = re.search(label + r"[：:]\s*([^\n]+)", chunk)
            if mm:
                d.meals[key] = mm.group(1).strip()
        mm = re.search(r"住宿[：:]\s*([^\n]+)", chunk)
        if mm:
            d.hotel = mm.group(1).strip()
        d.detail = re.sub(r"(早餐|午餐|晚餐|住宿)[：:][^\n]+", "", chunk)[:800]
        it.days.append(d)
    return it


def parse_cn_any(data: bytes, name: str, depart: date | None) -> CnItinerary:
    if name.lower().endswith(".docx"):
        it = parse_cn_itinerary(data, depart)
        if it.days:
            return it
        paras, _ = load_docx(data)
        return parse_cn_text("\n".join(paras), depart)
    return parse_cn_text(load_pdf_text(data), depart)
