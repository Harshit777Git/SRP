from dataclasses import dataclass
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit


@dataclass(frozen=True)
class Download:
    filename: str
    content: str
    content_type: str = "text/csv; charset=utf-8"


def serve(port, dispatch, max_body=256000):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_headers(self, status, content_type, size=None, filename=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            if filename is not None:
                self.send_header("Content-Disposition",f'attachment; filename="{filename}"')
            if size is not None:
                self.send_header("Content-Length", str(size))
            self.end_headers()

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def handle_request(self):
            path = urlsplit(self.path)
            route = [unquote(p) for p in path.path.split("/") if p]
            query = {k:v[-1] for k,v in parse_qs(path.query).items()}
            if self.command == "GET" and route == ["stream"]:
                self.send_headers(200,"text/event-stream")
                try:
                    while True:
                        snapshot = dispatch("GET",["snapshot"],query,{})
                        self.wfile.write(("data: "+json.dumps(snapshot,allow_nan=False)+"\n\n").encode())
                        self.wfile.flush()
                        time.sleep(.4)
                except (OSError, KeyError):
                    pass
                return
            try:
                length = int(self.headers.get("Content-Length","0"))
                if length < 0 or length > max_body:
                    raise ValueError("request too large")
                body = json.loads(self.rfile.read(length)) if length else {}
                result = dispatch(self.command,route,query,body)
                status = 200
            except KeyError:
                result, status = {"error":"resource not found"}, 404
            except (TypeError, ValueError) as error:
                result, status = {"error":str(error)}, 400
            filename = None
            if isinstance(result, Download):
                response, content_type,filename = result.content.encode(),result.content_type,result.filename
            elif isinstance(result, str):
                response, content_type = result.encode(), "text/csv"
            else:
                response, content_type = json.dumps(result,allow_nan=False).encode(), "application/json"
            self.send_headers(status,content_type,len(response),filename)
            self.wfile.write(response)

        do_GET = do_POST = handle_request

    ThreadingHTTPServer((os.getenv("API_HOST", "0.0.0.0"),port),Handler).serve_forever()
