"""Loopback-only curated demonstration, not production hosting or a code sandbox."""
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import json
from .examples import EXAMPLES, get_example
from .kernel import audit
from .reporting import RECORD_ID, compare_reports, list_reports, read_report, save_report

WEB = Path(__file__).with_name("web")


class Handler(BaseHTTPRequestHandler):
    def __init__(self,*args,artifact_directory,**kwargs):
        self.artifact_directory = Path(artifact_directory)
        super().__init__(*args,**kwargs)

    def respond(self,status,value,kind="application/json; charset=utf-8"):
        payload = json.dumps(value,allow_nan=False).encode() if kind.startswith("application/json") else value
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(payload)

    def trusted_host(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}",f"localhost:{self.server.server_port}")

    def do_GET(self):
        if not self.trusted_host():
            self.respond(403,{"error":"Use the loopback URL printed by 6D."});return
        path = urlsplit(self.path).path
        if path == "/api/examples":
            self.respond(200,{"examples":[e.public_record() for e in EXAMPLES.values()],"model_mode":"disabled"})
        elif path == '/api/provider-status':
            from .providers import provider_status
            self.respond(200, provider_status(Path(__file__).resolve().parents[2]))
        elif path == "/api/reports":
            self.respond(200,{"reports":list_reports(self.artifact_directory)})
        elif path.startswith("/api/reports/"):
            record_id = path.removeprefix("/api/reports/")
            if not RECORD_ID.fullmatch(record_id):
                self.respond(400,{"error":"Invalid evidence record identifier."});return
            try:
                self.respond(200,{"record_id":record_id,"report":read_report(self.artifact_directory/f"{record_id}.json")})
            except (OSError, ValueError):
                self.respond(404,{"error":"The record is missing or its digest cannot be verified."})
        else:
            filename = {"/":"index.html","/app.js":"app.js","/style.css":"style.css"}.get(path)
            if filename:
                kind = {"index.html":"text/html; charset=utf-8","app.js":"text/javascript; charset=utf-8","style.css":"text/css; charset=utf-8"}[filename]
                self.respond(200,(WEB/filename).read_bytes(),kind)
            else:
                self.respond(404,{"error":"Not found."})

    def do_POST(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if not self.trusted_host() or (origin is not None and origin != f"http://{host}"):
            self.respond(403,{"error":"Cross-origin audit requests are not allowed."});return
        path = urlsplit(self.path).path
        if path not in ('/api/audit', '/api/investigate', '/api/compare'):
            self.respond(404,{"error":"Not found."});return
        try:
            length = int(self.headers.get("Content-Length","0"))
            if length <= 0 or length > 8192:
                raise ValueError("The request must be a small curated-audit selection.")
            if self.headers.get("Content-Type","").split(";")[0] != "application/json":
                raise ValueError("Use an application/json request.")
            request = json.loads(self.rfile.read(length))
            if path == '/api/compare':
                if not isinstance(request,dict) or set(request)!={'previous_record_id','new_record_id'}:
                    raise ValueError("Select two saved audit records to compare.")
                identities = (request['previous_record_id'], request['new_record_id'])
                if any(not isinstance(identity,str) or not RECORD_ID.fullmatch(identity) for identity in identities):
                    raise ValueError("Invalid evidence record identifier.")
                try:
                    previous, current = (read_report(self.artifact_directory/f'{identity}.json') for identity in identities)
                    comparison = compare_reports(previous,current)
                except OSError:
                    self.respond(404,{'error':'One of the selected evidence records is unavailable.'});return
                except (ValueError,KeyError,TypeError):
                    self.respond(409,{'error':'A selected record cannot be verified. Comparison was not performed.'});return
                self.respond(200,{'previous_record_id':identities[0],'new_record_id':identities[1],
                                  'previous_title':previous['example_title'],'new_title':current['example_title'],
                                  'comparison':comparison});return
            if not isinstance(request,dict) or set(request)!={"example_id","contract_sha256","review_accepted"}:
                raise ValueError("Only the selected example, reviewed contract hash and acknowledgement are accepted.")
            if request["review_accepted"] is not True:
                raise ValueError("Review and acknowledge the contract before running.")
            example = get_example(request["example_id"])
            if request["contract_sha256"] != example.contract.sha256:
                raise ValueError("The selected contract differs from the one reviewed. Review it again.")
            review = {"mode":"operator_acknowledged_local_ui","human_acceptance_claimed":True,"authenticated_identity":False}
            if path == '/api/investigate':
                from .investigation import investigate
                from .providers import FixtureProvider
                report = investigate(example, FixtureProvider(), review=review)
            else:
                report = audit(example, review=review)
            paths = save_report(report,self.artifact_directory)
            self.respond(200,{"record_id":paths["record_id"],"report":report})
        except (ValueError, KeyError, TypeError) as exc:
            self.respond(400,{"error":str(exc)})
        except OSError:
            self.respond(500,{"error":"The local evidence record could not be written."})


def serve_local(port,artifact_directory):
    if not 1 <= port <= 65535:
        raise ValueError("Choose a TCP port from 1 to 65535.")
    handler = partial(Handler,artifact_directory=artifact_directory)
    server = ThreadingHTTPServer(("127.0.0.1",port),handler)
    print(f"6D local prototype: http://127.0.0.1:{server.server_port}",flush=True)
    print("Curated inputs only. No paid services or model calls. Ctrl+C to stop.",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
