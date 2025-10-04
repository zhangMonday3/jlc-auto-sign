import sys
import time
import tempfile
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

username = sys.argv[1]
password = sys.argv[2]

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")

log("正在启动浏览器...")
driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 20)

# 1️⃣ 打开签到页
driver.get("https://oshwhub.com/sign_in")
log("已打开 JLC 签到页，等待页面加载...")

time.sleep(3)
current_url = driver.current_url

# 2️⃣ 如果自动跳转到了登录页
if "passport.jlc.com/login" in current_url:
    log("检测到未登录状态，正在执行登录流程...")

    try:
        # 点击“手机号登录”
        phone_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"手机号登录")]'))
        )
        phone_btn.click()
        log("已切换到手机号登录。")
        time.sleep(1)
    except:
        log("手机号登录按钮可能已默认选中。")

    # 输入账号
    try:
        user_input = wait.until(
            EC.presence_of_element_located((By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]'))
        )
        user_input.send_keys(username)
        log("已输入用户名。")

        pwd_input = wait.until(
            EC.presence_of_element_located((By.XPATH, '//input[@type="password"]'))
        )
        pwd_input.send_keys(password)
        log("已输入密码。")
    except Exception as e:
        log(f"❌ 登录输入框未找到: {e}")
        driver.quit()
        sys.exit(1)

    # 点击登录按钮
    try:
        login_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button[span[text()="登录"]]'))
        )
        login_btn.click()
        log("已点击登录按钮。")
    except:
        log("❌ 未找到登录按钮。")
        driver.quit()
        sys.exit(1)

    # 等待滑块验证码（如果出现）
    time.sleep(3)
    try:
        slider = wait.until(EC.presence_of_element_located((By.ID, "nc_1_n1z")))
        track = driver.find_element(By.ID, "nc_1_n1t")

        track_width = track.size['width']
        slider_width = slider.size['width']
        move_distance = track_width - slider_width
        log(f"检测到滑块验证码，滑动距离约 {move_distance}px。")

        actions = ActionChains(driver)
        actions.click_and_hold(slider).perform()

        for i in range(30):
            actions.move_by_offset(move_distance / 30, 0).perform()
            time.sleep(0.02)

        actions.release().perform()
        log("滑块拖动完成。")
        time.sleep(5)
    except:
        log("未检测到滑块验证码，直接继续。")

    # 登录后等待跳转回签到页
    log("等待登录跳转...")
    for _ in range(15):
        if "oshwhub.com" in driver.current_url:
            break
        time.sleep(1)

# 3️⃣ 等待签到页加载
log("等待签到页加载...")
time.sleep(5)

# 4️⃣ 点击“立即签到”
try:
    sign_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
    )
    sign_btn.click()
    log("✅ 签到成功！")
except Exception as e:
    log("⚠ 未找到签到按钮，可能已签到或页面结构变化。")

time.sleep(3)
driver.quit()
log("任务完成，浏览器已关闭。")
