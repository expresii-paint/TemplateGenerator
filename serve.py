#!/usr/bin/env python3
"""Serve the Template Generator locally AND proxy Expresii Command Server calls.

Why a proxy?  The Expresii Command Server (http://localhost:9000) does not answer
CORS preflight OPTIONS requests, so a browser page served from a *different* origin
(e.g. :8753) is blocked from POSTing to it. Serving the app from the same origin and
forwarding /expresii/* to :9000 removes the cross-origin problem entirely.

Run:   python serve.py            # serves on http://127.0.0.1:8753
       python serve.py --port 80  # optionally pick a port
Open http://127.0.0.1:8753/index.html
"""
import argparse, http.server, socketserver, urllib.request, urllib.error, sys, os

EXP_HOST = "localhost"
EXP_PORT = 9000
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def _proxy(self):
        # path: /expresii/<host>[/<rest>]  ->  http://<host>/<rest>
        # e.g. /expresii/192.168.1.50:9000/info  ->  http://192.168.1.50:9000/info
        rest = self.path[len("/expresii"):]
        parts = rest.lstrip("/").split("/", 1)
        host = parts[0]
        sub = "/" + parts[1] if len(parts) > 1 else "/"
        target = f"http://{host}{sub}"
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(target, data=body, method=self.command)
        for k in ("Content-Type", "Accept"):
            if k in self.headers:
                req.add_header(k, self.headers[k])
        try:
            resp = urllib.request.urlopen(req, timeout=120)
            data = resp.read()
            status = resp.getcode()
            ctype = resp.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as e:
            data = e.read()
            status = e.code
            ctype = e.headers.get("Content-Type", "application/json")
        except Exception as e:  # noqa
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(f'{{"error":"proxy upstream: {e}"}}'.encode())
            return
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        # answer CORS preflight so the browser is satisfied even for the proxy path
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/expresii"):
            self._proxy()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/expresii"):
            self._proxy()
        else:
            self.send_response(405)
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith("/expresii"):
            self._proxy()
        else:
            self.send_response(405)
            self.end_headers()

    def end_headers(self):
        # never let the browser cache the app html during development
        if not self.path.startswith("/expresii"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("[serve] " + (fmt % args) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8753)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    os.chdir(ROOT)
    with socketserver.ThreadingTCPServer((args.host, args.port), Handler) as httpd:
        print(f"Template Generator:  http://{args.host}:{args.port}/index.html")
        print(f"Expresii proxy:      /expresii/*  ->  http://{EXP_HOST}:{EXP_PORT}")
        print("Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


if __name__ == "__main__":
    main()
