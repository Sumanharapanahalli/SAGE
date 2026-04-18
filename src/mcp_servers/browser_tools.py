"""
SAGE MCP Server — Browser Tools
=================================
Browser automation for SAGE agents using Playwright. Provides web scraping,
screenshot capture, and page interaction capabilities.

Falls back gracefully if Playwright is not installed — returns structured
error messages so agents can report the missing dependency.

Works with any LLM provider — agents call these through MCPRegistry.invoke().
"""

import logging
import os
import tempfile

logger = logging.getLogger("browser_tools_mcp")

try:
    from fastmcp import FastMCP
    mcp = FastMCP("browser-tools")
except ImportError:
    logger.warning("fastmcp not installed — MCP server cannot start standalone")
    mcp = None


def _check_playwright() -> str | None:
    """Return None if Playwright AND the chromium browser binary are available,
    or an error reason string otherwise."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright not installed. Run: pip install playwright && playwright install chromium"

    try:
        with sync_playwright() as p:
            path = p.chromium.executable_path
            if not path or not os.path.isfile(path):
                return (
                    "playwright chromium binary missing at "
                    f"{path!r}. Run: playwright install chromium"
                )
    except Exception as exc:
        return f"playwright runtime unavailable: {exc}"
    return None


def _get_screenshot_dir() -> str:
    """Return a directory for storing browser screenshots."""
    try:
        from src.core.project_loader import project_config, _SOLUTIONS_DIR
        sage_dir = os.path.join(_SOLUTIONS_DIR, project_config.project_name, ".sage")
        screenshots = os.path.join(sage_dir, "screenshots")
        os.makedirs(screenshots, exist_ok=True)
        return screenshots
    except Exception:
        return tempfile.gettempdir()


if mcp:
    @mcp.tool()
    def browse_page(
        url: str,
        wait_seconds: float = 2.0,
        extract_text: bool = True,
        extract_links: bool = False,
        max_text_length: int = 10000,
    ) -> dict:
        """
        Navigate to a URL and extract page content.

        Args:
            url:             URL to navigate to.
            wait_seconds:    Seconds to wait for page to load (default 2.0).
            extract_text:    Extract visible text content (default True).
            extract_links:   Extract all links on the page (default False).
            max_text_length: Truncate text content at this length (default 10000).

        Returns page title, text content, and optionally links.
        """
        reason = _check_playwright()
        if reason:
            return {"available": False, "reason": reason}

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if wait_seconds > 0:
                    page.wait_for_timeout(int(wait_seconds * 1000))

                result = {
                    "available": True,
                    "success": True,
                    "url": page.url,
                    "title": page.title(),
                }

                if extract_text:
                    text = page.inner_text("body")
                    result["text"] = text[:max_text_length]
                    result["text_truncated"] = len(text) > max_text_length

                if extract_links:
                    links = page.eval_on_selector_all(
                        "a[href]",
                        "els => els.map(e => ({text: e.innerText.trim().slice(0,100), href: e.href}))"
                    )
                    result["links"] = links[:200]

                browser.close()
                return result

        except Exception as e:
            return {"available": True, "success": False, "error": str(e), "url": url}

    @mcp.tool()
    def screenshot_page(
        url: str,
        full_page: bool = False,
        wait_seconds: float = 2.0,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ) -> dict:
        """
        Capture a screenshot of a web page.

        Args:
            url:              URL to screenshot.
            full_page:        Capture entire scrollable page (default False).
            wait_seconds:     Seconds to wait before capture (default 2.0).
            viewport_width:   Browser viewport width (default 1280).
            viewport_height:  Browser viewport height (default 720).

        Returns path to saved screenshot PNG.
        """
        reason = _check_playwright()
        if reason:
            return {"available": False, "reason": reason}

        try:
            from playwright.sync_api import sync_playwright
            import time

            screenshot_dir = _get_screenshot_dir()
            filename = f"screenshot_{int(time.time())}.png"
            filepath = os.path.join(screenshot_dir, filename)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={"width": viewport_width, "height": viewport_height}
                )
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if wait_seconds > 0:
                    page.wait_for_timeout(int(wait_seconds * 1000))

                page.screenshot(path=filepath, full_page=full_page)
                browser.close()

            return {
                "available": True,
                "success": True,
                "url": url,
                "screenshot_path": filepath,
                "full_page": full_page,
                "viewport": f"{viewport_width}x{viewport_height}",
            }

        except Exception as e:
            return {"available": True, "success": False, "error": str(e), "url": url}

    @mcp.tool()
    def click_and_extract(
        url: str,
        selector: str,
        wait_after_click_ms: int = 2000,
        extract_selector: str = "body",
        max_text_length: int = 10000,
    ) -> dict:
        """
        Navigate to a page, click an element, and extract resulting content.

        Args:
            url:                  URL to navigate to.
            selector:             CSS selector of element to click.
            wait_after_click_ms:  Milliseconds to wait after click (default 2000).
            extract_selector:     CSS selector to extract text from after click (default "body").
            max_text_length:      Truncate extracted text at this length.

        Returns extracted text after the click action.
        """
        reason = _check_playwright()
        if reason:
            return {"available": False, "reason": reason}

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1000)

                page.click(selector, timeout=10000)
                page.wait_for_timeout(wait_after_click_ms)

                text = page.inner_text(extract_selector)
                browser.close()

                return {
                    "available": True,
                    "success": True,
                    "url": url,
                    "clicked": selector,
                    "text": text[:max_text_length],
                    "text_truncated": len(text) > max_text_length,
                }

        except Exception as e:
            return {"available": True, "success": False, "error": str(e), "url": url}

    @mcp.tool()
    def fill_form(
        url: str,
        fields: dict,
        submit_selector: str = None,
        wait_after_submit_ms: int = 2000,
    ) -> dict:
        """
        Navigate to a page, fill form fields, and optionally submit.

        Args:
            url:                   URL containing the form.
            fields:                Dict of {css_selector: value} pairs to fill.
            submit_selector:       CSS selector of submit button (optional).
            wait_after_submit_ms:  Milliseconds to wait after submit (default 2000).

        Returns page state after form interaction.
        """
        reason = _check_playwright()
        if reason:
            return {"available": False, "reason": reason}

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1000)

                filled = []
                for selector, value in fields.items():
                    page.fill(selector, value, timeout=10000)
                    filled.append(selector)

                submitted = False
                if submit_selector:
                    page.click(submit_selector, timeout=10000)
                    page.wait_for_timeout(wait_after_submit_ms)
                    submitted = True

                result = {
                    "available": True,
                    "success": True,
                    "url": page.url,
                    "title": page.title(),
                    "fields_filled": filled,
                    "submitted": submitted,
                }
                browser.close()
                return result

        except Exception as e:
            return {"available": True, "success": False, "error": str(e), "url": url}


if __name__ == "__main__":
    if mcp is None:
        print("ERROR: fastmcp not installed. Run: pip install fastmcp")
        import sys
        sys.exit(1)
    mcp.run()
