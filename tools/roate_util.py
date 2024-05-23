#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author:  zcp
# @Date: 2024-04-22 14:00:00
# @Last Modified by:   zcp

import torch.nn as nn
import time
import httpx
import random
from io import BytesIO
from PIL import Image
import torch
from playwright.sync_api import Page, sync_playwright
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_result
from torchvision import transforms

from tools import utils

class CNN(nn.Module):
    def __init__(self):
        super(CNN, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(64 * 5 * 5, 128)
        self.fc2 = nn.Linear(128, 360)  # 360 classes for 0-359 degrees rotation

    def forward(self, x : torch.Tensor) -> torch.Tensor:
        x = self.pool(torch.relu(self.conv1(x)))
        x = self.pool(torch.relu(self.conv2(x)))
        x = self.pool(torch.relu(self.conv3(x)))
        x = x.view(-1, 64 * 5 * 5)
        x = torch.relu(self.fc1(x))
        x = self.fc2(x)
        return x



def get_angle(image: Image) -> int:
    transform = transforms.Compose([
        transforms.Resize((40, 40)),
        transforms.ToTensor(),
    ])
    image = image.convert('RGB')
    image = transform(image).unsqueeze(0)

    # Load the model
    model = CNN()
    model.load_state_dict(torch.load('libs/rotate_model.pth'))
    model.eval()
    # Make a prediction
    with torch.no_grad():
        output = model(image)
        _, predicted = torch.max(output, 1)
        return predicted.item()

def get_tracks(distance : int):
    """
    获取移动轨迹
    :param distance: 需要移动的距离
    """
    tracks = []  # 移动轨迹
    current = 0  # 当前位移
    mid = distance * 4 / 5  # 减速阈值
    t = 0.2  # 计算间隔
    v = 0  # 初始速度

    while current < distance:
        if current < mid:
            a = random.randint(3, 5)  # 加速度为正5
        else:
            a = random.randint(-5, -3)  # 加速度为负3

        v0 = v  # 初速度 v0
        v = v0 + a * t  # 当前速度
        move = v0 * t + 1 / 2 * a * t * t  # 移动距离
        current += move
        tracks.append(round(current))

    return tracks

@retry(stop=stop_after_attempt(10), wait=wait_fixed(2), retry=retry_if_result(lambda value: value is False))
async def correct_angle(context_page: Page) -> bool:
    """
    通过滑动验证码，进行验证码校验
    Args:
        context_page: 页面上下文
    returns:
    """
    if await context_page.query_selector('//div[@class="red-captcha-slider"]') is None:
        return True

    # 开始滑动验证码
    await context_page.wait_for_selector('//div[@id="red-captcha-rotate"]/img')

    img_url = await context_page.get_attribute('//div[@id="red-captcha-rotate"]/img', 'src')
    response = httpx.get(img_url)
    img = Image.open(BytesIO(response.content))

    correction_angle = get_angle(img)
    await context_page.wait_for_selector('//div[@class="red-captcha-slider"]')
    slider = await context_page.query_selector('//div[@class="red-captcha-slider"]')
    slider_box = await slider.bounding_box()

    # 角度移动距离转换
    move_x = correction_angle * 0.79

    # 滑块移动
    await context_page.mouse.move((slider_box['x'] + slider_box['width'] / 2), (slider_box['y'] + slider_box['height'] / 2))
    await context_page.mouse.down()

    tracks = get_tracks(move_x)
    for track in tracks:
        target_X = track + slider_box['x'] + slider_box['width'] / 2
        target_Y = slider_box['y'] + slider_box['height'] / 2
        await context_page.mouse.move(target_X, target_Y)
    await context_page.mouse.up()

    time.sleep(3)
    if await context_page.query_selector('//div[@class="red-captcha-slider"]') is None:
        utils.logger.info("[XiaoHongShuClient.correct_angle] verify success.")
        return True
    else:
        utils.logger.info("[XiaoHongShuClient.correct_angle] verify failed.")
        return False

if __name__ == '__main__':
    # with sync_playwright() as playwright:
    #     browser = playwright.chromium.launch(headless=False)
    #     context = browser.new_context()
    #
    #     context.add_init_script(path='../libs/stealth.min.js')
    #     page = context.new_page()
    #     page.goto('https://www.xiaohongshu.com/website-login/captcha?redirectPath=https%3A%2F%2Fwww.xiaohongshu.com%2Fexplore&verifyUuid=shield-4f9bcc31-0bc0-462a-843a-e60239713e46&verifyType=101&verifyBiz=461')
    #
    #     context.add_init_script(path='../libs/stealth.min.js')
    #
    #     time.sleep(5)
    #
    #     correct_angle(page)
    #     browser.close()

    pass