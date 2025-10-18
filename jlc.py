import sys
import time
import json
import tempfile
import random
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def format_nickname(nickname):
    """格式化昵称，只显示第一个字和最后一个字，中间用星号代替"""
    if not nickname or len(nickname.strip()) == 0:
        return "未知用户"
    
    nickname = nickname.strip()
    if len(nickname) == 1:
        return f"{nickname}*"
    elif len(nickname) == 2:
        return f"{nickname[0]}*"
    else:
        return f"{nickname[0]}{'*' * (len(nickname)-2)}{nickname[-1]}"

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

def get_oshwhub_points(driver, account_index):
    """获取开源平台积分数量"""
    try:
        # 获取当前页面的Cookie
        cookies = driver.get_cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'accept': 'application/json, text/plain, */*',
            'cookie': cookie_str
        }
        
        # 调用用户信息API获取积分
        response = requests.get("https://oshwhub.com/api/users", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and data.get('success'):
                points = data.get('result', {}).get('points', 0)
                log(f"账号 {account_index} - 📊 当前积分: {points}")
                return points
        
        log(f"账号 {account_index} - ⚠ 无法获取积分信息")
        return 0
    except Exception as e:
        log(f"账号 {account_index} - ⚠ 获取积分失败: {e}")
        return 0

class JLCClient:
    """调用嘉立创接口"""
    
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
        self.initial_jindou = 0  # 签到前金豆数量
        self.final_jindou = 0    # 签到后金豆数量
        self.jindou_reward = 0   # 本次获得金豆（通过差值计算）
        self.sign_status = "未知"  # 签到状态
        self.has_reward = False  # 是否领取了额外奖励
        
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
            log(f"账号 {self.account_index} - ✅ 用户信息获取成功")
            return True
        else:
            error_msg = data.get('message', '未知错误') if data else '请求失败'
            log(f"账号 {self.account_index} - ❌ 获取用户信息失败: {error_msg}")
            return False
    
    def get_points(self):
        """获取金豆数量"""
        log(f"账号 {self.account_index} - 获取金豆数量...")
        url = f"{self.base_url}/api/activity/front/getCustomerIntegral"
        data = self.send_request(url)
        
        if data and data.get('success'):
            jindou_count = data.get('data', {}).get('integralVoucher', 0)
            log(f"账号 {self.account_index} - 当前金豆: {jindou_count}")
            return jindou_count
        else:
            log(f"账号 {self.account_index} - ❌ 获取金豆数量失败")
            return 0
    
    def check_sign_status(self):
        """检查签到状态"""
        log(f"账号 {self.account_index} - 检查签到状态...")
        url = f"{self.base_url}/api/activity/sign/getCurrentUserSignInConfig"
        data = self.send_request(url)
        
        if data and data.get('success'):
            have_sign_in = data.get('data', {}).get('haveSignIn', False)
            if have_sign_in:
                log(f"账号 {self.account_index} - ✅ 今日已签到")
                self.sign_status = "已签到过"
                return True
            else:
                log(f"账号 {self.account_index} - 今日未签到")
                self.sign_status = "未签到"
                return False
        else:
            error_msg = data.get('message', '未知错误') if data else '请求失败'
            log(f"账号 {self.account_index} - ❌ 检查签到状态失败: {error_msg}")
            self.sign_status = "检查失败"
            return None
    
    def sign_in(self):
        """执行签到"""
        log(f"账号 {self.account_index} - 执行签到...")
        url = f"{self.base_url}/api/activity/sign/signIn?source=4"
        data = self.send_request(url)
        
        if data and data.get('success'):
            gain_num = data.get('data', {}).get('gainNum')
            if gain_num:
                # 直接签到成功，获得金豆
                log(f"账号 {self.account_index} - ✅ 签到成功，签到使金豆+{gain_num}")
                self.sign_status = "签到成功"
                return True
            else:
                # 有奖励可领取，先领取奖励
                log(f"账号 {self.account_index} - 有奖励可领取，先领取奖励")
                self.has_reward = True
                
                # 领取奖励
                if self.receive_voucher():
                    # 领取奖励成功后，直接视为签到完成，不再重新签到
                    log(f"账号 {self.account_index} - ✅ 奖励领取成功，签到完成")
                    self.sign_status = "领取奖励成功"
                    return True
                else:
                    self.sign_status = "领取奖励失败"
                    return False
        else:
            error_msg = data.get('message', '未知错误') if data else '请求失败'
            log(f"账号 {self.account_index} - ❌ 签到失败: {error_msg}")
            self.sign_status = "签到失败"
            return False
    
    def receive_voucher(self):
        """领取奖励"""
        log(f"账号 {self.account_index} - 领取奖励...")
        url = f"{self.base_url}/api/activity/sign/receiveVoucher"
        data = self.send_request(url)
        
        if data and data.get('success'):
            log(f"账号 {self.account_index} - ✅ 领取成功")
            return True
        else:
            error_msg = data.get('message', '未知错误') if data else '请求失败'
            log(f"账号 {self.account_index} - ❌ 领取奖励失败: {error_msg}")
            return False
    
    def calculate_jindou_difference(self):
        """计算金豆差值"""
        self.jindou_reward = self.final_jindou - self.initial_jindou
        if self.jindou_reward > 0:
            reward_text = f" (+{self.jindou_reward})"
            if self.has_reward:
                reward_text += "（有奖励）"
            log(f"账号 {self.account_index} - 🎉 总金豆增加: {self.initial_jindou} → {self.final_jindou}{reward_text}")
        elif self.jindou_reward == 0:
            log(f"账号 {self.account_index} - ⚠ 总金豆无变化，可能今天已签到过: {self.initial_jindou} → {self.final_jindou} (0)")
        else:
            log(f"账号 {self.account_index} - ❗ 金豆减少: {self.initial_jindou} → {self.final_jindou} ({self.jindou_reward})")
        
        return self.jindou_reward
    
    def execute_full_process(self):
        """执行完整的金豆签到流程"""
        log(f"账号 {self.account_index} - 开始完整金豆签到流程")
        
        # 1. 获取用户信息
        if not self.get_user_info():
            return False
        
        time.sleep(random.randint(1, 2))
        
        # 2. 获取签到前金豆数量
        log(f"账号 {self.account_index} - 获取签到前金豆数量...")
        self.initial_jindou = self.get_points()
        log(f"账号 {self.account_index} - 签到前金豆: {self.initial_jindou}")
        
        time.sleep(random.randint(1, 2))
        
        # 3. 检查签到状态
        sign_status = self.check_sign_status()
        if sign_status is None:  # 检查失败
            return False
        elif sign_status:  # 已签到
            # 已签到，直接获取金豆数量
            log(f"账号 {self.account_index} - 今日已签到，跳过签到操作")
        else:  # 未签到
            # 4. 执行签到
            time.sleep(random.randint(2, 3))
            if not self.sign_in():
                return False
        
        time.sleep(random.randint(1, 2))
        
        # 5. 获取签到后金豆数量
        log(f"账号 {self.account_index} - 获取签到后金豆数量...")
        self.final_jindou = self.get_points()
        log(f"账号 {self.account_index} - 签到后金豆: {self.final_jindou}")
        
        # 6. 计算金豆差值
        self.calculate_jindou_difference()
        
        return True

def navigate_and_interact_m_jlc(driver, account_index):
    """在 m.jlc.com 进行导航和交互以触发网络请求"""
    log(f"账号 {account_index} - 在 m.jlc.com 进行交互操作...")
    
    try:
        WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
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
                time.sleep(2)
                break
            except:
                continue
        
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)
        driver.refresh()
        time.sleep(5)
        
    except Exception as e:
        log(f"账号 {account_index} - 交互操作出错: {e}")

def is_sunday():
    """检查今天是否是周日"""
    return datetime.now().weekday() == 6

def is_last_day_of_month():
    """检查今天是否是当月最后一天"""
    today = datetime.now()
    next_month = today.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    return today.day == last_day.day

def capture_reward_info(driver, account_index, gift_type):
    """抓取并输出奖励信息，返回礼包领取结果"""
    try:
        reward_elem = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, '//p[contains(text(), "恭喜获取")]'))
        )
        reward_text = reward_elem.text.strip()
        gift_name = "七日礼包" if gift_type == "7天" else "月度礼包"
        log(f"账号 {account_index} - {gift_name}领取结果：{reward_text}")
        return f"开源平台{gift_name}领取结果: {reward_text}"
    except Exception as e:
        log(f"账号 {account_index} - 已点击{gift_type}好礼，未获取到奖励信息(可能已领取过或未达到领取条件)，请自行前往开源平台查看。")
        return None

def click_gift_buttons(driver, account_index):
    """根据日期条件点击7天好礼和月度好礼按钮，并抓取奖励信息，返回所有领取结果"""
    reward_results = []
    
    if not is_sunday() and not is_last_day_of_month():
        return reward_results

    try:
        # 等待一秒
        time.sleep(1)
        
        log(f"账号 {account_index} - 开始点击礼包按钮...")
        
        sunday = is_sunday()
        last_day = is_last_day_of_month()

        if sunday:
            # 尝试点击7天好礼
            try:
                seven_day_gift = driver.find_element(By.XPATH, '//div[contains(@class, "sign_text__r9zaN")]/span[text()="7天好礼"]')
                seven_day_gift.click()
                log(f"账号 {account_index} - ✅ 检测到今天是周日，成功点击7天好礼，祝你周末愉快~")
                
                # 等待1秒并抓取奖励信息
                time.sleep(1)
                reward_result = capture_reward_info(driver, account_index, "7天")
                if reward_result:
                    reward_results.append(reward_result)
                
                # 如果也是月底，刷新页面
                if last_day:
                    driver.refresh()
                    time.sleep(5)
                
            except Exception as e:
                log(f"账号 {account_index} - ⚠ 无法点击7天好礼: {e}")

        if last_day:
            # 尝试点击月度好礼
            try:
                monthly_gift = driver.find_element(By.XPATH, '//div[contains(@class, "sign_text__r9zaN")]/span[text()="月度好礼"]')
                monthly_gift.click()
                log(f"账号 {account_index} - ✅ 检测到今天是月底，成功点击月度好礼")          
                
                # 等待1秒并抓取奖励信息
                time.sleep(1)
                reward_result = capture_reward_info(driver, account_index, "月度")
                if reward_result:
                    reward_results.append(reward_result)
                
            except Exception as e:
                log(f"账号 {account_index} - ⚠ 无法点击月度好礼: {e}")
            
    except Exception as e:
        log(f"账号 {account_index} - ❌ 点击礼包按钮时出错: {e}")

    return reward_results

def get_user_nickname_from_api(driver, account_index):
    """通过API获取用户昵称"""
    try:
        # 获取当前页面的Cookie
        cookies = driver.get_cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'accept': 'application/json, text/plain, */*',
            'cookie': cookie_str
        }
        
        # 调用用户信息API
        response = requests.get("https://oshwhub.com/api/users", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and data.get('success'):
                nickname = data.get('result', {}).get('nickname', '')
                if nickname:
                    formatted_nickname = format_nickname(nickname)
                    log(f"账号 {account_index} - 👤 昵称: {formatted_nickname}")
                    return formatted_nickname
        
        log(f"账号 {account_index} - ⚠ 无法获取用户昵称")
        return None
    except Exception as e:
        log(f"账号 {account_index} - ⚠ 获取用户昵称失败: {e}")
        return None

def ensure_login_page(driver, account_index):
    """确保进入登录页面，如果未检测到登录页面则重启浏览器"""
    max_restarts = 5
    restarts = 0
    
    while restarts < max_restarts:
        try:
            driver.get("https://oshwhub.com/sign_in")
            log(f"账号 {account_index} - 已打开 JLC 签到页")
            
            time.sleep(5 + random.randint(2, 3))
            current_url = driver.current_url

            # 检查是否在登录页面
            if "passport.jlc.com/login" in current_url:
                log(f"账号 {account_index} - ✅ 检测到未登录状态")
                return True
            else:
                restarts += 1
                if restarts < max_restarts:
                    # 静默重启浏览器
                    driver.quit()
                    
                    # 重新初始化浏览器
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
                    
                    # 静默等待后继续循环
                    time.sleep(2)
                else:
                    log(f"账号 {account_index} - ❌ 重启浏览器{max_restarts}次后仍无法进入登录页面")
                    return False
                    
        except Exception as e:
            restarts += 1
            if restarts < max_restarts:
                try:
                    driver.quit()
                except:
                    pass
                
                # 重新初始化浏览器
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
                
                time.sleep(2)
            else:
                log(f"账号 {account_index} - ❌ 重启浏览器{max_restarts}次后仍出现异常: {e}")
                return False
    
    return False

def sign_in_account(username, password, account_index, total_accounts, retry_count=0):
    """为单个账号执行完整的签到流程（包含重试机制）"""
    log(f"开始处理账号 {account_index}/{total_accounts}" + (f" (重试)" if retry_count > 0 else ""))
    
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
    
    # 记录详细结果
    result = {
        'account_index': account_index,
        'nickname': '未知',
        'oshwhub_status': '未知',
        'oshwhub_success': False,
        'initial_points': 0,      # 签到前积分
        'final_points': 0,        # 签到后积分
        'points_reward': 0,       # 本次获得积分
        'reward_results': [],     # 礼包领取结果
        'jindou_status': '未知',
        'jindou_success': False,
        'initial_jindou': 0,
        'final_jindou': 0,
        'jindou_reward': 0,
        'has_jindou_reward': False,  # 金豆是否有额外奖励
        'token_extracted': False,
        'secretkey_extracted': False,
        'retry_count': retry_count
    }

    try:
        # 1. 确保进入登录页面
        if not ensure_login_page(driver, account_index):
            result['oshwhub_status'] = '无法进入登录页'
            return result

        current_url = driver.current_url

        # 2. 登录流程
        log(f"账号 {account_index} - 检测到未登录状态，正在执行登录流程...")

        try:
            phone_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"账号登录")]'))
            )
            phone_btn.click()
            log(f"账号 {account_index} - 已切换账号登录")
            time.sleep(2)
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
            result['oshwhub_status'] = '登录失败'
            return result

        # 点击登录
        try:
            login_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit"))
            )
            login_btn.click()
            log(f"账号 {account_index} - 已点击登录按钮")
        except Exception as e:
            log(f"账号 {account_index} - ❌ 登录按钮定位失败: {e}")
            result['oshwhub_status'] = '登录失败'
            return result

        # 处理滑块验证
        time.sleep(5)
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
        max_wait = 25
        for i in range(max_wait):
            current_url = driver.current_url
            
            # 检查是否成功跳转回签到页面
            if "oshwhub.com" in current_url and "passport.jlc.com" not in current_url:
                log(f"账号 {account_index} - 成功跳转回签到页面")
                break
            
            time.sleep(2)
        else:
            log(f"账号 {account_index} - ⚠ 跳转超时，但继续执行")

        # 3. 获取用户昵称
        nickname = get_user_nickname_from_api(driver, account_index)
        if nickname:
            result['nickname'] = nickname

        # 4. 获取签到前积分数量
        log(f"账号 {account_index} - 获取签到前积分数量...")
        result['initial_points'] = get_oshwhub_points(driver, account_index)
        log(f"账号 {account_index} - 签到前积分: {result['initial_points']}")

        # 5. 开源平台签到
        log(f"账号 {account_index} - 等待签到页加载...")
        time.sleep(5)

        try:
            driver.refresh()
            time.sleep(4)
        except:
            pass

        # 执行开源平台签到
        try:
            # 先检查是否已经签到
            try:
                signed_element = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
                log(f"账号 {account_index} - ✅ 今天已经在开源平台签到过了！")
                result['oshwhub_status'] = '已签到过'
                result['oshwhub_success'] = True
                
                # 即使已签到，也尝试点击礼包按钮
                result['reward_results'] = click_gift_buttons(driver, account_index)
                
            except:
                # 如果没有找到"已签到"元素，则尝试点击"立即签到"按钮
                try:
                    sign_btn = wait.until(
                        EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
                    )
                    sign_btn.click()
                    log(f"账号 {account_index} - ✅ 开源平台签到成功！")
                    result['oshwhub_status'] = '签到成功'
                    result['oshwhub_success'] = True
                    
                    # 等待签到完成
                    time.sleep(2)
                    
                    # 6. 签到完成后点击7天好礼和月度好礼
                    result['reward_results'] = click_gift_buttons(driver, account_index)
                    
                except Exception as e:
                    log(f"账号 {account_index} - ❌ 开源平台签到失败，未找到签到按钮: {e}")
                    result['oshwhub_status'] = '签到失败'
                    
        except Exception as e:
            log(f"账号 {account_index} - ❌ 开源平台签到异常: {e}")
            result['oshwhub_status'] = '签到异常'

        time.sleep(3)

        # 7. 获取签到后积分数量
        log(f"账号 {account_index} - 获取签到后积分数量...")
        result['final_points'] = get_oshwhub_points(driver, account_index)
        log(f"账号 {account_index} - 签到后积分: {result['final_points']}")

        # 8. 计算积分差值
        result['points_reward'] = result['final_points'] - result['initial_points']
        if result['points_reward'] > 0:
            log(f"账号 {account_index} - 🎉 总积分增加: {result['initial_points']} → {result['final_points']} (+{result['points_reward']})")
        elif result['points_reward'] == 0:
            log(f"账号 {account_index} - ⚠ 总积分无变化，可能今天已签到过: {result['initial_points']} → {result['final_points']} (0)")
        else:
            log(f"账号 {account_index} - ❗ 积分减少: {result['initial_points']} → {result['final_points']} ({result['points_reward']})")

        # 9. 金豆签到流程
        log(f"账号 {account_index} - 开始金豆签到流程...")
        driver.get("https://m.jlc.com/")
        log(f"账号 {account_index} - 已访问 m.jlc.com，等待页面加载...")
        time.sleep(10)
        
        navigate_and_interact_m_jlc(driver, account_index)
        
        access_token = extract_token_from_local_storage(driver)
        secretkey = extract_secretkey_from_devtools(driver)
        
        result['token_extracted'] = bool(access_token)
        result['secretkey_extracted'] = bool(secretkey)
        
        if access_token and secretkey:
            log(f"账号 {account_index} - ✅ 成功提取 token 和 secretkey")
            
            jlc_client = JLCClient(access_token, secretkey, account_index)
            jindou_success = jlc_client.execute_full_process()
            
            # 记录金豆签到结果
            result['jindou_success'] = jindou_success
            result['jindou_status'] = jlc_client.sign_status
            result['initial_jindou'] = jlc_client.initial_jindou
            result['final_jindou'] = jlc_client.final_jindou
            result['jindou_reward'] = jlc_client.jindou_reward
            result['has_jindou_reward'] = jlc_client.has_reward
            
            if jindou_success:
                log(f"账号 {account_index} - ✅ 金豆签到流程完成")
            else:
                log(f"账号 {account_index} - ❌ 金豆签到流程失败")
        else:
            log(f"账号 {account_index} - ❌ 无法提取到 token 或 secretkey，跳过金豆签到")
            result['jindou_status'] = 'Token提取失败'

    except Exception as e:
        log(f"账号 {account_index} - ❌ 程序执行错误: {e}")
        result['oshwhub_status'] = '执行异常'
    finally:
        driver.quit()
        log(f"账号 {account_index} - 浏览器已关闭")
    
    return result

def should_retry(merged_success):
    """判断是否需要重试：如果开源平台或金豆签到未成功"""
    need_retry = not merged_success['oshwhub'] or not merged_success['jindou']
    return need_retry

def process_single_account(username, password, account_index, total_accounts):
    """处理单个账号，包含重试机制，并合并多次尝试的最佳结果"""
    max_retries = 3  # 最多重试3次
    merged_result = {
        'account_index': account_index,
        'nickname': '未知',
        'oshwhub_status': '未知',
        'oshwhub_success': False,
        'initial_points': 0,
        'final_points': 0,
        'points_reward': 0,
        'reward_results': [],     # 礼包领取结果
        'jindou_status': '未知',
        'jindou_success': False,
        'initial_jindou': 0,
        'final_jindou': 0,
        'jindou_reward': 0,
        'has_jindou_reward': False,
        'token_extracted': False,
        'secretkey_extracted': False,
        'retry_count': 0  # 记录最后使用的retry_count
    }
    
    merged_success = {'oshwhub': False, 'jindou': False}

    for attempt in range(max_retries + 1):  # 第一次执行 + 重试次数
        result = sign_in_account(username, password, account_index, total_accounts, retry_count=attempt)
        
        # 合并开源平台结果：如果本次成功且之前未成功，则更新
        if result['oshwhub_success'] and not merged_success['oshwhub']:
            merged_success['oshwhub'] = True
            merged_result['oshwhub_status'] = result['oshwhub_status']
            merged_result['initial_points'] = result['initial_points']
            merged_result['final_points'] = result['final_points']
            merged_result['points_reward'] = result['points_reward']
            merged_result['reward_results'] = result['reward_results']  # 合并礼包结果
            log(f"账号 {account_index} - 正在处理开源平台签到成功结果")
        
        # 合并金豆结果：如果本次成功且之前未成功，则更新
        if result['jindou_success'] and not merged_success['jindou']:
            merged_success['jindou'] = True
            merged_result['jindou_status'] = result['jindou_status']
            merged_result['initial_jindou'] = result['initial_jindou']
            merged_result['final_jindou'] = result['final_jindou']
            merged_result['jindou_reward'] = result['jindou_reward']
            merged_result['has_jindou_reward'] = result['has_jindou_reward']
            log(f"账号 {account_index} - 正在处理金豆签到成功结果")
        
        # 更新其他字段（如果之前未知）
        if merged_result['nickname'] == '未知' and result['nickname'] != '未知':
            merged_result['nickname'] = result['nickname']
        
        if not merged_result['token_extracted'] and result['token_extracted']:
            merged_result['token_extracted'] = result['token_extracted']
        
        if not merged_result['secretkey_extracted'] and result['secretkey_extracted']:
            merged_result['secretkey_extracted'] = result['secretkey_extracted']
        
        # 更新retry_count为最后一次尝试的
        merged_result['retry_count'] = result['retry_count']
        
        # 检查是否还需要重试
        if not should_retry(merged_success) or attempt >= max_retries:
            break
        else:
            log(f"账号 {account_index} - 🔄 准备第 {attempt + 1} 次重试，等待 {random.randint(2, 6)} 秒后重新开始...")
            time.sleep(random.randint(2, 6))
    
    # 最终设置success字段基于合并
    merged_result['oshwhub_success'] = merged_success['oshwhub']
    merged_result['jindou_success'] = merged_success['jindou']
    
    return merged_result

def main():
    if len(sys.argv) < 3:
        print("用法: python jlc.py 账号1,账号2,账号3... 密码1,密码2,密码3... [失败退出标志]")
        print("示例: python jlc.py user1,user2,user3 pwd1,pwd2,pwd3")
        print("示例: python jlc.py user1,user2,user3 pwd1,pwd2,pwd3 true")
        print("失败退出标志: 不传或任意值-关闭, true-开启(任意账号签到失败时返回非零退出码)")
        sys.exit(1)
    
    usernames = [u.strip() for u in sys.argv[1].split(',') if u.strip()]
    passwords = [p.strip() for p in sys.argv[2].split(',') if p.strip()]
    
    # 解析失败退出标志，默认为关闭
    enable_failure_exit = False
    if len(sys.argv) >= 4:
        enable_failure_exit = (sys.argv[3].lower() == 'true')
    
    log(f"失败退出功能: {'开启' if enable_failure_exit else '关闭'}")
    
    if len(usernames) != len(passwords):
        log("❌ 错误: 账号和密码数量不匹配!")
        sys.exit(1)
    
    total_accounts = len(usernames)
    log(f"开始处理 {total_accounts} 个账号的签到任务")
    
    # 存储所有账号的结果
    all_results = []
    
    for i, (username, password) in enumerate(zip(usernames, passwords), 1):
        log(f"开始处理第 {i} 个账号")
        result = process_single_account(username, password, i, total_accounts)
        all_results.append(result)
        
        if i < total_accounts:
            wait_time = random.randint(3, 5)
            log(f"等待 {wait_time} 秒后处理下一个账号...")
            time.sleep(wait_time)
    
    # 输出详细总结
    log("=" * 70)
    log("📊 详细签到任务完成总结")
    log("=" * 70)
    
    oshwhub_success_count = 0
    jindou_success_count = 0
    total_points_reward = 0
    total_jindou_reward = 0
    retried_accounts = []
    
    # 记录失败的账号
    failed_accounts = []
    
    for result in all_results:
        account_index = result['account_index']
        nickname = result.get('nickname', '未知')
        retry_count = result.get('retry_count', 0)
        
        if retry_count > 0:
            retried_accounts.append(account_index)
        
        # 检查是否有失败情况
        if not result['oshwhub_success'] or not result['jindou_success']:
            failed_accounts.append(account_index)
        
        log(f"账号 {account_index} ({nickname}) 详细结果:" + (f" [重试{retry_count}次]" if retry_count > 0 else ""))
        log(f"  ├── 开源平台: {result['oshwhub_status']}")
        
        # 显示积分变化
        if result['points_reward'] > 0:
            log(f"  ├── 积分变化: {result['initial_points']} → {result['final_points']} (+{result['points_reward']})")
            total_points_reward += result['points_reward']
        elif result['points_reward'] == 0 and result['initial_points'] > 0:
            log(f"  ├── 积分变化: {result['initial_points']} → {result['final_points']} (0)")
        else:
            log(f"  ├── 积分状态: 无法获取积分信息")
        
        log(f"  ├── 金豆签到: {result['jindou_status']}")
        
        # 显示金豆变化
        if result['jindou_reward'] > 0:
            jindou_text = f"  ├── 金豆变化: {result['initial_jindou']} → {result['final_jindou']} (+{result['jindou_reward']})"
            if result['has_jindou_reward']:
                jindou_text += "（有奖励）"
            log(jindou_text)
            total_jindou_reward += result['jindou_reward']
        elif result['jindou_reward'] == 0 and result['initial_jindou'] > 0:
            log(f"  ├── 金豆变化: {result['initial_jindou']} → {result['final_jindou']} (0)")
        else:
            log(f"  ├── 金豆状态: 无法获取金豆信息")
        
        # 显示礼包领取结果
        for reward_result in result['reward_results']:
            log(f"  ├── {reward_result}")
        
        if result['oshwhub_success']:
            oshwhub_success_count += 1
        if result['jindou_success']:
            jindou_success_count += 1
        
        log("  " + "-" * 50)
    
    # 总体统计
    log("📈 总体统计:")
    log(f"  ├── 总账号数: {total_accounts}")
    log(f"  ├── 开源平台签到成功: {oshwhub_success_count}/{total_accounts}")
    log(f"  ├── 金豆签到成功: {jindou_success_count}/{total_accounts}")
    
    if total_points_reward > 0:
        log(f"  ├── 总计获得积分: +{total_points_reward}")
    
    if total_jindou_reward > 0:
        log(f"  ├── 总计获得金豆: +{total_jindou_reward}")
    
    # 计算成功率
    oshwhub_rate = (oshwhub_success_count / total_accounts) * 100
    jindou_rate = (jindou_success_count / total_accounts) * 100
    
    log(f"  ├── 开源平台成功率: {oshwhub_rate:.1f}%")
    log(f"  └── 金豆签到成功率: {jindou_rate:.1f}%")
    
    # 失败账号列表
    failed_oshwhub = [r['account_index'] for r in all_results if not r['oshwhub_success']]
    failed_jindou = [r['account_index'] for r in all_results if not r['jindou_success']]
    
    if failed_oshwhub:
        log(f"  ⚠ 开源平台失败账号: {', '.join(map(str, failed_oshwhub))}")
    
    if failed_jindou:
        log(f"  ⚠ 金豆签到失败账号: {', '.join(map(str, failed_jindou))}")
    
    if not failed_oshwhub and not failed_jindou:
        log("  🎉 所有账号全部签到成功!")
    
    log("=" * 70)
    
    # 根据失败退出标志决定退出码
    if enable_failure_exit and failed_accounts:
        log(f"❌ 检测到失败的账号: {', '.join(map(str, failed_accounts))}")
        log("❌ 由于失败退出功能已开启，返回报错退出码以获得邮件提醒")
        sys.exit(1)
    else:
        if enable_failure_exit:
            log("✅ 所有账号签到成功，程序正常退出")
        else:
            log("✅ 程序正常退出（失败退出未开启）")
        sys.exit(0)

if __name__ == "__main__":
    main()
