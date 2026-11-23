import asyncio
from playwright.async_api import async_playwright

async def capture_screenshots():
    print("Launching Chromium via Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        print("Navigating to http://localhost:8501...")
        await page.goto("http://localhost:8501", wait_until="networkidle")
        await asyncio.sleep(4)

        # 1. Baseline Clean Dashboard
        ss1 = "C:/Users/yashs/Projects/traceops-ai/pitch/screenshots/01_dashboard_baseline.png"
        await page.screenshot(path=ss1, full_page=False)
        print("Captured:", ss1)

        # 2. Trigger Runaway Loop (Exact Hash <0.5 ms)
        loop_btn = page.locator("button:has-text('2. Runaway Recursive Loop')")
        if await loop_btn.count() > 0:
            print("Triggering Runaway Loop attack...")
            await loop_btn.first.click()
            await asyncio.sleep(3)
            ss2 = "C:/Users/yashs/Projects/traceops-ai/pitch/screenshots/02_runaway_loop_intercepted.png"
            await page.screenshot(path=ss2, full_page=False)
            print("Captured:", ss2)

        # 3. Trigger High-Value Refund (SUSPEND_HITL)
        hitl_btn = page.locator("button:has-text('4. High-Value Refund')")
        if await hitl_btn.count() > 0:
            print("Triggering High-Value Refund HITL...")
            await hitl_btn.first.click()
            await asyncio.sleep(3)
            ss3 = "C:/Users/yashs/Projects/traceops-ai/pitch/screenshots/03_hitl_suspended_approval.png"
            await page.screenshot(path=ss3, full_page=False)
            print("Captured:", ss3)

        await browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    asyncio.run(capture_screenshots())
