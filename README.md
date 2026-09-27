# toma-auto-router

**Route each task to the cheapest model that can actually do it.**

An MCP server (plus a Hermes Desktop plugin) that classifies a task by
difficulty and recommends a model from a configurable tier table. Pure
heuristics, standard library only — no API keys, no network, no dependencies.

```
"Write an ISI paper on biofertilisers"   →  hard     deepseek/deepseek-v4-pro
"Translate the first stanza"             →  easy     deepseek/deepseek-flash
"HR records — GDPR, no internet"         →  offline  ollama/gemma3:12b
"Summarise this report"                  →  medium   openrouter/qwen3.8-flash
```

---

## Why

Most people run one expensive frontier model for everything, or one weak local
model for everything. Both waste something. A tiered stack costs less *and*
runs faster — but only if the routing is not a manual decision you make twenty
times a day.

This tool makes that decision explicit, inspectable and cheap: keyword rules
weighted across four levels, in several languages, tuned by you in a JSON file.

## Layout

```
mcp_auto_router.py          MCP server — exposes route_task() and stack_info()
desktop-plugin/plugin.js    Hermes Desktop UI: side pane, status chip, ⌘K entries
config.example.json         Example tier/signal override
```

## Install — MCP server

No dependencies. Any Python ≥ 3.8 (including the 3.9 that ships with macOS).

```bash
git clone https://github.com/Radu-Cristian-Toma/toma-auto-router.git
cd toma-auto-router
python3 mcp_auto_router.py --route "Write a grant proposal"   # smoke test
```

Register it with any MCP host. Hermes:

```bash
hermes mcp add auto-router --command /usr/bin/python3 \
  --args ~/.hermes/mcp_auto_router.py
```

Claude Desktop / Cursor (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "auto-router": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_auto_router.py"]
    }
  }
}
```

Restart the host. The server speaks JSON-RPC 2.0 over stdio
(`initialize` → `tools/list` → `tools/call`) and answers on two tools:

| Tool | Purpose |
|---|---|
| `route_task(task)` | Classify a task; return level, provider, model, scores and the matched rules |
| `stack_info()` | Print the whole tier table with costs |

## Install — Hermes Desktop plugin

```bash
mkdir -p ~/.hermes/desktop-plugins/model-router
cp desktop-plugin/plugin.js ~/.hermes/desktop-plugins/model-router/
```

The folder name must equal the plugin `id`. Then **⌘Q** and reopen the app — it
adds a right-hand pane, a status-bar chip showing the live model, and ⌘K
entries (`Router: Deep → deepseek-v4-pro`).

Clicking a tier writes `/model <alias>` into the composer **without sending
it**. You press Enter. Nothing switches behind your back.

## Configure your own stack

Defaults are tuned for a DeepSeek + OpenRouter + Ollama setup. Override them
without editing the source:

```bash
cp config.example.json config.json
AUTO_ROUTER_CONFIG=./config.json python3 mcp_auto_router.py
# or
python3 mcp_auto_router.py --config ./config.json
```

Any subset of `tiers`, `signals` and `default_level` may be given; everything
else falls back to the defaults. `signals` entries are
`[level, weight, regex]` — the weight is multiplied by the number of matches,
so a task mentioning both *paper* and *statistics* scores higher on `hard`.

### Tuning

- **Too much on `hard`?** Lower its weights, or add a counterweight.
- **`offline` never fires?** Your keywords are in another language — the
  defaults carry English and Romanian only.
- **Wrong winner between two levels?** Check `scores` in the JSON output;
  levels are compared by weight first, then by declaration order in `tiers`.

## Limitations — read this

- **Heuristics, not a classifier.** It reads keywords and length. It has no
  idea what your task actually requires.
- **A wrong route is silent.** Nothing verifies the answer afterwards. Treat
  the output as advice, not as a gate.
- **Two languages only** in the defaults (English, Romanian).
- **Not a cost optimiser.** It does not read your billing data. The `cost`
  fields are hand-written strings for display.

## License

MIT — see [LICENSE](LICENSE).

---

# toma-auto-router (RO)

**Trimite fiecare sarcină către cel mai ieftin model care o poate duce la capăt.**

Un server MCP (plus un plugin pentru Hermes Desktop) care clasifică o sarcină
după dificultate și recomandă un model dintr-un tabel de niveluri
configurabil. Numai euristici, doar biblioteca standard — fără chei API, fără
rețea, fără dependențe.

```
„Redactează un articol ISI despre biofertilizanți"  →  hard     deepseek/deepseek-v4-pro
„Tradu prima strofă"                                →  easy     deepseek/deepseek-flash
„Date personale — GDPR, fără internet"              →  offline  ollama/gemma3:12b
„Rezumă raportul"                                   →  medium   openrouter/qwen3.8-flash
```

## De ce

Majoritatea folosesc un singur model scump pentru tot, sau un model local slab
pentru tot. Ambele risipesc ceva. O stivă pe niveluri costă mai puțin *și*
rulează mai repede — dar numai dacă rutarea nu e o decizie manuală pe care o
iei de douăzeci de ori pe zi.

## Instalare

Fără dependențe. Orice Python ≥ 3.8 (inclusiv 3.9, cel livrat cu macOS).

```bash
git clone https://github.com/Radu-Cristian-Toma/toma-auto-router.git
cd toma-auto-router
python3 mcp_auto_router.py --route "Redactează o cerere de finanțare"   # test
```

Înregistrare la Hermes:

```bash
hermes mcp add auto-router --command /usr/bin/python3 \
  --args ~/.hermes/mcp_auto_router.py
```

Plugin Desktop:

```bash
mkdir -p ~/.hermes/desktop-plugins/model-router
cp desktop-plugin/plugin.js ~/.hermes/desktop-plugins/model-router/
```

Numele folderului trebuie să fie identic cu `id`-ul pluginului. Apoi **⌘Q** și
redeschide aplicația. Click pe un nivel scrie `/model <alias>` în composer
**fără a-l trimite** — tu confirmi cu Enter.

## Configurare proprie

```bash
cp config.example.json config.json
AUTO_ROUTER_CONFIG=./config.json python3 mcp_auto_router.py
```

Se poate da orice submulțime din `tiers`, `signals`, `default_level`; restul
cade pe valorile implicite. Intrările `signals` sunt `[nivel, greutate, regex]`.

## Limitări — de citit

- **Euristică, nu clasificator.** Citește cuvinte-cheie și lungime.
- **O rutare greșită e silențioasă.** Nimic nu verifică răspunsul după aceea.
- **Doar două limbi** în valorile implicite (engleză, română).
- **Nu e optimizator de cost.** Nu citește datele tale de facturare.

## Licență

MIT — vezi [LICENSE](LICENSE).
