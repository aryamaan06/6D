"""Exercise a locally mapped CI container; never contacts cloud/model providers."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('before', 'after'), required=True)
    args = parser.parse_args()
    address, origin = 'http://127.0.0.1:18080', 'https://review.example.com'
    folder = Path('work/hosted-ci'); folder.mkdir(parents=True, exist_ok=True)
    state = folder / 'restart-check.json'
    opener = build_opener(ProxyHandler({}), NoRedirect())

    def call(path, body=None, cookie=None, expected=200):
        headers = {'Host': 'review.example.com', 'Origin': origin, 'Content-Type': 'application/json'}
        if cookie:
            headers['Cookie'] = cookie
        request = Request(address + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            response = opener.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            assert response.status == expected, (path, response.status)
            value = json.loads(response.read())
            return value, response.headers

    for attempt in range(30):
        try:
            health, _ = call('/health')
            assert health['service'] == 'sixd-hosted-judge'
            break
        except OSError:
            if attempt == 29:
                raise
            time.sleep(1)
    if args.phase == 'before':
        code = Path('work/hosted-ci/invitation').read_text(encoding='utf-8').strip()
        _, headers = call('/api/hosted/login', {'access_code': code})
        cookie = headers['Set-Cookie'].split(';', 1)[0]
        assert '; Secure' in headers['Set-Cookie'] and '; HttpOnly' in headers['Set-Cookie']
        view, _ = call('/api/workspace', cookie=cookie)
        assert view['run'] is not None
        call('/api/shutdown', {}, cookie=cookie, expected=403)
        call('/api/ai/connect', {'api_key': 'synthetic-forbidden-provider-key'}, cookie=cookie, expected=403)
        status, _ = call('/api/ai/status', cookie=cookie)
        assert status['key_present'] is False and status['configured'] is False
        saved = {'cookie': cookie, 'digest': sha256(json.dumps(view['run'], sort_keys=True).encode()).hexdigest(),
                 'project_id': view['project_id']}
        state.write_text(json.dumps(saved), encoding='utf-8')
    else:
        saved = json.loads(state.read_text(encoding='utf-8'))
        view, _ = call('/api/workspace', cookie=saved['cookie'])
        assert view['project_id'] == saved['project_id']
        assert sha256(json.dumps(view['run'], sort_keys=True).encode()).hexdigest() == saved['digest']
        call('/api/hosted/logout', {}, cookie=saved['cookie'])
        call('/api/projects', cookie=saved['cookie'], expected=401)
    print(json.dumps({'phase': args.phase, 'passed': True, 'provider_calls': 0, 'mode': 'local_linux_container'}))


if __name__ == '__main__':
    main()
