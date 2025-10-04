import numpy as np
from retrying import retry
from selenium import webdriver
import os
import time
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--no-sandbox')  # 解决 DevToolsActivePort 文件不存在的报错
chrome_options.add_argument('window-size=1920x1080')  # 指定浏览器分辨率
chrome_options.add_argument('--disable-gpu')  # 谷歌文档提到需要加上这个属性来规避 bug
chrome_options.add_argument('--headless')  # 无头模式，Linux 下必须加

def get_web_driver():
    chromedriver = "/usr/bin/chromedriver"
    os.environ["webdriver.chrome.driver"] = chromedriver
    driver = webdriver.Chrome(executable_path=chromedriver, chrome_options=chrome_options)
    driver.implicitly_wait(10)  # 所有操作最长等待 10s
    return driver

# 等待元素可见（备用）
def is_visible(driver, locator, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, locator)))
        return element
    except:
        return False

class Track(object):
    """生成模拟人类手势的滑动轨迹"""

    @staticmethod
    def gen_track(distance):  
        """
        distance: 需要滑动的总距离
        返回: 每一步的位移列表
        """
        result = []
        current = 0
        mid = distance * 4 / 5  # 前 4/5 距离加速，后 1/5 减速
        t = 0.2
        v = 1  # 初速度

        while current < distance:
            if current < mid:
                a = 4  # 加速度
            else:
                a = -3  # 减速度
            v0 = v
            v = v0 + a * t
            move = v0 * t + 0.5 * a * t * t
            current += move
            result.append(round(move))

        return result
