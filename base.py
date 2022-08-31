import os
from urllib.parse import urlparse, ParseResult

import requests
from scrapy import Selector
import requests.packages.urllib3

requests.packages.urllib3.disable_warnings()


class BaseSign:
    # 请求相关
    session: requests.Session
    base_url: str
    url_info: ParseResult
    content: list
    # 用户信息配置
    username: str
    password: str
    # 签到页配置
    index_path: str  # 签到页面路径
    form_hash_xpath: str  # 签到页面formhash
    sign_path: str  # 签到请求链接
    sign_text_xpath: str  # 签到文本匹配路径
    sign_text: str  # 签到文本

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

    def __init__(self, base_url, username, password, proxy=False):
        self.url_info = urlparse(base_url)
        self.base_url = base_url
        self.username = username
        self.password = password
        self.content = list()
        self.session = requests.session()
        if proxy:
            proxy = os.getenv('SIGN_UP_PROXY')
            if proxy is not None:
                self.session.proxies.update({
                    'http': 'http://' + proxy,
                    'https': 'http://' + proxy
                })
        self.session.verify = False

        print(f"自助脚本初始化完成：{base_url}")

    def login(self) -> bool:
        print("需要实现")
        return False

    def sign(self) -> bool:
        qd_response = self.session.get(f"{self.base_url}/{self.index_path}")
        sign_selector = Selector(response=qd_response)
        sign_info = sign_selector.xpath(self.sign_text_xpath).extract_first()
        self.pwl(sign_info)
        if sign_info and sign_info.strip() == self.sign_text:
            self.pwl("进行签到中...")
            form_hash = sign_selector.xpath(self.form_hash_xpath).extract_first()
            if form_hash == "":
                self.pwl("获取签到表单验证失败")
                return False
            response = self.session.get(
                f"{self.base_url}/{self.sign_path}" % form_hash)
            result_selector = Selector(response=response)
            result = result_selector.xpath("/root/text()").extract_first()
            self.pwl(f"签到异常信息：{result}")
            if result:
                return False
            else:
                return True
        return True

    def pwl(self, c: str):
        print(c)
        if c:
            self.content.append(c)

    def log(self) -> str:
        return "\n".join(self.content)
