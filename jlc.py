#!/usr/bin/env python3
# coding: utf-8
"""
整合版：oshwhub 网页签到（积分） + 嘉立创金豆签到（通过登录信息自动提取 x-jlc-accesstoken & secretkey）
用法:
    python script.py user1,user2 pwd1,pwd2
"""

import sys
import time
import tempfile
import random
import json
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ------- 日志工具 -------
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ------- 原网页签到逻辑（尽量保持原样） -------
def sign_in_account(username, password, account_index, total_accounts):
    """为单个账号执行网页端签到流程（oshwhub）并在登录后提取 JLC token 执行金豆签到"""
    log(f"开始处理账号 {account_index}/{total_accounts} ({username})")
    
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
    # 尝试隐藏 webdriver 特征
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception:
        pass

    wait = WebDriverWait(driver, 20)
    account_success = False
    jlc_token = None
    jlc_secret = None

    try:
        # 1. 打开签到页
        driver.get("https://oshwhub.com/sign_in")
        log(f"账号 {account_index} - 已打开 JLC 签到页，等待页面加载...")
        time.sleep(10 + random.randint(1, 5))
        current_url = driver.current_url

        # 2. 如果自动跳转到了登录页（passport）
        if "passport.jlc.com/login" in current_url or "passport.jlc.com" in current_url or "login" in current_url:
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
                return False

            # 点击登录按钮
            try:
                login_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit"))
                )
                login_btn.click()
                log(f"账号 {account_index} - 已点击登录按钮。")
            except Exception as e:
                log(f"账号 {account_index} - ❌ 登录按钮定位失败: {e}")
                return False

            # 等待并处理滑块验证码
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
                move_distance = int(track_width - slider_width - 10)
                if move_distance < 10:
                    move_distance = int(track_width * 0.8)
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
            except Exception as e:
                log(f"账号 {account_index} - 未检测到滑块验证码或滑块处理失败: {e}")

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

        # 3. 等待签到页加载 & 刷新
        log(f"账号 {account_index} - 等待签到页加载...")
        time.sleep(3 + random.randint(1, 3))
        try:
            driver.refresh()
            time.sleep(3)
        except:
            log(f"账号 {account_index} - 刷新页面失败，继续执行。")

        # 4. 点击"立即签到"（网页积分签到）
        try:
            sign_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"立即签到")]'))
            )
            sign_btn.click()
            log(f"账号 {account_index} - ✅ 网页端积分签到成功！")
            account_success = True
        except Exception as e:
            log(f"账号 {account_index} - ⚠ 未找到即时签到按钮，可能已签到或页面结构变化: {e}")
            try:
                signed_text = driver.find_element(By.XPATH, '//span[contains(text(),"已签到")]')
                log(f"账号 {account_index} - ✅ 今天已经在网页端签到过了！")
                account_success = True
            except:
                log(f"账号 {account_index} - ❌ 网页端签到失败，且未检测到已签到状态。")
                account_success = False

        time.sleep(2)

        # ------------- 新增：跳转到 m.jlc.com 提取 token 并调用 API -------------
        try:
            # 跳转到 m.jlc.com（同源以便读取 localStorage）
            log(f"账号 {account_index} - 正在跳转到 https://m.jlc.com 获取 x-jlc-accesstoken ...")
            driver.get("https://m.jlc.com")
            # 给页面加载和 JS 写 localStorage 的机会
            time.sleep(5 + random.randint(1, 3))

            # 尝试从 localStorage 获取 token / secretkey
            try:
                token = driver.execute_script("return window.localStorage.getItem('x-jlc-accesstoken') || window.localStorage.getItem('jlc_accesstoken') || window.localStorage.getItem('token')")
            except Exception as e:
                log(f"账号 {account_index} - 读取 localStorage 时异常: {e}")
                token = None

            try:
                secretkey = driver.execute_script("return window.localStorage.getItem('secretkey') || window.localStorage.getItem('jlc_secretkey') || window.localStorage.getItem('secret')")
            except Exception as e:
                secretkey = None

            # 如果 localStorage 没有，尝试从 cookies 中找类似字段
            if not token:
                try:
                    cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                    token = cookies.get('x-jlc-accesstoken') or cookies.get('jlc_token') or cookies.get('token')
                    if token:
                        log(f"账号 {account_index} - 从 cookie 找到 token")
                except Exception as e:
                    log(f"账号 {account_index} - 获取 cookie 时异常: {e}")

            if token:
                log(f"账号 {account_index} - 获取到 x-jlc-accesstoken: [长度 {len(token)}]")
                jlc_token = token
                jlc_secret = secretkey
            else:
                log(f"账号 {account_index} - ❌ 未能自动获取 x-jlc-accesstoken (localStorage/cookie 均未找到)。如需自动金豆签到，请确保 m.jlc.com 登录态存在并 localStorage 存在 token。")
        except Exception as e:
            log(f"账号 {account_index} - 跳转或读取 token 过程中发生异常: {e}")

    except Exception as e:
        log(f"账号 {account_index} - ❌ 程序执行过程中发生错误: {e}")
        try:
            driver.save_screenshot(f"error_screenshot_account_{account_index}.png")
            log(f"账号 {account_index} - 已保存错误截图到 error_screenshot_account_{account_index}.png")
        except Exception:
            log(f"账号 {account_index} - 无法保存截图")
    finally:
        # 在调用外部 API 之前保留 driver 关闭或在外部关闭。这里先用到 token 后再关闭 driver。
        # 但为避免长期占用，我们关闭 driver 以便 requests 直接请求 API。
        try:
            driver.quit()
        except:
            pass
        log(f"账号 {account_index} - 浏览器已关闭。")

    # 如果提取到了 token，调用嘉立创 API 做金豆签到（支持领取奖励）
    jlc_result = None
    if jlc_token:
        try:
            jlc_result = jlc_sign_flow(jlc_token, jlc_secret, account_index)
        except Exception as e:
            log(f"账号 {account_index} - 调用金豆签到接口时发生异常: {e}")
    else:
        log(f"账号 {account_index} - 跳过金豆签到（未获取 token）")

    return account_success, jlc_result


# ------- 嘉立创 API 相关（requests） -------
def jlc_sign_flow(token, secretkey, account_index):
    """
    使用 requests 调用嘉立创相关 API 完成金豆签到、领取奖励与查询金豆
    返回一个 dict 包含过程信息
    """
    base_url = "https://m.jlc.com"
    session = requests.Session()

    # 组装 headers（模仿脚本）
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'x-jlc-clienttype': 'WEB',
        'accept': 'application/json, text/plain, */*',
        'Referer': 'https://m.jlc.com/mapp/pages/my/index',
        'x-jlc-accesstoken': token,
    }
    if secretkey:
        headers['secretkey'] = secretkey

    session.headers.update(headers)

    result = {
        'account_index': account_index,
        'token_len': len(token) if token else 0,
        'steps': []
    }

    def safe_get(path, note):
        url = base_url + path
        try:
            r = session.get(url, timeout=15)
            try:
                data = r.json()
            except Exception:
                data = {'success': False, 'raw_text': r.text}
            log(f"账号 {account_index} - [API] {note} -> HTTP {r.status_code}")
            result['steps'].append({note: data})
            return data
        except Exception as e:
            log(f"账号 {account_index} - [API] {note} 请求异常: {e}")
            result['steps'].append({note: f"请求异常: {e}"})
            return None

    # 1. 获取用户信息
    data = safe_get("/api/appPlatform/center/setting/selectPersonalInfo", "获取用户信息")
    try:
        if data and data.get('success'):
            name = data.get('data', {}).get('customerCode') or data.get('data', {}).get('nickName') or ''
            log(f"账号 {account_index} - 昵称：{name}")
        else:
            log(f"账号 {account_index} - 获取用户信息失败或返回不成功: {data}")
    except Exception:
        pass
    time.sleep(random.uniform(1.0, 1.5))

    # 2. 检测是否已签到
    data = safe_get("/api/activity/sign/getCurrentUserSignInConfig", "检测签到配置/今日是否已签到")
    if not data:
        log(f"账号 {account_index} - 无法检测签到状态（请求失败）。")
    else:
        try:
            if not data.get('success'):
                log(f"账号 {account_index} - 检测签到接口返回失败: {data.get('message')}")
            else:
                have_sign = data.get('data', {}).get('haveSignIn')
                if have_sign:
                    log(f"账号 {account_index} - 今日已签到（API 返回）。")
                else:
                    # 尝试签到
                    time.sleep(random.uniform(1.0, 2.5))
                    data_sign = safe_get("/api/activity/sign/signIn?source=4", "执行签到 signIn?source=4")
                    if data_sign and data_sign.get('success'):
                        # 根据返回判断是否直接获得 gainNum 或需要领取 voucher
                        gain = None
                        try:
                            gain = data_sign.get('data', {}).get('gainNum')
                        except:
                            gain = None
                        if gain:
                            log(f"账号 {account_index} - ✅ 金豆签到成功，金豆 +{gain}")
                        else:
                            # 没有直接给 gainNum，说明有奖励需要领取
                            log(f"账号 {account_index} - 签到接口提示有奖励可领取，将尝试调用 receiveVoucher")
                            time.sleep(random.uniform(1.0, 2.0))
                            rv = safe_get("/api/activity/sign/receiveVoucher", "领取奖励 receiveVoucher")
                            if rv and rv.get('success'):
                                log(f"账号 {account_index} - 领取奖励成功（receiveVoucher）。")
                                # 签到后再次检查 signIn 以获得 gainNum
                                time.sleep(random.uniform(1.0, 1.5))
                                ds2 = safe_get("/api/activity/sign/signIn?source=4", "再次执行 signIn 获取实际奖励")
                                if ds2 and ds2.get('success'):
                                    g2 = ds2.get('data', {}).get('gainNum')
                                    if g2:
                                        log(f"账号 {account_index} - ✅ 金豆签到成功，金豆 +{g2}")
                            else:
                                log(f"账号 {account_index} - 领取奖励接口返回失败或没有权限: {rv}")
                    else:
                        log(f"账号 {account_index} - 签到接口返回失败或异常: {data_sign}")
        except Exception as e:
            log(f"账号 {account_index} - 解析检测签到返回时出错: {e}")

    time.sleep(random.uniform(1.0, 1.5))
    # 3. 查询当前金豆
    data_pts = safe_get("/api/activity/front/getCustomerIntegral", "获取金豆余额 getCustomerIntegral")
    try:
        if data_pts and data_pts.get('success'):
            integral = data_pts.get('data', {}).get('integralVoucher')
            log(f"账号 {account_index} - 当前金豆：{integral}")
        else:
            log(f"账号 {account_index} - 查询金豆接口返回失败或没有权限: {data_pts}")
    except Exception as e:
        log(f"账号 {account_index} - 解析金豆查询返回出错: {e}")

    return result


# ------- 主逻辑入口 -------
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
        log("请确保每个账号都有对应的密码，且用逗号分隔")
        sys.exit(1)

    if not usernames or not passwords:
        log("❌ 错误: 账号或密码列表为空!")
        sys.exit(1)

    total_accounts = len(usernames)
    log(f"开始处理 {total_accounts} 个账号的签到任务")

    success_count = 0
    failed_accounts = []

    for i, (username, password) in enumerate(zip(usernames, passwords), 1):
        log(f"开始处理第 {i} 个账号 ({username})")
        success, jlc_result = sign_in_account(username, password, i, total_accounts)

        if success:
            success_count += 1
            log(f"✅ 第 {i} 个账号网页端签到成功")
        else:
            failed_accounts.append(i)
            log(f"❌ 第 {i} 个账号网页端签到失败")

        # jlc_result 已记录过程（可视为成功或部分成功），这里仅打印 summary
        if jlc_result:
            try:
                # 从 steps 中查找最后一次 getCustomerIntegral 的结果
                steps = jlc_result.get('steps', [])
                # 找到最后一个与 getCustomerIntegral 相关的 step 并打印
                last_pts = None
                for st in reversed(steps):
                    if isinstance(st, dict):
                        if "获取金豆余额 getCustomerIntegral" in list(st.keys())[0] or "获取金豆余额" in list(st.keys())[0]:
                            last_pts = st
                            break
                if last_pts:
                    log(f"账号 {i} - 金豆接口返回：{last_pts}")
            except Exception:
                pass

        if i < total_accounts:
            wait_time = random.randint(10, 30)
            log(f"等待 {wait_time} 秒后处理下一个账号...")
            time.sleep(wait_time)

    # 汇总
    log("=" * 50)
    log("签到任务完成总结:")
    log(f"总账号数: {total_accounts}")
    log(f"网页端签到成功数: {success_count}")
    log(f"网页端签到失败数: {len(failed_accounts)}")
    if failed_accounts:
        log(f"失败的账号序号: {', '.join(map(str, failed_accounts))}")
    else:
        log("✅ 所有账号网页端签到成功!")
    log("=" * 50)


if __name__ == "__main__":
    main()
