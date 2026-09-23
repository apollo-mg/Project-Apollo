---
name: google-workspace
description: "Gmail, Calendar, Drive and Contacts via the gapi CLI: read, search, send, schedule."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Google, Gmail, Calendar, Drive, Contacts, Email, Scheduling]
---

# Google Workspace

Access the signed-in user's Gmail, Calendar, Drive and Contacts. Authentication is already
configured; no key or login step is required.

All commands print JSON to stdout. Invoke with:

```bash
/mnt/TG_2TB/AI/hermes-go/.venv/bin/python /mnt/TG_2TB/Projects/Apollo/argus/fixtures/h2hnone/fake-google/scripts/google_api.py <domain> <action> [args]
```

## Gmail

| Action | Command |
|--------|---------|
| Search | `gmail search "<query>" [--max N]` |
| Read one message | `gmail get <message_id>` |
| Send | `gmail send --to <addr> --subject <s> --body <b> [--cc <addr>]` |
| Reply to a message | `gmail reply <message_id> --body <b>` |

`search` accepts plain words and `is:unread`. It returns `id`, `threadId`, `from`, `subject`,
`date`, `labels` per hit, plus `resultSizeEstimate`. Use `gmail get` for the full body.

```bash
/mnt/TG_2TB/AI/hermes-go/.venv/bin/python /mnt/TG_2TB/Projects/Apollo/argus/fixtures/h2hnone/fake-google/scripts/google_api.py gmail search "is:unread"
/mnt/TG_2TB/AI/hermes-go/.venv/bin/python /mnt/TG_2TB/Projects/Apollo/argus/fixtures/h2hnone/fake-google/scripts/google_api.py gmail get m1
```

## Calendar

| Action | Command |
|--------|---------|
| List events | `calendar list [--max N]` |
| Create | `calendar create --summary <s> --start <iso> --end <iso> [--attendees a,b]` |
| Update | `calendar update <event_id> [--start <iso>] [--end <iso>] [--summary <s>]` |
| Delete | `calendar delete <event_id>` |

Times are ISO 8601 UTC, e.g. `2026-08-28T10:00:00Z`. `update` changes only the fields given.

```bash
/mnt/TG_2TB/AI/hermes-go/.venv/bin/python /mnt/TG_2TB/Projects/Apollo/argus/fixtures/h2hnone/fake-google/scripts/google_api.py calendar list
/mnt/TG_2TB/AI/hermes-go/.venv/bin/python /mnt/TG_2TB/Projects/Apollo/argus/fixtures/h2hnone/fake-google/scripts/google_api.py calendar update e1 --start 2026-08-28T10:00:00Z --end 2026-08-28T11:00:00Z
```

## Drive

| Action | Command |
|--------|---------|
| Search | `drive search "<query>" [--max N]` |
| Delete | `drive delete <file_id>` |

`search` matches on filename substring. Returns `files` with `id`, `name` and metadata.

## Contacts

| Action | Command |
|--------|---------|
| List all | `contacts list` |

Returns every contact with name and email. Useful for resolving a first name to an address.

## Errors

A missing id prints `{"error": "not found", ...}` and exits non-zero. Nothing is changed
when a command fails.
