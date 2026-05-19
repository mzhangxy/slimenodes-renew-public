import time
import os
import json
import requests
from datetime import datetime, timedelta
from DrissionPage import ChromiumPage, ChromiumOptions

# ================= 配置区域 =================
PROXY = os.getenv("PROXY") or None
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
ACCOUNTS = os.getenv("BYTENUT", "")

URL_LOGIN_PANEL = "https://www.bytenut.com/auth/login"
URL_HOMEPAGE = "https://www.bytenut.com/homepage"
API_SERVER_LIST = "https://www.bytenut.com/game-panel/api/gpPanelServer/user/servers"
API_EXTENSION_INFO = "https://www.bytenut.com/game-panel/api/gp-free-server/extension-info/{}"
API_START_SERVER = "https://www.bytenut.com/game-panel/api/serverStartQueue/requestStart/{}"

def parse_accounts(raw: str):
    accounts = []
    for line in raw.strip().split('\n'):
        line = line.strip()
        if not line or '-----' not in line:
            continue
        parts = line.split('-----', 1)
        if len(parts) == 2:
            accounts.append((parts[0].strip(), parts[1].strip()))
    return accounts

class BytenutRenewal:
    def __init__(self):
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.screenshot_dir = os.path.join(self.BASE_DIR, "artifacts")
        os.makedirs(self.screenshot_dir, exist_ok=True)

        self.proxy_address = "127.0.0.1:10808"

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] [INFO] {msg}", flush=True)

    def mask_account(self, u):
        if "@" in u:
            local, domain = u.split("@", 1)
            return f"{local[:2]}***@{domain}"
        return f"{u[:2]}***"

    def mask_server_id(self, sid):
        return f"****{sid[-4:]}" if len(sid) > 4 else "****"

    def send_tg(self, icon, title, account, server_id, state, expiry, extra=""):
        if not TG_TOKEN or not TG_CHAT_ID: return
        msg = f"{icon} {title}\n\n账号: {account}\n服务器: {server_id}\n状态: {state}\n到期: {expiry}\n{extra}\n\nByteNut Auto (DP Edition)"
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                          json={"chat_id": TG_CHAT_ID, "text": msg}, timeout=10)
        except Exception as e: self.log(f"TG发送失败: {e}")

    def solve_turnstile(self, page):
        self.log("🛡️ 开始处理 Turnstile...")
        
        try:
            # --- 步骤 1: 检查是否已自动通过 ---
            try:
                resp_input = page.ele('css:[name="cf-turnstile-response"]')
                if resp_input and resp_input.value:
                    self.log("⚡ [自动通过] Token 已存在，无需点击！")
                    return True
            except:
                pass

            # --- 步骤 2: 锁定 Iframe ---
            self.log("🔍 寻找 Turnstile iframe...")
            target_iframe = page.get_frame('css:iframe[src^="https://challenges.cloudflare.com"]', timeout=8)
            
            if not target_iframe:
                self.log("⚠️ 尝试通过 ID 前缀查找...")
                target_iframe = page.get_frame('css:iframe[id^="cf-chl-widget-"]', timeout=5)

            if not target_iframe:
                self.log("❌ 彻底找不到 iframe")
                return False

            self.log("✅ 成功锁定 Iframe，准备穿透...")
            time.sleep(2) 

            # --- 步骤 3: 穿透 Closed Shadow Root ---
            click_success = False
            
            try:
                iframe_body = target_iframe.ele('tag:body')
                if not iframe_body:
                    raise Exception("无法获取 iframe body")

                sr = iframe_body.shadow_root
                
                if sr:
                    target_ele = sr.ele('css:input[type="checkbox"]')
                    if not target_ele:
                        target_ele = sr.ele('css:div.main-wrapper') or sr.ele('css:#content')
                    
                    if target_ele:
                        self.log("🖱️ 在 ShadowRoot 内部找到目标，执行物理点击...")
                        target_ele.click.at(offset_x=10, offset_y=10)
                        click_success = True
                    else:
                        self.log("⚠️ ShadowRoot 内部未找到明显元素")
                else:
                    self.log("⚠️ 未检测到 ShadowRoot")

            except Exception as e:
                self.log(f"⚠️ 穿透点击尝试失败: {e}")

            # --- 步骤 4: (保底方案) 坐标盲点 ---
            # 修复了原代码中跳过盲点的逻辑漏洞
            if not click_success:
                self.log("🏹 [保底方案] 执行 Iframe 坐标盲点...")
                try:
                    target_iframe.frame_ele.click.at(offset_x=25, offset_y=30)
                    click_success = True
                except Exception as e:
                    self.log(f"❌ 盲点失败: {e}")

            # --- 步骤 5: 验证结果 ---
            if click_success:
                self.log("⏳ 点击已执行，等待验证通过...")
                for i in range(20):
                    time.sleep(1)
                    resp = page.ele('css:[name="cf-turnstile-response"]')
                    
                    # 检查是否有值
                    if resp and resp.value:
                        self.log(f"🎉 验证成功！Token 已注入 (耗时 {i+1}s)")
                        return True
                    
                    # 检查 iframe 是否消失 (成功特征)
                    if not page.ele('css:iframe[src^="https://challenges.cloudflare.com"]'):
                         resp = page.ele('css:[name="cf-turnstile-response"]')
                         if resp and resp.value:
                             self.log("🎉 验证成功 (Iframe已消失)！")
                             return True
                
                self.log("⚠️ 等待超时，未获取到 Token")
                return False
            
            return False

        except Exception as e:
            self.log(f"🔥 Turnstile 处理异常: {e}")
            return False

    def call_api(self, page, url, method="GET"):
        js_code = f"""
        var url = '{url}';
        var method = '{method}';
        var token = localStorage.getItem('yl-token') || '';
        var options = {{
            method: method,
            headers: {{
                'Yl-Token': token,
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }},
            credentials: 'same-origin'
        }};
        if (method === 'POST') {{
            options.body = JSON.stringify({{}});
        }}
        return fetch(url, options).then(res => res.json()).catch(err => ({{code: 500, msg: err.toString()}}));
        """
        try:
            data = page.run_js(js_code)
            if data and data.get('code') != 200:
                self.log(f"⚠️ 服务端响应异常: {data}")
            return data.get('data') if data and data.get('code') == 200 else None
        except Exception as e:
            self.log(f"API请求本地异常: {e}")
            return None

    def format_expiry(self, dt_str):
        if not dt_str: return "Unknown"
        try:
            dt_str = dt_str.replace('Z', '').split('.')[0]
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=8)
            return dt.strftime("%Y-%m-%d %H:%M")
        except: return dt_str

    def run(self):
        self.log("🚀 ByteNut 续期启动 (DrissionPage)")
        accounts = parse_accounts(ACCOUNTS)
        
        co = ChromiumOptions()
        # 6. 代理配置
        if self.proxy_address:
            # 确保格式正确，防止 Chrome 解析错误
            proxy_str = f"socks5://{self.proxy_address}"
            self.log(f"🌐 配置代理参数: --proxy-server={proxy_str}")
            co.set_argument(f'--proxy-server={proxy_str}')

        if os.getenv("GITHUB_ACTIONS"):
            co.set_browser_path('/usr/bin/google-chrome')
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--disable-dev-shm-usage')
            co.set_argument('--window-size=1280,1024')
            co.set_argument('--ignore-certificate-errors')
            

        page = ChromiumPage(co)

        try:
            for idx, (user, pwd) in enumerate(accounts, 1):
                m_user = self.mask_account(user)
                self.log(f"==== 账号 [{idx}] {m_user} ====")
                
                page.get(URL_LOGIN_PANEL)
                page.ele('@placeholder=Username').input(user)
                page.ele('@placeholder=Password').input(pwd)
                page.ele('tag:button@@text():Sign In').click()
                
                time.sleep(5)
                if "login" in page.url:
                    self.log("❌ 登录失败")
                    continue

                page.get(URL_HOMEPAGE)
                servers = self.call_api(page, API_SERVER_LIST)
                if not servers: continue

                server = servers[0]
                sid = server.get('id')
                m_sid = self.mask_server_id(sid)
                state = server.get('serverInfo', {}).get('state', 'unknown')
                expiry = self.format_expiry(server.get('expiredTime'))

                ext_info = self.call_api(page, API_EXTENSION_INFO.format(sid))
                can_extend = ext_info.get('canExtend') if ext_info else False

                action_taken = False
                
                # 初始化状态文本，用于最终合并发报
                renewal_detail = "冷却中" if not can_extend else "待执行"
                boot_detail = "无需操作 (已在线)" if state != "offline" else "待执行"
                tg_icon = "⏳"
                tg_title = "当前无需操作"

                # ================= 1. 独立续期分支 =================
                if can_extend:
                    self.log("⏳ 处于可续期状态，准备进入详情页...")
                    page.get(f"https://www.bytenut.com/free-gamepanel/{sid}")
                    time.sleep(3)
                    page.ele('text:RENEW SERVER').click()
                    
                    if self.solve_turnstile(page):
                        self.log("⏳ 等待前端状态同步...")
                        time.sleep(3) # 【新增】给前端框架绑定 Token 的缓冲时间
                        
                        btn = page.ele('css:button.extend-btn', timeout=10)
                        if btn and not btn.attrs.get('disabled'):
                            btn.click()
                            self.log("🖱️ 续期点击完成")
                            time.sleep(5)
                            
                            watch_btn = page.ele('text:Watch Video to Claim', timeout=5)
                            if watch_btn: 
                                self.log("📺 触发广告续期，正在点击...")
                                watch_btn.click()
                                time.sleep(3)
                                
                                # 尝试关闭可能弹出的广告提示框
                                close_btn = page.ele('text:Close', timeout=3) or page.ele('text:关闭', timeout=3)
                                if close_btn:
                                    close_btn.click()
                                    time.sleep(2)
                                    
                        action_taken = True
                        renewal_detail = "✅ 成功执行"
                        
                        # 【新增】续期完成后强制刷新页面，清除可能残留的弹窗/遮罩，为开机做准备
                        self.log("🔄 刷新页面以清理DOM状态...")
                        page.refresh()
                        time.sleep(10)
                    else:
                        self.log("❌ 续期验证码处理失败")
                        renewal_detail = "❌ 验证码处理失败"
                        tg_icon = "⚠️"
                        tg_title = "执行出现异常"

                # ================= 2. 独立开机分支 =================
                if state == "offline":
                    self.log("⚡ 检测到服务器离线，准备进入详情页点击开机按钮...")
                    page.get(f"https://www.bytenut.com/free-gamepanel/{sid}")
                    time.sleep(5)
                    
                    start_btn = page.ele('css:button.start-btn', timeout=10)
                    
                    if start_btn and not start_btn.attrs.get('disabled'):
                        start_btn.click()
                        self.log("🖱️ 已点击 Start 开机按钮")
                        time.sleep(3)
                        
                        if self.solve_turnstile(page):
                            self.log("✅ 开机验证码处理通过")
                            boot_detail = "✅ 指令已发送"
                        else:
                            self.log("⚠️ 未检测到开机验证码，或无需验证")
                            boot_detail = "✅ 指令已发送 (无验证码)"
                            
                        self.log("⏳ 等待 15 秒让后端执行开机并刷新状态...")
                        time.sleep(15)
                        action_taken = True
                    else:
                        self.log("❌ 找不到 Start 按钮或按钮处于禁用状态")
                        boot_detail = "❌ 未找到有效按钮"
                        tg_icon = "⚠️"
                        tg_title = "执行出现异常"
                        
                elif action_taken:
                    self.log("⏳ 等待 8 秒让后端到期时间刷新...")
                    time.sleep(8)

                # ================= 3. 结果汇总与通知 =================
                new_state = state
                new_expiry = expiry

                if action_taken:
                    updated_servers = self.call_api(page, API_SERVER_LIST)
                    if updated_servers:
                        for s in updated_servers:
                            if s.get('id') == sid:
                                new_state = s.get('serverInfo', {}).get('state', state)
                                new_expiry = self.format_expiry(s.get('expiredTime'))
                                break
                    
                    if tg_icon != "⚠️":  # 如果过程没有报错，标记为成功
                        tg_icon = "✅"
                        tg_title = "任务执行完成"
                
                self.log(f"✅ 最新状态: {new_state}, 到期时间: {new_expiry}")
                
                # 合并两条详细信息
                extra_info = f"💡 续期操作: {renewal_detail}\n💡 开机操作: {boot_detail}"
                self.send_tg(tg_icon, tg_title, m_user, m_sid, new_state, new_expiry, extra_info)

        finally:
            page.quit()
            self.log("✅ 任务结束")

if __name__ == "__main__":
    BytenutRenewal().run()
