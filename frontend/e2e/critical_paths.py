import asyncio
import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

from playwright.async_api import Browser, Page, expect, async_playwright


ALLOWED_API_PATHS = {
    "/api/repositories",
    "/api/scan",
    "/api/overview",
    "/api/graph",
    "/api/files",
    "/api/file-detail",
    "/api/search",
    "/api/query",
}

REPOSITORY = {
    "name": "fixture",
    "root_path": "/fixture",
    "files": 2,
    "indexed_at": "2025-01-01T00:00:00Z",
}

GRAPH = {
    "nodes": [
        {
            "id": "main.py",
            "label": "main.py",
            "score": 92,
            "labels": ["File"],
            "language": "Python",
            "loc": 2,
            "fan_in": 1,
        },
        {
            "id": "service.py",
            "label": "service.py",
            "score": 12,
            "labels": ["File"],
            "language": "Python",
            "loc": 2,
            "fan_in": 0,
        },
    ],
    "edges": [{"source": "main.py", "target": "service.py", "type": "IMPORTS"}],
    "total_files": 2,
    "total_edges": 1,
}

FILES = {
    "files": [
        {
            "path": "main.py",
            "language": "Python",
            "loc": 2,
            "complexity": 1,
            "churn_count": 3,
            "load_bearing_score": 92,
            "risk_category": "HIGH_RISK",
        },
        {
            "path": "service.py",
            "language": "Python",
            "loc": 2,
            "complexity": 1,
            "churn_count": 0,
            "load_bearing_score": 12,
        },
    ]
}

FILE_DETAIL = {
    "path": "main.py",
    "language": "Python",
    "loc": 2,
    "complexity": 1,
    "churn_count": 3,
    "last_modified": None,
    "load_bearing_score": 92,
    "risk_category": "HIGH_RISK",
    "symbols": [
        {
            "name": "run",
            "kind": "function",
            "signature": "()",
            "start_line": 1,
            "end_line": 2,
        }
    ],
    "imports": ["service.py"],
    "dependents": [],
    "external_deps": [],
    "risk_components": {
        "fan_in": 1,
        "fan_out": 1,
        "complexity": 1,
        "churn_count": 3,
        "fan_in_normalized": 0.9,
        "complexity_normalized": 0.1,
        "churn_normalized": 0.3,
        "fan_out_normalized": 0.2,
    },
}

QUERY_RESPONSE = {
    "answer": "main.py starts the application.",
    "evidence": [{"path": "main.py"}],
    "semantic_matches": [
        {
            "path": "main.py",
            "summary": "Application entry point",
            "score": 0.9,
        }
    ],
}


class ApiFixture:
    def __init__(self) -> None:
        self.scanned = False
        self.failures: dict[str, list[str]] = {}
        self.abort_next_scan = False
        self.block_next_scan = False
        self.scan_started = asyncio.Event()
        self.release_scan = asyncio.Event()
        self.initial_repositories_loaded = asyncio.Event()
        self.repository_requests = 0
        self.intentional_aborts: set[str] = set()
        self.unexpected_requests: list[str] = []

    def fail_next(self, path: str, message: str) -> None:
        self.failures.setdefault(path, []).append(message)

    async def route(self, route) -> None:
        request = route.request
        path = urlparse(request.url).path

        if path not in ALLOWED_API_PATHS:
            self.unexpected_requests.append(f"{request.method} {path}")
            await route.abort()
            return

        failures = self.failures.get(path, [])
        if failures:
            message = failures.pop(0)
            await route.fulfill(
                status=503,
                content_type="text/plain",
                body=message,
            )
            return

        if path == "/api/scan":
            if self.abort_next_scan:
                self.abort_next_scan = False
                self.intentional_aborts.add(request.url)
                await route.abort()
                return
            if self.block_next_scan:
                self.block_next_scan = False
                self.scan_started.set()
                await self.release_scan.wait()
            self.scanned = True
            await route.fulfill(
                status=200,
                json={
                    "repository": REPOSITORY["name"],
                    "root_path": REPOSITORY["root_path"],
                    "files": 2,
                    "symbols": 4,
                    "imports": 1,
                },
            )
        elif path == "/api/repositories":
            self.repository_requests += 1
            repositories = [REPOSITORY] if self.scanned and self.repository_requests > 1 else []
            await route.fulfill(status=200, json={"repositories": repositories})
            if self.repository_requests == 1:
                self.initial_repositories_loaded.set()
        elif path == "/api/overview":
            await route.fulfill(
                status=200,
                json={
                    "overview": {"files": 2, "symbols": 4, "avg_score": 82},
                    "load_bearing": FILES["files"][:1],
                },
            )
        elif path == "/api/graph":
            await route.fulfill(status=200, json=GRAPH)
        elif path == "/api/files":
            await route.fulfill(status=200, json=FILES)
        elif path == "/api/file-detail":
            requested_path = parse_qs(urlparse(request.url).query).get("path", [""])[0]
            detail = FILE_DETAIL | {"path": requested_path}
            await route.fulfill(status=200, json=detail)
        elif path == "/api/search":
            await route.fulfill(status=200, json={"results": [{"path": "main.py"}]})
        elif path == "/api/query":
            await route.fulfill(status=200, json=QUERY_RESPONSE)


@asynccontextmanager
async def browser_case(browser: Browser, url: str, viewport: dict | None = None):
    context = await browser.new_context(viewport=viewport or {"width": 1440, "height": 900})
    page = await context.new_page()
    fixture = ApiFixture()
    page_errors: list[str] = []
    request_failures: list[str] = []

    def record_request_failure(request) -> None:
        if request.url in fixture.intentional_aborts:
            fixture.intentional_aborts.remove(request.url)
        else:
            request_failures.append(f"{request.method} {request.url}: {request.failure}")

    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("requestfailed", record_request_failure)
    await context.route("**/api/**", fixture.route)
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await expect(page.get_by_role("heading", name="Map your codebase")).to_be_visible()
        await asyncio.wait_for(fixture.initial_repositories_loaded.wait(), timeout=10)
        yield page, fixture, page_errors, request_failures
    finally:
        await context.close()


def assert_clean(
    fixture: ApiFixture,
    page_errors: list[str],
    request_failures: list[str],
) -> None:
    assert not fixture.unexpected_requests, fixture.unexpected_requests
    assert not fixture.intentional_aborts, fixture.intentional_aborts
    assert not page_errors, page_errors
    assert not request_failures, request_failures


async def scan(page: Page) -> None:
    await page.get_by_label("Repository path").fill("/fixture")
    await page.get_by_role("button", name="Analyze repository").click()
    await expect(page.get_by_text("Repository scanned successfully.")).to_be_visible()


async def open_main_file(page: Page) -> None:
    main_node = page.locator(".graph-node").filter(has_text="main.py")
    await expect(main_node).to_be_visible()
    await main_node.click()
    await expect(page.locator(".inspector h2")).to_have_text("main.py")


async def ask(page: Page, question: str, wait_for_search: bool = True) -> None:
    trigger = page.get_by_role("button", name="Search files, symbols, or ask Cartographer...")
    await trigger.click()
    input_box = page.get_by_placeholder("Search files, symbols, or ask Cartographer...")
    ask_option = page.get_by_text(f'Ask Cartographer: "{question}"')
    if wait_for_search:
        async with page.expect_response(
            lambda response: urlparse(response.url).path == "/api/search"
        ):
            await input_box.fill(question)
    else:
        await input_box.fill(question)
    await expect(ask_option).to_be_visible()
    async with page.expect_response(lambda response: urlparse(response.url).path == "/api/query"):
        await input_box.press("Enter")


async def test_empty_workspace_and_keyboard_workflow(browser: Browser, url: str) -> None:
    async with browser_case(browser, url) as (page, fixture, page_errors, request_failures):
        repository_input = page.get_by_label("Repository path")
        scan_button = page.get_by_role("button", name="Analyze repository")
        await expect(page.get_by_text("Previously Scanned Repositories")).to_have_count(0)

        await page.keyboard.press("Tab")
        await expect(repository_input).to_be_focused()
        await page.keyboard.type("/fixture")
        await page.keyboard.press("Tab")
        await expect(
            page.get_by_role("checkbox", name="Generate AI summaries after scan")
        ).to_be_focused()
        await page.keyboard.press("Tab")
        await expect(scan_button).to_be_focused()
        assert await scan_button.evaluate("(element) => element.matches(':focus-visible')")
        await page.keyboard.press("Enter")
        await expect(page.get_by_text("Repository scanned successfully.")).to_be_visible()

        home_button = page.get_by_role("button", name="Home")
        palette_button = page.get_by_role(
            "button", name="Search files, symbols, or ask Cartographer..."
        )
        await page.keyboard.press("Tab")
        await expect(home_button).to_be_focused()
        await page.keyboard.press("Tab")
        await expect(palette_button).to_be_focused()
        assert await palette_button.evaluate("(element) => element.matches(':focus-visible')")
        await page.keyboard.press("Enter")
        palette_input = page.get_by_placeholder("Search files, symbols, or ask Cartographer...")
        await expect(palette_input).to_be_focused()
        await page.keyboard.type("How does main.py start?")
        async with page.expect_response(
            lambda response: urlparse(response.url).path == "/api/query"
        ):
            await page.keyboard.press("Enter")
        await expect(page.get_by_text("main.py starts the application.")).to_be_visible()
        assert_clean(fixture, page_errors, request_failures)


async def test_scan_loading_state_uses_a_releasable_barrier(browser: Browser, url: str) -> None:
    async with browser_case(browser, url) as (page, fixture, page_errors, request_failures):
        fixture.block_next_scan = True
        await page.get_by_label("Repository path").fill("/fixture")
        try:
            await page.get_by_role("button", name="Analyze repository").click()
            await asyncio.wait_for(fixture.scan_started.wait(), timeout=10)
            scanning_button = page.get_by_role("button", name="Scanning repository...")
            await expect(scanning_button).to_be_disabled()
        finally:
            fixture.release_scan.set()

        await expect(page.get_by_text("Repository scanned successfully.")).to_be_visible()
        assert_clean(fixture, page_errors, request_failures)


async def test_scan_graph_file_risk_and_question_workflow(browser: Browser, url: str) -> None:
    async with browser_case(browser, url) as (page, fixture, page_errors, request_failures):
        await scan(page)
        await expect(page.locator(".graph-node").filter(has_text="main.py")).to_be_visible()
        await open_main_file(page)
        await expect(page.locator(".inspector")).to_contain_text("Risk 92")
        await page.get_by_role("button", name="Risk hotspots").click()
        await expect(page.locator(".risk-hotspots-list")).to_contain_text("main.py")

        await ask(page, "How does main.py start?", wait_for_search=True)
        await expect(page.get_by_text("main.py starts the application.")).to_be_visible()
        await expect(page.get_by_text("EVIDENCE & MATCHES")).to_be_visible()
        await expect(page.locator(".evidence-list")).to_contain_text("Application entry point")

        for width, height in ((390, 844), (768, 1024), (1440, 900)):
            await page.set_viewport_size({"width": width, "height": height})
            horizontal_overflow = await page.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )
            assert not horizontal_overflow, f"horizontal overflow at {width}x{height}"

        assert_clean(fixture, page_errors, request_failures)


async def test_scan_failure_can_be_retried(browser: Browser, url: str) -> None:
    async with browser_case(browser, url) as (page, fixture, page_errors, request_failures):
        fixture.fail_next("/api/scan", "scan service unavailable")
        await page.get_by_label("Repository path").fill("/fixture")
        await page.get_by_role("button", name="Analyze repository").click()
        await expect(page.locator(".toast--error")).to_contain_text("scan service unavailable")
        await expect(page.locator(".toast--success")).to_have_count(0)

        await page.get_by_role("button", name="Analyze repository").click()
        await expect(page.get_by_text("Repository scanned successfully.")).to_be_visible()
        assert_clean(fixture, page_errors, request_failures)


async def test_aborted_scan_can_be_retried(browser: Browser, url: str) -> None:
    async with browser_case(browser, url) as (page, fixture, page_errors, request_failures):
        fixture.abort_next_scan = True
        await page.get_by_label("Repository path").fill("/fixture")
        await page.get_by_role("button", name="Analyze repository").click()
        await expect(page.locator(".toast--error")).to_be_visible()
        await expect(page.locator(".toast--success")).to_have_count(0)

        await page.get_by_role("button", name="Analyze repository").click()
        await expect(page.get_by_text("Repository scanned successfully.")).to_be_visible()
        assert_clean(fixture, page_errors, request_failures)


async def test_graph_failure_is_reported_and_rescan_recovers(browser: Browser, url: str) -> None:
    async with browser_case(browser, url) as (page, fixture, page_errors, request_failures):
        fixture.fail_next("/api/graph", "graph database unavailable")
        await page.get_by_label("Repository path").fill("/fixture")
        await page.get_by_role("button", name="Analyze repository").click()
        await expect(page.locator(".toast--error")).to_contain_text("graph database unavailable")
        await expect(page.locator(".toast--success")).to_have_count(0)

        await page.get_by_role("button", name="Rescan repository").click()
        await expect(page.get_by_text("Repository scanned successfully.")).to_be_visible()
        await expect(page.locator(".graph-node").filter(has_text="main.py")).to_be_visible()
        assert_clean(fixture, page_errors, request_failures)


async def test_file_and_query_failures_are_reported_and_recover(browser: Browser, url: str) -> None:
    async with browser_case(browser, url) as (page, fixture, page_errors, request_failures):
        await scan(page)
        fixture.fail_next("/api/file-detail", "file details unavailable")
        main_node = page.locator(".graph-node").filter(has_text="main.py")
        await main_node.click()
        await expect(page.locator(".toast--error")).to_contain_text("file details unavailable")
        await main_node.click()
        await expect(page.locator(".inspector h2")).to_have_text("main.py")

        fixture.fail_next("/api/query", "question service unavailable")
        await ask(page, "How does main.py start?")
        await expect(
            page.locator(".toast--error").filter(has_text="question service unavailable")
        ).to_be_visible()
        await ask(page, "How does main.py start?")
        await expect(page.get_by_text("main.py starts the application.")).to_be_visible()
        assert_clean(fixture, page_errors, request_failures)


async def main() -> None:
    url = os.environ["CARTOGRAPHER_E2E_URL"]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            scenarios = (
                test_empty_workspace_and_keyboard_workflow,
                test_scan_loading_state_uses_a_releasable_barrier,
                test_scan_graph_file_risk_and_question_workflow,
                test_scan_failure_can_be_retried,
                test_aborted_scan_can_be_retried,
                test_graph_failure_is_reported_and_rescan_recovers,
                test_file_and_query_failures_are_reported_and_recover,
            )
            for scenario in scenarios:
                await scenario(browser, url)
                print(f"browser scenario passed: {scenario.__name__}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
