import nacl.signing
import nacl.encoding

class Identity:
    def __init__(self, signing_key: nacl.signing.SigningKey):
        self._key = signing_key
        # 地址设为十六进制格式的公钥
        self.address = self._key.verify_key.encode(nacl.encoding.HexEncoder).decode()

    @classmethod
    def from_seed(cls, seed_hex: str):
        return cls(nacl.signing.SigningKey(seed_hex, encoder=nacl.encoding.HexEncoder))

    def sign(self, message: bytes) -> str:
        # 返回十六进制格式的签名
        return self._key.sign(message).signature.hex()
