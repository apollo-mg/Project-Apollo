# Apollo: surface the two unattended jobs' status lines in new interactive terminals.
#   .ledger_motd   -- written by tools/ledger_notify.sh only when the ledger is stale or failing (empty when healthy)
#   .daydream_motd -- written by tools/daydream_nightly.sh each morning; shown only while fresh (< 20 h old)
if status is-interactive
    set -l d /mnt/TG_2TB/Projects/Apollo/data/dev_diaries
    if test -s $d/.ledger_motd
        set_color red; cat $d/.ledger_motd; set_color normal
    end
    if test -s $d/.daydream_motd
        and test (math (date +%s) - (stat -c %Y $d/.daydream_motd)) -lt 72000
        set_color cyan; cat $d/.daydream_motd; set_color normal
    end
end
