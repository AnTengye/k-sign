import os
import random
import secrets
import ssl
import string
import traceback
from urllib.parse import urlparse, ParseResult, quote

import requests
import requests.packages.urllib3
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.packages.urllib3.util.ssl_ import create_urllib3_context
from scrapy import Selector

from gifcode import handle_yzm
from notify import send

requests.packages.urllib3.disable_warnings()

DEFAULT_TIMEOUT = 10  # seconds


class BaseSign:
    # 请求相关
    session: requests.Session
    base_url: str
    url_info: ParseResult
    content: list
    exec_method: list = []  # 除了login以外，还默认需要执行的逻辑
    retry_times = 1
    ua: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    # 用户信息配置
    username: str
    password: str
    app_name: str
    app_key: str
    # 登录配置
    login_type: str = "" # 登录方式 login: 常规登录 login_code: 需要普通验证码 login_cookie: 需要cookie方式
    login_setting_code_type: str = "img" # 登录验证码类型 img|gif
    login_setting_code_check: bool = False  # 验证码是否需要校验
    login_page_path: str = ""  # 登录页面链接
    login_update_page_path: str = ""  # 登录页面验证码链接
    login_resp_success: str = r"succeedhandle_\('(.*?)'"
    login_resp_error: str = r"errorhandle_\((.*?),"
    code_debug: bool = False
    # 签到页配置
    index_path: str  # 签到页面路径
    form_hash_xpath: str  # 签到页面formhash
    sign_path: str  # 签到请求链接
    sign_text_xpath: str  # 签到文本匹配路径
    sign_text: str  # 签到文本
    sign_method: str = "get"  # 签到方式，get/post
    sign_mood: str = "very very good"  # 签到心情（仅post可用）

    err_msg_dict = {
        'msg_captcha_notopen': '该验证功能未开启',
        'msg_captcha_cancel': '您已主动关闭验证码',
        'msg_captcha_fail': '验证失败，请重试',
        'msg_captcha_success': '验证通过',
        'msg_account_empty': '请输入登录账号',
        'msg_areacode_error': '请重新选择区号',
        'msg_phone_empty': '请输入手机号',
        'msg_phone_formaterror': '手机号格式错误',
        'msg_seccode_empty': '请输入短信验证码',
        'msg_seccode_formaterror': '短信验证码格式错误',
        'msg_username_empty': '请输入用户名',
        'msg_uid_empty': '请输入用户UID',
        'msg_email_empty': '请输入E-mail',
        'msg_email_format_error': '邮箱格式不正确',
        'msg_password_empty': '请输入密码',
        'msg_password_different': '两次密码不一致',
        'msg_function_abnormal': '未知错误,请刷新页面后重试',
        'msg_captcha_configurationerror': '配置错误',
        'msg_captcha_parametererror': '参数错误',
        'msg_smssendphone_null': '接收手机号不能为空',
        'msg_smssendphone_error': '接收手机号格式错误',
        'msg_captcha_ok_sendsms_error': '验证通过,短信发送失败,请重试',
        'msg_generatecode_error': '生成短信验证码出现错误,请重试',
        'msg_request_fail': '请求失败，请刷新页面后重试',
        'msg_sendsms_success': '短信发送成功',
        'msg_sendsms_error': '短信发送失败',
        'msg_sendsms_error998': '短信配置错误',
        'msg_sendsms_error1': '手机号格式错误',
        'msg_sendsms_error2': '短信验证码错误',
        'msg_sendsms_error3': '未知错误',
        'msg_sendsms_error4': '短信发送达到当日限额',
        'msg_sendsms_error5': '短信发送流控限制,请勿频繁发送短信',
        'msg_sendsms_error6': '您所在的地区暂未开放该功能',
        'msg_sendsms_error7': '抱歉，您所在地区该功能维护中，暂时无法发送短信',
        'msg_function_closed': '该功能未开启',
        'msg_logintype_closed': '该登录方式未开启,请刷新页面后重试',
        'msg_device_illegal': '来路非法',
        'msg_register_illegal': '非法注册',
        'msg_register_success': '注册成功',
        'msg_register_fail': '注册失败',
        'msg_login_illegal': '非法登录',
        'msg_login_success': '登录成功',
        'msg_login_fail': '登录失败',
        'msg_login_fail_try_seccode': '登录失败,请尝试使用手机短信验证码方式登录',
        'msg_err_seccodeguoqi': '短信验证码已失效,请重新获取',
        'msg_err_checkseccode': '短信验证码校验失败',
        'msg_err_mobile_exist': '该手机号已被注册',
        'msg_err_username_len_invalid': '请将用户名设置为3到15位',
        'msg_err_password_len_invalid': '请将密码设置为6到20位',
        'msg_err_email_illegal': 'Email 地址无效',
        'msg_err_email_domain_illegal': '抱歉，Email 包含不可使用的邮箱域名',
        'msg_err_email_duplicate': '该 Email 地址已被注册',
        'msg_err_phonebind': '该手机号码已被使用',
        'msg_err_nouser': '未查到该用户信息，请重试',
        'msg_err_oldphonebind': '未获取到已绑定手机号数据，请重试',
        'msg_err_getareacode': '区号数据获取失败，当前仅支持国内手机用户注册',
        'msg_err_weibangding': '该手机号尚未在网站进行绑定',
        'msg_err_location_login_force_qq': '您所在的用户组必须使用QQ帐号登录',
        'msg_err_location_login_force_mail': '您所在的用户组必须使用邮箱登录',
        'msg_err_location_login_outofdate': '您当前的帐号已经太长时间未登录网站，为确保安全，必须验证手机后才能继续操作',
        'msg_err_location_login_password_tooshort': '您当前帐号的密码过于简单，为确保安全，必须修改密码后才能继续操作',
        'msg_err_location_login_differentplaces': '检测到您的帐号在异地登录，为确保安全，必须验证手机后才能继续操作',
        'msg_err_location_login_needverify': '请先对已绑定的手机号进行验证，才能继续操作',
        'msg_err_getpasswd_account_notmatch': '抱歉，您填写的账户资料不匹配，不能使用取回密码功能，如有疑问请与管理员联系',
        'msg_err_getpasswd_account_invalid': '抱歉，创始人、受保护用户、拥有站点设置权限的用户不能使用取回密码功能',
        'msg_areacode_notopen': '抱歉，您所在地区该功能维护中，暂时无法操作',
        'msg_answer_empty': '您选择了安全问题，请填写答案',
        'msg_answer_empty2': '请输入答案',
        'msg_err_answerset': '您设置了安全问题，请选择安全问题，并填写正确的答案后重新登录',
        'msg_err_logintoomany': '密码错误次数过多，请15分钟后登录',
        'msg_err_mimaerror': '您的登录密码不正确',
        'msg_verify_success': '验证成功',
        'msg_verify_fail': '验证失败',
        'msg_err_getpasswd_illegal': '抱歉，签名已过期，无法取回密码，请重试',
        'msg_getpasswd_succeed': '您的密码已重新设置，请使用新密码登录',
        'msg_err_profile_passwd_illegal': '抱歉，密码空或包含非法字符',
        'msg_err_profile_password_tooshort1': '密码太短了，至少要',
        'msg_err_profile_password_tooshort2': '个字符',
        'msg_err_password_weak': '密码太弱，密码中必须包含',
        'strongpw_1': '数字',
        'strongpw_2': '小写字母',
        'strongpw_3': '大写字母',
        'strongpw_4': '特殊符号',
        'msg_need_login': '请先登录',
        'module_not_exists': '无效的功能',
        'param_error': '参数错误',
        'msg_register_username_empty': '请输入用户名',
        'msg_register_password_empty': '请输入密码',
        'msg_register_email_empty': '请输入邮箱',
        'msg_register_email_format_error': '邮箱格式不正确',
        'btn_next': '下一步',
        'btn_previous': '上一步',
        'msg_err_username_empty': '请输入用户名',
        'msg_err_username_len_short_invalid_error': '用户名过短',
        'msg_err_username_len_long_invalid_error': '用户名过长',
        'msg_err_username_sensitive': '用户名包含敏感字符!',
        'msg_err_username_shield': '用户名包含被系统屏蔽的字符!',
        'msg_err_username_reged': '该用户名已注册，请更换新用户名!',
        'msg_err_username_exist': '用户名已存在!',
        'msg_getpasswd_account_notmatch': '抱歉，您填写的账户资料不匹配，不能使用取回密码功能，如有疑问请与管理员联系',
        'msg_lostpasswd_email_not_exist': '抱歉，使用此 Email 的用户不存在，不能使用取回密码功能',
        'msg_lostpasswd_many_users_use_email': '抱歉，存在多个使用此 Email 的用户，请填写您需要找回密码的用户名',
        'msg_getpasswd_account_invalid': '抱歉，创始人、受保护用户、拥有站点设置权限的用户不能使用取回密码功能',
        'msg_getpasswd_send_succeed': '取回密码的方法已通过 Email 发送到您的信箱中，<br />请在 3 天之内修改您的密码',
        'msg_register_success_sendemail_error': '注册成功,但注册验证邮件发送失败,请重新发送验证！',
        'msg_register_success_email_verify': '注册成功,请前往邮箱进行邮件验证！',
        'msg_err_register_ctrl1': '抱歉，您的 IP 地址在 ',
        'msg_err_register_ctrl2': ' 小时内无法注册',
        'msg_err_register_flood_ctrl1': '抱歉，IP 地址在 24 小时内只能注册 ',
        'msg_err_register_flood_ctrl2': ' 次',
        'msg_invitecode_success': '可用的邀请码',
        'msg_invitecode_error': '邀请码不正确',
        'msg_invitecode_empty': '请输入邀请码',
        'msg_err_getpasswd_has_send': '取回密码的方法已通过 Email 发送到您的信箱中，如果您没有收到，请稍等15分钟后重试',
        'msg_err_onlyseccodelogin': '抱歉，您所在的用户组仅支持使用"短信验证码"方式登录！',
        'msg_err_notregister': '该手机号尚未在网站注册，请先进行账号注册',
        'msg_err_seccodetoomany': '短信验证码错误次数过多，请稍等15分钟后重试',
        'msg_yanzheng_success': '验证问答答案正确',
        'msg_yanzheng_error': '验证问答答案不正确',
        'msg_yanzheng_empty': '请输入验证问答答案',
    }

    def __init__(self, base_url, app_name, app_key, proxy=False, timeout=10):
        self.app_key = app_key
        self.app_name = app_name
        env_url = os.getenv(f'SIGN_URL_{app_key}')
        if env_url is None or env_url == "":
            if base_url == "":
                raise f"未设置网址，请添加变量:SIGN_URL_{app_key}"
        else:
            base_url = env_url
        env_proxy = os.getenv(f'SIGN_PROXY_{app_key}')
        if env_proxy is None or env_proxy == "":
            proxy=proxy
        else:
            if env_proxy == "False":
                proxy = False
            else:
                proxy = True

        self.url_info = urlparse(base_url)
        self.base_url = base_url
        up = os.getenv(f'SIGN_UP_{app_key}')
        if up:
            user_info = up.split("|")
            self.username = user_info[0]
            self.password = user_info[1]
        else:
            raise "未设置账号信息，请添加变量SIGN_UP_" + app_key
        self.app_name = app_name
        self.content = list()
        session = requests.session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = TimeoutHTTPAdapter(timeout=timeout, max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"User-Agent": self.ua})
        self.session = session
        if proxy:
            proxy = os.getenv('SIGN_UP_PROXY')
            if proxy is not None:
                self.session.proxies.update({
                    'http': 'http://' + proxy,
                    'https': 'http://' + proxy
                })
        self.session.verify = False

        print(f"自助脚本初始化完成：\n目标地址：{self.base_url}\n用户名：{self.username}\n代理状态：{proxy}")

    def login(self) -> bool:
        if self.login_type == "login":
            return self._login()
        elif self.login_type == "login_code":
            return self._code_login()
        elif self.login_type == "login_cookie":
            return self._cookie_login()
        else:
            self.pwl("未实现登录")
            return False


    def sign(self) -> bool:
        qd_response = self.session.get(f"{self.base_url}/{self.index_path}")
        sign_selector = Selector(response=qd_response)
        sign_info = sign_selector.xpath(self.sign_text_xpath).extract_first()
        if sign_info:
            self.pwl(sign_info.strip())
            if sign_info.strip() == self.sign_text:
                self.pwl("进行签到中...")
                form_hash = sign_selector.xpath(self.form_hash_xpath).extract_first()
                if form_hash == "":
                    self.pwl("获取签到表单验证失败")
                    return False
                if self.sign_method == "post":
                    return self._post_sign(form_hash)
                else:
                    return self._get_sign(form_hash)
            else:
                return True
        else:
            self.pwl("签到信息获取失败，网站可能发生变更")
            return False

    def _get_sign(self, form_hash) -> bool:
        """
        适用于get请求的通用签到
        :param form_hash: 前端表单校验码
        :return:
        """
        response = self.session.get(
            f"{self.base_url}/{self.sign_path}" % form_hash)
        result_selector = Selector(response=response)
        result = result_selector.xpath("/root/text()").extract_first()
        self.pwl(f"签到异常信息：{result}")
        if result:
            return False
        else:
            return True

    def _login(self) -> bool:
        """
        通用登录（不含验证码）
        :return:
        """
        print(f"进行 {self.username} 登录")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        # //form[@name="login"]/div/input[1]/@value
        # //input[@name="formhash"]/@value
        # //*[@id="scbar_form"]/input[2]/@value
        form_hash = selector.xpath('//input[@name="formhash"]/@value').extract_first()
        if form_hash is None:
            self.pwl("formhash匹配失败")
            return False
        url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=LocOL&inajax=1"
        payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2Fportal.php&username={self.username}&password={self.password}&questionid=0&answer=&cookietime=2592000'
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,'
                      '*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/member.php?mod=logging&action=login',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/102.0.0.0 Safari/537.36 '
        }
        response = self.session.post(url, headers=headers, data=payload)
        result_selector = Selector(response=response)
        jump_src = result_selector.re(r"succeedhandle_\('(.*?)'")
        if len(jump_src) == 0:
            result = result_selector.re(r'errorhandle_\((.*?),')
            if len(result) == 0:
                self.pwl(f'登录失败:{response.text}')
                return False
            self.pwl(result[0])
            return False
        else:
            self.sign_url = jump_src[0]
        self.pwl('登录成功')
        return True

    def _code_login(self) -> bool:
        """
        通用登录（含验证码）
        :return:
        """
        print(f"进行 {self.username} 登录")
        if self.login_page_path == "":
            login_page_path = "member.php?mod=logging&action=login"
        else:
            login_page_path = self.login_page_path
        response = self.session.get(f"{self.base_url}/{login_page_path}")
        selector = Selector(response=response)
        form_hash = selector.xpath('//input[@name="formhash"]/@value').extract_first("")
        sec_data = selector.re(r"updateseccode\('(\w*?)'")
        update_data = selector.re(r"update=([0-9]*)&")
        update = ""
        sec_hash = ""
        if len(sec_data) != 0:
            sec_hash = sec_data[0]
        if len(update_data) != 0:
            update = update_data[0]
        else:
            random_float = random.uniform(0, 1)
            if self.login_update_page_path == "":
                login_update_page_path = f"misc.php?mod=seccode&action=update&idhash={sec_hash}&{random_float}&modid=member::logging"
            else:
                login_update_page_path = self.login_update_page_path
            update_response = self.session.get(f"{self.base_url}/{login_update_page_path}")
            update_selector = Selector(response=update_response)
            update_data = update_selector.re(r"update=([0-9]*)&")
            if len(update_data) != 0:
                update = update_data[0]
        if sec_hash and form_hash:
            verify_code = self._code(sec_hash, update, 5)
            if not verify_code:
                return False
            url = f"{self.base_url}/{login_page_path}?mod=logging&action=login&loginsubmit=yes&loginhash=Lmv7D&inajax=1"
            payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2Fforum.php&loginfield=username&username={self.username}&password={self.password}&seccodehash={sec_hash}&seccodemodid=member%3A%3Alogging&seccodeverify={verify_code}&questionid=0&answer=&cookietime=2592000'
            headers = {
                'authority': self.url_info.hostname,
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'pragma': 'no-cache',
                'referer': f'{self.base_url}/{login_page_path}?mod=logging&action=login',
                'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
            }
            response = self.session.post(url, headers=headers, data=payload)
            result_selector = Selector(response=response)
            jump_src = result_selector.re(self.login_resp_success)
            if len(jump_src) == 0:
                result = result_selector.re(self.login_resp_error)
                if len(result) > 0:
                    self.pwl(result[0])
                return False
            else:
                self.session.get(jump_src[0])
                self.pwl(f'登录成功')
            return True
        else:
            self.pwl("链接访问异常")

    def _cookie_login(self) -> bool:
        cookie_string = os.getenv(f'SIGN_COOKIE_{self.app_key}')
        if cookie_string is None or cookie_string == "":
            raise f"未设置cookie，请添加变量:SIGN_COOKIE_{self.app_key}"
        cookies = {}
        for cookie in cookie_string.split(";"):
            key, value = cookie.strip().split("=")
            cookies[key] = value
        self.session.cookies.update(cookies)
        qd_response = self.session.get(self.base_url)
        if self.username in qd_response.text:
            self.pwl("登录成功")
            return True
        else:
            self.pwl("cookie 已过期")
            return False

    def _code(self, sec_hash, update, times=3) -> str:
        if times == 0:
            self.pwl("错误次数过多")
            return ""
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/member.php?mod=logging&action=login',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'image',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
        }
        payload = {}
        url = f"{self.base_url}/misc.php?mod=seccode&update={update}&idhash={sec_hash}"
        response = self.session.get(url, headers=headers, data=payload)
        result = handle_yzm(response.content, t=self.login_setting_code_type, debug=self.code_debug)
        if result.encode().isalnum():
            if self.login_setting_code_check:
                check_url = f"{self.base_url}/misc.php?mod=seccode&action=check&inajax=1&modid=member::logging&idhash={sec_hash}&secverify={result}"
                check_payload = {}
                check_headers = {
                    'authority': self.url_info.hostname,
                    'accept': '*/*',
                    'accept-language': 'zh-CN,zh;q=0.9',
                    'cache-control': 'no-cache',
                    'pragma': 'no-cache',
                    'referer': f'{self.base_url}/member.php?mod=logging&action=login',
                    'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
                    'x-requested-with': 'XMLHttpRequest'
                }
                check_response = self.session.get(check_url, headers=check_headers, data=check_payload)
                check_selector = Selector(response=check_response, type='xml')
                is_success = check_selector.re(r'succeed')
                if len(is_success) != 0:
                    return result
                else:
                    self.pwl(f"校验失败：{check_response.text}")
            else:
                return result
        return self._code(sec_hash, update, times - 1)

    def _post_sign(self, form_hash) -> bool:
        """
        适用于post请求的通用签到
        :param form_hash: 前端表单校验码
        :return:
        """
        url = f"{self.base_url}/plugin.php?id=dc_signin:sign&inajax=1"
        payload = f'formhash={form_hash}&signsubmit=yes&handlekey=signin&emotid=1&referer={quote(self.base_url, safe="")}%2Fdc_signin-dc_signin.html&content={self.sign_mood}'
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/dc_signin-dc_signin.html',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }

        response = self.session.post(url, headers=headers, data=payload)
        result_selector = Selector(response=response)
        jump_src = result_selector.re(r"succeedhandle_signin\('(.*?)', '(.*)'")
        if len(jump_src) == 0:
            result = result_selector.re(r'errorhandle_signin\((.*?),')
            if len(result) == 0:
                self.pwl(f'签到失败:{response.text}')
                return False
            self.pwl(result[0])
            return False
        else:
            self.pwl(jump_src[1])
        return True

    def _post_content_sign(self, form_hash) -> bool:
        """
        适用于post请求的带心情的签到
        :param form_hash: 前端表单校验码
        :return:
        """
        url = f"{self.base_url}/plugin.php?id=dc_signin:sign&inajax=1"
        payload = f'formhash={form_hash}&signsubmit=yes&handlekey=signin&emotid=1&referer={quote(self.base_url, safe="")}%2Fdc_signin-dc_signin.html&content={self.sign_mood}'
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/dc_signin-dc_signin.html',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }

        response = self.session.post(url, headers=headers, data=payload)
        result_selector = Selector(response=response)
        jump_src = result_selector.re(r"succeedhandle_signin\('(.*?)', '(.*)'")
        if len(jump_src) == 0:
            result = result_selector.re(r'errorhandle_signin\((.*?),')
            if len(result) == 0:
                self.pwl(f'签到失败:{response.text}')
                return False
            self.pwl(result[0])
            return False
        else:
            self.pwl(jump_src[1])
        return True

    def pwl(self, c: str):
        """
        日志记录
        :param c:
        :return:
        """
        print(c)
        if c:
            self.content.append(c)

    def log(self) -> str:
        """
        返回日志
        :return:
        """
        return "\n".join(self.content)

    def uid(self, length=32) -> str:
        """
        生成随机的uid
        :param length:
        :return:
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def check_code(self, input_str, str_len=4):
        if len(input_str) != str_len:
            return False
        # 检查字符串是否只包含英文字母或数字
        if not input_str.isalnum():
            return False

        return True

    def run(self):
        content = self._exec("")
        send(title=self.app_name, content=content)

    def pre(self):
        pass

    def _exec(self, content) -> str:
        self.retry_times -= 1
        try:
            self.pre()
            login = self.login()
            result = {"登录": login}
            if login:
                if len(self.exec_method) != 0:
                    for v in self.exec_method:
                        func = getattr(self, v)
                        result[v] = func()
            elif self.retry_times > 0:
                return self._exec(content)
            for k, r in result.items():
                content += f"{k} 结果：{r}\n"
            content += f"日志：\n{self.log()}"
        except (
                requests.exceptions.RetryError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout
        ) as e:
            # 当网络不好时，进行重试
            traceback.print_exc()
            content += str(e.args[0])
            if self.retry_times > 0:
                return self._exec(content)
        except requests.exceptions.RequestException as e:
            traceback.print_exc()
            content += "网络请求有误，请检查代理设置"
        except Exception as e:
            traceback.print_exc()
            content += "执行异常，请查看日志排查"
        return content


class SignPlugin:
    # 签到页配置
    index_path: str  # 签到页面路径
    form_hash_xpath: str  # 签到页面formhash
    sign_path: str  # 签到请求链接
    sign_text_xpath: str  # 签到文本匹配路径
    sign_text: str  # 签到文本
    sign_method: str = "get"  # 签到方式，get/post
    sign_mood: str = "very very good"  # 签到心情（仅post可用）

    def setting(self):
        pass


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        print("已启用", self.__class__.__name__, "插件")
        self.timeout = DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


class CipherSuiteAdapter(HTTPAdapter):
    """
    支持绕过cf认证
    """
    __attrs__ = [
        'ssl_context',
        'max_retries',
        'config',
        '_pool_connections',
        '_pool_maxsize',
        '_pool_block',
        'source_address'
    ]
    DEFAULT_CIPHERS = ":".join(
        [
            "ECDHE+AESGCM",
            "ECDHE+CHACHA20",
            "DHE+AESGCM",
            "DHE+CHACHA20",
            "ECDH+AESGCM",
            "DH+AESGCM",
            "ECDH+AES",
            "DH+AES",
            "RSA+AESGCM",
            "RSA+AES",
            "!aNULL",
            "!eNULL",
            "!MD5",
            "!DSS",
        ]
    )

    def __init__(self, *args, **kwargs):
        print("已启用", self.__class__.__name__, "插件")
        ciphers = ":".join(
            [
                "ECDHE+AESGCM",
                "ECDHE+CHACHA20",
                "DHE+AESGCM",
                "DHE+CHACHA20",
                "ECDH+AESGCM",
                "DH+AESGCM",
                "ECDH+AES",
                "DH+AES",
                "RSA+AESGCM",
                "RSA+AES",
            ]
        )
        self.timeout = DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        self.ssl_context = kwargs.pop('ssl_context', None)
        self.cipherSuite = kwargs.pop('cipherSuite', ciphers)
        self.source_address = kwargs.pop('source_address', None)
        self.server_hostname = kwargs.pop('server_hostname', None)
        self.ecdhCurve = kwargs.pop('ecdhCurve', 'prime256v1')

        if self.source_address:
            if isinstance(self.source_address, str):
                self.source_address = (self.source_address, 0)

            if not isinstance(self.source_address, tuple):
                raise TypeError(
                    "source_address must be IP address string or (ip, port) tuple"
                )

        if not self.ssl_context:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

            self.ssl_context.orig_wrap_socket = self.ssl_context.wrap_socket
            self.ssl_context.wrap_socket = self.wrap_socket

            if self.server_hostname:
                self.ssl_context.server_hostname = self.server_hostname
                self.ssl_context.check_hostname = False

            self.ssl_context.set_ciphers(self.cipherSuite)
            self.ssl_context.set_ecdh_curve(self.ecdhCurve)
            self.ssl_context.options |= (ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1)

        super(CipherSuiteAdapter, self).__init__(**kwargs)

    # ------------------------------------------------------------------------------- #

    def wrap_socket(self, *args, **kwargs):
        if hasattr(self.ssl_context, 'server_hostname') and self.ssl_context.server_hostname:
            kwargs['server_hostname'] = self.ssl_context.server_hostname
            self.ssl_context.check_hostname = False
        else:
            self.ssl_context.check_hostname = True
        return self.ssl_context.orig_wrap_socket(*args, **kwargs)

    # ------------------------------------------------------------------------------- #

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        kwargs['source_address'] = self.source_address
        return super(CipherSuiteAdapter, self).init_poolmanager(*args, **kwargs)

    # ------------------------------------------------------------------------------- #

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        kwargs['source_address'] = self.source_address
        return super(CipherSuiteAdapter, self).proxy_manager_for(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


ORIGIN_CIPHERS = (
    'ECDH+AESGCM:DH+AESGCM:ECDH+AES256:ECDH+AES128:DH+AES256:DH+AES:ECDH+HIGH:DH+HIGH:ECDH+3DES:DH+3DES:RSA+AESGCM'
    ':RSA+AES:RSA+HIGH:RSA+3DES')


class DESAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        # 在请求中重新启用 3DES 支持的 TransportAdapter
        CIPHERS = ORIGIN_CIPHERS.split(":")
        random.shuffle(CIPHERS)
        # print("1:", CIPHERS)
        CIPHERS = ":".join(CIPHERS)
        # print("2:", CIPHERS)
        self.COPHERS = CIPHERS + ":!aNULL:!eNULL:!MD5"
        super(DESAdapter, self).__init__(*args, **kwargs)

    # 在一般情况下，当我们实现一个子类的时候，__init__的第一行应该是super().__init__(*args, **kwargs)，
    # 但是由于init_poolmanager和proxy_manager_for是复写了父类的两个方法，
    # 这两个方法是在执行super().__init__(*args, **kwargs)的时候就执行的。
    # 所以，我们随机设置 Cipher Suits 的时候，需要放在super().__init__(*args, **kwargs)的前面。
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=self.COPHERS)
        kwargs["ssl_context"] = context
        return super(DESAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=self.COPHERS)
        kwargs["ssl_context"] = context
        return super(DESAdapter, self).proxy_manager_for(*args, **kwargs)
