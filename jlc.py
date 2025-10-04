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

try:
    # 1️⃣ 打开签到页
    driver.get("https://oshwhub.com/sign_in")
    log("已打开 JLC 签到页，等待页面加载...")

    time.sleep(15)
    current_url = driver.current_url

    # 2️⃣ 如果自动跳转到了登录页
    if "passport.jlc.com/login" in current_url:
        log("检测到未登录状态，正在执行登录流程...")

        try:
            # 点击"账号登录"
            phone_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"账号登录")]'))
            )
            phone_btn.click()
            log("已切换账号登录。")
            time.sleep(2)
        except Exception as e:
            log(f"账号登录按钮可能已默认选中或未找到: {e}")

        # 输入账号
        try:
            user_input = wait.until(
                EC.presence_of_element_located((By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]'))
            )
            user_input.clear()
            user_input.send_keys(username)
            log("已输入用户名。")

            pwd_input = wait.until(
                EC.presence_of_element_located((By.XPATH, '//input[@type="password"]'))
            )
            pwd_input.clear()
            pwd_input.send_keys(password)
            log("已输入密码。")
        except Exception as e:
            log(f"❌ 登录输入框未找到: {e}")
            driver.quit()
            sys.exit(1)

        # 点击登录按钮 - 使用更稳定的定位方式
        try:
            # 方法1: 使用CSS选择器定位登录按钮
            login_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit"))
            )
            login_btn.click()
            log("已点击登录按钮（通过CSS选择器）。")
        except:
            try:
                # 方法2: 使用包含特定类的button
                login_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.el-button--primary"))
                )
                login_btn.click()
                log("已点击登录按钮（通过主按钮类）。")
            except:
                try:
                    # 方法3: 使用XPath查找包含"登录"文本的button
                    login_btn = wait.until(
                        EC.element_to_be_clickable((By.XPATH, '//button[.//span[contains(text(), "登录")]]'))
                    )
                    login_btn.click()
                    log("已点击登录按钮（通过span文本）。")
                except Exception as e:
                    log(f"❌ 所有登录按钮定位方式都失败: {e}")
                    # 保存页面源码用于调试
                    with open("debug_page.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    log("已保存页面源码到 debug_page.html")
                    driver.quit()
                    sys.exit(1)

        # 等待滑块验证码（如果出现）
        time.sleep(5)
        try:
            slider = driver.find_element(By.ID, "nc_1_n1z")
            track = driver.find_element(By.ID, "nc_1_n1t")

            track_width = track.size['width']
            slider_width = slider.size['width']
            move_distance = track_width - slider_width
            log(f"检测到滑块验证码，滑动距离约 {move_distance}px。")

            actions = ActionChains(driver)
            actions.click_and_hold(slider).perform()

            # 更平滑的滑动
            for i in range(50):
                actions.move_by_offset(move_distance / 50, 0).perform()
                time.sleep(0.03)

            actions.release().perform()
            log("滑块拖动完成。")
            time.sleep(5)
            
            # 检查滑块是否成功
            try:
                success_msg = driver.find_element(By.ID, "nc_1__scale_text")
                if "通过" in success_msg.text or "验证成功" in success_msg.text:
                    log("滑块验证成功。")
                else:
                    log("滑块验证可能失败。")
            except:
                log("无法获取滑块验证结果。")
                
        except Exception as e:
            log(f"未检测到滑块验证码: {e}")

        # 登录后等待跳转回签到页
        log("等待登录跳转...")
        for i in range(20):
            current_url = driver.current_url
            if "oshwhub.com" in current_url and "passport.jlc.com" not in current_url:
                log("成功跳转回签到页面。")
                break
            log(f"等待跳转... ({i+1}/20) 当前URL: {current_url}")
            time.sleep(2)
        else:
            log("⚠ 跳转超时，但继续执行签到流程。")

    # 3️⃣ 等待签到页加载
    log("等待签到页加载...")
    time.sleep(5)

    # 刷新页面确保在正确的页面
    driver.refresh()
    time.sleep(3)

    # 4️⃣ 点击"立即签到"
    try:
        sign_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
        )
        sign_btn.click()
        log("✅ 签到成功！")
    except Exception as e:
        log(f"⚠ 未找到签到按钮，可能已签到或页面结构变化: {e}")
        # 检查是否已经签到
        try:
            signed_text = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
            log("✅ 今天已经签到过了！")
        except:
            log("❌ 签到失败，且未检测到已签到状态。")

    time.sleep(3)

except Exception as e:
    log(f"❌ 程序执行过程中发生错误: {e}")
    # 保存截图用于调试
    driver.save_screenshot("error_screenshot.png")
    log("已保存错误截图到 error_screenshot.png")

finally:
    driver.quit()
    log("任务完成，浏览器已关闭。")
