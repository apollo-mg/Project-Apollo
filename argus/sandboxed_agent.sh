#!/usr/bin/env bash
# Run the agent under test inside a bubblewrap sandbox. Used as:
#   driver.py ... --agent-cmd /path/sandboxed_agent.sh <python> -m acp_adapter.entry
# The driver spawns the agent with cwd = the scenario sandbox and HERMES_HOME set, so
# both paths are derived here and the driver needs no changes.
#
# WHY (AFM-44, AFM-45, 2026-09-22): the agent's terminal tool runs real commands as the
# user. Models under test grepped the user's real mail archive, searched the whole home
# directory, tried to send mail with `mail`, launched a headless Chrome that outlived its
# scenario, and read the fake world's raw seed file -- which carries the corpus's own
# "AMBIGUITY" hints. The world was sandboxed; the host was not.
#
# What the agent can see: a read-only /, an EMPTY /home and /mnt, and bound back in only
#   - hermes-go (ro)                  the agent's own code and venv
#   - the uv Python the venv uses (ro) it lives under ~/.local and would vanish with /home
#   - its fixture's agent-home (rw)   HERMES_HOME
#   - its fixture's fake-google (rw)  the mail CLI must write state.json; seed.json hidden
#   - its scenario sandbox (rw)       the working directory
# Network is shared so the agent can reach the model on 127.0.0.1. --unshare-pid means a
# process the agent backgrounds dies with the agent instead of outliving the scenario.
set -eu
: "${HERMES_HOME:?driver must set HERMES_HOME}"
FX=$(dirname "$HERMES_HOME")
SB=$PWD
# The Hermes tree is the one the interpreter belongs to (2026-10-28): `<tree>/.venv/bin/python` -> <tree>. HERMES_TREE
# overrides. Runs before 2026-10-28 used TheTom/hermes-go 0.20.4 (1524739b, a fork of upstream Hermes Agent); from then
# on, a pinned upstream Hermes Agent (see HERMES_VERSIONS.md).
case "${1:-}" in */.venv/bin/python*) HG_FROM_ARG=$(dirname "$(dirname "$(dirname "$1")")");; *) HG_FROM_ARG=;; esac
HG=${HERMES_TREE:-${HG_FROM_ARG:-/mnt/TG_2TB/AI/hermes-go}}
[ -x "$HG/.venv/bin/python" ] || { echo "sandboxed_agent: no venv python under $HG" >&2; exit 92; }
# A uv-managed interpreter lives under ~/.local (hidden by the empty /home), so bind its whole uv python root, which holds
# interpreters only. A system interpreter (/usr) is already visible through the read-only /.
PYREAL=$(readlink -f "$HG/.venv/bin/python"); PYBIND=()
case "$PYREAL" in
  /usr/*) ;;
  *) PYHOME=$(sed -n 's/^home *= *//p' "$HG/.venv/pyvenv.cfg"); PYHOME=$(dirname "$(dirname "$PYHOME")")
     case "$PYREAL" in "$PYHOME"/*) PYBIND=(--ro-bind "$PYHOME" "$PYHOME");; *)
         echo "sandboxed_agent: venv python resolves outside $PYHOME" >&2; exit 91;; esac;;
esac
[ -d "$FX/fake-google" ] || { echo "sandboxed_agent: no fake-google under $FX" >&2; exit 90; }
# Strip every credential-named variable (2026-09-22). The driver passes the caller's whole
# environment, which carried a Claude Code session token, and the network is shared. The
# agent has no legitimate use for any of them: its model key is a dummy in config.yaml and
# Hermes reads agent-home/.env from the file, not from the process environment.
SECRETS=()
for v in $(compgen -e); do
    case "${v^^}" in *TOKEN*|*SECRET*|*PASSW*|*API_KEY*|*_KEY|*CREDENTIAL*|*AUTH*) SECRETS+=(--unsetenv "$v");; esac
done
exec bwrap \
    --ro-bind / / \
    --dev /dev --proc /proc \
    --tmpfs /tmp --tmpfs /run/user \
    --tmpfs /home --dir "$HOME" \
    --tmpfs /mnt \
    --ro-bind "$HG" "$HG" \
    "${PYBIND[@]}" \
    --bind "$FX/agent-home" "$FX/agent-home" \
    --bind "$FX/fake-google" "$FX/fake-google" \
    --tmpfs "$FX/fake-google/fixtures" \
    --bind "$SB" "$SB" \
    --unshare-pid --unshare-ipc --die-with-parent \
    --unsetenv DISPLAY --unsetenv WAYLAND_DISPLAY \
    --unsetenv DBUS_SESSION_BUS_ADDRESS --unsetenv SSH_AUTH_SOCK "${SECRETS[@]}" \
    --chdir "$SB" \
    -- "$@"
