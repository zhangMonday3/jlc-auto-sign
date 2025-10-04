import sys
import time
import tempfile
import random
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
    
    os_success = False  # 开源平台积分签到成功标志
    gb_success = False  # 金豆签到成功标志
    login_success = False  # 登录成功标志，初始为False

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
                # 点击"账号登录"（如果存在）
                phone_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"账号登录")]'))
                )
                phone_btn.click()
                log(f"账号 {account_index} - 已切换到账号登录模式。")
                time.sleep(2)
            except Exception as e:
                log(f"账号 {account_index} - 账号登录按钮可能已默认选中或未找到: {e}")

            # 输入用户名和密码
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
                # 定位滑块元素
                slider = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_slide"))
                )
                
                # 获取滑块轨道
                track = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".nc_scale"))
                )
                
                # 计算滑动距离
                track_width = track.size['width']
                slider_width = slider.size['width']
                move_distance = track_width - slider_width - 10  # 略微减少距离避免过头
                
                log(f"账号 {account_index} - 检测到滑块验证码，滑动距离约 {move_distance}px。")
                
                # 创建动作链模拟人类滑动
                actions = ActionChains(driver)
                
                # 按住滑块
                actions.click_and_hold(slider).perform()
                time.sleep(0.5)
                
                # 分段滑动：先快后慢，添加抖动
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
                log(f"账号 {account_index} - 未检测到滑块验证码或处理失败: {e}")

            # 等待登录后跳转回开源平台积分签到页
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
            # 未跳转到登录页，假设已登录
            log(f"账号 {account_index} - 未检测到登录页，假设已登录。")
            login_success = True

        # 3. 等待开源平台积分签到页加载
        log(f"账号 {account_index} - 等待开源平台积分签到页加载...")
        time.sleep(3 + random.randint(1, 3))

        # 刷新页面确保正确加载
        try:
            driver.refresh()
            time.sleep(3)
        except:
            log(f"账号 {account_index} - 刷新页面失败，继续执行。")

        # 4. 执行开源平台积分签到
        try:
            sign_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
            )
            sign_btn.click()
            log(f"账号 {account_index} - ✅ 开源平台积分签到成功！")
            os_success = True
        except Exception as e:
            log(f"账号 {account_index} - ⚠ 未找到开源平台积分签到按钮，可能已签到或页面变化: {e}")
            # 检查是否已签到
            try:
                signed_text = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
                log(f"账号 {account_index} - ✅ 开源平台积分签到今天已经完成！")
                os_success = True
            except:
                log(f"账号 {account_index} - ❌ 开源平台积分签到失败，且未检测到已签到状态。")
                os_success = False

        time.sleep(2)

        if login_success:
            try:
                driver.get("https://m.jlc.com/pages/my/index")
                log(f"账号 {account_index} - 已跳转到手机网页版嘉立创我的页面，等待加载...")
                time.sleep(6)

                # 如果有"登录/注册"按钮，说明未登录
                try:
                    login_register_btn = driver.find_element(By.CSS_SELECTOR, "uni-button.login-btn")
                    if login_register_btn and login_register_btn.is_displayed():
                        log(f"账号 {account_index} - 检测到'点击登录/注册'，需要先登录（跳过金豆签到）。")
                        # 截图并返回，方便人工干预
                        save_debug_screenshot(driver, account_index, "need_manual_login")
                        # 不直接返回 False, False，让脚本继续其他账号
                        return os_success, gb_success
                except:
                    log(f"账号 {account_index} - 未检测到'登录/注册'，继续金豆签到流程。")

                # 先尝试点击"金豆数"入口
                try:
                    gold_bean_span = wait.until(
                        EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"金豆数")]'))
                    )
                    gold_bean_span.click()
                    log(f"账号 {account_index} - 已点击'金豆数'。")
                    # 截图，便于调试弹窗状态
                    save_debug_screenshot(driver, account_index, "after_click_jindou")
                except Exception as e:
                    log(f"账号 {account_index} - ⚠ 未找到'金豆数'元素: {e}")
                    # 尝试直接打开金豆页面
                    driver.get("https://m.jlc.com/pages-common/integral/index")
                    log(f"账号 {account_index} - 直接跳转到金豆页面")
                    time.sleep(4)
                    save_debug_screenshot(driver, account_index, "direct_open_integral")

                # 等待弹窗或遮罩出现（若有）
                popup = None
                try:
                    popup = WebDriverWait(driver, 6).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup"))
                    )
                    log(f"账号 {account_index} - 检测到弹窗（base-popup）。")
                    save_debug_screenshot(driver, account_index, "popup_detected")
                except Exception:
                    log(f"账号 {account_index} - 未检测到弹窗（等待时间内）。")

                # 如果弹窗存在，优先在弹窗内查找各种按钮/提示
                if popup:
                    try:
                        # 1) 弹窗内是否显示"今天已签过了"
                        try:
                            already = popup.find_element(By.XPATH, ".//div[contains(normalize-space(.),'今天已签过了')]")
                            if already:
                                log(f"账号 {account_index} - 弹窗显示：今天已签过了。")
                                # 点击弹窗内"知道了"或关闭按钮（使遮罩消失）
                                try:
                                    ok_btn = popup.find_element(By.XPATH, ".//*[contains(normalize-space(.),'知道了') or contains(normalize-space(.),'确定')]")
                                    ok_btn.click()
                                    log(f"账号 {account_index} - 已点击弹窗内的'知道了/确定'按钮。")
                                except Exception:
                                    # 备用：寻找 primary-btn 文本的按钮
                                    try:
                                        alt_ok = popup.find_element(By.XPATH, ".//uni-button[contains(@class,'primary-btn') or contains(normalize-space(.),'知道了')]")
                                        alt_ok.click()
                                        log(f"账号 {account_index} - 已点击弹窗备用关闭按钮。")
                                    except Exception as ee:
                                        log(f"账号 {account_index} - 无法自动关闭已签到弹窗: {ee}")
                                gb_success = True
                                # 等待遮罩消失
                                try:
                                    WebDriverWait(driver, 5).until_not(EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask")))
                                except:
                                    time.sleep(1)
                        except Exception:
                            # 没有"今天已签过了"的提示，继续寻找"立即签到"
                            pass

                        # 2) 弹窗内是否存在"立即签到"按钮（文本匹配任意子节点）
                        if not gb_success:
                            try:
                                immediate_btn = popup.find_element(By.XPATH, ".//*[contains(normalize-space(.),'立即签到')]")
                                if immediate_btn:
                                    # 滚动到元素并点击
                                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", immediate_btn)
                                    try:
                                        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, ".//*[contains(normalize-space(.),'立即签到')]")))
                                    except:
                                        pass
                                    immediate_btn.click()
                                    log(f"账号 {account_index} - 已点击弹窗内的'立即签到'。")
                                    gb_success = True
                                    # 等待弹窗关闭或遮罩消失
                                    try:
                                        WebDriverWait(driver, 5).until_not(EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask")))
                                    except:
                                        time.sleep(1)
                            except Exception as e:
                                log(f"账号 {account_index} - 未找到弹窗内'立即签到'按钮: {e}")

                        # 3) 若弹窗存在但既无'今天已签过了'也无'立即签到'，尝试关闭弹窗（如有popup-close）
                        if not gb_success:
                            try:
                                close_btn = popup.find_element(By.XPATH, ".//*[contains(@class,'popup-close') or contains(normalize-space(.),'知道了') or contains(normalize-space(.),'关闭') or contains(@class,'ad')]")
                                close_btn.click()
                                log(f"账号 {account_index} - 已尝试点击弹窗的关闭控件。")
                                # 等待遮罩消失
                                try:
                                    WebDriverWait(driver, 5).until_not(EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask")))
                                except:
                                    time.sleep(1)
                            except Exception as e:
                                log(f"账号 {account_index} - 未能找到/点击弹窗关闭控件: {e}")
                                # 仍然尝试点击遮罩以关闭（最后手段）
                                try:
                                    mask = driver.find_element(By.CSS_SELECTOR, "div.base-popup__mask")
                                    driver.execute_script("arguments[0].click();", mask)
                                    log(f"账号 {account_index} - 已尝试点击遮罩以关闭弹窗（尝试）。")
                                    try:
                                        WebDriverWait(driver, 3).until_not(EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask")))
                                    except:
                                        time.sleep(1)
                                except Exception as ee:
                                    log(f"账号 {account_index} - 无法点击遮罩: {ee}")

                # 如果弹窗不存在或已经处理完，尝试页面上的备用签到入口（弹窗关闭后的正规入口）
                if not gb_success:
                    # 等待遮罩完全消失（若存在）
                    try:
                        WebDriverWait(driver, 6).until_not(EC.presence_of_element_located((By.CSS_SELECTOR, "div.base-popup__mask")))
                    except:
                        # 继续也许遮罩很快会消失
                        time.sleep(1)

                    try:
                        sign_div = WebDriverWait(driver, 8).until(
                            EC.element_to_be_clickable((By.XPATH, '//div[contains(@class,"sign") and contains(normalize-space(.),"签到")]'))
                        )
                        # 滚动并点击
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sign_div)
                        sign_div.click()
                        log(f"账号 {account_index} - 已点击页面上的'签到'（备用入口）。")
                        gb_success = True
                    except Exception as e:
                        log(f"账号 {account_index} - ⚠ 未找到页面备用签到入口或点击被遮挡: {e}")
                        # 最后保存截图供你定位
                        save_debug_screenshot(driver, account_index, "jindou_fail")
                # 金豆流程结束
            except Exception as e:
                log(f"账号 {account_index} - ❌ 金豆签到流程中发生错误: {e}")
                save_debug_screenshot(driver, account_index, "goldbean_exception")
                gb_success = False

    except Exception as e:
        log(f"账号 {account_index} - ❌ 程序执行过程中发生错误: {e}")
        try:
            driver.save_screenshot(f"error_screenshot_account_{account_index}.png")
            log(f"账号 {account_index} - 已保存错误截图到 error_screenshot_account_{account_index}.png")
        except:
            log(f"账号 {account_index} - 无法保存截图")

    finally:
        driver.quit()
        log(f"账号 {account_index} - 浏览器已关闭。")
    
    return os_success, gb_success

def main():
    if len(sys.argv) < 3:
        print("用法: python script.py 账号1,账号2,账号3... 密码1,密码2,密码3...")
        print("示例: python script.py user1,user2,user3 pwd1,pwd2,pwd3")
        sys.exit(1)
    
    usernames = [u.strip() for u in sys.argv[1].split(',') if u.strip()]
    passwords = [p.strip() for p in sys.argv[2].split(',') if p.strip()]
    
    if len(usernames) != len(passwords):
        log("❌ 错误: 账号和密码数量不匹配!")
        log(f"账号数量: {len(usernames)}, 密码数量: {len(passwords)}")
        sys.exit(1)
    
    total_accounts = len(usernames)
    log(f"开始处理 {total_accounts} 个账号的签到任务")
    
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
        log(f"开源平台积分签到失败的账号序号: {', '.join(map(str, failed_accounts_os))}")
    else:
        log("✅ 所有账号开源平台积分签到成功!")
    
    log(f"金豆签到成功数: {success_count_gb}")
    log(f"金豆签到失败数: {len(failed_accounts_gb)}")
    if failed_accounts_gb:
        log(f"金豆签到失败的账号序号: {', '.join(map(str, failed_accounts_gb))}")
    else:
        log("✅ 所有账号金豆签到成功!")
    log("=" * 50)

if __name__ == "__main__":
    main()
