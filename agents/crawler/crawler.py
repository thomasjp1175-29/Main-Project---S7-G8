import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def run_crawler(target_url: str):
    print(f"[+] Starting AutoWebFix Crawler for: {target_url}")
    
    console_logs = []
    failed_requests = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
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

        await browser.close()

    # Create diagnostic report object
    report_data = {
        "target_url": target_url,
        "page_title": title,
        "http_status": status,
        "timestamp": datetime.now().isoformat(),
        "console_logs": console_logs,
        "failed_requests": failed_requests
    }

    # Ensure logs folder exists and save report
    os.makedirs("logs", exist_ok=True)
    report_path = os.path.join("logs", "crawl_report.json")
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=4)

    print(f"\n[+] Diagnostic report saved to: {report_path}")

if __name__ == "__main__":
    test_url = "https://quotes.toscrape.com/"
    asyncio.run(run_crawler(test_url))