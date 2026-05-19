import os
import time
from playwright.sync_api import sync_playwright, expect

def main():
    # 从环境变量获取凭证
    discord_token = os.environ.get("DISCORD_TOKEN")
    saved_cookie = os.environ.get("SLIMENODES_COOKIE")

    with sync_playwright() as p:
        # 在 GitHub Actions 中运行无头模式 (headless=True)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            # 设置语言，确保 Discord 弹出的按钮文字符合预期
            locale="zh-TW" 
        )
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
            
            page.goto("https://dash.slimenodes.com/dashboard")
            page.wait_for_load_state("networkidle")
            
            # 检查是否成功进入仪表盘 (检测 URL 和特征元素)
            if "dashboard" in page.url and page.locator('text="Your server"').is_visible():
                print("✅ Cookie 依然有效，成功跳过登录流程！")
                cookie_valid = True
            else:
                print("⚠️ Cookie 已过期或失效，准备执行 Discord Token 登录...")
                context.clear_cookies() # 清除失效的 Cookie

        # 3. Cookie 失效时的后备方案：Discord Token 注入登录
        if not cookie_valid:
            if not discord_token:
                raise Exception("❌ 未配置 DISCORD_TOKEN，无法完成登录！")

            print("▶ 开始通过 Discord Token 注入...")
            page.goto("https://discord.com/login")
            
            # 将 Token 注入浏览器的 LocalStorage
            page.evaluate(f'''() => {{
                window.localStorage.setItem('token', '"{discord_token}"');
            }}''')
            page.reload()
            
            # 等待 Discord 主界面加载，确认登录成功
            page.wait_for_selector('div[class*="app_"]', timeout=15000)
            print("✅ Discord 账号状态注入成功。")

            # 4. 前往目标网站发起 OAuth 授权
            print("▶ 前往 SlimeNodes 面板点击登录...")
            page.goto("https://dash.slimenodes.com")
            
            # 点击登录按钮
            page.locator('a.button[href="/login"]').click()
            
            # 等待跳转到 Discord 授权页
            page.wait_for_url("**/oauth2/authorize**")
            print("▶ 成功进入 Discord 授权页面。")
            
            # 5. 核心难点：处理必须滚动到底部才能点击的授权按钮
            time.sleep(2) # 给 React 渲染留一点时间
            
            # 循环注入 JS：将页面内所有有滚动条的元素强制滚动到底部
            max_attempts = 15
            for _ in range(max_attempts):
                page.evaluate('''() => {
                    document.querySelectorAll('*').forEach(e => {
                        if (e.scrollHeight > e.clientHeight) {
                            e.scrollTop = e.scrollHeight;
                        }
                    });
                }''')
                time.sleep(0.5)
                
                # 定位蓝色的授权按钮 (它不再被 disabled，且文字变为 授权/Authorize)
                # 兼容中文和英文环境
                auth_btn = page.locator('button[type="button"]:not([disabled])', has_text="授权")
                if auth_btn.count() == 0:
                    auth_btn = page.locator('button[type="button"]:not([disabled])', has_text="Authorize")
                
                if auth_btn.count() > 0 and auth_btn.is_visible():
                    auth_btn.click()
                    print("✅ 成功点击授权按钮！")
                    break
            else:
                raise Exception("❌ 无法激活授权按钮，可能 UI 已更改或滚动未生效。")

            # 6. 提取最新的 Cookie
            print("▶ 等待面板回调与鉴权...")
            page.wait_for_url("**/dashboard**", timeout=20000)
            page.wait_for_load_state("networkidle")
            
            cookies = context.cookies()
            new_sid = next((c["value"] for c in cookies if c["name"] == "connect.sid" and "slimenodes" in c["domain"]), None)
            
            if new_sid:
                print("✅ 成功截获最新的 connect.sid！")
                # 写入一个临时文件，让 Github Actions 读取它
                with open("new_cookie.txt", "w") as f:
                    f.write(new_sid)
            else:
                raise Exception("❌ 登录成功，但未能在 Cookie 中找到 connect.sid！")

        # ----------------------------------------------------
        # 这里可以继续编写你的后续操作，比如点击续期按钮等逻辑
        print("🎉 自动化流程全部执行完毕！")
        # ----------------------------------------------------

        browser.close()

if __name__ == "__main__":
    main()
