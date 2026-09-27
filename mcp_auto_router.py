#!/usr/bin/env python3
"""toma-auto-router — an MCP server that routes a task to the right model tier.

Exposes two MCP tools over stdio (JSON-RPC 2.0):

  route_task(task)  -> classify a task by difficulty and recommend a model
  stack_info()      -> print the full configured tier table

The router is pure heuristics: weighted keyword rules in several languages,
plus length/context signals. No network, no API keys, no dependencies —
standard library only, so it runs under any Python >= 3.8 (including the
3.9 that ships with macOS).

Configuration
-------------
Tiers and rules have working defaults tuned for a DeepSeek + OpenRouter +
Ollama stack. Override them without touching this file:

    AUTO_ROUTER_CONFIG=/path/to/config.json
    # or
    python3 mcp_auto_router.py --config /path/to/config.json

The JSON file may contain any subset of:

    {"tiers": {...}, "signals": [[level, weight, "regex"], ...], "default_level": "easy"}

Wire it into any MCP host (Claude Desktop, Hermes, Cursor, ...):

    {
      "mcpServers": {
        "auto-router": {
          "command": "python3",
          "args": ["/absolute/path/to/mcp_auto_router.py"]
        }
      }
    }

License: MIT.
"""

import argparse
import json
import os
import re
import sys

SERVER_NAME = "toma-auto-router"
SERVER_VERSION = "1.2.0"
DEFAULT_PROTOCOL = "2024-11-05"
DEFAULT_LEVEL = "easy"

# ---------------------------------------------------------------------------
# Default tiers — edit for your own stack.
# ---------------------------------------------------------------------------
DEFAULT_TIERS = {
    "easy": {
        "provider": "deepseek",
        "model": "deepseek-flash",
        "alias": None,
        "why": "Volume work: plain text, translations, files, link checks.",
        "cost": "~$0.14/$0.28 per 1M tokens",
        "latency": "~2s",
    },
    "medium": {
        "provider": "openrouter",
        "model": "qwen/qwen3.8-flash",
        "alias": "or-qwen",
        "why": "Mid-sized tasks: drafting, summarising, light synthesis.",
        "cost": "~$0.00003 per call",
        "latency": "~4s",
    },
    "hard": {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "alias": None,
        "why": "Complex reasoning: papers, grant proposals, deep analysis.",
        "cost": "~$0.435/$0.87 per 1M tokens",
        "latency": "~5s",
    },
    "offline": {
        "provider": "ollama",
        "model": "gemma3:12b",
        "alias": None,
        "why": "Sensitive data, no network, zero cost.",
        "cost": "$0 (local)",
        "latency": "~19 tok/s",
    },
}

# ---------------------------------------------------------------------------
# Default signal rules: (level, weight, regex). Weight scales with hit count.
# Written multi-lingual on purpose — a task is often described in the user's
# own language, not in English.
# ---------------------------------------------------------------------------
DEFAULT_SIGNALS = [
    ("hard", 12, r"\b(article|paper|manuscript|grant|proposal|project|thesis|"
                 r"dissertation|analys|reason|deduc|strateg|architect|audit|"
                 r"methodolog|statistic|biostatistic|model(?:l)?ing|optimi[sz]|"
                 r"articol|isi|bdi|cerere|finantare|propunere|teza|dizertat|"
                 r"recenz|review|lucrare stiintifica)"),
    ("hard", 8, r"\b(prove|justify|compare|evaluate|interpret|diagnose|debug|"
                r"refactor|design|demonstrat|justific|compar|evalu|interpreteaz|"
                r"depaneaz|proiecteaz)"),
    ("offline", 10, r"\b(confidential|sensitive|gdpr|offline|local|private|"
                    r"no internet|do not send|personal data|confidential|"
                    r"sensibil|fara internet|nu trimite|date personale)"),
    ("medium", 6, r"\b(summar|synthes|translat|rewrite|draft|generate|explain|"
                  r"structure|plan|organi[sz]e|rezum|sintez|traduc|rescrie|"
                  r"redacteaz|genereaz|explic|structur|planific|organizeaz)"),
    ("easy", 4, r"\b(translate|fix|format|copy|list|count|extract|rename|convert|"
                r"delete|corecteaz|copie|listeaza|numara|extrage|redenumeste|"
                r"converteste|sterge)"),
]

LONG_CONTEXT_RE = r"\b(document|pdf|manuscript|report|thesis|book|volume|whole|chapter|" \
                  r"raport|manuscris|cart|volum|intreg|capitol)"

# ---------------------------------------------------------------------------
# Runtime configuration (defaults, optionally overridden by a JSON file)
# ---------------------------------------------------------------------------
TIERS = {k: dict(v) for k, v in DEFAULT_TIERS.items()}
SIGNALS = list(DEFAULT_SIGNALS)


def load_config(path):
    """Merge a JSON config over the defaults. Unknown keys are ignored."""
    global TIERS, SIGNALS, DEFAULT_LEVEL
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write("toma-auto-router: cannot read %s: %s\n" % (path, exc))
        return

    if isinstance(data.get("tiers"), dict):
        for name, tier in data["tiers"].items():
            merged = dict(TIERS.get(name, {}))
            merged.update(tier)
            TIERS[name] = merged

    if isinstance(data.get("signals"), list):
        parsed = []
        for item in data["signals"]:
            if isinstance(item, list) and len(item) == 3:
                try:
                    parsed.append((str(item[0]), int(item[1]), str(item[2])))
                except (TypeError, ValueError):
                    continue
        if parsed:
            SIGNALS = parsed

    if isinstance(data.get("default_level"), str):
        DEFAULT_LEVEL = data["default_level"]


def classify(task):
    """Return (level, scores, matched_signals). Highest score wins."""
    text = (task or "").lower()
    scores = {name: 0 for name in TIERS}
    hits = []

    for level, weight, pattern in SIGNALS:
        try:
            found = re.findall(pattern, text, flags=re.IGNORECASE)
        except re.error:
            continue
        if found and level in scores:
            scores[level] += weight * len(found)
            hits.append("%s(+%d)" % (level, weight * len(found)))

    if re.search(LONG_CONTEXT_RE, text, flags=re.IGNORECASE) and len(text) > 400:
        scores["hard"] = scores.get("hard", 0) + 5
        hits.append("hard(+5 long context)")
    if len(text) > 1200:
        scores["hard"] = scores.get("hard", 0) + 4
        hits.append("hard(+4 large request)")

    if not scores:
        return DEFAULT_LEVEL, scores, hits + ["default: no tiers configured"]

    order = list(TIERS)
    best = max(order, key=lambda k: (scores.get(k, 0), order.index(k)))
    if scores.get(best, 0) == 0:
        best = DEFAULT_LEVEL if DEFAULT_LEVEL in TIERS else order[0]
        hits.append("default")
    return best, scores, hits


def route(task):
    level, scores, hits = classify(task)
    tier = dict(TIERS.get(level, {}))
    tier["level"] = level
    tier["scores"] = scores
    tier["matched"] = hits
    alias = tier.get("alias")
    if alias:
        tier["invoke"] = "/model %s" % alias
    elif level == DEFAULT_LEVEL:
        tier["invoke"] = "already the default"
    else:
        tier["invoke"] = "/model %s" % tier.get("model", "?")
    return tier


TOOLS = [
    {
        "name": "route_task",
        "description": (
            "Classify a task by difficulty and recommend the provider and model "
            "from the configured tier table. Call it before picking a model for "
            "a new task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task to route."}
            },
            "required": ["task"],
        },
    },
    {
        "name": "stack_info",
        "description": "Print the full configured model stack and its costs.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def send(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def send_result(req_id, payload):
    send({"jsonrpc": "2.0", "id": req_id, "result": payload})


def send_error(req_id, code, message):
    send({"jsonrpc": "2.0", "id": req_id,
          "error": {"code": code, "message": message}})


def handle(msg):
    method = msg.get("method")
    req_id = msg.get("id")

    if method == "initialize":
        params = msg.get("params") or {}
        send_result(req_id, {
            "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
        return

    if method in ("notifications/initialized", "notifications/cancelled"):
        return

    if method == "ping":
        send_result(req_id, {})
        return

    if method == "tools/list":
        send_result(req_id, {"tools": TOOLS})
        return

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "route_task":
            payload = route(args.get("task", ""))
        elif name == "stack_info":
            payload = {"tiers": TIERS, "order": list(TIERS),
                       "default_level": DEFAULT_LEVEL}
        else:
            send_error(req_id, -32602, "Unknown tool: %s" % name)
            return
        send_result(req_id, {
            "content": [{"type": "text",
                         "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "isError": False,
        })
        return

    if req_id is not None:
        send_error(req_id, -32601, "Unknown method: %s" % method)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=os.environ.get("AUTO_ROUTER_CONFIG"),
                        help="JSON file overriding tiers/signals "
                             "(or set AUTO_ROUTER_CONFIG)")
    parser.add_argument("--route", metavar="TASK",
                        help="classify TASK once and exit (no MCP server) "
                             "— handy for testing")
    args = parser.parse_args()

    if args.config:
        load_config(args.config)

    if args.route:
        print(json.dumps(route(args.route), ensure_ascii=False, indent=2))
        return

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        try:
            handle(msg)
        except Exception as exc:  # a server must never die on one bad message
            if isinstance(msg, dict) and msg.get("id") is not None:
                send_error(msg["id"], -32603, "Internal error: %s" % exc)


if __name__ == "__main__":
    main()
