# -*- coding: utf-8 -*-
"""
发布/更新 Momcozy Google Play 评分看板到 app-data 平台 (云端版)。
用法:
  python publish.py update   # 日常: preview -> update(用 dashboard_get 取版本)
认证: 优先环境变量 MCP_TOKEN (GitHub Secret), 否则 mcp_token.txt, 最后内置 token 兜底
"""
import io, json, os, sys, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MCP_URL = "https://app-data-mcp.luteos.site/mcp"
TOKEN_FILE = os.path.join(BASE, "mcp_token.txt")
HTML_PATH = os.path.join(BASE, "dashboard_platform.html")
STATE_PATH = os.path.join(BASE, "state.json")
TITLE = "Momcozy · Google Play 评分看板"
SLUG = "momcozy-gplay-rating"

_FALLBACK = "appdata_P9hYVE-RPS_IpURYinP0_f35B9k5_UC-_CmTk28EabM"  # 兜底, 可能过期, 建议配置 Secret

def load_token():
    tok = os.environ.get("MCP_TOKEN", "").strip()
    if not tok and os.path.exists(TOKEN_FILE):
        tok = open(TOKEN_FILE, encoding="utf-8").read().strip()
    if not tok:
        tok = _FALLBACK
    if not tok.lower().startswith("bearer "):
        tok = "Bearer " + tok
    return tok

_session_id = None
_req_id = 0

def _post(payload):
    global _session_id
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream",
               "Authorization": load_token()}
    if _session_id:
        headers["Mcp-Session-Id"] = _session_id
    req = urllib.request.Request(MCP_URL, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=600) as resp:
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            _session_id = sid
        body = resp.read().decode("utf-8", errors="replace")
        ctype = resp.headers.get("Content-Type", "")
    if "text/event-stream" in ctype:
        for line in body.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk and chunk != "[DONE]":
                    return json.loads(chunk)
        return None
    return json.loads(body) if body.strip() else None

def rpc(method, params=None, notify=False):
    global _req_id
    payload = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        payload["params"] = params
    if not notify:
        _req_id += 1
        payload["id"] = _req_id
    return _post(payload)

def call_tool(name, args):
    r = rpc("tools/call", {"name": name, "arguments": args})
    if r is None:
        raise RuntimeError("MCP 无响应: " + name)
    if isinstance(r, dict) and "error" in r:
        raise RuntimeError(f"MCP 错误({name}): {json.dumps(r['error'], ensure_ascii=False)[:300]}")
    return r

def extract(res):
    if isinstance(res, dict) and "result" in res:
        res = res["result"]
    if isinstance(res, dict):
        content = res.get("content") or []
        raw = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
        try:
            p = json.loads(raw)
            if isinstance(p, str):
                try:
                    return json.loads(p)
                except Exception:
                    return p
            return p
        except Exception:
            return raw
    return res

def preview(turn):
    with io.open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    res = extract(call_tool("dashboard_preview", {
        "question": "更新 Momcozy Google Play 评分看板（静态数据快照，每日09:00自动刷新）",
        "turn_id": turn,
        "source": {"title": TITLE, "html": html, "libraries": ["chartjs@4.4.1"]},
    }))
    with io.open(os.path.join(BASE, "preview_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    v = (res or {}).get("validation") or {}
    errs = v.get("errors") or []
    pid = (res or {}).get("previewId") or (res or {}).get("id")
    print("preview:", "browser=" + str(v.get("browser")), "errors=" + str(len(errs)), "previewId=" + str(pid))
    for e in errs[:5]:
        print("  ERR:", json.dumps(e, ensure_ascii=False)[:200])
    if v.get("browser") != "passed" or errs:
        raise SystemExit("preview 校验未通过")
    return pid

def load_state():
    if os.path.exists(STATE_PATH):
        return json.load(open(STATE_PATH, encoding="utf-8"))
    return {}

def save_state(st):
    with io.open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "update"
    rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "gplay-dashboard", "version": "1.0"}})
    rpc("notifications/initialized", {}, notify=True)
    st = load_state()

    if action == "update":
        if not st.get("id"):
            raise SystemExit("state.json 无看板 id")
        got = extract(call_tool("dashboard_get", {
            "question": "读取当前看板版本", "turn_id": "gplay-get-1", "id": st["id"]}))
        ver = (got or {}).get("version")
        print("current version:", ver)
        pid = preview("gplay-update-" + str(int(__import__("time").time())))
        res = extract(call_tool("dashboard_update", {
            "question": "每日定时更新 Momcozy Google Play 评分看板数据",
            "turn_id": "gplay-update-1",
            "id": st["id"], "expectedVersion": ver, "previewId": pid,
            "idempotencyKey": "momcozy-gplay-update-" + str(int(__import__("time").time())),
            "status": "published"}))
        print("updated:", (res or {}).get("dashboardUrl"), "version=", (res or {}).get("version"))
        save_state({"id": st["id"], "url": (res or {}).get("dashboardUrl") or st.get("url"),
                    "version": (res or {}).get("version")})
    else:
        raise SystemExit("云端版仅支持 update (看板已在平台创建, 无需 init)")

if __name__ == "__main__":
    main()
