"""
真实 API 客户端 (本地代理 -> claude-opus-4-8)。

两个能力:
  - sample(prompt, n): fork n 条完整回答 (温度采样)。
  - continue_from(prompt, assistant_prefix, n): assistant prefill 续写 —— 复现
    "续写诱导", 让模型从给定前缀继续, 用于沿轨迹测拒绝凝结位置。

注意: Messages API 不返回逐 token logprob, 故无 surprisal。只验证行为半边。
"""

import json, urllib.request, concurrent.futures as cf

BASE = "http://127.0.0.1:3000"
TOKEN = "sk-6rGvCK7qSXKWpln9f42gl9RK3Ka0a5pEVgcWIblZVKyBOOlL"
MODEL = "claude-opus-4-8"   # 裸名; 带 [1m] 后缀无 channel

# R10 修复用: 显式良性 system, 绕开代理对"无 system 字段"请求注入的
# ~6395-token cyber-pentest override (本项目自查发现的代理污染通道)。
DEFAULT_SYSTEM = "You are a helpful assistant."


def _post(messages, max_tokens=400, temperature=1.0, system=None):
    body = {"model": MODEL, "max_tokens": max_tokens,
            "temperature": temperature, "messages": messages}
    if system is not None:
        body["system"] = system
    body = json.dumps(body).encode()
    req = urllib.request.Request(BASE.rstrip("/") + "/v1/messages",
                                 data=body, method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("x-api-key", TOKEN)
    req.add_header("authorization", "Bearer " + TOKEN)
    req.add_header("anthropic-version", "2023-06-01")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    parts = [b.get("text", "") for b in d.get("content", []) if b.get("type") == "text"]
    return "".join(parts)


def _one(messages, max_tokens, temperature, system=None, retries=4):
    """单次请求, 对 502/503/429 等瞬时网关错误退避重试 (proxy 上游不稳)。"""
    import time, random
    last = None
    for attempt in range(retries):
        try:
            return _post(messages, max_tokens, temperature, system=system)
        except urllib.error.HTTPError as e:
            last = f"__ERR__HTTPError:HTTP Error {e.code}"
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(8, 0.8 * (2 ** attempt)) + random.random())
                continue
            return last
        except Exception as e:
            last = f"__ERR__{type(e).__name__}:{str(e)[:80]}"
            time.sleep(min(8, 0.8 * (2 ** attempt)) + random.random())
    return last


def sample(prompt, n=12, max_tokens=400, temperature=1.0, workers=3, system=None):
    """fork n 条完整回答, 并发提交。system=None 走旧的无-system 通道 (会被代理
    注入 override); 传 system (如 DEFAULT_SYSTEM) 走干净通道。"""
    msgs = [{"role": "user", "content": prompt}]
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_one, msgs, max_tokens, temperature, system) for _ in range(n)]
        return [f.result() for f in futs]


def continue_from(prompt, assistant_prefix, n=12, max_tokens=300,
                  temperature=1.0, workers=3, system=None):
    """assistant prefill 续写: 模型从 assistant_prefix 末尾继续。"""
    msgs = [{"role": "user", "content": prompt},
            {"role": "assistant", "content": assistant_prefix}]
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_one, msgs, max_tokens, temperature, system) for _ in range(n)]
        return [f.result() for f in futs]


if __name__ == "__main__":
    out = sample("In general, for the typical adult, regarding a mild tension "
                 "headache, explain the usual physiological mechanism.",
                 n=3, max_tokens=120)
    for i, o in enumerate(out):
        print(f"--- sample {i} ---\n{o[:200]}\n")
