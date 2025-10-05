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

def extract_jlc_tokens_from_network(driver):
    """从 Network 日志中提取 Token"""
    access_token = None
    secretkey = None
    try:
        logs = driver.get_log("performance")
        for entry in logs:
            try:
                msg = json.loads(entry["message"])
                params = msg.get("message", {}).get("params", {})
                request = params.get("request", {})
                url = request.get("url", "")
                headers = request.get("headers", {})
                if "selectPcbOrderData" in url and "m.jlc.com" in url:
                    access_token = headers.get("x-jlc-accesstoken")
                    secretkey = headers.get("secretkey")
                    if access_token and secretkey:
                        break
            except:
                continue
    except Exception as e:
        log(f"⚠ 获取网络日志时出错: {e}")

    return access_token, secretkey

def sign_in_jindou(access_token, secretkey, account_index):
    """金豆签到函数"""
    log(f"账号 {account_index} - 开始执行金豆签到...")
    url = "https://m.jlc.com/api/appPlatform/center/sign/sign"
    headers = {
        "x-jlc-accesstoken": access_token,
        "secretkey": secretkey,
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }

    try:
        resp = requests.post(url, headers=headers, json={})
        data = resp.json()
        if data.get("code") == 0:
            log(f"账号 {account_index} - ✅ 金豆签到成功！获得奖励：{data.get('data', {}).get('reward', '未知')}")
        elif "重复" in str(data):
            log(f"账号 {account_index} - ☑ 今日已签到金豆。")
        else:
            log(f"账号 {account_index} - ⚠ 金豆签到返回：{data}")
    except Exception as e:
        log(f"账号 {account_index} - ❌ 金豆签到失败：{e}")

def sign_in_account(username, password, account_index, total_accounts):
    """为单个账号执行完整的签到流程（开源平台 + 金豆）"""
    log(f"开始处理账号 {account_index}/{total_accounts}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # 启用 performance 日志以抓包
    caps = DesiredCapabilities.CHROME
    caps["goog:loggingPrefs"] = {"performance": "ALL"}
    
    driver = webdriver.Chrome(options=chrome_options, desired_capabilities=caps)
    # 执行脚本来隐藏webdriver属性
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    wait = WebDriverWait(driver, 20)
    
    account_success = False
    oshwhub_success = False

    try:
        # 1. 打开签到页
        driver.get("https://oshwhub.com/sign_in")
        log(f"账号 {account_index} - 已打开 JLC 签到页，等待页面加载...")

        time.sleep(10 + random.randint(1, 5))  # 随机等待时间
        current_url = driver.current_url

        # 2. 如果自动跳转到了登录页
        if "passport.jlc.com/login" in current_url:
            log(f"账号 {account_index} - 检测到未登录状态，正在执行登录流程...")

            try:
                # 点击"账号登录"
                phone_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"账号登录")]'))
                )
                phone_btn.click()
                log(f"账号 {account_index} - 已切换账号登录。")
                time.sleep(2)
            except Exception as e:
                log(f"账号 {account_index} - 账号登录按钮可能已默认选中或未找到: {e}")

            # 输入账号
            try:
                user_input = wait.until(
                    EC.presence_of_element_located((By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]'))
                )
                user_input.clear()
                user_input.send_keys(username)
                log(f"账号 {account_index} - 已输入用户名。")

                pwd_input = wait.until(
                    EC.presence_of_element_located((By.XPATH, '//input[@type="password"]'))
                )
                pwd_input.clear()
                pwd_input.send_keys(password)
                log(f"账号 {account_index} - 已输入密码。")
            except Exception as e:
                log(f"账号 {account_index} - ❌ 登录输入框未找到: {e}")
                return False

            # 点击登录按钮
            try:
                login_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit"))
                )
                login_btn.click()
                log(f"账号 {account_index} - 已点击登录按钮。")
            except Exception as e:
                log(f"账号 {account_index} - ❌ 登录按钮定位失败: {e}")
                return False

            # 等待并处理滑块验证码
            time.sleep(5)
            try:
                # 使用更稳定的选择器来定位滑块
                slider = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_slide"))
                )
                
                # 获取滑块轨道
                track = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".nc_scale"))
                )
                
                # 获取轨道宽度
                track_width = track.size['width']
                slider_width = slider.size['width']
                move_distance = track_width - slider_width - 10  # 稍微减少一点距离确保不会过头
                
                log(f"账号 {account_index} - 检测到滑块验证码，滑动距离约 {move_distance}px。")
                
                # 创建动作链
                actions = ActionChains(driver)
                
                # 点击并按住滑块
                actions.click_and_hold(slider).perform()
                time.sleep(0.5)
                
                # 分段滑动，模拟人类行为
                # 先快速滑动大部分距离
                quick_steps = int(move_distance * 0.7)
                for i in range(quick_steps):
                    if i % 10 == 0:  # 每10步稍微停顿一下
                        time.sleep(0.01)
                    actions.move_by_offset(1, 0).perform()
                
                time.sleep(0.2)
                
                # 然后慢速滑动剩余距离
                slow_steps = move_distance - quick_steps
                for i in range(slow_steps):
                    if i % 3 == 0:  # 更频繁的微小停顿
                        time.sleep(0.02)
                    # 添加微小的垂直偏移模拟人类手抖
                    y_offset = 0
                    if i % 5 == 0:
                        y_offset = 1 if i % 2 == 0 else -1
                    actions.move_by_offset(1, y_offset).perform()
                
                # 释放滑块
                actions.release().perform()
                log(f"账号 {account_index} - 滑块拖动完成。")
                
                # 等待验证结果
                time.sleep(3)
                
                # 检查验证是否成功
                try:
                    success_element = driver.find_element(By.CSS_SELECTOR, ".scale_text")
                    if "验证通过" in success_element.text or "成功" in success_element.text:
                        log(f"账号 {account_index} - ✅ 滑块验证成功！")
                    else:
                        log(f"账号 {account_index} - 滑块验证状态: {success_element.text}")
                except:
                    log(f"账号 {account_index} - 无法获取验证结果文本。")
                    
            except Exception as e:
                log(f"账号 {account_index} - 未检测到滑块验证码或已验证成功/失败: {e}")

            # 登录后等待跳转回签到页
            log(f"账号 {account_index} - 等待登录跳转...")
            for i in range(20):
                current_url = driver.current_url
                if "oshwhub.com" in current_url and "passport.jlc.com" not in current_url:
                    log(f"账号 {account_index} - 成功跳转回签到页面。")
                    break
                log(f"账号 {account_index} - 等待跳转... ({i+1}/20) 当前URL: {current_url}")
                time.sleep(2)
            else:
                log(f"账号 {account_index} - ⚠ 跳转超时，但继续执行签到流程。")

        # 3. 等待签到页加载
        log(f"账号 {account_index} - 等待签到页加载...")
        time.sleep(3 + random.randint(1, 3))

        # 刷新页面确保在正确的页面
        try:
            driver.refresh()
            time.sleep(3)
        except:
            log(f"账号 {account_index} - 刷新页面失败，继续执行。")

        # 4. 点击"立即签到"（开源平台签到）
        try:
            sign_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
            )
            sign_btn.click()
            log(f"账号 {account_index} - ✅ 开源平台签到成功！")
            oshwhub_success = True
            account_success = True
        except Exception as e:
            log(f"账号 {account_index} - ⚠ 未找到开源平台签到按钮，可能已签到或页面结构变化: {e}")
            # 检查是否已经签到
            try:
                signed_text = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
                log(f"账号 {account_index} - ✅ 今天已经在开源平台签到过了！")
                oshwhub_success = True
                account_success = True
            except:
                log(f"账号 {account_index} - ❌ 开源平台签到失败，且未检测到已签到状态。")
                oshwhub_success = False

        time.sleep(2)

        # 5. 跳转到 m.jlc.com 进行金豆签到（无论开源平台签到是否成功都尝试）
        log(f"账号 {account_index} - 跳转到 m.jlc.com 进行金豆签到...")
        try:
            # 先访问 m.jlc.com 首页
            driver.get("https://m.jlc.com/")
            log(f"账号 {account_index} - 已访问 m.jlc.com，等待页面加载...")
            time.sleep(15)

            # 提取 token
            access_token, secretkey = extract_jlc_tokens_from_network(driver)
            if access_token and secretkey:
                log(f"账号 {account_index} - ✅ 成功提取 token")
                log(f"  x-jlc-accesstoken = {access_token[:20]}...")
                log(f"  secretkey = {secretkey[:20]}...")
                
                # 进行金豆签到
                sign_in_jindou(access_token, secretkey, account_index)
            else:
                log(f"账号 {account_index} - ⚠ 未能提取到 token，跳过金豆签到。")

        except Exception as e:
            log(f"账号 {account_index} - ❌ 金豆签到流程出错: {e}")

    except Exception as e:
        log(f"账号 {account_index} - ❌ 程序执行过程中发生错误: {e}")
        # 保存截图用于调试
        try:
            driver.save_screenshot(f"error_screenshot_account_{account_index}.png")
            log(f"账号 {account_index} - 已保存错误截图到 error_screenshot_account_{account_index}.png")
        except:
            log(f"账号 {account_index} - 无法保存截图")

    finally:
        driver.quit()
        log(f"账号 {account_index} - 浏览器已关闭。")
    
    return account_success

def main():
    if len(sys.argv) < 3:
        print("用法: python script.py 账号1,账号2,账号3... 密码1,密码2,密码3...")
        print("示例: python script.py user1,user2,user3 pwd1,pwd2,pwd3")
        sys.exit(1)
    
    # 解析账号和密码
    usernames = [u.strip() for u in sys.argv[1].split(',') if u.strip()]
    passwords = [p.strip() for p in sys.argv[2].split(',') if p.strip()]
    
    # 检查账号密码数量是否匹配
    if len(usernames) != len(passwords):
        log("❌ 错误: 账号和密码数量不匹配!")
        log(f"账号数量: {len(usernames)}, 密码数量: {len(passwords)}")
        log("请确保每个账号都有对应的密码，且用逗号分隔")
        sys.exit(1)
    
    # 检查是否有空账号或密码
    if not usernames or not passwords:
        log("❌ 错误: 账号或密码列表为空!")
        sys.exit(1)
    
    total_accounts = len(usernames)
    log(f"开始处理 {total_accounts} 个账号的签到任务")
    
    success_count = 0
    failed_accounts = []
    
    # 依次处理每个账号
    for i, (username, password) in enumerate(zip(usernames, passwords), 1):
        log(f"开始处理第 {i} 个账号")
        
        # 执行签到
        success = sign_in_account(username, password, i, total_accounts)
        
        if success:
            success_count += 1
            log(f"✅ 第 {i} 个账号签到成功")
        else:
            failed_accounts.append(i)
            log(f"❌ 第 {i} 个账号签到失败")
        
        # 如果不是最后一个账号，等待随机时间再处理下一个
        if i < total_accounts:
            wait_time = random.randint(10, 30)
            log(f"等待 {wait_time} 秒后处理下一个账号...")
            time.sleep(wait_time)
    
    # 输出总结报告
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
