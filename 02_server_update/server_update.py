import os
import sys
import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Otomatis binding ke folder tempat file ini berada
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PORT = 8085
LOG_FILE = os.path.join(DIRECTORY, "access.log")

def write_log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

class CORSHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        write_log(format % args)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

if __name__ == "__main__":
    write_log(f"Server starting up on port {PORT} serving {DIRECTORY}")
    server = HTTPServer(("0.0.0.0", PORT), CORSHandler)
    server.serve_forever()
