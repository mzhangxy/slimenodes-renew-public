import os
import time
import re
import requests
from playwright.sync_api import sync_playwright, expect

# --- Telegram 通知函数 ---
def send_tg_message(msg):
    tg_token = os.environ.get("TG_BOT_TOKEN")
    tg_chat_id = os.environ.get("TG_CHAT_ID")
    if not tg_token or not tg_chat_id:
        print("▶ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过 Telegram 通知。")
        return
    try:
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        payload = {"chat_id": tg_chat_id, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ TG 通知发送发生异常: {e}")

def main():
    discord_token = os.environ.get("DISCORD_TOKEN")
    saved_cookie = os.environ.get("SLIMENODES_COOKIE")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="zh-TW")
        page = context.new_page()

        try:
            # 1. 全局拦截广告
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
                    page.goto("https://dash.slimenodes.com/dashboard", timeout=60000, wait_until="domcontentloaded")
                    page.locator('text="Your server"').wait_for(timeout=15000)
                    
                    if "dashboard" in page.url:
                        print("✅ Cookie 依然有效，成功跳过登录流程！")
                        page.screenshot(path="step1_cookie_success.png")
                        cookie_valid = True
                except Exception as e:
                    print(f"⚠️ Cookie 会话恢复失败或已过期: {e}")
                    page.screenshot(path="step1_cookie_failed.png")
                    print("▶ 准备退回使用 Discord Token 重新获取授权...")
                    context.clear_cookies()

            # 3. Cookie 失效时的后备方案：Discord Token 注入登录
            if not cookie_valid:
                if not discord_token:
                    raise Exception("❌ 未配置 DISCORD_TOKEN，无法完成登录！")

                print("▶ 开始通过 Discord Token 注入...")
                page.goto("https://discord.com/login", wait_until="domcontentloaded")
                
                page.evaluate(f'''() => {{
                    const iframe = document.createElement('iframe');
                    iframe.style.display = 'none';
                    document.body.appendChild(iframe);
                    
                    const intervalId = setInterval(() => {{
                        iframe.contentWindow.localStorage.setItem('token', '"{discord_token}"');
                    }}, 50);
                    
                    window._injectionInterval = intervalId;
                }}''')
                
                time.sleep(2.5) 
                page.reload(wait_until="domcontentloaded")
                
                try:
                    page.wait_for_selector('div[class*="app_"]', timeout=15000)
                    print("✅ Discord 账号状态注入成功。")
                    page.screenshot(path="step2_discord_injected.png")
                except Exception:
                    page.screenshot(path="step2_discord_injection_failed.png")
                    raise Exception("❌ Discord Token 注入后未能加载主界面，可能 Token 已失效或被风控。")

                # 4. 前往目标网站发起 OAuth 授权
                print("▶ 前往 SlimeNodes 面板点击登录...")
                page.goto("https://dash.slimenodes.com", wait_until="domcontentloaded")
                page.locator('a.button[href="/login"]').click()
                
                page.wait_for_url("**/oauth2/authorize**", timeout=30000)
                time.sleep(3) 
                
                # 5. 处理授权按钮
                for i in range(15):
                    page.evaluate('''() => {
                        document.querySelectorAll('*').forEach(e => {
                            if (e.scrollHeight > e.clientHeight) e.scrollTop = e.scrollHeight;
                        });
                    }''')
                    time.sleep(0.5)
                    
                    auth_btn = page.locator('button:not([disabled]), [role="button"]:not([disabled])').filter(
                        has_text=re.compile(r"授权|授權|Authorize", re.IGNORECASE)
                    )
                    
                    if auth_btn.count() > 0 and auth_btn.first.is_visible():
                        auth_btn.first.click()
                        print("✅ 成功点击授权按钮！")
                        time.sleep(2)
                        break
                else:
                    page.screenshot(path="step4_oauth_scroll_failed.png")
                    raise Exception("❌ 无法激活并点击授权按钮。")

            # 6. 提取最新的 Cookie
            print("▶ 等待面板回调与鉴权...")
            page.locator('text="Your server"').wait_for(timeout=30000)
            print("✅ 成功进入面板 Dashboard！")
            
            cookies = context.cookies()
            new_sid = next((c["value"] for c in cookies if c["name"] == "connect.sid" and "slimenodes" in c["domain"]), None)
            
            if new_sid:
                print("✅ 成功截获最新的 connect.sid！")
                with open("new_cookie.txt", "w") as f:
                    f.write(new_sid)
            else:
                raise Exception("❌ 登录成功，但未能在 Cookie 中找到 connect.sid！")

            # ==========================================
            # 7. [已修正] 核心业务：自动续期与成功断言
            # ==========================================
            print("▶ 开始执行服务器续期操作...")
            page.goto("https://dash.slimenodes.com/servers", wait_until="domcontentloaded")
            
            # 精准定位黄色的 Renew 按钮
            renew_btn = page.locator('a.btn-warning[href*="/renew"]')
            if renew_btn.count() > 0 and renew_btn.is_visible():
                page.screenshot(path="step7_servers_page.png")
                renew_btn.click()
                print("✅ 已点击 Renew 按钮，等待面板处理与跳转...")
            else:
                raise Exception("❌ 在页面上未找到黄色的 Renew 按钮！")

            # 验证跳转回 Dashboard 后的绿色横幅 (直接匹配面板自带的拼写错误)
            try:
                page.locator('text="Succesfully"').wait_for(timeout=20000)
                page.screenshot(path="step8_renew_result.png")
                
                success_msg = "🎉 <b>SlimeNodes 续期成功！</b>\n面板提示: <code>Succesfully purchased renewal for server!</code>"
                print(success_msg)
                send_tg_message(success_msg)
            except Exception as e:
                page.screenshot(path="step8_renew_failed.png")
                raise Exception(f"❌ 点击续期后未检测到成功提示横幅，可能续期失败: {e}")

            print("🎉 自动化流程全部圆满执行完毕！")

        except Exception as e:
            # 当发生任何报错时，捕获异常、截图死前现场、发通知，并强行阻断 Actions
            page.screenshot(path="error_fatal.png")
            error_msg = f"⚠️ <b>SlimeNodes 自动化执行失败</b>\n错误详情:\n<code>{str(e)}</code>"
            print(error_msg)
            send_tg_message(error_msg)
            raise e  

        finally:
            browser.close()

if __name__ == "__main__":
    main()
