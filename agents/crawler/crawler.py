import asyncio
import json
import os
import sys
from collections import deque
from datetime import datetime
from urllib.parse import urlparse, urljoin, urldefrag
from playwright.async_api import async_playwright

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def normalize_url(url: str) -> str:
    """Strip fragments and clean up trailing slashes for deduplication."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"

def is_valid_http_url(url: str) -> bool:
    """Ensure link is HTTP/HTTPS and not javascript:, mailto:, tel:, etc."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https")

def is_same_domain(url: str, base_domain: str) -> bool:
    """Verify if the URL belongs to the target domain (domain-bound)."""
    parsed = urlparse(url)
    return parsed.netloc.lower() == base_domain.lower()

async def inject_hud(page, current_page_num: int, max_pages: int, depth: int, queue_len: int, total_issues: int):
    """Injects or updates an interactive glassmorphic HUD directly on the page."""
    await page.evaluate(f"""() => {{
        let hud = document.getElementById('autowebfix-hud');
        if (!hud) {{
            hud = document.createElement('div');
            hud.id = 'autowebfix-hud';
            Object.assign(hud.style, {{
                position: 'fixed',
                top: '16px',
                right: '16px',
                zIndex: '99999999',
                backgroundColor: 'rgba(15, 23, 42, 0.94)',
                color: '#f8fafc',
                padding: '14px 20px',
                borderRadius: '12px',
                boxShadow: '0 10px 30px rgba(0,0,0,0.4)',
                border: '1px solid #38bdf8',
                fontFamily: 'system-ui, -apple-system, sans-serif',
                pointerEvents: 'none',
                backdropFilter: 'blur(10px)',
                minWidth: '280px',
                transition: 'all 0.3s ease'
            }});
            document.body.appendChild(hud);
        }}
        hud.innerHTML = `
            <div style="font-weight: 700; font-size: 13px; color: #38bdf8; display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span>AutoWebFix Crawler</span>
                <span style="background: #0284c7; color: white; padding: 2px 8px; border-radius: 999px; font-size: 11px;">Page {current_page_num}/{max_pages}</span>
            </div>
            <div style="font-size: 11px; color: #94a3b8; margin-bottom: 6px;">
                Depth: <b style="color: #f1f5f9;">{depth}</b> | Queue: <b style="color: #f1f5f9;">{queue_len}</b> | Issues: <b style="color: {('#ef4444' if total_issues > 0 else '#22c55e')};">{total_issues}</b>
            </div>
            <div id="autowebfix-status" style="font-size: 12px; color: #a3e635; font-weight: 500;">
                Initializing inspection...
            </div>
        `;
    }}""")

async def update_hud_status(page, message: str, color: str = "#38bdf8"):
    """Update status message inside the active HUD."""
    try:
        safe_msg = message.replace('"', '\\"').replace("'", "\\'")
        await page.evaluate(f"""() => {{
            const el = document.getElementById('autowebfix-status');
            if (el) {{
                el.innerText = '{safe_msg}';
                el.style.color = '{color}';
            }}
        }}""")
    except Exception:
        pass

async def run_crawler(target_url: str, max_pages: int = 10, max_depth: int = 3):
    target_url = normalize_url(target_url)
    base_domain = urlparse(target_url).netloc
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("logs", f"{base_domain.replace(':', '_')}_{timestamp}")
    screenshots_dir = os.path.join(run_dir, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    report_path = os.path.join(run_dir, "crawl_report.json")

    print("\n" + "=" * 60)
    print("  [*] AUTOWEBFIX: MULTI-PAGE & DOMAIN-BOUND CRAWLER")
    print(f"  [*] Target:     {target_url}")
    print(f"  [*] Domain:     {base_domain}")
    print(f"  [*] Max Pages:  {max_pages}  |  Max Depth: {max_depth}")
    print("=" * 60 + "\n")

    queue = deque([(target_url, 0)])
    visited_urls = set()
    tested_links = {}
    broken_links = []
    all_broken_images = []
    pages_audited = []
    total_issues_count = 0

    async with async_playwright() as p:
        print("[+] Launching visible desktop browser...")
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=400,
            args=["--start-maximized"]
        )

        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        # -------------------------------------------------------------------------
        # FIX: Register listeners ONCE outside the loop to prevent duplicate
        # registrations and memory leaks across page navigations.
        # -------------------------------------------------------------------------
        current_telemetry = {
            "console_logs": [],
            "uncaught_errors": [],
            "failed_requests": [],
            "http_errors": []
        }

        page.on("console", lambda msg: current_telemetry["console_logs"].append({
            "type": msg.type,
            "text": msg.text,
            "location": msg.location
        }))

        page.on("pageerror", lambda exc: current_telemetry["uncaught_errors"].append({
            "message": str(exc),
            "stack": getattr(exc, "stack", None)
        }))

        page.on("requestfailed", lambda req: current_telemetry["failed_requests"].append({
            "url": req.url,
            "method": req.method,
            "failure": req.failure
        }))

        page.on("response", lambda res: current_telemetry["http_errors"].append({
            "url": res.url,
            "status": res.status,
            "status_text": res.status_text
        }) if res.status >= 400 else None)
        # -------------------------------------------------------------------------

        page_counter = 0

        while queue and page_counter < max_pages:
            current_url, depth = queue.popleft()
            normalized_current = normalize_url(current_url)

            if normalized_current in visited_urls:
                continue

            visited_urls.add(normalized_current)
            page_counter += 1

            print(f"\n------------------------------------------------------------")
            print(f"[{page_counter}/{max_pages}] Visiting (Depth {depth}): {current_url}")
            print(f"------------------------------------------------------------")

            # Reset telemetry buffer cleanly for this page iteration
            current_telemetry["console_logs"].clear()
            current_telemetry["uncaught_errors"].clear()
            current_telemetry["failed_requests"].clear()
            current_telemetry["http_errors"].clear()

            # Navigate to page
            page_status = "UNKNOWN"
            page_title = "N/A"
            try:
                response = await page.goto(current_url, timeout=30000, wait_until="domcontentloaded")
                page_status = response.status if response else "NO_RESPONSE"
                page_title = await page.title()
                print(f"[+] Loaded: '{page_title}' (Status: HTTP {page_status})")
            except Exception as e:
                print(f"[-] Navigation failed: {e}")
                page_status = f"ERROR: {type(e).__name__}"

            # Calculate current issues so far
            current_page_issues = (
                len(current_telemetry["uncaught_errors"]) +
                len(current_telemetry["failed_requests"]) +
                sum(1 for c in current_telemetry["console_logs"] if c["type"] == "error")
            )
            total_issues_count += current_page_issues

            # Inject HUD
            await inject_hud(page, page_counter, max_pages, depth, len(queue), total_issues_count)
            await page.wait_for_timeout(400)

            # Scroll through the page
            await update_hud_status(page, "Scanning page layout...", "#fbbf24")
            await page.evaluate("window.scrollBy({ top: 450, behavior: 'smooth' });")
            await page.wait_for_timeout(600)
            await page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' });")
            await page.wait_for_timeout(400)

            # --- DOM-Level Broken Image Check ---
            await update_hud_status(page, "Checking images & media assets...", "#38bdf8")
            broken_images_on_page = await page.evaluate("""() => {
                const imgs = Array.from(document.querySelectorAll('img'));
                const broken = [];
                for (const img of imgs) {
                    const src = img.getAttribute('src') || '';
                    const isBroken = !img.complete || img.naturalWidth === 0 || !src.trim();
                    if (isBroken) {
                        img.style.outline = '3px dashed #ef4444';
                        img.style.outlineOffset = '2px';
                        img.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
                        broken.push({
                            src: img.src || src,
                            alt: img.alt || '[No Alt Text]',
                            id: img.id || '',
                            className: img.className || ''
                        });
                    }
                }
                return broken;
            }""")

            for b_img in broken_images_on_page:
                b_img["page_url"] = current_url
                all_broken_images.append(b_img)
                total_issues_count += 1
                print(f"  [X BROKEN IMAGE] src='{b_img['src']}' alt='{b_img['alt']}'")

            # --- Discover and Analyze Hyperlinks ---
            await update_hud_status(page, "Analyzing hyperlinks & detecting broken links...", "#38bdf8")
            raw_links = await page.query_selector_all("a")
            print(f"[+] Found {len(raw_links)} hyperlinks on page.")

            discovered_internal = []
            page_broken_links = []

            for link_elem in raw_links:
                try:
                    href = await link_elem.get_attribute("href")
                    if not href or href.strip().startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue

                    full_url = normalize_url(urljoin(current_url, href))
                    if not is_valid_http_url(full_url):
                        continue

                    link_text = (await link_elem.inner_text()).strip() or "[Icon/Empty]"
                    same_domain = is_same_domain(full_url, base_domain)

                    # Check link status
                    if full_url in tested_links:
                        status_code = tested_links[full_url]
                    else:
                        try:
                            check_res = await context.request.get(full_url, timeout=6000, max_redirects=5, fail_on_status_code=False)
                            status_code = check_res.status
                        except Exception as e:
                            status_code = f"FAILED: {type(e).__name__}"
                        tested_links[full_url] = status_code

                    # Check if broken (HTTP >= 400 or failed connection)
                    is_broken = False
                    if isinstance(status_code, int) and status_code >= 400:
                        is_broken = True
                    elif isinstance(status_code, str) and status_code.startswith("FAILED"):
                        is_broken = True

                    if is_broken:
                        broken_record = {
                            "source_page": current_url,
                            "anchor_text": link_text,
                            "target_url": full_url,
                            "status": status_code
                        }
                        page_broken_links.append(broken_record)
                        broken_links.append(broken_record)
                        total_issues_count += 1

                        # Visually mark broken link in RED and attach on-screen HTTP status badge
                        await link_elem.evaluate("""(el, status) => {
                            el.style.outline = '3px solid #ef4444';
                            el.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
                            const badge = document.createElement('span');
                            badge.innerText = ` [HTTP ${status}]`;
                            badge.style.cssText = 'background: #ef4444; color: white; font-size: 10px; font-weight: bold; padding: 1px 5px; border-radius: 4px; margin-left: 4px; vertical-align: middle; display: inline-block;';
                            el.appendChild(badge);
                        }""", status_code)
                        print(f"  [X BROKEN LINK] ({status_code}) '{link_text}' -> {full_url}")

                    else:
                        # Mark live link in GREEN
                        await link_elem.evaluate("""el => {
                            el.style.outline = '2px solid #22c55e';
                        }""")

                    # Domain-bound queue: Enqueue internal links only
                    if same_domain and not is_broken:
                        if full_url not in visited_urls and (full_url, depth + 1) not in queue:
                            if depth + 1 <= max_depth:
                                queue.append((full_url, depth + 1))
                                discovered_internal.append(full_url)

                except Exception:
                    continue

            print(f"[+] Enqueued {len(discovered_internal)} new domain URLs. (Queue size: {len(queue)})")

            # Update HUD status with summary
            status_text = f"Discovered {len(discovered_internal)} internal links | Broken: {len(page_broken_links)} | Bad Imgs: {len(broken_images_on_page)}"
            await update_hud_status(page, status_text, "#a855f7" if not (page_broken_links or broken_images_on_page) else "#ef4444")
            await page.wait_for_timeout(600)

            # Capture page screenshot
            screenshot_file = os.path.join(screenshots_dir, f"page_{page_counter}.png")
            try:
                await page.screenshot(path=screenshot_file, full_page=True)
                print(f"[+] Screenshot saved: {screenshot_file}")
            except Exception as e:
                print(f"[-] Screenshot failed: {e}")

            # Store page audit record by copying current telemetry
            pages_audited.append({
                "page_number": page_counter,
                "url": current_url,
                "title": page_title,
                "depth": depth,
                "http_status": page_status,
                "screenshot": screenshot_file,
                "metrics": {
                    "console_errors": sum(1 for c in current_telemetry["console_logs"] if c["type"] == "error"),
                    "console_warnings": sum(1 for c in current_telemetry["console_logs"] if c["type"] == "warning"),
                    "uncaught_js_exceptions": len(current_telemetry["uncaught_errors"]),
                    "failed_requests": len(current_telemetry["failed_requests"]),
                    "http_status_errors": len(current_telemetry["http_errors"]),
                    "broken_links_found": len(page_broken_links),
                    "broken_images_found": len(broken_images_on_page)
                },
                "issues": {
                    "uncaught_exceptions": list(current_telemetry["uncaught_errors"]),
                    "broken_links": page_broken_links,
                    "broken_images": broken_images_on_page,
                    "http_errors": list(current_telemetry["http_errors"]),
                    "console_logs": list(current_telemetry["console_logs"])
                }
            })

            await page.wait_for_timeout(800)

        # Final HUD message
        try:
            await update_hud_status(page, f"Crawl finished! Audited {page_counter} pages. Closing...", "#22c55e")
            await page.wait_for_timeout(2500)
        except Exception:
            pass

        await browser.close()
        print("\n[+] Browser session closed.")

    # Comprehensive multi-page report
    final_report = {
        "crawl_metadata": {
            "target_url": target_url,
            "base_domain": base_domain,
            "timestamp": datetime.now().isoformat(),
            "max_pages_limit": max_pages,
            "max_depth_limit": max_depth,
            "pages_crawled_count": len(pages_audited),
            "unique_urls_tested": len(tested_links)
        },
        "summary": {
            "total_pages_crawled": len(pages_audited),
            "total_broken_links": len(broken_links),
            "total_broken_images": len(all_broken_images),
            "total_uncaught_js_errors": sum(p["metrics"]["uncaught_js_exceptions"] for p in pages_audited),
            "total_console_errors": sum(p["metrics"]["console_errors"] for p in pages_audited),
            "total_network_failures": sum(p["metrics"]["failed_requests"] for p in pages_audited)
        },
        "broken_links": broken_links,
        "broken_images": all_broken_images,
        "pages": pages_audited
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=4)

    print("\n" + "=" * 60)
    print("  [*] AUDIT FINISHED - MULTI-PAGE REPORT GENERATED")
    print("=" * 60)
    print(f"  Pages Crawled:        {final_report['summary']['total_pages_crawled']}")
    print(f"  Total Broken Links:   {final_report['summary']['total_broken_links']}")
    print(f"  Total Broken Images:  {final_report['summary']['total_broken_images']}")
    print(f"  Uncaught JS Errors:   {final_report['summary']['total_uncaught_js_errors']}")
    print(f"  Console Errors:       {final_report['summary']['total_console_errors']}")
    print(f"  Report File:          {report_path}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    seed_url = "https://quotes.toscrape.com/"
    # Crawl up to 10 pages within the same domain, max depth 3
    asyncio.run(run_crawler(seed_url, max_pages=10, max_depth=3))
