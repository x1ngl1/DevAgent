"""密钥加密存储工具 — 使用 Fernet (AES-128-CBC + HMAC) 替代 Base64"""
import os
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 加密密钥从环境变量读取，不存在则使用默认开发密钥（仅用于本地开发）
# 生产环境务必设置 FERNET_KEY 环境变量
_FERNET_KEY = None


def _get_fernet() -> Optional[object]:
    """获取 Fernet 实例"""
    global _FERNET_KEY
    try:
        from cryptography.fernet import Fernet
        key = os.getenv("FERNET_KEY")
        if key:
            return Fernet(key.encode() if isinstance(key, str) else key)
        # 开发环境：使用项目级固定密钥（仍比 Base64 安全）
        if _FERNET_KEY is None:
            _FERNET_KEY = Fernet.generate_key()
        return Fernet(_FERNET_KEY)
    except ImportError:
        logger.warning("cryptography not installed, falling back to base64")
        return None
    except Exception as e:
        logger.error(f"Fernet init failed: {e}")
        return None


def encrypt_api_key(plaintext: str) -> str:
    """加密 API Key，返回 Base64 密文"""
    if not plaintext:
        return ""
    f = _get_fernet()
    if f:
        try:
            return f.encrypt(plaintext.encode()).decode()
        except Exception as e:
            logger.error(f"Encrypt failed: {e}")
    # 降级：Base64 编码（仅当 cryptography 不可用时）
    return base64.b64encode(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """解密 API Key，返回明文"""
    if not ciphertext:
        return ""

    # 1) 先尝试 Base64 解码（兼容旧数据格式）
    try:
        decoded = base64.b64decode(ciphertext)
        plaintext = decoded.decode("utf-8")
        # 如果解码出来全是可读 ASCII / 常见 Key 字符，说明是旧格式 Base64
        if plaintext.isprintable() or all(32 <= ord(c) < 127 or c in '\n\r\t' for c in plaintext):
            return plaintext
    except Exception:
        pass  # 不是 Base64，继续尝试 Fernet

    # 2) 尝试 Fernet 解密
    f = _get_fernet()
    if f:
        try:
            return f.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            logger.warning(f"Fernet decrypt failed: {e}")

    # 3) 都失败
    logger.error("Failed to decrypt API key")
    return ""


def generate_fernet_key() -> str:
    """生成新的 Fernet 密钥（用于初始化）"""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()
