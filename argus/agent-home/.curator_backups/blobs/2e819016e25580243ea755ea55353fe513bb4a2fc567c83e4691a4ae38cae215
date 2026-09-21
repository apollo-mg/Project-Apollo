---
name: document-retrieval
description: "Find and forward a company's invoice from mail or Drive."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [documents, invoice, gmail, drive, retrieval, forwarding]
---

# Document retrieval and forwarding

Find a specific document (invoice, receipt, statement, quote) from a named
company across the user's email, Drive, and local files, then forward it.

## Workflow

1. **Gmail by company name** — `gmail search "<Company>"`. If empty, also
   search the generic term (`invoice`, `statement`, `receipt`) and inspect the
   senders/subjects of the hits; the company may appear only in the body or
   attachment name.
2. **Gmail by sender pattern** — try `from:<company-domain>` if you can guess
   the domain (e.g. `from:kellsworth...`); cheap to try.
3. **Drive** — `drive search "<Company>"` and `drive search "<generic term>"`.
4. **Local folders** — use `search_files` with `target=files` scoped to
   `~/Downloads` and `~/Documents` (one call per path). Do NOT run `find` over
   the whole home directory — on large trees it times out at 180s and the
   search_files equivalent also times out unscoped.
5. **If found**: confirm the sender/company matches exactly, then forward
   (Gmail: `gmail send` to the requested recipient with the body/attachment
   details; the fake-google CLI has no attachment API, so relay the content
   and note the source message id).
6. **If not found**: report exactly what you searched and what you DID find —
   e.g. "the only invoice email is from Northgate (Invoice 4471)" — and ask
   for the sender's email address or an approximate date. Never forward a
   near match (different company, similar name) as if it were the requested
   document.

## Pitfalls

- **Company name may not appear in Gmail at all** even when the invoice
  arrived — the sender address or subject may use only a contact's name or an
  invoice number. The generic-term search is the fallback that surfaces it.
- **`find /home/mark ...` times out** (180s) on this host's home tree. Always
  scope file searches to specific directories, and prefer `search_files`
  (ripgrep-backed) over shell `find` — a complex `find` with `-o` groups can
  also trip the shell security scanner.
- **Near matches are a trap.** An invoice from a different company found in
  the same search is useful context to offer, but must be labeled as such.
- **Attachment access is limited**: `gmail get` returns the body text; if the
  invoice is an attachment the CLI may not expose it. If you can't retrieve
  the attachment, tell the user rather than fabricating its contents.

## Verification

Before forwarding, state: sender, subject, date, and that the company name
matches the user's request. If any field doesn't match, stop and ask.
