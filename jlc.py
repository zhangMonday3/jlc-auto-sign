import sys
import time
import tempfile
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options

# ===== 日志函数 =====
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ===== 登录参数 =====
username = sys.argv[1]
password = sys.argv[2]

# ===== Chrome 配置 =====
chrome_options = Options()
chrome_options.add_argument("--headless")  # 无界面模式
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")

# 每次运行用独立目录防止冲突
user_data_dir = tempfile.mkdtemp()
chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

# 启动浏览器
log("正在启动浏览器...")
driver = webdriver.Chrome(options=chrome_options)

# 打开登录页
driver.get("https://passport.jlc.com/login?appId=JLC_OSHWHUB&redirectUrl=https%3A%2F%2Foshwhub.com%2Fsign_in")
time.sleep(3)
log("页面加载完成。")

# 点击手机号登录
try:
    phone_login_btn = driver.find_element(By.XPATH, '//button[contains(text(), "手机号登录")]')
    phone_login_btn.click()
    log("已切换到手机号登录。")
except:
    log("未找到手机号登录按钮，可能默认已选中。")

time.sleep(1)

# 输入账号
user_input = driver.find_element(By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]')
user_input.send_keys(username)
log("已输入用户名。")

# 输入密码
pwd_input = driver.find_element(By.XPATH, '//input[@type="password"]')
pwd_input.send_keys(password)
log("已输入密码。")

# 点击登录
login_btn = driver.find_element(By.XPATH, '//button[span[text()="登录"]]')
login_btn.click()
log("已点击登录按钮。")

time.sleep(3)

# ===== 滑块验证码 =====
try:
    slider = driver.find_element(By.ID, "nc_1_n1z")   # 滑块按钮
    track = driver.find_element(By.ID, "nc_1_n1t")    # 滑块轨道

    track_width = track.size['width']
    slider_width = slider.size['width']
    move_distance = track_width - slider_width

    log(f"检测到滑块验证码：需要拖动 {move_distance} 像素。")

    actions = ActionChains(driver)
    actions.click_and_hold(slider).perform()

    steps = 30
    for i in range(steps):
        offset = move_distance / steps
        actions.move_by_offset(offset, 0).perform()
        time.sleep(0.02)

    actions.release().perform()
    log("滑块拖动完成。")
except Exception as e:
    log("未检测到滑块验证码，直接继续。")

# 等待页面跳转
log("等待 15 秒完成登录跳转...")
time.sleep(15)

# ===== 签到按钮 =====
try:
    sign_btn = driver.find_element(By.XPATH, '//span[contains(text(), "立即签到")]')
    sign_btn.click()
    log("✅ 签到成功！")
except Exception as e:
    log("⚠ 未找到签到按钮，可能已经签到过。")

time.sleep(3)
driver.quit()
log("任务结束，浏览器已关闭。")
