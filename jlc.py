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

def extract_token_from_local_storage(driver):
    """直接从 localStorage 提取 X-JLC-AccessToken"""
    try:
        token = driver.execute_script("return window.localStorage.getItem('X-JLC-AccessToken');")
        if token:
            log(f"✅ 成功从 localStorage 提取 token: {token[:30]}...")
            return token
        else:
            log("❌ localStorage 中未找到 X-JLC-AccessToken")
            alternative_keys = [
                "x-jlc-accesstoken",
                "accessToken", 
                "token",
                "jlc-token"
            ]
            for key in alternative_keys:
                token = driver.execute_script(f"return window.localStorage.getItem('{key}');")
                if token:
                    log(f"✅ 从 localStorage 的 {key} 提取到 token: {token[:30]}...")
                    return token
    except Exception as e:
        log(f"❌ 从 localStorage 提取 token 失败: {e}")
    
    return None

def extract_secretkey_from_devtools(driver):
    """使用 DevTools 从网络请求中提取 secretkey"""
    secretkey = None
    
    try:
        logs = driver.get_log('performance')
        
        for entry in logs:
            try:
                message = json.loads(entry['message'])
                message_type = message.get('message', {}).get('method', '')
                
                if message_type == 'Network.requestWillBeSent':
                    request = message.get('message', {}).get('params', {}).get('request', {})
                    url = request.get('url', '')
                    
                    if 'm.jlc.com' in url:
                        headers = request.get('headers', {})
                        secretkey = (
                            headers.get('secretkey') or 
                            headers.get('SecretKey') or
                            headers.get('secretKey') or
                            headers.get('SECRETKEY')
                        )
                        
                        if secretkey:
                            log(f"✅ 从请求中提取到 secretkey: {secretkey[:20]}...")
                            break
                
                elif message_type == 'Network.responseReceived':
                    response = message.get('message', {}).get('params', {}).get('response', {})
                    url = response.get('url', '')
                    
                    if 'm.jlc.com' in url:
                        headers = response.get('requestHeaders', {})
                        secretkey = (
                            headers.get('secretkey') or 
                            headers.get('SecretKey') or
                            headers.get('secretKey') or
                            headers.get('SECRETKEY')
                        )
                        
                        if secretkey:
                            log(f"✅ 从响应中提取到 secretkey: {secretkey[:20]}...")
                            break
                            
            except:
                continue
                
    except Exception as e:
        log(f"❌ DevTools 提取 secretkey 出错: {e}")
    
    return secretkey

class JLCClient:
    """嘉立创 API 客户端"""
    
    def __init__(self, access_token, secretkey, account_index):
        self.base_url = "https://m.jlc.com"
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'x-jlc-clienttype': 'WEB',
            'accept': 'application/json, text/plain, */*',
            'x-jlc-accesstoken': access_token,
            'secretkey': secretkey,
            'Referer': 'https://m.jlc.com/mapp/pages/my/index',
        }
        self.account_index = account_index
        self.message = ""
        self.gain_num = 0  # 本次签到获得的金豆数量
        self.current_points = 0  # 当前金豆总数
        
    def send_request(self, url, method='GET'):
        """发送 API 请求"""
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, timeout=10)
            else:
                response = requests.post(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                log(f"账号 {self.account_index} - ❌ 请求失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            log(f"账号 {self.account_index} - ❌ 请求异常 ({url}): {e}")
            return None
    
    def get_user_info(self):
        """获取用户信息"""
        log(f"账号 {self.account_index} - 获取用户信息...")
        url = f"{self.base_url}/api/appPlatform/center/setting/selectPersonalInfo"
        data = self.send_request(url)
        
        if data and data.get('success'):
            log(f"账号 {self.account_index} - ✅ 获取用户信息成功")
            return True
        else:
            error_msg = data.get('message', '未知错误') if data else '请求失败'
            log(f"账号 {self.account_index} - ❌ 获取用户信息失败: {error_msg}")
            return False
    
    def check_sign_status(self):
        """检查签到状态"""
        log(f"账号 {self.account_index} - 检查签到状态...")
        url = f"{self.base_url}/api/activity/sign/getCurrentUserSignInConfig"
        data = self.send_request(url)
        
        if data and data.get('success'):
            have_sign_in = data.get('data', {}).get('haveSignIn', False)
            if have_sign_in:
                log(f"账号 {self.account_index} - ✅ 今日已签到")
                self.message += "今日已签到\n"
                return True  # 已签到
            else:
                log(f"账号 {self.account_index} - 今日未签到")
                return False  # 未签到
        else:
            error_msg = data.get('message', '未知错误') if data else '请求失败'
            log(f"账号 {self.account_index} - ❌ 检查签到状态失败: {error_msg}")
            return None  # 检查失败
    
    def sign_in(self):
        """执行签到"""
        log(f"账号 {self.account_index} - 执行签到...")
        url = f"{self.base_url}/api/activity/sign/signIn?source=4"
        data = self.send_request(url)
        
        if data and data.get('success'):
            gain_num = data.get('data', {}).get('gainNum')
            if gain_num:
                # 直接签到成功，获得金豆
                self.gain_num = gain_num
                log(f"账号 {self.account_index} - ✅ 签到成功，金豆+{gain_num}")
                self.message += f"签到成功，金豆+{gain_num}\n"
                return True
            else:
                # 有奖励可领取，先领取奖励
                log(f"账号 {self.account_index} - 有奖励可领取，先领取奖励")
                self.message += "有奖励可领取\n"
                
                # 领取奖励
                if self.receive_voucher():
                    # 领取成功后，等待一下再次签到
                    time.sleep(random.randint(1, 2))
                    log(f"账号 {self.account_index} - 奖励领取成功，重新执行签到")
                    return self.sign_in()  # 重新执行签到
                else:
                    return False
        else:
            error_msg = data.get('message', '未知错误') if data else '请求失败'
            log(f"账号 {self.account_index} - ❌ 签到失败: {error_msg}")
            return False
    
    def receive_voucher(self):
        """领取奖励"""
        log(f"账号 {self.account_index} - 领取奖励...")
        url = f"{self.base_url}/api/activity/sign/receiveVoucher"
        data = self.send_request(url)
        
        if data and data.get('success'):
            log(f"账号 {self.account_index} - ✅ 领取成功")
            self.message += "领取成功\n"
            return True
        else:
            error_msg = data.get('message', '未知错误') if data else '请求失败'
            log(f"账号 {self.account_index} - ❌ 领取奖励失败: {error_msg}")
            return False
    
    def get_points(self):
        """获取金豆数量"""
        log(f"账号 {self.account_index} - 获取金豆数量...")
        url = f"{self.base_url}/api/activity/front/getCustomerIntegral"
        data = self.send_request(url)
        
        if data and data.get('success'):
            self.current_points = data.get('data', {}).get('integralVoucher', 0)
            log(f"账号 {self.account_index} - 当前金豆: {self.current_points}")
            self.message += f"当前金豆: {self.current_points}\n\n"
            return self.current_points
        else:
            log(f"账号 {self.account_index} - ❌ 获取金豆数量失败")
            return 0
    
    def execute_full_process(self):
        """执行完整的金豆签到流程"""
        log(f"账号 {self.account_index} - 开始完整金豆签到流程")
        
        # 1. 获取用户信息
        if not self.get_user_info():
            return False
        
        time.sleep(random.randint(1, 2))
        
        # 2. 检查签到状态
        sign_status = self.check_sign_status()
        if sign_status is None:  # 检查失败
            return False
        elif sign_status:  # 已签到
            # 已签到，直接获取金豆数量
            pass
        else:  # 未签到
            # 3. 执行签到
            time.sleep(random.randint(2, 3))
            if not self.sign_in():
                return False
        
        time.sleep(random.randint(1, 2))
        
        # 4. 获取金豆数量
        self.get_points()
        
        return True

def navigate_and_interact_m_jlc(driver, account_index):
    """在 m.jlc.com 进行导航和交互以触发网络请求"""
    log(f"账号 {account_index} - 在 m.jlc.com 进行交互操作...")
    
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(2)
        
        nav_selectors = [
            "//div[contains(text(), '我的')]",
            "//div[contains(text(), '个人中心')]",
            "//div[contains(text(), '用户中心')]",
            "//a[contains(@href, 'user')]",
            "//a[contains(@href, 'center')]",
        ]
        
        for selector in nav_selectors:
            try:
                element = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, selector)))
                element.click()
                log(f"账号 {account_index} - 点击导航元素: {selector}")
                time.sleep(3)
                break
            except:
                continue
        
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)
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

    caps = DesiredCapabilities.CHROME
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}
    
    driver = webdriver.Chrome(options=chrome_options, desired_capabilities=caps)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    wait = WebDriverWait(driver, 25)
    account_success = False
    jlc_message = ""
    oshwhub_success = False
    jindou_success = False
    jindou_gain = 0
    current_points = 0

    try:
        # 开源平台签到流程
        driver.get("https://oshwhub.com/sign_in")
        log(f"账号 {account_index} - 已打开 JLC 签到页")
        
        time.sleep(12 + random.randint(2, 5))
        current_url = driver.current_url

        if "passport.jlc.com/login" in current_url:
            log(f"账号 {account_index} - 检测到未登录状态，正在执行登录流程...")
            user_input = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="请输入手机号"]')))
            user_input.send_keys(username)
            time.sleep(1 + random.random())
            
            pass_input = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="请输入密码"]')))
            pass_input.send_keys(password)
            time.sleep(1 + random.random())
            
            login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]')))
            login_btn.click()
            log(f"账号 {account_index} - 已提交登录表单")
            time.sleep(8 + random.randint(1, 3))
        
        # 开源平台签到
        try:
            sign_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]')))
            sign_btn.click()
            log(f"账号 {account_index} - ✅ 开源平台签到成功！")
            oshwhub_success = True
            account_success = True
        except Exception as e:
            log(f"账号 {account_index} - ⚠ 开源平台签到按钮: {e}")
            try:
                signed_text = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
                log(f"账号 {account_index} - ✅ 今天已经在开源平台签到过了！")
                oshwhub_success = True
                account_success = True
            except:
                log(f"账号 {account_index} - ❌ 开源平台签到失败")

        time.sleep(3)

        # 金豆签到流程
        log(f"账号 {account_index} - 开始金豆签到流程...")
        driver.get("https://m.jlc.com/")
        log(f"账号 {account_index} - 已访问 m.jlc.com，等待页面加载...")
        time.sleep(15)
        
        navigate_and_interact_m_jlc(driver, account_index)
        
        access_token = extract_token_from_local_storage(driver)
        secretkey = extract_secretkey_from_devtools(driver)
        
        if access_token and secretkey:
            log(f"账号 {account_index} - ✅ 成功提取 token 和 secretkey")
            
            jlc_client = JLCClient(access_token, secretkey, account_index)
            jindou_success = jlc_client.execute_full_process()
            jlc_message = jlc_client.message
            jindou_gain = jlc_client.gain_num
            current_points = jlc_client.current_points
            
            if jindou_success:
                account_success = account_success and True
                log(f"账号 {account_index} - ✅ 金豆签到流程完成")
            else:
                log(f"账号 {account_index} - ❌ 金豆签到流程失败")
        else:
            log(f"账号 {account_index} - ❌ 无法提取到 token 或 secretkey，跳过金豆签到")

    except Exception as e:
        log(f"账号 {account_index} - ❌ 程序执行错误: {e}")
    finally:
        driver.quit()
        log(f"账号 {account_index} - 浏览器已关闭")
    
    # 返回详细的签到结果
    return {
        "account_index": account_index,
        "success": account_success,
        "oshwhub_success": oshwhub_success,
        "jindou_success": jindou_success,
        "jindou_gain": jindou_gain,
        "current_points": current_points,
        "jlc_message": jlc_message
    }

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
    account_results = []  # 存储每个账号的详细结果
    
    for i, (username, password) in enumerate(zip(usernames, passwords), 1):
        log(f"开始处理第 {i} 个账号")
        result = sign_in_account(username, password, i, total_accounts)
        account_results.append(result)
        
        if result["success"]:
            success_count += 1
            log(f"✅ 第 {i} 个账号签到成功")
        else:
            failed_accounts.append(i)
            log(f"❌ 第 {i} 个账号签到失败")
        
        if i < total_accounts:
            wait_time = random.randint(15, 40)
            log(f"等待 {wait_time} 秒后处理下一个账号...")
            time.sleep(wait_time)
    
    # 详细结果总结
    log("\n" + "=" * 50)
    log("签到任务详细结果:")
    for result in account_results:
        log(f"\n账号 {result['account_index']} 结果:")
        log(f"开源平台签到: {'成功 ✅' if result['oshwhub_success'] else '失败 ❌'}")
        
        if result['jindou_success']:
            log(f"金豆签到: 成功 ✅")
            if result['jindou_gain'] > 0:
                log(f"本次获得金豆: +{result['jindou_gain']}")
            else:
                log(f"今日已签到，未获得新金豆")
            log(f"当前金豆总数: {result['current_points']}")
        else:
            log(f"金豆签到: 失败 ❌")
        
        if result['jlc_message']:
            log(f"金豆签到详情:\n{result['jlc_message']}")
    
    # 总体总结
    log("\n" + "=" * 50)
    log("签到任务完成总结:")
    log(f"总账号数: {total_accounts}")
    log(f"成功数: {success_count}")
    log(f"失败数: {len(failed_accounts)}")
    
    if failed_accounts:
        log(f"失败的账号序号: {', '.join(map(str, failed_accounts))}")
    else:
        log("✅ 所有账号签到成功!")
    
    # 金豆统计
    total_gain = sum(result['jindou_gain'] for result in account_results)
    total_points = sum(result['current_points'] for result in account_results)
    log(f"\n金豆统计:")
    log(f"本次签到获得金豆总数: {total_gain}")
    log(f"所有账号当前金豆总数: {total_points}")
    log("=" * 50)

if __name__ == "__main__":
    main()
