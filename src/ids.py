"""ULID 生成：48 位毫秒时间戳 + 80 位随机数，Crockford Base32 编码成 26 字符。

为什么不用自增：多端/离线要能各自生成，且不暴露"存了多少条"。
为什么不装 ulid 库：二十行够了，还省一个依赖。
"""

import secrets
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_id() -> str:
    value = ((time.time_ns() // 1_000_000) << 80) | secrets.randbits(80)
    return "".join(_ALPHABET[(value >> shift) & 31] for shift in range(125, -1, -5))
