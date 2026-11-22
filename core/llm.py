# -*- coding: utf-8 -*-
"""通用 LLM 调用（OpenAI 兼容），只用标准库。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


def chat(messages: list[dict], api_key: str,
         base_url: str = "https://api.deepseek.com",
         model: str = "deepseek-chat",
         temperature: float = 0.2, timeout: int = 180,
         json_mode: bool = False) -> str:
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        return data["choices"][0]["message"]["content"] or ""
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"AI 接口返回 {e.code}：{body}") from e
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"AI 调用失败：{e}") from e


def loads_json(text: str) -> dict:
    import re
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
                pass
    return {}
