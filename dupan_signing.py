"""Offline Android client signatures for the Baidu Netdisk task-center flow.

This module never contacts the App or the network. The encrypted SK and account
UID are private inputs exported once from the same logged-in Android profile.
It does not generate the Sofire ``z`` value or the HTJ ``jt`` value.
"""

import base64
import binascii
import hashlib
import re


# MD5 of the signing certificate in the verified Baidu Netdisk 13.32.1 APK.
APP_CERT_MD5 = "ae5821440fab5e1a61a025f014bd8972"
RCHANNEL_AK = "1e34f40405355a992583c9d7b166cd39"


def _rc4(data, key):
    state = list(range(256))
    position = 0
    for index in range(256):
        position = (position + state[index] + key[index % len(key)]) % 256
        state[index], state[position] = state[position], state[index]
    left = right = 0
    result = bytearray()
    for value in data:
        left = (left + 1) % 256
        right = (right + state[left]) % 256
        state[left], state[right] = state[right], state[left]
        result.append(value ^ state[(state[left] + state[right]) % 256])
    return bytes(result)


def native_rand_pair(bduss, uid, encrypted_sk, timestamp, devuid, version,
                     certificate_md5=APP_CERT_MD5):
    """Return the Android client's ``rand`` and ``rand2`` for one timestamp.

    The result is only an offline signature match. It does not prove that an
    ``antisave`` reward request without App/HTJ fields will be accepted.
    """
    if (not isinstance(bduss, str) or not bduss or len(bduss) > 4096 or
            re.search(r"[\r\n\x00]", bduss)):
        raise ValueError("invalid BDUSS")
    if not isinstance(uid, str) or not re.fullmatch(r"[0-9]{1,24}", uid):
        raise ValueError("invalid account UID")
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{10}", timestamp):
        raise ValueError("invalid timestamp")
    if (not isinstance(devuid, str) or not devuid or len(devuid) > 2048 or
            re.search(r"[\r\n\x00]", devuid)):
        raise ValueError("invalid device UID")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9.]{3,20}", version):
        raise ValueError("invalid App version")
    if (not isinstance(certificate_md5, str) or
            not re.fullmatch(r"[0-9a-f]{32}", certificate_md5)):
        raise ValueError("invalid signing certificate digest")
    if not isinstance(encrypted_sk, str) or len(encrypted_sk) > 4096:
        raise ValueError("invalid encrypted SK")
    try:
        decoded = base64.b64decode(encrypted_sk, validate=True)
        sk = _rc4(decoded, uid.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeError, ValueError) as exc:
        raise ValueError("invalid encrypted SK") from exc
    if not sk or len(sk) > 4096 or re.search(r"[\r\n\x00]", sk):
        raise ValueError("invalid decrypted SK")
    def sha1(value):
        return hashlib.sha1(value.encode("utf-8")).hexdigest()

    common = sha1(bduss) + uid + sk + timestamp + devuid
    return sha1(common), sha1(common + version + certificate_md5)


def native_rchannel(uid, timestamp, channel):
    """Recreate the Android hybrid bridge's time-bound ``rchannel``."""
    if not isinstance(uid, str) or not re.fullmatch(r"[0-9]{1,24}", uid):
        raise ValueError("invalid account UID")
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{10}", timestamp):
        raise ValueError("invalid timestamp")
    if (not isinstance(channel, str) or not channel or len(channel) > 2048 or
            re.search(r"[\r\n\x00]", channel)):
        raise ValueError("invalid channel")
    return hashlib.md5((RCHANNEL_AK + uid + timestamp + channel).encode("utf-8")).hexdigest()
