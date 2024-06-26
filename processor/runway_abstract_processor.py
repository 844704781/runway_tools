import json

import net_tools
from processor.abstract_processor import AbstractProcessor
import time
from abc import abstractmethod
import re
from entity.error_code import ErrorCode
from entity.result_utils import ResultDo
from logger_config import logger

from common.custom_exception import CustomException
from entity.error_code import ErrorCode

import re


class RunWayAbstractParser(AbstractProcessor):
    """
        处理runway公共方法
    """

    def __init__(self, username, password, name, task_id: str = None):
        super().__init__(username, password, name, task_id)
        host = 'https://app.runwayml.com'
        self.LOGIN_PATH = host + '/login'
        self.GEN_PATH = host + '/video-tools/teams/v2v2/ai-tools/gen-2'

        logger.info(self.name + "checking ->" + host)
        check_result = net_tools.check_website_availability(host)
        logger.info(self.name + "result ->" + str(check_result))
        if not check_result:
            raise CustomException(ErrorCode.TIME_OUT, "无法连接" + host + "请检查网络")

    def login(self, page):
        try:
            page.goto(self.LOGIN_PATH, wait_until="domcontentloaded")
        except Exception as e:
            raise CustomException(ErrorCode.TIME_OUT, "获取数据超时，稍后重试")
        # 输入账号
        username_input = page.locator('input[name="usernameOrEmail"]')

        username_input.fill(self.username)

        # 输入密码
        password_input = page.locator('input[type="password"]')
        password_input.fill(self.password)
        if len(self.password) <= 6:
            self.balance_callback(_account=self.username, _count=-1, _message='密码长度小于等于6')
            return False
        # 点击提交按钮
        submit_button = page.locator('button[type="submit"]')
        submit_button.click()
        is_login = False
        # 等待一段时间确保页面加载完全
        try:
            # 检查是否登录成功
            page.wait_for_selector('a[href="/ai-tools/gen-2"]')
            is_login = True
        except Exception as e:
            pass
        if not is_login:
            try:
                logger.info(self.name + "登录失败,获取失败原因")
                err_message = page.locator("xpath=//div[@data-kind='error']")
                danger_txt = err_message.inner_text()
                logger.info(self.name + f"登录失败，失败原因为:{danger_txt}")
                self.balance_callback(_account=self.username, _count=-1, _message=danger_txt)
            except Exception as e:
                pass
            finally:
                return False
        # 示例：保存
        return True

    def get_seconds(self, page):
        def extract_number(text):
            if 'Unlimited' in text:
                return 2147483647

            match = re.search(r'\d+', text)
            if match:
                return int(match.group())
            else:
                return 0

        # TODO 处理无次数限制情况
        p_tag = page.locator('.Text-sc-cweq7v-1.GetMoreCreditsButton__UnitsLeftText-sc-66lapz-0.fNdEQX')
        un_limit_tag = page.locator("xpath=//span[@class='Text__BaseText-sc-7ge0qa-0 eDDjVb']")
        count_text = None
        for i in range(0, 3):
            try:
                logger.info(f"{self.name}正在获取余额")
                count_text = un_limit_tag.inner_text(timeout=10000)
            except Exception as e:
                pass
            if count_text is None or len(count_text) == 0:
                try:
                    count_text = p_tag.inner_text(timeout=10000)
                except Exception as e:
                    pass
            if count_text is not None:
                logger.info(f"{self.name}余额获取成功,尝试次数:{i}")
                break
            logger.info(f"{self.name}余额获取失败，重新尝试，剩余尝试次数:{3 - i}")
        if count_text is None:
            raise CustomException(ErrorCode.TIME_OUT, "余额无法获取")
        count = extract_number(count_text)
        if self.balance_callback is not None:
            self.balance_callback(_account=self.username, _count=count, _message='余额充足')
        if count < 10:
            raise CustomException(ErrorCode.INSUFFICIENT_BALANCE, f"当前余额:{count},余额不足,请充值")

        return count

    def loading(self, page):
        # 等待生成结果
        # 这里可以根据页面的加载状态或其他条件来判断生成结果是否加载完成
        src_attribute = None
        percent = 0
        while True:
            video_element = page.locator('.OutputVideo___StyledVideoOutputNative-sc-di1eng-2.fLPiNR')
            count = video_element.count()
            percent = percent if count == 0 else 100
            self.print_progress(percent)
            if count > 0:
                logger.info("\n" + self.name + "视频生成成功")
                src_attribute = video_element.evaluate('''element => element.getAttribute('src')''')
                break
            else:
                # 获取文本内容
                element_locator = page.locator('.ProgressBar__percentage__o2hVF')  # 使用你提供的类名选择器
                try:
                    progress_text = element_locator.inner_html()
                except Exception as e:
                    continue

                progress_text = int(progress_text[:-1])
                percent = 100 / 75 * progress_text // 1
            # 暂停一段时间再进行下一次检查
            time.sleep(5)
        return src_attribute

    @abstractmethod
    def write(self, page):
        pass

    def commit(self, page):
        # 点击按钮

        # generate_button = page.locator('button:has-text("Generate 4s")')
        # err = None
        # try:
        #     generate_button.wait_for(timeout=30000)
        # except Exception as e:
        #     err = e
        # if err is not None:
        i = 0
        num = 10
        generate_button = page.locator(
            "xpath=//button[contains(@class,'ExploreModeGenerateButton__Button-sc-ny02we-0')]")
        while i < num:
            logger.info(self.name + f"尝试获取点击按钮，剩余尝试次数:\t{num - i}")
            disabled = generate_button.evaluate('(element) => element.disabled')
            logger.info(self.name + f"当前按钮可点击状态按钮:disabled:{disabled}")
            if not disabled:
                break
            time.sleep(5)
            i += 1

        generate_button.click()
