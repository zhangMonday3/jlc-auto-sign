import sys
import time
import tempfile
import random
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def save_debug_screenshot(driver, account_index, description):
    """保存调试截图"""
    try:
        filename = f"debug_account_{account_index}_{description}_{int(time.time())}.png"
        driver.save_screenshot(filename)
        log(f"账号 {account_index} - 已保存调试截图: {filename}")
    except Exception as e:
        log(f"账号 {account_index} - 无法保存调试截图: {e}")


def sign_in_account(username, password, account_index, total_accounts):
    """为单个账号执行开源平台积分签到和金豆签到流程"""
    log(f"开始处理账号 {account_index}/{total_accounts}")

    profile_dir = tempfile.mkdtemp()
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    wait = WebDriverWait(driver, 20)

    os_success = False
    gb_success = False
    login_success = False

    try:
        # 1. 打开开源平台积分签到页
        driver.get("https://oshwhub.com/sign_in")
        log(f"账号 {account_index} - 已打开开源平台积分签到页，等待页面加载...")
        time.sleep(8)
        current_url = driver.current_url

        # 2. 检查是否需要登录
        if "passport.jlc.com/login" in current_url:
            log(f"账号 {account_index} - 检测到未登录状态，正在执行登录流程...")

            try:
                phone_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"账号登录")]'))
                )
                phone_btn.click()
                log(f"账号 {account_index} - 已切换到账号登录模式。")
                time.sleep(2)
            except Exception as e:
                log(f"账号 {account_index} - 账号登录按钮可能已默认选中或未找到: {e}")

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

            try:
                login_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit"))
                )
                login_btn.click()
                log(f"账号 {account_index} - 已点击登录按钮。")
            except Exception as e:
                log(f"账号 {account_index} - ❌ 登录按钮定位失败: {e}")
                return False, False

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
                log(f"账号 {account_index} - 检测到滑块验证码，滑动距离约 {move_distance}px。")

                actions = ActionChains(driver)
                actions.click_and_hold(slider).perform()
                time.sleep(0.5)

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
                    y_offset = 0
                    if i % 5 == 0:
                        y_offset = 1 if i % 2 == 0 else -1
                    actions.move_by_offset(1, y_offset).perform()

                actions.release().perform()
                log(f"账号 {account_index} - 滑块拖动完成。")
                time.sleep(3)

                try:
                    success_element = driver.find_element(By.CSS_SELECTOR, ".scale_text")
                    if "验证通过" in success_element.text or "成功" in success_element.text:
                        log(f"账号 {account_index} - ✅ 滑块验证成功！")
                    else:
                        log(f"账号 {account_index} - 滑块验证状态: {success_element.text}")
                except:
                    log(f"账号 {account_index} - 无法获取验证结果文本。")
            except Exception as e:
                log(f"账号 {account_index} - 未检测到滑块验证码或处理失败: {e}")

            log(f"账号 {account_index} - 等待登录跳转...")
            for i in range(20):
                current_url = driver.current_url
                if "oshwhub.com" in current_url and "passport.jlc.com" not in current_url:
                    log(f"账号 {account_index} - ✅ 成功跳转回开源平台积分签到页面，登录成功。")
                    login_success = True
                    break
                log(f"账号 {account_index} - 等待跳转... ({i+1}/20) 当前URL: {current_url}")
                time.sleep(2)
            else:
                log(f"账号 {account_index} - ⚠ 跳转超时，登录可能失败，继续尝试开源平台积分签到。")
        else:
            log(f"账号 {account_index} - 未检测到登录页，假设已登录。")
            login_success = True

        log(f"账号 {account_index} - 等待开源平台积分签到页加载...")
        time.sleep(3 + random.randint(1, 3))

        try:
            driver.refresh()
            time.sleep(3)
        except:
            log(f"账号 {account_index} - 刷新页面失败，继续执行。")

        try:
            sign_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
            )
            sign_btn.click()
            log(f"账号 {account_index} - ✅ 开源平台积分签到成功！")
            os_success = True
        except Exception as e:
            log(f"账号 {account_index} - ⚠ 未找到开源平台积分签到按钮: {e}")
            try:
                signed_text = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
                log(f"账号 {account_index} - ✅ 开源平台积分签到今天已经完成！")
                os_success = True
            except:
                log(f"账号 {account_index} - ❌ 开源平台积分签到失败")
                os_success = False

        time.sleep(2)

        # 处理金豆签到
        if login_success:
            try:
                driver.get("https://m.jlc.com/pages/my/index")
                log(f"账号 {account_index} - 已跳转到嘉立创我的页面，等待加载...")
                time.sleep(6)

                try:
                    login_register_btn = driver.find_element(By.CSS_SELECTOR, "uni-button.login-btn")
                    if login_register_btn and login_register_btn.is_displayed():
                        log(f"账号 {account_index} - 检测到'点击登录/注册'，跳过金豆签到。")
                        save_debug_screenshot(driver, account_index, "need_manual_login")
                        return os_success, gb_success
                except:
                    log(f"账号 {account_index} - 未检测到'登录/注册'，继续金豆签到流程。")

                try:
                    gold_bean_span = wait.until(
                        EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"金豆数")]'))
                    )
                    gold_bean_span.click()
                    log(f"账号 {account_index} - 已点击'金豆数'。")
                    save_debug_screenshot(driver, account_index, "after_click_jindou")
                except Exception as e:
                    log(f"账号 {account_index} - ⚠ 未找到'金豆数': {e}")
                    driver.get("https://m.jlc.com/pages-common/integral/index")
                    log(f"账号 {account_index} - 直接跳转到金豆页面")
                    time.sleep(4)
                    save_debug_screenshot(driver, account_index, "direct_open_integral")

                popup = None
                try:
                    popup = WebDriverWait(driver, 6).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup"))
                    )
                    log(f"账号 {account_index} - 检测到弹窗。")
                    save_debug_screenshot(driver, account_index, "popup_detected")
                except Exception:
                    log(f"账号 {account_index} - 未检测到弹窗。")

                if popup:
                    try:
                        try:
                            already = popup.find_element(By.XPATH, ".//div[contains(normalize-space(.),'今天已签过了')]")
                            if already:
                                log(f"账号 {account_index} - 弹窗显示：今天已签过了。")
                                try:
                                    ok_btn = popup.find_element(By.XPATH, ".//*[contains(normalize-space(.),'知道了') or contains(normalize-space(.),'确定')]")
                                    ok_btn.click()
                                except:
                                    try:
                                        alt_ok = popup.find_element(By.XPATH, ".//uni-button[contains(@class,'primary-btn') or contains(normalize-space(.),'知道了')]")
                                        alt_ok.click()
                                    except Exception as ee:
                                        log(f"账号 {account_index} - 无法自动关闭已签到弹窗: {ee}")
                                gb_success = True
                                try:
                                    WebDriverWait(driver, 5).until_not(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask"))
                                    )
                                except:
                                    time.sleep(1)
                        except Exception:
                            pass

                        if not gb_success:
                            try:
                                immediate_btn = popup.find_element(By.XPATH, ".//*[contains(normalize-space(.),'立即签到')]")
                                if immediate_btn:
                                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", immediate_btn)
                                    try:
                                        WebDriverWait(driver, 5).until(
                                            EC.element_to_be_clickable((By.XPATH, ".//*[contains(normalize-space(.),'立即签到')]"))
                                        )
                                    except:
                                        pass
                                    immediate_btn.click()
                                    log(f"账号 {account_index} - 已点击弹窗内的'立即签到'")
                                    gb_success = True
                                    try:
                                        WebDriverWait(driver, 5).until_not(
                                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask"))
                                        )
                                    except:
                                        time.sleep(1)
                            except Exception as e:
                                log(f"账号 {account_index} - 未找到'立即签到'按钮: {e}")

                        if not gb_success:
                            try:
                                close_btn = popup.find_element(
                                    By.XPATH,
                                    ".//*[contains(@class,'popup-close') or contains(normalize-space(.),'知道了') or contains(normalize-space(.),'关闭')]"
                                )
                                close_btn.click()
                                log(f"账号 {account_index} - 已尝试关闭弹窗。")
                                try:
                                    WebDriverWait(driver, 5).until_not(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask"))
                                    )
                                except:
                                    time.sleep(1)
                            except Exception as e:
                                log(f"账号 {account_index} - 无法关闭弹窗: {e}")
                    except Exception as e:
                        log(f"账号 {account_index} - 弹窗处理异常: {e}")

                if not gb_success:
                    try:
                        WebDriverWait(driver, 6).until_not(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask"))
                        )
                    except:
                        time.sleep(1)

                    try:
                        sign_div = WebDriverWait(driver, 8).until(
                            EC.element_to_be_clickable((By.XPATH, '//div[contains(@class,"sign") and contains(normalize-space(.),"签到")]'))
                        )
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sign_div)
                        sign_div.click()
                        log(f"账号 {account_index} - 已点击页面上的'签到'")
                        gb_success = True
                    except Exception as e:
                        log(f"账号 {account_index} - ⚠ 未找到页面备用签到入口: {e}")
                        save_debug_screenshot(driver, account_index, "jindou_fail")

            except Exception as e:
                log(f"账号 {account_index} - ❌ 金豆签到流程中发生错误: {e}")
                save_debug_screenshot(driver, account_index, "goldbean_exception")
                gb_success = False

    except Exception as e:
        log(f"账号 {account_index} - ❌ 程序执行过程中发生错误: {e}")
        try:
            driver.save_screenshot(f"error_screenshot_account_{account_index}.png")
            log(f"账号 {account_index} - 已保存错误截图")
        except:
            log(f"账号 {account_index} - 无法保存截图")
    finally:
        driver.quit()
        shutil.rmtree(profile_dir, ignore_errors=True)
        log(f"账号 {account_index} - 浏览器已关闭。")

    return os_success, gb_success


def main():
    if len(sys.argv) < 3:
        print("用法: python script.py 账号1,账号2,... 密码1,密码2,...")
        sys.exit(1)

    usernames = [u.strip() for u in sys.argv[1].split(',') if u.strip()]
    passwords = [p.strip() for p in sys.argv[2].split(',') if p.strip()]

    if len(usernames) != len(passwords):
        log("❌ 错误: 账号和密码数量不匹配!")
        sys.exit(1)

    total_accounts = len(usernames)
    log(f"开始处理 {total_accounts} 个账号")

    success_count_os = 0
    success_count_gb = 0
    failed_accounts_os = []
    failed_accounts_gb = []

    for i, (username, password) in enumerate(zip(usernames, passwords), 1):
        log(f"开始处理第 {i} 个账号")
        os_success, gb_success = sign_in_account(username, password, i, total_accounts)

        if os_success:
            success_count_os += 1
            log(f"✅ 第 {i} 个账号开源平台积分签到成功")
        else:
            failed_accounts_os.append(i)
            log(f"❌ 第 {i} 个账号开源平台积分签到失败")

        if gb_success:
            success_count_gb += 1
            log(f"✅ 第 {i} 个账号金豆签到成功")
        else:
            failed_accounts_gb.append(i)
            log(f"❌ 第 {i} 个账号金豆签到失败")

        if i < total_accounts:
            wait_time = random.randint(5, 10)
            log(f"等待 {wait_time} 秒后处理下一个账号...")
            time.sleep(wait_time)

    log("=" * 50)
    log("签到任务完成总结:")
    log(f"总账号数: {total_accounts}")
    log(f"开源平台积分签到成功数: {success_count_os}")
    log(f"开源平台积分签到失败数: {len(failed_accounts_os)}")
    if failed_accounts_os:
        log(f"失败的账号序号: {', '.join(map(str, failed_accounts_os))}")
    else:
        log("✅ 所有账号开源平台积分签到成功!")

    log(f"金豆签到成功数: {success_count_gb}")
    log(f"金豆签到失败数: {len(failed_accounts_gb)}")
    if failed_accounts_gb:
        log(f"失败的账号序号: {', '.join(map(str, failed_accounts_gb))}")
    else:
        log("✅ 所有账号金豆签到成功!")
    log("=" * 50)


if __name__ == "__main__":
    main()
