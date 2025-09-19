#!/usr/bin/env python3
"""
Simple development server for testing the map without building Tauri
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Change to the src directory
os.chdir(Path(__file__).parent / "src")

PORT = 8080

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers for development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

Handler = MyHTTPRequestHandler

print(f"Starting development server on http://localhost:{PORT}")
print(f"Open http://localhost:{PORT}/mapbox.html?port=8765 in your browser")
print("Press Ctrl+C to stop")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        sys.exit(0)