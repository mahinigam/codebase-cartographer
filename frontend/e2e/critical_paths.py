import os

from playwright.sync_api import expect, sync_playwright


def install_api(page):
    scanned = False

    def route(route):
        nonlocal scanned
        url = route.request.url
        if url.endswith("/api/repositories"):
            body = {"repositories": [{"name": "fixture", "root_path": "/fixture", "files": 1}]} if scanned else {"repositories": []}
        elif "/api/scan" in url:
            scanned = True
            body = {"repository": "fixture", "root_path": "/fixture", "files": 1, "symbols": 1, "imports": 0}
        elif "/api/overview" in url:
            body = {"overview": {"files": 1, "symbols": 1, "avg_score": 2}, "load_bearing": []}
        elif "/api/graph" in url:
            body = {"nodes": [], "edges": []}
        elif "/api/files" in url:
            body = {"files": [{"path": "main.py", "loc": 2, "load_bearing_score": 2}]}
        else:
            body = {"results": []}
        route.fulfill(status=200, json=body)
    page.route("**/api/**", route)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        install_api(page)
        page.goto(os.environ["CARTOGRAPHER_E2E_URL"], wait_until="networkidle")
        expect(page.get_by_role("heading", name="Map your codebase")).to_be_visible()
        page.get_by_label("Repository path").fill("/fixture")
        page.get_by_role("button", name="Analyze repository").click()
        expect(page.get_by_text("Repository scanned successfully.")).to_be_visible()
        expect(page.get_by_text("fixture").first).to_be_visible()
        assert not errors, errors
        browser.close()
        print("browser critical path: passed")


if __name__ == "__main__":
    main()
