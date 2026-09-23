# -*- coding: utf-8 -*-
"""云端版每日编排: 抓取 -> 建库/更新 -> 生成看板 -> 更新平台发布"""
import io, os, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

steps = [
    ("抓取数据(官方API+美国评论+店面快照)", os.path.join(BASE, "fetch_daily.py")),
    ("生成看板HTML", os.path.join(BASE, "build_dashboard.py")),
    ("更新平台看板", os.path.join(BASE, "publish.py"), "update"),
]
ok = True
for step in steps:
    name, script = step[0], step[1]
    args = step[2:] if len(step) > 2 else []
    print("=" * 56)
    print(">>", name)
    r = subprocess.run([sys.executable, script] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip()[-1500:])
    if r.returncode != 0:
        ok = False
        print("!! 步骤失败:", name, "exit=", r.returncode)
        break
print("=" * 56)
print("[每日更新" + ("完成" if ok else "中断") + "]")
sys.exit(0 if ok else 1)
