#!/usr/bin/env python3
"""Localhost pass-through proxy for Deviation 2: lmx -> this -> llama-server. lmx still does all the timing; this only
records, for each request, the request body, the streamed text, llama.cpp's final `timings` / `usage`, and when the
first and last content chunks passed through (to cross-check lmx). Bytes are forwarded as read, flushed per read.
usage: g4_proxy.py LISTEN_PORT UPSTREAM_PORT CAPTURE.jsonl"""
import http.client, http.server, json, sys, time

LISTEN, UP, CAP = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "proxy-connection", "upgrade", "te", "trailer"}


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"                  # close-delimited responses: streamed bytes need no re-chunking

    def log_message(self, *a):
        pass

    def _proxy(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        t0 = time.monotonic()
        c = http.client.HTTPConnection("127.0.0.1", UP, timeout=600)
        c.request(self.command, self.path, body=body,
                  headers={k: v for k, v in self.headers.items() if k.lower() not in HOP | {"host"}})
        r = c.getresponse()
        self.send_response(r.status)
        for k, v in r.getheaders():
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        buf, first, last = b"", None, None
        while True:
            chunk = r.read1(65536)
            if not chunk:
                break
            self.wfile.write(chunk); self.wfile.flush()
            buf += chunk
            if b'"content"' in chunk:
                now = time.monotonic() - t0
                first = first if first is not None else now
                last = now
        c.close()
        if self.command == "POST" and self.path.endswith("/chat/completions"):
            rec = {"t": time.time(), "path": self.path, "request": json.loads(body or b"{}"), "status": r.status,
                   "proxy_first_content_s": first, "proxy_last_content_s": last}
            text, timings, usage, finish = [], None, None, None
            for line in buf.decode(errors="replace").splitlines():
                if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                    continue
                try:
                    ev = json.loads(line[6:])
                except Exception:
                    continue
                for ch in ev.get("choices") or []:
                    d = ch.get("delta") or ch.get("message") or {}
                    if d.get("content"):
                        text.append(d["content"])
                    finish = ch.get("finish_reason") or finish
                timings = ev.get("timings") or timings
                usage = ev.get("usage") or usage
            if not text and buf[:1] == b"{":          # non-streamed response
                try:
                    j = json.loads(buf); m = j["choices"][0]["message"]
                    text, timings, usage, finish = [m.get("content") or ""], j.get("timings"), j.get("usage"), j["choices"][0].get("finish_reason")
                except Exception:
                    pass
            rec.update({"text": "".join(text), "timings": timings, "usage": usage, "finish_reason": finish})
            with open(CAP, "a") as f:
                f.write(json.dumps(rec) + "\n"); f.flush()

    do_GET = do_POST = _proxy


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", LISTEN), H).serve_forever()
