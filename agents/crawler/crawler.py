import asyncio
from playwright.async_api import async_playwright

async def run_crawler(target_url: str):
    print(f"[+] Starting AutoWebFix Crawler for: {target_url}")
    
    console_logs = []
    failed_requests = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Listener for JavaScript console errors
        page.on("console", lambda msg: console_logs.append({
            "type": msg.type,
            "text": msg.text
        }))

        # Listener for failed network requests
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

        title = await page.title()
        print(f"[+] Page Title: '{title}'")

        await browser.close()

    print("\n--- Crawl Diagnostic Summary ---")
    print(f"Captured {len(console_logs)} console log(s).")
    for log in console_logs:
        if log["type"] in ["error", "warning"]:
            print(f"  [{log['type'].upper()}] {log['text']}")

    print(f"Captured {len(failed_requests)} failed network request(s).")
    for req in failed_requests:
        print(f"  [FAILED REQUEST] {req['url']} -> {req['failure']}")

if __name__ == "__main__":
    test_url = "https://example.com"
    asyncio.run(run_crawler(test_url))