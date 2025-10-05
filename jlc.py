import sys
import time
import json
import tempfile
import random
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def enable_devtools_logging(driver):
    """启用 DevTools 性能日志记录"""
    driver.execute_cdp_cmd('Network.enable', {})
    driver.execute_cdp_cmd('Performance.enable', {})
    log("DevTools 网络监控已启用")

def extract_tokens_from_devtools(driver, target_url_pattern="m.jlc.com"):
    """使用 DevTools 协议从网络请求中提取 token"""
    access_token = None
    secretkey = None
    
    try:
        # 获取性能日志
        logs = driver.get_log('performance')
        
        for entry in logs:
            try:
                message = json.loads(entry['message'])
                message_type = message.get('message', {}).get('method', '')
                
                # 检查网络响应
                if message_type == 'Network.responseReceived':
                    response = message.get('message', {}).get('params', {}).get('response', {})
                    url = response.get('url', '')
                    
                    if target_url_pattern in url:
                        headers = response.get('requestHeaders', {})
                        access_token = headers.get('x-jlc-accesstoken') or headers.get('X-JLC-AccessToken')
                        secretkey = headers.get('secretkey') or headers.get('SecretKey')
                        
                        if access_token and secretkey:
                            log(f"从响应中提取到 token: URL={url}")
                            break
                
                # 检查网络请求
                elif message_type == 'Network.requestWillBeSent':
                    request = message.get('message', {}).get('params', {}).get('request', {})
                    url = request.get('url', '')
                    
                    if target_url_pattern in url:
                        headers = request.get('headers', {})
                        access_token = headers.get('x-jlc-accesstoken') or headers.get('X-JLC-AccessToken')
                        secretkey = headers.get('secretkey') or headers.get('SecretKey')
                        
                        if access_token and secretkey:
                            log(f"从请求中提取到 token: URL={url}")
                            break
                            
            except Exception as e:
                continue
                
    except Exception as e:
        log(f"DevTools 提取 token 出错: {e}")
    
    return access_token, secretkey

def extract_tokens_from_js(driver):
    """尝试从 JavaScript 变量中提取 token"""
    access_token = None
    secretkey = None
    
    try:
        # 尝试从 localStorage 获取
        access_token = driver.execute_script("return window.localStorage.getItem('x-jlc-accesstoken') || window.localStorage.getItem('accessToken') || window.sessionStorage.getItem('x-jlc-accesstoken');")
        secretkey = driver.execute_script("return window.localStorage.getItem('secretkey') || window.localStorage.getItem('secretKey') || window.sessionStorage.getItem('secretkey');")
        
        if access_token and secretkey:
            log("从 localStorage/sessionStorage 提取到 token")
            return access_token, secretkey
    except:
        pass
    
    try:
        # 尝试从 JavaScript 变量获取
        access_token = driver.execute_script("return window.x_jlc_accesstoken || window.accessToken || window.token;")
        secretkey = driver.execute_script("return window.secretkey || window.secretKey;")
        
        if access_token and secretkey:
            log("从 JavaScript 变量提取到 token")
            return access_token, secretkey
    except:
        pass
    
    return None, None

def sign_in_jindou(access_token, secretkey, account_index):
    """金豆签到函数"""
    log(f"账号 {account_index} - 开始执行金豆签到...")
    
    # 多个可能的签到接口
    sign_urls = [
        "https://m.jlc.com/api/appPlatform/center/sign/sign",
        "https://m.jlc.com/api/appPlatform/sign/sign",
        "https://m.jlc.com/api/center/sign/sign"
    ]
    
    headers = {
        "x-jlc-accesstoken": access_token,
        "secretkey": secretkey,
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "origin": "https://m.jlc.com",
        "referer": "https://m.jlc.com/"
    }

    for url in sign_urls:
        try:
            log(f"账号 {account_index} - 尝试签到接口: {url}")
            resp = requests.post(url, headers=headers, json={}, timeout=10)
            data = resp.json()
            
            if data.get("code") == 0:
                reward = data.get('data', {}).get('reward', '未知')
                log(f"账号 {account_index} - ✅ 金豆签到成功！获得奖励：{reward}")
                return True
            elif "重复" in str(data) or "已签到" in str(data):
                log(f"账号 {account_index} - ☑ 今日已签到金豆。")
                return True
            else:
                log(f"账号 {account_index} - ⚠ 金豆签到返回：{data}")
        except Exception as e:
            log(f"账号 {account_index} - ❌ 金豆签到失败 ({url}): {e}")
    
    return False

def navigate_and_interact_m_jlc(driver, account_index):
    """在 m.jlc.com 进行导航和交互以触发 token 请求"""
    log(f"账号 {account_index} - 在 m.jlc.com 进行交互操作...")
    
    try:
        # 等待页面加载
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # 滚动页面
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(2)
        
        # 尝试点击可能的导航元素
        nav_selectors = [
            "//div[contains(text(), '我的')]",
            "//div[contains(text(), '个人中心')]",
            "//div[contains(text(), '用户中心')]",
            "//a[contains(@href, 'user')]",
            "//a[contains(@href, 'center')]",
            "//div[@class='tabbar']//div[contains(text(), '我的')]",
            "//div[@class='footer']//div[contains(text(), '我的')]"
        ]
        
        for selector in nav_selectors:
            try:
                element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                element.click()
                log(f"账号 {account_index} - 点击导航元素: {selector}")
                time.sleep(3)
                break
            except:
                continue
        
        # 再次滚动
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)
        
        # 尝试刷新页面
        driver.refresh()
        time.sleep(5)
        
    except Exception as e:
        log(f"账号 {account_index} - 交互操作出错: {e}")

def sign_in_account(username, password, account_index, total_accounts):
    """为单个账号执行完整的签到流程"""
    log(f"开始处理账号 {account_index}/{total_accounts}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # 启用性能日志
    caps = DesiredCapabilities.CHROME
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}
    
    driver = webdriver.Chrome(options=chrome_options, desired_capabilities=caps)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    wait = WebDriverWait(driver, 25)
    account_success = False

    try:
        # 启用 DevTools 日志
        enable_devtools_logging(driver)

        # 1. 打开签到页
        driver.get("https://oshwhub.com/sign_in")
        log(f"账号 {account_index} - 已打开 JLC 签到页")
        
        # 延长等待时间
        time.sleep(12 + random.randint(2, 5))
        current_url = driver.current_url

        # 2. 登录流程
        if "passport.jlc.com/login" in current_url:
            log(f"账号 {account_index} - 检测到未登录状态，正在执行登录流程...")

            try:
                # 切换到账号登录
                phone_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"账号登录")]'))
                )
                phone_btn.click()
                log(f"账号 {account_index} - 已切换账号登录")
                time.sleep(3)
            except Exception as e:
                log(f"账号 {account_index} - 账号登录按钮可能已默认选中: {e}")

            # 输入账号密码
            try:
                user_input = wait.until(
                    EC.presence_of_element_located((By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]'))
                )
                user_input.clear()
                user_input.send_keys(username)

                pwd_input = wait.until(
                    EC.presence_of_element_located((By.XPATH, '//input[@type="password"]'))
                )
                pwd_input.clear()
                pwd_input.send_keys(password)
                log(f"账号 {account_index} - 已输入账号密码")
            except Exception as e:
                log(f"账号 {account_index} - ❌ 登录输入框未找到: {e}")
                return False

            # 点击登录
            try:
                login_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit"))
                )
                login_btn.click()
                log(f"账号 {account_index} - 已点击登录按钮")
            except Exception as e:
                log(f"账号 {account_index} - ❌ 登录按钮定位失败: {e}")
                return False

            # 处理滑块验证
            time.sleep(8)
            try:
                slider = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_slide"))
                )
                
                track = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".nc_scale"))
                )
                
                track_width = track.size['width']
                slider_width = slider.size['width']
                move_distance = track_width - slider_width - 10
                
                log(f"账号 {account_index} - 检测到滑块验证码，滑动距离: {move_distance}px")
                
                actions = ActionChains(driver)
                actions.click_and_hold(slider).perform()
                time.sleep(0.5)
                
                # 分段滑动
                quick_steps = int(move_distance * 0.7)
                for i in range(quick_steps):
                    if i % 10 == 0:
                        time.sleep(0.01)
                    actions.move_by_offset(1, 0).perform()
                
                time.sleep(0.2)
                
                slow_steps = move_distance - quick_steps
                for i in range(slow_steps):
                    if i % 3 == 0:
                        time.sleep(0.02)
                    y_offset = 1 if i % 2 == 0 else -1 if i % 5 == 0 else 0
                    actions.move_by_offset(1, y_offset).perform()
                
                actions.release().perform()
                log(f"账号 {account_index} - 滑块拖动完成")
                time.sleep(5)
                
            except Exception as e:
                log(f"账号 {account_index} - 滑块验证处理: {e}")

            # 等待跳转
            log(f"账号 {account_index} - 等待登录跳转...")
            for i in range(25):
                current_url = driver.current_url
                if "oshwhub.com" in current_url and "passport.jlc.com" not in current_url:
                    log(f"账号 {account_index} - 成功跳转回签到页面")
                    break
                time.sleep(2)
            else:
                log(f"账号 {account_index} - ⚠ 跳转超时，但继续执行")

        # 3. 开源平台签到
        log(f"账号 {account_index} - 等待签到页加载...")
        time.sleep(5)

        try:
            driver.refresh()
            time.sleep(4)
        except:
            pass

        # 执行开源平台签到
        try:
            sign_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
            )
            sign_btn.click()
            log(f"账号 {account_index} - ✅ 开源平台签到成功！")
            account_success = True
        except Exception as e:
            log(f"账号 {account_index} - ⚠ 开源平台签到按钮: {e}")
            try:
                signed_text = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
                log(f"账号 {account_index} - ✅ 今天已经在开源平台签到过了！")
                account_success = True
            except:
                log(f"账号 {account_index} - ❌ 开源平台签到失败")

        time.sleep(3)

        # 4. 金豆签到流程
        log(f"账号 {account_index} - 开始金豆签到流程...")
        
        # 跳转到 m.jlc.com
        driver.get("https://m.jlc.com/")
        log(f"账号 {account_index} - 已访问 m.jlc.com，等待页面加载...")
        
        # 延长等待时间
        time.sleep(15)
        
        # 进行交互操作以触发 token 请求
        navigate_and_interact_m_jlc(driver, account_index)
        
        # 多次尝试提取 token
        access_token, secretkey = None, None
        extraction_attempts = [
            ("DevTools 网络监控", extract_tokens_from_devtools),
            ("JavaScript 变量", extract_tokens_from_js),
            ("二次 DevTools 提取", lambda d: extract_tokens_from_devtools(d))
        ]
        
        for attempt_name, extract_func in extraction_attempts:
            if not access_token or not secretkey:
                log(f"账号 {account_index} - 尝试 {attempt_name} 提取 token...")
                access_token, secretkey = extract_func(driver)
                time.sleep(3)
        
        if access_token and secretkey:
            log(f"账号 {account_index} - ✅ 成功提取 token")
            log(f"  Token 前20位: {access_token[:20]}...")
            log(f"  SecretKey 前20位: {secretkey[:20]}...")
            
            # 执行金豆签到
            jindou_success = sign_in_jindou(access_token, secretkey, account_index)
            if jindou_success:
                account_success = account_success and True
        else:
            log(f"账号 {account_index} - ❌ 无法提取到 token，跳过金豆签到")
            
            # 保存页面源码和截图用于调试
            try:
                page_source = driver.page_source
                with open(f"debug_page_account_{account_index}.html", "w", encoding="utf-8") as f:
                    f.write(page_source)
                driver.save_screenshot(f"debug_screenshot_account_{account_index}.png")
                log(f"账号 {account_index} - 已保存调试信息")
            except:
                pass

    except Exception as e:
        log(f"账号 {account_index} - ❌ 程序执行错误: {e}")
        try:
            driver.save_screenshot(f"error_screenshot_account_{account_index}.png")
        except:
            pass

    finally:
        driver.quit()
        log(f"账号 {account_index} - 浏览器已关闭")
    
    return account_success

def main():
    if len(sys.argv) < 3:
        print("用法: python script.py 账号1,账号2,账号3... 密码1,密码2,密码3...")
        print("示例: python script.py user1,user2,user3 pwd1,pwd2,pwd3")
        sys.exit(1)
    
    usernames = [u.strip() for u in sys.argv[1].split(',') if u.strip()]
    passwords = [p.strip() for p in sys.argv[2].split(',') if p.strip()]
    
    if len(usernames) != len(passwords):
        log("❌ 错误: 账号和密码数量不匹配!")
        sys.exit(1)
    
    total_accounts = len(usernames)
    log(f"开始处理 {total_accounts} 个账号的签到任务")
    
    success_count = 0
    failed_accounts = []
    
    for i, (username, password) in enumerate(zip(usernames, passwords), 1):
        log(f"开始处理第 {i} 个账号")
        
        success = sign_in_account(username, password, i, total_accounts)
        
        if success:
            success_count += 1
            log(f"✅ 第 {i} 个账号签到成功")
        else:
            failed_accounts.append(i)
            log(f"❌ 第 {i} 个账号签到失败")
        
        if i < total_accounts:
            wait_time = random.randint(15, 40)
            log(f"等待 {wait_time} 秒后处理下一个账号...")
            time.sleep(wait_time)
    
    # 输出总结
    log("=" * 50)
    log("签到任务完成总结:")
    log(f"总账号数: {total_accounts}")
    log(f"成功数: {success_count}")
    log(f"失败数: {len(failed_accounts)}")
    
    if failed_accounts:
        log(f"失败的账号序号: {', '.join(map(str, failed_accounts))}")
    else:
        log("✅ 所有账号签到成功!")
    log("=" * 50)

if __name__ == "__main__":
    main()
