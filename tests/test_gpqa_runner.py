"""Tests for data/receipts/sci-distill/run_gpqa.py's dispatch (PREREG_SCI_DISTILL.md Deviation 2). Self-contained: fake
OpenAI-compatible servers in threads, synthetic items in place of GPQA (no dataset, no GPQA text). Checks that work is
handed out strictly in order (the finished set is a prefix of the work order), that no request starts after the
deadline, that a server listed mid-run joins, that a resumed run finishes the rest without duplicates, and that the
public file stays text-free."""
import importlib.util, json, random, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SD = Path(__file__).resolve().parent.parent / "data" / "receipts" / "sci-distill"
spec = importlib.util.spec_from_file_location("run_gpqa", SD / "run_gpqa.py")
rg = importlib.util.module_from_spec(spec); spec.loader.exec_module(rg)
ITEMS = [{"id": f"{k:016x}", "q": f"synthetic question {k}", "domain": "Physics",
          "choices": [f"right {k}", f"wrong a {k}", f"wrong b {k}", f"wrong c {k}"]} for k in range(198)]


def fake_server(arrivals):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            arrivals.append(time.time())
            time.sleep(0.005 + (body["seed"] % 50) / 1000)          # 5-55 ms, varies per request
            out = json.dumps({"choices": [{"message": {"content": f"ANSWER: {random.Random(body['seed']).choice('ABCD')}",
                                                       "reasoning_content": "r"}, "finish_reason": "stop"}],
                              "usage": {"completion_tokens": 10, "prompt_tokens": 30}}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


class Dispatch(unittest.TestCase):
    def run_main(self, *args):
        argv, sys.argv = sys.argv, ["run_gpqa.py", *args]
        try:
            rg.main()
        finally:
            sys.argv = argv

    def test_order_deadline_join_resume(self):
        rg.items = lambda: ITEMS
        arrivals = []
        (s1, u1), (s2, u2) = fake_server(arrivals), fake_server(arrivals)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); urls, pub, prv = d / "urls.txt", d / "pub.jsonl", d / "prv.jsonl"
            urls.write_text(u1 + "\n")
            threading.Timer(0.5, lambda: urls.open("a").write(u2 + "\n")).start()
            deadline = time.time() + 2.0
            common = ["--arm", "T", "--urls", f"@{urls}", "--rounds", "1-4", "--slots", "4", "--public", str(pub), "--private", str(prv)]
            self.run_main(*common, "--deadline", str(deadline))
            rows = [json.loads(l) for l in pub.open()][1:]
            order = [(r, it["id"]) for r in range(1, 5) for it in ITEMS]
            done = {(x["round"], x["id"]) for x in rows}
            self.assertTrue(0 < len(done) < len(order), "the deadline should cut the run short")
            self.assertEqual(done, set(order[:len(done)]), "finished work must be a prefix of the work order")
            self.assertFalse([t for t in arrivals if t > deadline], "a request started after the deadline")
            self.assertEqual({x["server"] for x in rows}, {u1, u2}, "the server listed mid-run must join")
            self.run_main(*common)   # resume, no deadline
            rows = [json.loads(l) for l in pub.open()][1:]
            self.assertEqual(sorted((x["round"], x["id"]) for x in rows), sorted(order), "resume must finish everything once")
            self.assertFalse(set().union(*rows) & {"content", "reasoning", "got", "gold", "q", "choices"}, "public rows must be text-free")
        s1.shutdown(); s2.shutdown()


if __name__ == "__main__":
    unittest.main()
