import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def run_crawler(target_url: str):
    print(f"[+] Starting AutoWebFix Crawler for: {target_url}")
    
    console_logs = []
    failed_requests = []
    screenshot_path = None

    async with async_playwright() as p:
        # Launch visible Chromium browser window with 1-second step delay
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()

        # Listeners for JavaScript errors & failed requests
        page.on("console", lambda msg: console_logs.append({
            "type": msg.type,
            "text": msg.text
        }))

        page.on("requestfailed", lambda req: failed_requests.append({
            "url": req.url,
            "failure": req.failure
        }))

        try:
            response = await page.goto(target_url, timeout=30000)
            status = response.status if response else "Unknown"
            print(f"[+] Page loaded with status HTTP {status}")
        except Exception as e:
            print(f"[-] Failed to load URL: {e}")
            status = "FAILED"

        title = await page.title()
        print(f"[+] Page Title: '{title}'")

        # Evaluate error conditions
        has_console_errors = any(log["type"] in ["error", "warning"] for log in console_logs)
        has_network_failures = len(failed_requests) > 0
        is_http_error = isinstance(status, int) and status >= 400

        # Capture full-page screenshot if an error condition is triggered
        if has_console_errors or has_network_failures or is_http_error:
            os.makedirs("logs/screenshots", exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join("logs", "screenshots", f"error_{timestamp_str}.png")
            
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"[!] Errors detected! Screenshot saved to: {screenshot_path}")

        # Pause for 3 seconds so you can watch the opened window
        await page.wait_for_timeout(3000)

        await browser.close()

    # Create diagnostic report object
    report_data = {
        "target_url": target_url,
        "page_title": title,
        "http_status": status,
        "timestamp": datetime.now().isoformat(),
        "console_logs": console_logs,
        "failed_requests": failed_requests,
        "screenshot_captured": screenshot_path
    }

    # Save report to logs/crawl_report.json
    os.makedirs("logs", exist_ok=True)
    report_path = os.path.join("logs", "crawl_report.json")
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=4)

    print(f"[+] Diagnostic report saved to: {report_path}")

if __name__ == "__main__":
    test_url = "https://quotes.toscrape.com/"
    asyncio.run(run_crawler(test_url))