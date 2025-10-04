import sys
import time
import tempfile
import random
import requests
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def get_jlc_token_from_browser(driver):
    """从浏览器中获取JLC token和secretkey"""
    log("尝试获取JLC token...")
    
    try:
        # 方法1: 通过localStorage获取
        token = driver.execute_script("return window.localStorage.getItem('x-jlc-accesstoken');")
        secretkey = driver.execute_script("return window.localStorage.getItem('secretkey');")
        
        if token and secretkey:
            log(f"✅ 成功从localStorage获取token: {token[:20]}...")
            return f"{token}#{secretkey}"
        
        # 方法2: 通过sessionStorage获取
        token = driver.execute_script("return window.sessionStorage.getItem('x-jlc-accesstoken');")
        secretkey = driver.execute_script("return window.sessionStorage.getItem('secretkey');")
        
        if token and secretkey:
            log(f"✅ 成功从sessionStorage获取token: {token[:20]}...")
            return f"{token}#{secretkey}"
        
        # 方法3: 通过cookie获取
        cookies = driver.get_cookies()
        for cookie in cookies:
            if 'token' in cookie['name'].lower() or 'accesstoken' in cookie['name'].lower():
                log(f"✅ 从cookie获取token: {cookie['value'][:20]}...")
                return cookie['value']
                
    except Exception as e:
        log(f"❌ 获取token失败: {e}")
    
    return None

def jlc_bean_signin(token_secret, account_index, total_accounts):
    """使用token进行金豆签到"""
    log(f"账号 {account_index} - 开始金豆签到流程")
    
    try:
        # 解析token和secretkey
        if '#' in token_secret:
            token, secretkey = token_secret.split('#', 1)
        else:
            log(f"账号 {account_index} - ❌ token格式错误，应为token#secretkey格式")
            return False
        
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'x-jlc-clienttype': 'WEB',
            'accept': 'application/json, text/plain, */*',
            'x-jlc-accesstoken': token,
            'secretkey': secretkey,
            'Referer': 'https://m.jlc.com/mapp/pages/my/index',
        }
        
        base_url = 'https://m.jlc.com'
        
        # 1. 获取用户信息
        user_info_url = f"{base_url}/api/appPlatform/center/setting/selectPersonalInfo"
        response = requests.get(user_info_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            user_data = response.json()
            if user_data.get('success'):
                customer_code = user_data['data'].get('customerCode', '未知')
                log(f"账号 {account_index} - 用户: {customer_code}")
            else:
                log(f"账号 {account_index} - ⚠ 获取用户信息失败: {user_data.get('message')}")
        else:
            log(f"账号 {account_index} - ⚠ 获取用户信息HTTP错误: {response.status_code}")
        
        # 2. 检查签到状态
        check_sign_url = f"{base_url}/api/activity/sign/getCurrentUserSignInConfig"
        response = requests.get(check_sign_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            check_data = response.json()
            if check_data.get('success'):
                if check_data['data'].get('haveSignIn'):
                    log(f"账号 {account_index} - ✅ 今日已签到(金豆)")
                    return True
                else:
                    log(f"账号 {account_index} - 今日未签到，开始签到...")
            else:
                log(f"账号 {account_index} - ❌ 检查签到状态失败: {check_data.get('message')}")
                return False
        else:
            log(f"账号 {account_index} - ❌ 检查签到状态HTTP错误: {response.status_code}")
            return False
        
        time.sleep(2)
        
        # 3. 执行签到
        sign_url = f"{base_url}/api/activity/sign/signIn?source=4"
        response = requests.get(sign_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            sign_data = response.json()
            if sign_data.get('success'):
                if sign_data['data'].get('gainNum'):
                    bean_count = sign_data['data']['gainNum']
                    log(f"账号 {account_index} - ✅ 金豆签到成功，获得 {bean_count} 金豆")
                    
                    # 如果有奖励需要领取
                    if not sign_data['data'].get('gainNum'):
                        log(f"账号 {account_index} - 有奖励可领取，尝试领取...")
                        receive_url = f"{base_url}/api/activity/sign/receiveVoucher"
                        receive_response = requests.get(receive_url, headers=headers, timeout=30)
                        
                        if receive_response.status_code == 200:
                            receive_data = receive_response.json()
                            if receive_data.get('success'):
                                log(f"账号 {account_index} - ✅ 奖励领取成功")
                            else:
                                log(f"账号 {account_index} - ⚠ 奖励领取失败: {receive_data.get('message')}")
                else:
                    log(f"账号 {account_index} - ✅ 签到成功")
            else:
                log(f"账号 {account_index} - ❌ 签到失败: {sign_data.get('message')}")
                return False
        else:
            log(f"账号 {account_index} - ❌ 签到HTTP错误: {response.status_code}")
            return False
        
        time.sleep(2)
        
        # 4. 获取当前金豆数量
        points_url = f"{base_url}/api/activity/front/getCustomerIntegral"
        response = requests.get(points_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            points_data = response.json()
            if points_data.get('success'):
                bean_count = points_data['data'].get('integralVoucher', 0)
                log(f"账号 {account_index} - 当前金豆数量: {bean_count}")
            else:
                log(f"账号 {account_index} - ⚠ 获取金豆数量失败: {points_data.get('message')}")
        else:
            log(f"账号 {account_index} - ⚠ 获取金豆数量HTTP错误: {response.status_code}")
        
        return True
        
    except Exception as e:
        log(f"账号 {account_index} - ❌ 金豆签到过程中发生错误: {e}")
        return False

def sign_in_account(username, password, account_index, total_accounts, enable_bean_sign=True):
    """为单个账号执行签到流程"""
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

    driver = webdriver.Chrome(options=chrome_options)
    # 执行脚本来隐藏webdriver属性
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    wait = WebDriverWait(driver, 20)
    
    account_success = False
    bean_success = False
    jlc_token = None

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
                return False, False

            # 点击登录按钮
            try:
                login_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit"))
                )
                login_btn.click()
                log(f"账号 {account_index} - 已点击登录按钮。")
            except Exception as e:
                log(f"账号 {account_index} - ❌ 登录按钮定位失败: {e}")
                return False, False

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

        # 4. 点击"立即签到" - 积分签到
        try:
            sign_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
            )
            sign_btn.click()
            log(f"账号 {account_index} - ✅ 积分签到成功！")
            account_success = True
        except Exception as e:
            log(f"账号 {account_index} - ⚠ 未找到积分签到按钮，可能已签到或页面结构变化: {e}")
            # 检查是否已经签到
            try:
                signed_text = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
                log(f"账号 {account_index} - ✅ 今天已经签到过了(积分)！")
                account_success = True
            except:
                log(f"账号 {account_index} - ❌ 积分签到失败，且未检测到已签到状态。")
                account_success = False

        time.sleep(2)

        # 5. 获取token用于金豆签到
        if enable_bean_sign:
            log(f"账号 {account_index} - 尝试获取token进行金豆签到...")
            jlc_token = get_jlc_token_from_browser(driver)
            
            if jlc_token:
                log(f"账号 {account_index} - 成功获取token，进行金豆签到...")
                # 使用获取到的token进行金豆签到
                bean_success = jlc_bean_signin(jlc_token, account_index, total_accounts)
            else:
                log(f"账号 {account_index} - ⚠ 无法获取token，跳过金豆签到")
                bean_success = False

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
    
    return account_success, bean_success

def main():
    if len(sys.argv) < 3:
        print("用法: python script.py 账号1,账号2,账号3... 密码1,密码2,密码3...")
        print("示例: python script.py user1,user2,user3 pwd1,pwd2,pwd3")
        print("可选参数: --no-bean 禁用金豆签到")
        sys.exit(1)
    
    # 检查是否禁用金豆签到
    enable_bean_sign = "--no-bean" not in sys.argv
    
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
    if enable_bean_sign:
        log("✅ 金豆签到功能已启用")
    else:
        log("⚠ 金豆签到功能已禁用")
    
    success_count = 0
    bean_success_count = 0
    failed_accounts = []
    bean_failed_accounts = []
    
    # 依次处理每个账号
    for i, (username, password) in enumerate(zip(usernames, passwords), 1):
        log(f"开始处理第 {i} 个账号")
        
        # 执行签到
        success, bean_success = sign_in_account(username, password, i, total_accounts, enable_bean_sign)
        
        if success:
            success_count += 1
            log(f"✅ 第 {i} 个账号积分签到成功")
        else:
            failed_accounts.append(i)
            log(f"❌ 第 {i} 个账号积分签到失败")
            
        if bean_success:
            bean_success_count += 1
            log(f"✅ 第 {i} 个账号金豆签到成功")
        elif enable_bean_sign:
            bean_failed_accounts.append(i)
            log(f"❌ 第 {i} 个账号金豆签到失败")
        
        # 如果不是最后一个账号，等待随机时间再处理下一个
        if i < total_accounts:
            wait_time = random.randint(10, 30)
            log(f"等待 {wait_time} 秒后处理下一个账号...")
            time.sleep(wait_time)
    
    # 输出总结报告
    log("=" * 50)
    log("签到任务完成总结:")
    log(f"总账号数: {total_accounts}")
    log(f"积分签到成功数: {success_count}")
    log(f"积分签到失败数: {len(failed_accounts)}")
    if enable_bean_sign:
        log(f"金豆签到成功数: {bean_success_count}")
        log(f"金豆签到失败数: {len(bean_failed_accounts)}")
    
    if failed_accounts:
        log(f"积分签到失败的账号序号: {', '.join(map(str, failed_accounts))}")
    else:
        log("✅ 所有账号积分签到成功!")
        
    if enable_bean_sign and bean_failed_accounts:
        log(f"金豆签到失败的账号序号: {', '.join(map(str, bean_failed_accounts))}")
    elif enable_bean_sign:
        log("✅ 所有账号金豆签到成功!")
    log("=" * 50)

if __name__ == "__main__":
    main()
