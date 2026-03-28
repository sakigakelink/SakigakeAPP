"""Temporary: dump browser localStorage for localhost:5000"""
import http.server, json, os, threading, webbrowser

HTML = b"""<!DOCTYPE html><html><body>
<script>
var d = {};
for (var i = 0; i < localStorage.length; i++) {
    var k = localStorage.key(i);
    d[k] = localStorage.getItem(k);
}
fetch("/s", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(d)
}).then(function() {
    document.body.innerText = "Done. Keys: " + Object.keys(d).join(", ");
});
</script>
<p>Reading localStorage...</p>
</body></html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(HTML)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        with open("ls_dump.json", "wb") as f:
            f.write(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
        print("Saved ls_dump.json")
        threading.Timer(1, lambda: os._exit(0)).start()

server = http.server.HTTPServer(("127.0.0.1", 5000), Handler)
print("Starting on http://localhost:5000/ ...")
threading.Timer(1, lambda: webbrowser.open("http://localhost:5000/")).start()
threading.Timer(30, lambda: os._exit(1)).start()
server.serve_forever()
