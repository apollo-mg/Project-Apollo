#!/usr/bin/env bash
# Print -- do not install -- a git pre-commit hook line that runs tools/prereg_check.py on staged preregs.
#
# It WARNS and never blocks: the "|| true" keeps a commit going whatever the check says. A prereg is committed
# before its first run, so the warning arrives at the moment the prior-art question is still live.
#
#   tools/install_prereg_hook.sh                          # read it
#   tools/install_prereg_hook.sh >> .git/hooks/pre-commit # install it yourself (then: chmod +x .git/hooks/pre-commit)
#
# Paths are relative to the repo root, where git runs hooks, so nothing machine-specific lands in the hook.
cat <<'EOF'
#!/usr/bin/env bash
# prereg prior-art check (warning only; see tools/prereg_check.py)
python3 tools/prereg_check.py --staged >&2 || echo "prereg_check: see above (warning only, commit continues)" >&2
true
EOF
