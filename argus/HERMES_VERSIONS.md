# Which Hermes the Argus harness runs

Argus drives the agent under test through Hermes's ACP adapter (`python -m acp_adapter.entry`) inside
`sandboxed_agent.sh`, one fresh agent per scenario with the fixture's own `HERMES_HOME`. It never talks to a running
Hermes gateway, so it coexists with any other Hermes install on the machine. The wrapper binds the tree that the given
interpreter belongs to (`<tree>/.venv/bin/python`), or `HERMES_TREE`.

| period | tree | version | commit | note |
|---|---|---|---|---|
| until 2026-10-28 | `/mnt/TG_2TB/AI/hermes-go` | 0.20.4 | `1524739b` (2026-08-29) | **TheTom/hermes-go**, a fork of upstream Hermes Agent (Tom's mobile/desktop apps on top). Every Argus result before 2026-10-28 ran on this fork, not stock Hermes. |
| from 2026-10-28 | `/mnt/TG_2TB/AI/hermes-agent-argus` | **0.22.5** (latest stable) | `bf0203a7` (2026-10-22) | upstream `NousResearch/hermes-agent`, `uv sync --frozen --extra all`, Python 3.14.8 (the lock supports 3.14 only) |

## Update policy

- **Monthly, stable releases only.** Upstream publishes a canary build daily (`v0.22.5+canary.YYYYMMDD...`); Argus pins the
  newest stable release once a month. Mark's own Hermes install is separate and can be anything.
- **The Hermes version is part of the instrument version.** Every result records it; numbers are compared only within one
  Hermes version.
- **On each bump:** re-run the anchor panel on both versions, and audit the tool surface (the harness-agnostic core
  track mirrors Hermes's tools).
- Install: `git clone --branch <tag> --depth 1 https://github.com/NousResearch/hermes-agent.git <dir>` then
  `uv sync --frozen --extra all --python <the lock's python>`; check `python -m acp_adapter.entry --version` through the
  wrapper.
