from rustchain.identity import Identity
def test_identity_signing():
    # "test" * 8 是 32 字节的种子，符合 Ed25519 要求
    id = Identity.from_seed("74657374" * 8)
    msg = b"hello"
    sig = id.sign(msg)
    assert len(sig) == 128 # hex 格式的 64 字节签名长度为 128
