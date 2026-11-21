# -*- coding: utf-8 -*-
"""AI 语义核对：判断描述是否指向同一件事，而不是字面比对。"""
from __future__ import annotations

import json
import re

from .models import (Booking, CnItinerary, Finding, OpsSheet, Voucher,
                     norm_time, pax_text)

RUBRIC = """你是新西兰入境游操作部的审核专家。你的任务是把「国内中文行程」「操作表（境外实际预订）」「已发 Voucher」三者对齐，找出真正会导致落地事故或结算错误的差异。

【判断标准——必须遵守】
1. 参考酒店：中文行程里的酒店是「参考酒店」，允许用同级或升级酒店替代，不要求字面一致，不因此报错。
   只有实际酒店档次明显低于中文标注（如标注 4 钻实订 3 钻、标注市区实订郊区）才算「必改」，
   同级或升级只在有必要时给「提示」。
2. 餐食描述按「总菜品数」合并计算。例如「7 菜 1 汤 + 鹿肉」与「8 菜 1 汤含鹿肉」是同一件事（鹿肉就是第 8 道菜），
   不得判为差异。同理「2 course + burger」「3 菜 1 汤」等要还原成总道数后再比。
3. 同义、别名、简称视为一致：Chopsticks 101 = 台北 101 小火锅；Frankton Ale House = Frankton；
   「黑金鲍海鲜牛羊肉火锅」≈「鲍鱼和牛火锅」；The Station Oamaru = Station；OPERA = The Opera。
4. 全角/半角、大小写、空格、连字符、书名号差异一律不算差异。
5. 时间必须精确到分钟，但「18:00」与「18:00:00」不算差异；相差 30 分钟以上才算问题。
6. 人数口径：19 ADT + 1 TL（领队）+ 1 GUIDE（当地导游）。景点若只按 1 位陪同出票，可能是导游免票，属正常；
   但要在说明里点出「需供应商确认导游免票」。
7. 只报「实质差异」：会导致客人住错酒店、吃不上饭、进不了景点、赶不上飞机、结算金额错误、或客人手中行程与实际不符。
   纯措辞、排版、拼写问题最多给「提示」。

【输出要求】
只输出 JSON，不要 markdown 代码块，结构如下：
{
  "summary": "一段 120 字以内的总体结论",
  "findings": [
    {"level": "必改|建议|提示",
     "category": "酒店|餐饮|景点|航班|人数|确认号|行程|单号",
     "target": "中文行程|路书|Voucher|操作表",
     "where": "如 D3 11/21 晚餐 / 11/21 Movenpick",
     "current": "现在写的",
     "expected": "应该改成",
     "reason": "为什么（一句话）",
     "confidence": 0.0-1.0}
  ],
  "hotel_review": [
    {"day": "D3 11/21", "cn": "中文参考酒店", "actual": "实订酒店", "verdict": "同级可接受|升级|降级|需确认", "note": "依据"}
  ]
}
findings 按严重程度排序；没有问题时 findings 返回空数组。"""


def _deg(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or ""))
    return s[:n]


def build_facts(ops: OpsSheet, cn: CnItinerary | None,
                vouchers: list[Voucher], itinerary_text: str = "") -> dict:
    facts = {
        "团号": ops.tour_code,
        "操作表人数": ops.pax_header,
        "领队": ops.tour_leader,
        "航班原文": _deg(ops.flights_raw, 400),
        "操作表预订": [
            {
                "类型": {"hotel": "酒店", "meal": "餐饮", "attraction": "景点",
                         "meal_note": "行程内已含餐（无独立预订）"}.get(b.kind, b.kind),
                "日期": b.date.isoformat() if b.date else "",
                "供应商": b.supplier,
                "项目": b.product,
                "时间": b.time,
                "人数": b.pax,
                "房间": b.rooms,
                "确认号": b.ref,
                "备注": _deg(b.note, 80),
            }
            for b in ops.bookings
        ],
        "已发Voucher": [
            {
                "券号": v.vno, "日期": v.date.isoformat() if v.date else "",
                "供应商": v.supplier, "项目": v.item, "时间": v.time,
                "人数": pax_text(v.pax_dict), "房间": v.rooms_text,
                "确认号": v.kk, "备注": _deg(v.note, 80),
            }
            for v in vouchers
        ],
    }
    if cn:
        facts["中文行程"] = {
            "团名": cn.tour_name,
            "航班": cn.flights,
            "每日": [
                {
                    "天": d.label,
                    "标题": _deg(d.title, 120),
                    "内容": _deg(d.detail, 320),
                    "早餐": d.meals.get("breakfast", ""),
                    "午餐": d.meals.get("lunch", ""),
                    "晚餐": d.meals.get("dinner", ""),
                    "住宿": _deg(d.hotel, 80),
                }
                for d in cn.days
            ],
        }
    if itinerary_text:
        facts["已发路书原文"] = _deg(itinerary_text, 6000)
    return facts


def run_ai(facts: dict, api_key: str, base_url: str = "https://api.deepseek.com",
           model: str = "deepseek-chat", timeout: int = 120) -> dict:
    """调用 OpenAI 兼容接口（DeepSeek / OpenAI / 其他）。

    只用标准库，避免额外依赖，Streamlit Cloud 上更稳。
    """
    import urllib.error
    import urllib.request

    url = base_url.rstrip("/") + "/chat/completions"
    user = ("以下是本次核对的数据（JSON）。请按标准逐项比对，只输出 JSON。\n\n"
            + json.dumps(facts, ensure_ascii=False, indent=1))
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "system", "content": RUBRIC},
                     {"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        return {"findings": [], "summary": "", "hotel_review": [],
                "error": f"AI 接口返回 {e.code}：{body}"}
    except Exception as e:  # noqa: BLE001
        return {"findings": [], "summary": "", "hotel_review": [],
                "error": f"AI 调用失败：{e}"}

    try:
        text = json.loads(raw)["choices"][0]["message"]["content"]
    except Exception:
        return {"findings": [], "summary": "", "hotel_review": [],
                "error": "AI 返回格式异常"}

    data = _loads(text)
    if not data:
        return {"findings": [], "summary": "", "hotel_review": [],
                "error": "AI 返回内容无法解析为 JSON"}

    findings = []
    for f in data.get("findings", []) or []:
        lvl = str(f.get("level", "提示")).strip()
        if lvl not in ("必改", "建议", "提示"):
            lvl = "提示"
        findings.append(Finding(
            level=lvl,
            category=str(f.get("category", "")).strip() or "行程",
            target=str(f.get("target", "")).strip() or "路书",
            where=str(f.get("where", "")).strip(),
            current=str(f.get("current", "")).strip(),
            expected=str(f.get("expected", "")).strip(),
            reason=str(f.get("reason", "")).strip(),
            source="AI",
            confidence=float(f.get("confidence", 0.8) or 0.8),
        ))
    return {
        "findings": findings,
        "summary": str(data.get("summary", "")).strip(),
        "hotel_review": data.get("hotel_review", []) or [],
        "error": None,
    }


def _loads(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None
