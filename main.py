import os
import time
from playwright.sync_api import sync_playwright, expect

def main():
    discord_token = os.environ.get("DISCORD_TOKEN")
    saved_cookie = os.environ.get("SLIMENODES_COOKIE")

    with sync_playwright() as p:
        # 在 GitHub Actions 中运行无头模式
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="zh-TW")
        page = context.new_page()

        # 1. 全局拦截 Google AdSense 广告 (屏蔽弹窗)
        def route_interceptor(route):
            url = route.request.url
            if "googleads" in url or "vignette" in url or "doubleclick" in url:
                route.abort()
            else:
                route.continue_()
        page.route("**/*", route_interceptor)

        # 2. 优先尝试使用历史 Cookie 登录
        cookie_valid = False
        if saved_cookie and saved_cookie.strip():
            print("▶ 发现已有 Cookie，正在尝试直接恢复会话...")
            context.add_cookies([{
                "name": "connect.sid",
                "value": saved_cookie,
                "domain": "dash.slimenodes.com",
                "path": "/"
            }])
            
            try:
                # [优化点] 只要 DOM 加载完就放行，超时放宽到 60s
                page.goto("https://dash.slimenodes.com/dashboard", timeout=60000, wait_until="domcontentloaded")
                
                # 等待页面特征元素，最多等15秒
                page.locator('text="Your server"').wait_for(timeout=15000)
                
                if "dashboard" in page.url:
                    print("✅ Cookie 依然有效，成功跳过登录流程！")
                    page.screenshot(path="step1_cookie_success.png") # [截图] Cookie 登录成功
                    cookie_valid = True
            except Exception as e:
                print(f"⚠️ Cookie 会话恢复失败或页面加载超时: {e}")
                page.screenshot(path="step1_cookie_failed.png") # [截图] Cookie 登录失败现场
                print("▶ 准备退回使用 Discord Token 重新获取授权...")
                context.clear_cookies()

        # 3. Cookie 失效时的后备方案：Discord Token 注入登录
        if not cookie_valid:
            if not discord_token:
                raise Exception("❌ 未配置 DISCORD_TOKEN，无法完成登录！")

            print("▶ 开始通过 Discord Token 注入...")
            page.goto("https://discord.com/login", wait_until="domcontentloaded")
            
            page.evaluate(f'''() => {{
                window.localStorage.setItem('token', '"{discord_token}"');
            }}''')
            page.reload(wait_until="domcontentloaded")
            
            try:
                page.wait_for_selector('div[class*="app_"]', timeout=15000)
                print("✅ Discord 账号状态注入成功。")
                page.screenshot(path="step2_discord_injected.png") # [截图] 确认进入了 Discord
            except Exception as e:
                page.screenshot(path="step2_discord_injection_failed.png")
                raise Exception(f"❌ Discord Token 注入后未能加载主界面: {e}")

            # 4. 前往目标网站发起 OAuth 授权
            print("▶ 前往 SlimeNodes 面板点击登录...")
            page.goto("https://dash.slimenodes.com", wait_until="domcontentloaded")
            page.screenshot(path="step3_panel_home.png") # [截图] 面板首页准备点击登录
            
            page.locator('a.button[href="/login"]').click()
            
            # 等待跳转到 Discord 授权页
            page.wait_for_url("**/oauth2/authorize**", timeout=30000)
            print("▶ 成功进入 Discord 授权页面。")
            time.sleep(3) # 给 React 渲染留一点时间
            
            # 5. 处理必须滚动到底部才能点击的授权按钮
            max_attempts = 15
            for i in range(max_attempts):
                page.evaluate('''() => {
                    document.querySelectorAll('*').forEach(e => {
                        if (e.scrollHeight > e.clientHeight) {
                            e.scrollTop = e.scrollHeight;
                        }
                    });
                }''')
                time.sleep(0.5)
                
                auth_btn = page.locator('button[type="button"]:not([disabled])', has_text="授权")
                if auth_btn.count() == 0:
                    auth_btn = page.locator('button[type="button"]:not([disabled])', has_text="Authorize")
                
                if auth_btn.count() > 0 and auth_btn.is_visible():
                    page.screenshot(path="step4_oauth_ready_to_click.png") # [截图] 按钮激活，准备点击
                    auth_btn.click()
                    print("✅ 成功点击授权按钮！")
                    time.sleep(2)
                    page.screenshot(path="step5_oauth_clicked.png") # [截图] 点击后的跳转状态
                    break
            else:
                page.screenshot(path="step4_oauth_scroll_failed.png")
                raise Exception("❌ 无法激活授权按钮，可能 UI 已更改或滚动未生效。")

            # 6. 提取最新的 Cookie
            print("▶ 等待面板回调与鉴权...")
            try:
                page.wait_for_url("**/dashboard**", timeout=30000)
                # 这里可以等一下特征元素，确认真的进去了
                page.locator('text="Your server"').wait_for(timeout=15000)
                page.screenshot(path="step6_dashboard_success.png") # [截图] 成功进入面板后台
            except Exception as e:
                page.screenshot(path="step6_dashboard_failed.png")
                raise Exception(f"❌ 授权后未能在规定时间内返回 Dashboard: {e}")
            
            cookies = context.cookies()
            new_sid = next((c["value"] for c in cookies if c["name"] == "connect.sid" and "slimenodes" in c["domain"]), None)
            
            if new_sid:
                print("✅ 成功截获最新的 connect.sid！")
                with open("new_cookie.txt", "w") as f:
                    f.write(new_sid)
            else:
                raise Exception("❌ 登录成功，但未能在 Cookie 中找到 connect.sid！")

        print("🎉 自动化流程全部执行完毕！")
        browser.close()

if __name__ == "__main__":
    main()
