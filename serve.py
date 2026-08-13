#!/usr/bin/env python3
"""Serve the Template Generator locally AND proxy Expresii Command Server calls.

Why a proxy?  The Expresii Command Server (http://localhost:9000) does not answer
CORS preflight OPTIONS requests, so a browser page served from a *different* origin
(e.g. :8753) is blocked from POSTing to it. Serving the app from the same origin and
forwarding /expresii/* to :9000 removes the cross-origin problem entirely.

Also adds /api/lineart — converts an uploaded raster image into a clean line drawing
(線稿) server-side via OpenCV, so the web app can offer 線稿 as a second "tool".

Run:   python serve.py            # serves on http://127.0.0.1:8753
       python serve.py --port 80  # optionally pick a port
Open http://127.0.0.1:8753/index.html
"""
import argparse, http.server, socketserver, urllib.request, urllib.error, sys, os
import json, base64
import cv2
import numpy as np

EXP_HOST = "localhost"
EXP_PORT = 9000
ROOT = os.path.dirname(os.path.abspath(__file__))


def image_to_lineart(img, scale=2, keep_text=True, transparent=False):
    """Core 線稿 pipeline (mirrors the one that produced lineart_final.png).

    img        : BGR ndarray
    scale      : integer upscale factor (1-4) before processing
    keep_text  : also recover small dark-ink printed title text
    transparent: if True, background alpha=0; else white background.
    Returns an encoded PNG (bytes).
    """
    if scale != 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    H, W = img.shape[:2]

    # ---- background (paper) colour from corners ----
    corners = np.concatenate([
        img[0:50, 0:50].reshape(-1, 3), img[0:50, -50:].reshape(-1, 3),
        img[-50:, 0:50].reshape(-1, 3), img[-50:, -50:].reshape(-1, 3),
    ], axis=0).astype(np.float32)
    bg = corners.mean(axis=0)
    diff = img.astype(np.float32) - bg
    dist = np.sqrt((diff ** 2).sum(axis=2)).astype(np.float32)
    cd = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    g8 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.uint8)

    # ---- leaf / subject silhouette outline (morphological gradient) ----
    cdb = cv2.GaussianBlur(cd, (7, 7), 0)
    leafmask = (cdb > 28).astype(np.uint8)
    leafmask = cv2.morphologyEx(leafmask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    leafmask = cv2.morphologyEx(leafmask, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    cnt, _ = cv2.findContours(leafmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    lm = np.zeros_like(leafmask)
    min_leaf = 1200 * max(1, (scale // 2) ** 2)
    for c in cnt:
        if cv2.contourArea(c) > min_leaf:
            cv2.drawContours(lm, [c], -1, 1, -1)
    leafmask = lm
    outline = cv2.morphologyEx(leafmask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    outline = cv2.morphologyEx(outline, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    outline = cv2.subtract(outline, cv2.erode(leafmask, np.ones((2, 2), np.uint8), 1))

    # ---- internal veins / stems via luminance Canny ----
    gb = cv2.GaussianBlur(g8, (3, 3), 0)
    ec = cv2.Canny(gb, 35, 110)
    subj = (leafmask == 1) | (gb < 150)
    veins = ec & subj.astype(np.uint8)

    lines = cv2.bitwise_or(outline, veins).astype(np.uint8)
    # remove stray specks
    n, lab, stats, _ = cv2.connectedComponentsWithStats(lines, 8)
    keep = np.zeros_like(lines)
    min_area = 14 * max(1, scale ** 2)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            keep[lab == i] = 255
    lines = keep
    lines = cv2.dilate(lines, np.ones((2, 2), np.uint8), 1)
    lines = cv2.medianBlur(lines, 3)

    # ---- optional printed title text (small dark-ink glyphs, upper area) ----
    if keep_text:
        tk = (gb < 140).astype(np.uint8)
        n2, lab2, stats2, cent2 = cv2.connectedComponentsWithStats(tk, 8)
        text = np.zeros_like(tk)
        max_ta = 6000 * max(1, (scale // 2) ** 2)
        for i in range(1, n2):
            a = stats2[i, cv2.CC_STAT_AREA]
            cy = cent2[i, 1]
            if 20 <= a <= max_ta and cy < H * 0.45:
                text[lab2 == i] = 255
        text = cv2.dilate(text, np.ones((2, 2), np.uint8), 1)
        lines = cv2.bitwise_or(lines, text).astype(np.uint8)

    # ---- assemble output ----
    if transparent:
        rgba = np.zeros((H, W, 4), dtype=np.uint8)
        rgba[lines == 255] = (0, 0, 0, 255)
        _, buf = cv2.imencode(".png", rgba)
    else:
        out = 255 - lines
        _, buf = cv2.imencode(".png", out)
    return buf.tobytes(), W, H


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

    def _lineart(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw.decode("utf-8", "replace"))
            b64 = req.get("image", "")
            if not b64:
                raise ValueError("missing 'image' (base64)")
            scale = int(req.get("scale", 2)) or 1
            scale = min(max(scale, 1), 4)
            keep_text = bool(req.get("keep_text", True))
            transparent = bool(req.get("transparent", False))
            img_b = base64.b64decode(b64)
            buf = np.frombuffer(img_b, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("could not decode image")
            png, W, H = image_to_lineart(img, scale, keep_text, transparent)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "image": base64.b64encode(png).decode("ascii"),
                "w": W, "h": H,
            }).encode("utf-8"))
        except Exception as e:  # noqa
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

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
        if self.path.startswith("/api/lineart"):
            self._lineart()
        elif self.path.startswith("/expresii"):
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
        print(f"Line-art API:        POST /api/lineart")
        print("Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


if __name__ == "__main__":
    main()
