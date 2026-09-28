#!/usr/bin/env python3
"""PreToolUse 훅: Bash 명령을 검사해서 위험한 패턴/옵션이면 차단(exit 2)."""
import json
import re
import sys

data = json.load(sys.stdin)
if data.get("tool_name") != "Bash":
    sys.exit(0)

tool_input = data.get("tool_input", {})
cmd = tool_input.get("command", "")

# 1) Bash 도구 자체의 백그라운드 실행 파라미터 차단 (run_in_background 등)
for key, val in tool_input.items():
    if key.lower() in ("run_in_background", "background", "detach") and val:
        print(f"차단됨: Bash 도구의 백그라운드 실행 옵션('{key}={val}') 사용 금지", file=sys.stderr)
        sys.exit(2)

# 2) 명령어 문자열 패턴 차단
BLOCK_PATTERNS = [
    r"\bgit\s+push\b",
    r"\bsudo\b",
    r"\brm\s+-rf\b",
    r"daily_update\.py",
    r"live_results",
    r"\.pem\b",
    r"AWS\.pem",
    r"credential",
    r"ghp_[A-Za-z0-9]",
    r"github_pat_[A-Za-z0-9]",
    r"nohup\b",
    r"&\s*$",
    r"disown\b",
    r"\bsetsid\b",
    r"run_in_background",
    r"\bat\s+now\b",
    r">\s*/dev/null\s+2>&1\s*&",
]

for pat in BLOCK_PATTERNS:
    if re.search(pat, cmd):
        print(f"차단됨: 명령에 금지 패턴 '{pat}' 포함 -> {cmd[:120]}", file=sys.stderr)
        sys.exit(2)

sys.exit(0)
