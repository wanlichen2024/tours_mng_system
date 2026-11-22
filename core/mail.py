# -*- coding: utf-8 -*-
"""邮件解析、分类摘要与问答检索。

不依赖任何第三方库：eml/zip 用标准库解析，AI 用 OpenAI 兼容接口。
"""
from __future__ import annotations

import email
import hashlib
import html
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from email.header import decode_header as _decode_hdr
from email.header import make_header as _make_hdr
from email.utils import parsedate_to_datetime
from typing import Iterable

from . import llm

PRIORITIES = ("P0", "P1", "P2", "P3")
PRIORITY_LABEL = {"P0": "今天必须处理", "P1": "今天回复",
                  "P2": "本周跟进", "P3": "可略读"}
CATEGORIES = ("供应商", "客人", "组团社", "财务", "平台/通知", "其他")


@dataclass
class Mail:
    id: str = ""
    msgid: str = ""
    sender: str = ""
    subject: str = ""
    date: str = ""
    body: str = ""
    category: str = ""
    priority: str = ""
    summary: str = ""
    action: str = ""
    deadline: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def label(self) -> str:
        return f"[{self.id}] {self.subject}"

    @property
    def cite(self) -> str:
        d = f" · {self.date}" if self.date else ""
        return f"[{self.id}] {self.sender}{d}｜{self.subject}"


# ---------------------------------------------------------------- 解析

def decode_header(value: str) -> str:
    try:
        return str(_make_hdr(_decode_hdr(value or "")))
    except Exception:
        return value or ""


def decode_bytes(raw: bytes, charset: str | None) -> str:
    for enc in (charset, "utf-8", "gb18030", "big5"):
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "ignore")


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def body_text(msg: email.message.Message, limit: int = 4000) -> str:
    plain, rich = "", ""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = decode_bytes(payload, part.get_content_charset())
        if ctype == "text/plain" and not plain:
            plain = text
        elif ctype == "text/html" and not rich:
            rich = html_to_text(text)
    out = plain.strip() or rich
    out = re.sub(r"\n{3,}", "\n\n", out)
    # 去掉引用历史，避免同一段内容重复进上下文
    out = re.split(r"\n(?:-{2,}\s*Original Message|-{2,}\s*原始邮件|On .+ wrote:)", out)[0]
    return out[:limit]


def _msg_to_mail(msg, idx: int) -> Mail:
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
        date_str = dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        date_str = ""
    mid = (msg.get("Message-ID") or "").strip()
    if not mid:
        raw = f"{msg.get('From')}|{msg.get('Subject')}|{msg.get('Date')}"
        mid = "sha1:" + hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()
    return Mail(
        id=f"m{idx}",
        msgid=mid,
        sender=decode_header(msg.get("From", "")),
        subject=decode_header(msg.get("Subject", "")) or "(无主题)",
        date=date_str,
        body=body_text(msg),
    )


def parse_upload(name: str, data: bytes, start: int = 1, limit: int = 60) -> list[Mail]:
    """支持 .eml 单封、.zip 批量（网页版导出的就是 zip 里塞 eml）。"""
    blobs: list[bytes] = []
    if name.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    if info.is_dir() or not info.filename.lower().endswith((".eml", ".msg")):
                        continue
                    blobs.append(z.read(info))
        except Exception:
            return []
    else:
        blobs.append(data)

    out: list[Mail] = []
    for raw in blobs:
        try:
            msg = email.message_from_bytes(raw)
        except Exception:
            continue
        out.append(_msg_to_mail(msg, start + len(out)))
        if len(out) >= limit:
            break
    return out


def relabel(mails: list[Mail]) -> list[Mail]:
    for i, m in enumerate(mails, 1):
        m.id = f"m{i}"
    return mails


# ---------------------------------------------------------------- 分类摘要

ANALYZE_PROMPT = """你是新西兰入境游公司的运营助理。下面是今天收到的未读邮件，请逐封归类并给出可执行的摘要。

优先级：
- P0 今天必须处理：有截止时间、供应商确认/取消、付款、航班或酒店变更、客人投诉
- P1 今天回复：客人或组团社在等答复、需要确认的预订、常规业务往来
- P2 本周跟进：报价、账单、资料补充
- P3 可略读：系统通知、推广、无需回复的抄送

类别：供应商 / 客人 / 组团社 / 财务 / 平台/通知 / 其他

要求：
1. 每封给一句话中文摘要（不超过 40 字），保留关键数字、日期、确认号、航班号。
2. action 写动词开头的具体动作；没有动作就留空字符串。
3. 同一件事的多封邮件各自归类，但 action 可以相同。
4. 邮箱地址、公司名保持原文。
5. 只输出 JSON：

{
  "digest": "两三句话说明今天的整体情况，按重要程度说",
  "emails": [
    {"id": "m1", "category": "供应商", "priority": "P0",
     "summary": "…", "action": "…", "deadline": "…"}
  ],
  "todos": ["按优先级排列的今日待办"]
}"""


def _fallback_analyze(mails: list[Mail]) -> dict:
    urgent = ("urgent", "asap", "cancel", "确认", "取消", "变更", "payment",
              "invoice", "付款", "发票", "deadline", "today")
    for m in mails:
        text = (m.subject + " " + m.body[:400]).lower()
        m.priority = "P1" if any(k in text for k in urgent) else "P2"
        m.category = "其他"
        m.summary = m.subject[:40]
        m.action = ""
    return {"digest": f"共 {len(mails)} 封邮件（未启用 AI，仅按关键词粗分）。",
            "emails": [], "todos": []}


def analyze(mails: list[Mail], api_key: str, base_url: str = "https://api.deepseek.com",
            model: str = "deepseek-chat", max_emails: int = 30) -> dict:
    if not api_key:
        return _fallback_analyze(mails)

    payload = []
    for m in mails[:max_emails]:
        payload.append({"id": m.id, "from": m.sender, "subject": m.subject,
                        "date": m.date, "body": m.body[:1000]})
    user = "邮件列表（JSON）：\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    text = llm.chat([{"role": "system", "content": ANALYZE_PROMPT},
                     {"role": "user", "content": user}],
                    api_key, base_url, model, json_mode=True)
    data = llm.loads_json(text)
    by_id = {m.id: m for m in mails}
    for item in data.get("emails", []) or []:
        m = by_id.get(str(item.get("id", "")))
        if not m:
            continue
        p = str(item.get("priority", "")).upper()
        m.priority = p if p in PRIORITIES else "P2"
        cat = str(item.get("category", "")).strip()
        m.category = cat if cat in CATEGORIES else "其他"
        m.summary = str(item.get("summary", "")).strip()
        m.action = str(item.get("action", "")).strip()
        m.deadline = str(item.get("deadline", "")).strip()
    for m in mails:
        if not m.priority:
            m.priority = "P2"
        if not m.category:
            m.category = "其他"
        if not m.summary:
            m.summary = m.subject[:40]
    return {"digest": str(data.get("digest", "")).strip(),
            "emails": data.get("emails", []),
            "todos": data.get("todos", []) or []}


def group_by_priority(mails: Iterable[Mail]) -> dict[str, list[Mail]]:
    groups: dict[str, list[Mail]] = {p: [] for p in PRIORITIES}
    for m in mails:
        groups.setdefault(m.priority or "P2", []).append(m)
    return groups


# ---------------------------------------------------------------- 问答检索

_STOP = set("的 了 是 在 我 你 他 她 它 这 那 有 和 与 就 也 都 要 请问 一下 帮我 关于 那个 这个 邮件 邮件里".split())


def _terms(text: str) -> list[str]:
    text = (text or "").lower()
    words = re.findall(r"[a-z0-9@._-]{2,}", text)
    han = re.findall(r"[\u4e00-\u9fa5]+", text)
    grams = []
    for seg in han:
        if len(seg) == 1:
            grams.append(seg)
        for i in range(len(seg) - 1):
            grams.append(seg[i:i + 2])
    return [t for t in words + grams if t not in _STOP]


def rank(mails: list[Mail], question: str, k: int = 5) -> list[Mail]:
    terms = _terms(question)
    if not terms:
        return mails[:k]
    scored = []
    for m in mails:
        hay = (m.sender + " " + m.subject + " " + m.summary + " " + m.body).lower()
        score = 0
        for t in terms:
            score += hay.count(t) * (3 if t in m.subject.lower() else 1)
        if m.priority == "P0":
            score += 1
        if score:
            scored.append((score, m))
    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:k]] or mails[:k]


CHAT_PROMPT = """你是新西兰入境游公司的运营助理，正在和操作员对话。下面会给出「今天邮件的清单」以及「与问题最相关的几封邮件全文」。

规则：
1. 只依据给出的邮件内容回答，不要编造发件人、日期、金额、确认号。
2. 引用邮件时用编号，如 [#m3]。
3. 如果邮件里没有答案，直接说「这几封邮件里没有提到」，并指出该去问谁或查什么。
4. 需要起草回复时，给出可直接发送的正文，中文或英文按对方语言。
5. 回答简洁，先给结论，再给依据；不要复述整封邮件。
6. 涉及日期、航班号、确认号、人数、房型时原样保留。"""


def answer(question: str, mails: list[Mail], history: list[dict],
           api_key: str, base_url: str = "https://api.deepseek.com",
           model: str = "deepseek-chat") -> str:
    if not api_key:
        return "还没有配置 AI Key。在左侧填入 API Key 后就能对话；也可以先用上面的摘要看邮件分类。"

    index_lines = []
    for m in mails:
        index_lines.append(f"[{m.id}] {m.date} | {m.priority} | {m.sender} | "
                           f"{m.subject} | {m.summary or m.subject[:30]}")
    hits = rank(mails, question, k=5)
    detail = []
    for m in hits:
        detail.append(f"===== [{m.id}] {m.subject} =====\n"
                      f"From: {m.sender}\nDate: {m.date}\n\n{m.body[:1500]}")

    context = ("【今日邮件清单】\n" + "\n".join(index_lines) +
               "\n\n【与问题最相关的邮件全文】\n" + "\n\n".join(detail))

    messages = [{"role": "system", "content": CHAT_PROMPT},
                {"role": "user", "content": context}]
    for h in history[-8:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": question})
    return llm.chat(messages, api_key, base_url, model, temperature=0.3)


def digest_text(mails: list[Mail], digest: str = "") -> str:
    lines = []
    if digest:
        lines += [digest, ""]
    for p in PRIORITIES:
        group = [m for m in mails if (m.priority or "P2") == p]
        if not group:
            continue
        lines.append(f"{p} · {PRIORITY_LABEL[p]}（{len(group)}）")
        for m in group:
            lines.append(f"  · [{m.id}] {m.summary or m.subject}")
            if m.action:
                lines.append(f"    动作：{m.action}")
            if m.deadline:
                lines.append(f"    截止：{m.deadline}")
        lines.append("")
    return "\n".join(lines)
