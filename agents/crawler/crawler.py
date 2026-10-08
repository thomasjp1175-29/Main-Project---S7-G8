import asyncio
import json
import os
from datetime import datetime
from urllib.parse import urlparse
from playwright.async_api import async_playwright

async def run_crawler(target_url: str):
    print(f"\n==========================================")
    print(f"[*] Starting AutoWebFix Headed Agent")
    print(f"[*] Target: {target_url}")
    print(f"==========================================\n")

    console_logs = []
    uncaught_errors = []
    failed_requests = []
    http_errors = []

    domain = urlparse(target_url).netloc.replace(":", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("logs", f"{domain}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    screenshot_path = os.path.join(run_dir, "screenshot.png")
    report_path = os.path.join(run_dir, "crawl_report.json")

    status = "UNKNOWN"
    title = "N/A"

    async with async_playwright() as p:
        # headless=False: launches a visible desktop window
        # slow_mo=800: slows down actions by 800ms for visual tracking
        print("[+] Launching visible browser window...")
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=800,
            args=["--start-maximized"]
        )

        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        # Listeners for real-time monitoring
        page.on("console", lambda msg: (
            console_logs.append({"type": msg.type, "text": msg.text, "location": msg.location}),
            print(f"  [Console {msg.type.upper()}] {msg.text}")
        ))

        page.on("pageerror", lambda exc: (
            uncaught_errors.append({"message": str(exc), "stack": getattr(exc, "stack", None)}),
            print(f"  [CRITICAL JS ERROR] {exc}")
        ))

        page.on("requestfailed", lambda req: (
            failed_requests.append({"url": req.url, "method": req.method, "failure": req.failure}),
            print(f"  [NETWORK FAILED] {req.method} {req.url}")
        ))

        page.on("response", lambda res: (
            http_errors.append({"url": res.url, "status": res.status, "status_text": res.status_text}),
            print(f"  [HTTP ERROR {res.status}] {res.url}")
        ) if res.status >= 400 else None)

        try:
            print(f"[+] Navigating to: {target_url}...")
            response = await page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
            status = response.status if response else "NO_RESPONSE"
            title = await page.title()
            print(f"[+] Loaded: '{title}' (Status: HTTP {status})")

            # In-page Visual HUD Banner
            await page.evaluate("""() => {
                const hud = document.createElement('div');
                hud.id = 'autowebfix-hud';
                hud.innerHTML = `
                    <div style="font-family: monospace; font-size: 13px; font-weight: bold; margin-bottom: 4px;">
                        🤖 AutoWebFix Agent Active
                    </div>
                    <div id="autowebfix-status" style="font-size: 12px; color: #a3e635;">
                        Analyzing page structure & resources...
                    </div>
                `;
                Object.assign(hud.style, {
                    position: 'fixed',
                    top: '16px',
                    right: '16px',
                    zIndex: '9999999',
                    backgroundColor: 'rgba(15, 23, 42, 0.92)',
                    color: '#ffffff',
                    padding: '12px 18px',
                    borderRadius: '10px',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                    border: '1px solid #38bdf8',
                    pointerEvents: 'none',
                    backdropFilter: 'blur(8px)',
                    transition: 'all 0.3s ease'
                });
                document.body.appendChild(hud);
            }""")

            async def update_hud(text: str, color: str = "#38bdf8"):
                await page.evaluate(f"""() => {{
                    const el = document.getElementById('autowebfix-status');
                    if (el) {{
                        el.innerText = "{text}";
                        el.style.color = "{color}";
                    }}
                }}""")

            await update_hud("Inspecting page content & elements...", "#38bdf8")
            await page.wait_for_timeout(1000)

            # Visually scroll through page
            print("[+] Scanning page layout (scrolling)...")
            await update_hud("Scanning page layout & scrolling...", "#fbbf24")
            await page.evaluate("window.scrollBy({ top: 400, behavior: 'smooth' });")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollBy({ top: 400, behavior: 'smooth' });")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' });")
            await page.wait_for_timeout(1000)

            # Highlight candidate links
            links = await page.query_selector_all("a")
            print(f"[+] Found {len(links)} links on the page.")
            await update_hud(f"Detected {len(links)} links. Highlighting candidates...", "#a855f7")

            for link in links[:5]:
                try:
                    await link.evaluate("""el => {
                        el.style.outline = '3px solid #f43f5e';
                        el.style.outlineOffset = '2px';
                        el.style.transition = 'outline 0.3s ease';
                    }""")
                    await page.wait_for_timeout(400)
                except Exception:
                    pass

            await update_hud("Capturing full-page snapshot...", "#38bdf8")
            await page.wait_for_timeout(500)

            # Capture screenshot
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"[+] Screenshot captured: {screenshot_path}")

            await update_hud("Audit Complete! Compiling report...", "#4ade80")
            print("[+] Inspection complete. Waiting 3 seconds before closing browser...")
            await page.wait_for_timeout(3000)

        except Exception as e:
            print(f"[-] Execution error: {e}")
            status = f"ERROR: {type(e).__name__}"

        await browser.close()
        print("[+] Browser window closed.")

    # Save diagnostic summary
    report_data = {
        "target_url": target_url,
        "page_title": title,
        "http_status": status,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "console_errors": sum(1 for c in console_logs if c["type"] == "error"),
            "uncaught_js_exceptions": len(uncaught_errors),
            "failed_requests": len(failed_requests),
            "http_status_errors": len(http_errors),
        },
        "diagnostics": {
            "uncaught_exceptions": uncaught_errors,
            "http_errors": http_errors,
            "failed_requests": failed_requests,
            "console_logs": console_logs
        },
        "artifacts": {
            "screenshot": screenshot_path
        }
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=4)

    print(f"\n[+] Diagnostic report saved to: {report_path}")
    print(f"[+] Summary: {json.dumps(report_data['summary'], indent=2)}")

if __name__ == "__main__":
    test_url = "https://books.toscrape.com/"
    asyncio.run(run_crawler(test_url))