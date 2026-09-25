"""Offline Android client signatures for the Baidu Netdisk task-center flow.

This module never contacts the App or the network. The encrypted SK, account UID,
and Sofire material are private inputs exported once from the same logged-in
Android profile. The claim-probe combines these offline signatures with the
separate Node/jsdom HTJ generator; this module itself never generates ``jt``.
"""

import base64
import binascii
import hashlib
import re
import secrets


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


def sofire_z(seed, status, flag1, flag2, flag3, timestamp, random_hex=None):
    """Recreate Sofire Asc.itb's 60-character value without Android.

    ``seed`` and the four flags are persistent, account/device-bound inputs.
    They must be kept in private state.  This does not produce the separate
    HTJ ``jt`` required by the reward endpoint.
    """
    if not isinstance(seed, str) or not re.fullmatch(r"[0-9A-F]{32}", seed):
        raise ValueError("invalid Sofire seed")
    if any(type(value) is not int or not 0 <= value <= 255
           for value in (status, flag1, flag2)):
        raise ValueError("invalid Sofire flags")
    if not isinstance(flag3, str) or not re.fullmatch(r"[0-9A-F]{2}", flag3):
        raise ValueError("invalid Sofire status suffix")
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{10}", timestamp):
        raise ValueError("invalid timestamp")
    instant = int(timestamp)
    if instant > 0xffffffff:
        raise ValueError("timestamp is outside Sofire range")
    if random_hex is None:
        random_hex = secrets.token_hex(3).upper()
    if not isinstance(random_hex, str) or not re.fullmatch(r"[0-9A-F]{6}", random_hex):
        raise ValueError("invalid Sofire nonce")

    shifted = (instant + 0x9AAC0F00) & 0xffffffff
    clock_hex = f"{instant:08X}"
    result = [""] * 60

    def put(start, value):
        result[start:start + len(value)] = value

    put(0, f"{(shifted >> 10) & 0xff:02X}")
    put(2, "58")
    for start, offset in ((4, 16), (8, 8), (12, 28), (20, 4),
                          (24, 0), (30, 24), (36, 12), (40, 20)):
        put(start, seed[offset:offset + 4][::-1])
    put(16, f"{ord(seed[16]) ^ status:02X}")
    put(18, f"{(shifted >> 18) & 0xff:02X}")
    put(28, f"{ord(seed[10]) ^ flag2:02X}")
    put(34, f"{ord(seed[6]) ^ flag1:02X}")
    put(44, random_hex[:2])
    put(46, clock_hex[4:])
    put(50, random_hex[2:4])
    put(52, flag3)
    put(54, random_hex[4:])
    put(56, clock_hex[:4])
    return "".join(result)


def extract_sofire_material(z):
    """Extract stable private inputs from one locally captured official z.

    This is an offline import helper, not a way to reuse a historical dynamic
    value. The caller must never log the returned material.
    """
    if not isinstance(z, str) or not re.fullmatch(r"[0-9A-F]{60}", z):
        raise ValueError("invalid Sofire value")
    seed = "".join(z[start:start + 4][::-1]
                   for start in (24, 20, 8, 36, 4, 40, 30, 12))
    timestamp = str(int(z[56:60] + z[46:50], 16))
    material = {"seed": seed, "status": int(z[16:18], 16) ^ ord(seed[16]),
                "flag1": int(z[34:36], 16) ^ ord(seed[6]),
                "flag2": int(z[28:30], 16) ^ ord(seed[10]),
                "flag3": z[52:54]}
    random_hex = z[44:46] + z[50:52] + z[54:56]
    if sofire_z(**material, timestamp=timestamp, random_hex=random_hex) != z:
        raise ValueError("inconsistent Sofire value")
    return material
