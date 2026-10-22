"""Local API bridge: python3 server.py. Binds only to localhost."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import threading
import time
from data_api import collect

ROOT = Path(__file__).resolve().parent
LOCK = threading.Lock()
CACHE = json.loads((ROOT / 'snapshot.json').read_text())
LAST_REFRESH = 0

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global CACHE, LAST_REFRESH
        path = self.path.split('?', 1)[0]
        if path in ('/', '/dashboard.html'):
            html = (ROOT / 'dashboard.template.html').read_text().replace('__SNAPSHOT__', json.dumps(CACHE).replace('<', '\\u003c'))
            self.reply(html.encode(), 'text/html; charset=utf-8')
        elif path == '/api/status':
            self.reply(b'{"service":"midterm-desk"}', 'application/json')
        elif path == '/api/refresh':
            try:
                with LOCK:
                    if time.monotonic() - LAST_REFRESH > 60:
                        fresh = collect(CACHE)
                        CACHE = fresh
                        LAST_REFRESH = time.monotonic()
                        (ROOT / 'snapshot.json').write_text(json.dumps(CACHE, separators=(',', ':')))
                        html = (ROOT / 'dashboard.template.html').read_text().replace('__SNAPSHOT__', json.dumps(CACHE).replace('<', '\\u003c'))
                        (ROOT / 'dashboard.html').write_text(html)
                self.reply(json.dumps(CACHE).encode(), 'application/json')
            except Exception as e:
                self.reply(json.dumps({'error': str(e)}).encode(), 'application/json', 502)
        else:
            self.reply(b'Not found', 'text/plain', 404)

    def reply(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    print('Midterm Desk: http://127.0.0.1:8765', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
