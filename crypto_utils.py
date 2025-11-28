"""
暗号化ユーティリティ
メッセージの暗号化・復号化を提供
"""
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2
import base64
import hashlib


class CryptoManager:
    def __init__(self, shared_key: str = "disaster-mesh-2024"):
        """
        暗号化マネージャーの初期化

        Args:
            shared_key: 共有秘密鍵（実運用では安全な方法で配布）
        """
        # 共有鍵から256ビットのAES鍵を生成
        self.key = PBKDF2(shared_key, b"mesh-network-salt", dkLen=32)

    def encrypt(self, plaintext: str) -> str:
        """
        平文を暗号化

        Args:
            plaintext: 暗号化する平文

        Returns:
            Base64エンコードされた暗号文（IV + 暗号化データ）
        """
        # ランダムなIV（初期化ベクトル）を生成
        iv = get_random_bytes(AES.block_size)

        # AES暗号化オブジェクトを作成（CBCモード）
        cipher = AES.new(self.key, AES.MODE_CBC, iv)

        # パディング（PKCS7）
        plaintext_bytes = plaintext.encode('utf-8')
        padding_length = AES.block_size - (len(plaintext_bytes) % AES.block_size)
        padded_plaintext = plaintext_bytes + bytes([padding_length] * padding_length)

        # 暗号化
        ciphertext = cipher.encrypt(padded_plaintext)

        # IV + 暗号文をBase64エンコード
        return base64.b64encode(iv + ciphertext).decode('utf-8')

    def decrypt(self, ciphertext_b64: str) -> str:
        """
        暗号文を復号化

        Args:
            ciphertext_b64: Base64エンコードされた暗号文

        Returns:
            復号化された平文
        """
        try:
            # Base64デコード
            data = base64.b64decode(ciphertext_b64)

            # IVと暗号文を分離
            iv = data[:AES.block_size]
            ciphertext = data[AES.block_size:]

            # 復号化
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            padded_plaintext = cipher.decrypt(ciphertext)

            # パディング除去
            padding_length = padded_plaintext[-1]
            plaintext = padded_plaintext[:-padding_length]

            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"復号化エラー: {str(e)}")

    def hash_message(self, message: str) -> str:
        """
        メッセージのハッシュ値を計算（改ざん検出用）

        Args:
            message: ハッシュ化するメッセージ

        Returns:
            SHA-256ハッシュ値（16進数文字列）
        """
        return hashlib.sha256(message.encode('utf-8')).hexdigest()

    def verify_hash(self, message: str, expected_hash: str) -> bool:
        """
        メッセージのハッシュ値を検証

        Args:
            message: 検証するメッセージ
            expected_hash: 期待されるハッシュ値

        Returns:
            ハッシュが一致する場合True
        """
        return self.hash_message(message) == expected_hash


if __name__ == "__main__":
    # テスト
    crypto = CryptoManager()

    # 暗号化テスト
    original = "これは災害時のテストメッセージです"
    print(f"元のメッセージ: {original}")

    encrypted = crypto.encrypt(original)
    print(f"暗号化: {encrypted}")

    decrypted = crypto.decrypt(encrypted)
    print(f"復号化: {decrypted}")

    # ハッシュテスト
    hash_value = crypto.hash_message(original)
    print(f"ハッシュ: {hash_value}")
    print(f"検証結果: {crypto.verify_hash(original, hash_value)}")
