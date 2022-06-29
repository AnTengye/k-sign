import json

from scrapy import Selector

from verify.gifcode import handle_yzm
from sign.base import BaseSign


class HaoSign(BaseSign):
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

    def __init__(self, username, password):
        super(HaoSign, self).__init__("https://www.hao4k.cn", username, password)

    def login(self, times=3) -> bool:
        if times == 0:
            print("失败次数过多")
            return False
        print(f"进行 {self.username} 登录-times:{times}")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_data = selector.re(r"formhash:'(\w*)'")
        discode_data = selector.re(r"discode: '(\w*)'")
        sec_data = selector.re(r"seccodehash: '(\w*)'")
        update_data = selector.re(r"update=([0-9]*)&")
        sec_hash = ""
        form_hash = ""
        update = ""
        discode = ""
        if len(form_data) != 0:
            form_hash = form_data[0]
        if len(sec_data) != 0:
            sec_hash = sec_data[0]
        if len(update_data) != 0:
            update = update_data[0]
        if len(discode_data) != 0:
            discode = discode_data[0]
        if sec_hash and form_hash:
            verify_code = self.code(sec_hash, update)
            url = f"{self.base_url}/plugin.php?id=jzsjiale_isms:api"
            payload = f'module=loginmima&version=1&loginsubmit=yes&discode={discode}&type=auto&account={self.username}&password={self.password}&questionid=0&answer=&seccodehash={sec_hash}&seccodeverify={verify_code}&formhash={form_hash}&logintype=mima&device=mobile&cookietime=2592000&referer=https%3A%2F%2Fwww.hao4k.cn%2F.%2F'
            headers = {
                'authority': self.url_info.hostname,
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'pragma': 'no-cache',
                'referer': f'{self.base_url}/member.php?mod=logging&action=login',
                'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Mobile Safari/537.36'
            }
            response = self.session.post(url, headers=headers, data=payload)
            try:
                result = json.loads(response.text)
                if result.get("code") == "1":
                    print("登录失败：", self.err_msg_dict.get(result.get("msg", ""), result.get("msg", "")))
                    return self.login(times - 1)
                elif result.get("code") == "0":
                    print("登录成功")
                    return True
                else:
                    print(result)
                    return self.login(times - 1)
            except Exception as e:
                print("请求异常:\n", response.text)
                return False

    def code(self, sec_hash, update) -> str:
        url = f"{self.base_url}/misc.php?mod=seccode&update={update}&idhash={sec_hash}"
        payload = {}
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
            'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Mobile Safari/537.36'
        }
        response = self.session.get(url, headers=headers, data=payload)
        return handle_yzm(50, response.content)
