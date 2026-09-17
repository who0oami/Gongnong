"""Browser integration check, using installed Edge and local Playwright tools."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'diagnostics/browser-tools'))
from playwright.sync_api import sync_playwright


def main():
    out = ROOT / 'diagnostics/mediapipe-love-v1' / datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/mediapipe-preview/', timeout=60000)
            page.wait_for_function('!!window.preview', timeout=60000)
            page.wait_for_function('document.querySelector("video").readyState >= 2')
            checks = []
            for frame in [0, 17, 34, 51, 67, 148, 220, 295]:
                page.locator('#seek').fill(str(frame))
                page.wait_for_function('!document.querySelector("video").seeking')
                page.wait_for_function('(frame)=>Number(document.querySelector("#seek").value)===frame', arg=frame)
                page.screenshot(path=str(out / f'frame_{frame:03}.png'))
                checks.append(page.evaluate('''() => ({
                    frame: Number(document.querySelector('#seek').value),
                    rotations: preview.rigs.map(r=>r.nodes.slice(0,3).map(n=>n.rotationQuaternion.asArray()))
                })'''))
            page.locator('#seek').fill('67')
            page.locator('#seek').dispatch_event('input')
            page.locator('#play').click()
            start = page.evaluate('document.querySelector("video").currentTime')
            page.wait_for_function('(start)=>document.querySelector("video").currentTime > start + 0.1', arg=start)
            page.locator('#play').click()
            assert not errors, errors
            assert all(all(all(isinstance(x, (float, int)) for x in q) for q in r)
                       for row in checks for r in row['rotations'])
            report = dict(status=page.locator('#status').inner_text(), errors=errors,
                          playback=True, frames=checks)
            (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            assert len({str(row['rotations']) for row in checks}) > 1, 'Animation did not change'
            print(json.dumps(dict(output=str(out),status=report['status'],errors=errors,playback=True,
                                  frames=[row['frame'] for row in checks]), ensure_ascii=True), flush=True)
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
