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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

username = sys.argv[1]
password = sys.argv[2]

chrome_options = Options()
chrome_options.add_argument("--headless")  # 若要调试可注释掉
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")

user_data_dir = tempfile.mkdtemp()
chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

log("正在启动浏览器...")
driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 30)

# 打开真正的登录入口
driver.get("https://oshwhub.com/sign_in")
log("页面加载中（约 10 秒）...")
time.sleep(10)  # 必须等待 iframe 和脚本加载完毕

# 切换到 JLC 登录 iframe
try:
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)
    log("已切换到登录 iframe。")
except Exception as e:
    log(f"❌ 未找到登录 iframe: {e}")
    driver.quit()
    sys.exit(1)

# 点击手机号登录
try:
    phone_login_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "手机号登录")]'))
    )
    phone_login_btn.click()
    log("已切换到手机号登录。")
except:
    log("未找到手机号登录按钮，可能默认已选中。")

# 输入账号密码
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
    log(f"❌ 未找到输入框: {e}")
    driver.quit()
    sys.exit(1)

# 点击登录
try:
    login_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//button[span[text()="登录"]]'))
    )
    login_btn.click()
    log("已点击登录按钮。")
except:
    log("❌ 登录按钮未找到。")
    driver.quit()
    sys.exit(1)

# 滑块验证
time.sleep(3)
try:
    slider = wait.until(EC.presence_of_element_located((By.ID, "nc_1_n1z")))
    track = driver.find_element(By.ID, "nc_1_n1t")

    track_width = track.size['width']
    slider_width = slider.size['width']
    move_distance = track_width - slider_width

    log(f"检测到滑块验证码，滑动距离 {move_distance} 像素。")

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

# 等待登录跳转
log("等待 15 秒完成登录跳转...")
time.sleep(15)
driver.switch_to.default_content()

# 签到按钮
try:
    sign_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//span[contains(text(), "立即签到")]'))
    )
    sign_btn.click()
    log("✅ 签到成功！")
except Exception as e:
    log("⚠ 未找到签到按钮，可能已经签到过或页面未加载。")

time.sleep(3)
driver.quit()
log("任务结束，浏览器已关闭。")
