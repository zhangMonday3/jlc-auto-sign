import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains

# 命令行参数：手机号、密码
username = sys.argv[1]
password = sys.argv[2]

# 启动浏览器
driver = webdriver.Chrome()
driver.maximize_window()
driver.get("https://oshwhub.com/sign_in")

time.sleep(15)

# 点击手机号登录
phone_login_btn = driver.find_element(By.XPATH, '//button[contains(text(), "手机号登录")]')
phone_login_btn.click()
time.sleep(1)

# 输入账号
user_input = driver.find_element(By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]')
user_input.send_keys(username)
time.sleep(0.5)

# 输入密码
pwd_input = driver.find_element(By.XPATH, '//input[@type="password"]')
pwd_input.send_keys(password)
time.sleep(0.5)

# 点击登录
login_btn = driver.find_element(By.XPATH, '//button[span[text()="登录"]]')
login_btn.click()

time.sleep(10)

# 处理滑块验证码
try:
    slider = driver.find_element(By.ID, "nc_1_n1z")   # 滑块按钮
    track = driver.find_element(By.ID, "nc_1_n1t")    # 滑块轨道

    track_width = track.size['width']
    slider_width = slider.size['width']
    move_distance = track_width - slider_width

    print(f"轨道宽度: {track_width}, 滑块宽度: {slider_width}, 需要拖动: {move_distance}")

    actions = ActionChains(driver)
    actions.click_and_hold(slider).perform()

    # 分步移动，模拟人类操作
    steps = 30
    for i in range(steps):
        offset = move_distance / steps
        actions.move_by_offset(offset, 0).perform()
        time.sleep(0.02)

    actions.release().perform()
    print("滑块拖动完成")
except Exception as e:
    print("没有检测到滑块验证码，直接继续。")

# 等待 15 秒（等待页面跳转成功）
time.sleep(15)

# 点击签到
try:
    sign_btn = driver.find_element(By.XPATH, '//span[contains(text(), "立即签到+1积分")]')
    sign_btn.click()
    print("签到成功 ✅")
except Exception as e:
    print("未找到签到按钮 ❌")

time.sleep(5)
driver.quit()
