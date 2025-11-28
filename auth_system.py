"""
認証システム - デジタル署名による強化されたセキュリティ
ECDSA（楕円曲線デジタル署名アルゴリズム）を使用
"""
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS
from Crypto.Hash import SHA256
import base64
import json
import os
from typing import Tuple, Optional


class AuthenticationManager:
    """認証マネージャー - 公開鍵暗号方式"""

    def __init__(self, keys_directory: str = "./keys"):
        """
        認証マネージャーの初期化

        Args:
            keys_directory: 鍵ファイルの保存ディレクトリ
        """
        self.keys_directory = keys_directory
        self.private_key: Optional[ECC.EccKey] = None
        self.public_key: Optional[ECC.EccKey] = None

        # 鍵ディレクトリの作成
        os.makedirs(keys_directory, exist_ok=True)

    def generate_keypair(self, node_id: str) -> Tuple[str, str]:
        """
        公開鍵・秘密鍵ペアを生成

        Args:
            node_id: ノードID

        Returns:
            (秘密鍵ファイルパス, 公開鍵ファイルパス)
        """
        # ECDSA鍵ペアを生成（P-256カーブ）
        self.private_key = ECC.generate(curve='P-256')
        self.public_key = self.private_key.public_key()

        # ファイルパス
        private_key_path = os.path.join(self.keys_directory, f"{node_id}_private.pem")
        public_key_path = os.path.join(self.keys_directory, f"{node_id}_public.pem")

        # 秘密鍵を保存
        with open(private_key_path, 'wt') as f:
            f.write(self.private_key.export_key(format='PEM'))

        # 公開鍵を保存
        with open(public_key_path, 'wt') as f:
            f.write(self.public_key.export_key(format='PEM'))

        print(f"[鍵生成] 鍵ペアを生成しました")
        print(f"  秘密鍵: {private_key_path}")
        print(f"  公開鍵: {public_key_path}")

        return private_key_path, public_key_path

    def load_keypair(self, node_id: str) -> bool:
        """
        既存の鍵ペアを読み込み

        Args:
            node_id: ノードID

        Returns:
            読み込み成功時True
        """
        private_key_path = os.path.join(self.keys_directory, f"{node_id}_private.pem")
        public_key_path = os.path.join(self.keys_directory, f"{node_id}_public.pem")

        if not os.path.exists(private_key_path) or not os.path.exists(public_key_path):
            return False

        try:
            # 秘密鍵を読み込み
            with open(private_key_path, 'rt') as f:
                self.private_key = ECC.import_key(f.read())

            # 公開鍵を読み込み
            with open(public_key_path, 'rt') as f:
                self.public_key = ECC.import_key(f.read())

            print(f"[鍵読み込み] 既存の鍵ペアを読み込みました")
            return True

        except Exception as e:
            print(f"[鍵読み込みエラー] {e}")
            return False

    def sign_message(self, message: str, node_id: str) -> str:
        """
        メッセージにデジタル署名を付与

        Args:
            message: 署名するメッセージ
            node_id: 署名者のノードID

        Returns:
            署名付きメッセージ（JSON）
        """
        if not self.private_key:
            raise ValueError("秘密鍵がロードされていません")

        # メッセージのハッシュを計算
        h = SHA256.new(message.encode('utf-8'))

        # デジタル署名を生成
        signer = DSS.new(self.private_key, 'fips-186-3')
        signature = signer.sign(h)

        # 署名をBase64エンコード
        signature_b64 = base64.b64encode(signature).decode('utf-8')

        # 公開鍵もBase64エンコード（他のノードが検証できるように）
        public_key_pem = self.public_key.export_key(format='PEM')
        public_key_b64 = base64.b64encode(public_key_pem.encode('utf-8')).decode('utf-8')

        # 署名付きメッセージを作成
        signed_message = {
            'message': message,
            'signature': signature_b64,
            'public_key': public_key_b64,
            'signer_id': node_id
        }

        return json.dumps(signed_message)

    def verify_signature(self, signed_message_json: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        デジタル署名を検証

        Args:
            signed_message_json: 署名付きメッセージ（JSON）

        Returns:
            (検証成功, メッセージ, 署名者ID)
        """
        try:
            signed_message = json.loads(signed_message_json)

            message = signed_message['message']
            signature_b64 = signed_message['signature']
            public_key_b64 = signed_message['public_key']
            signer_id = signed_message['signer_id']

            # 署名をデコード
            signature = base64.b64decode(signature_b64)

            # 公開鍵をデコード
            public_key_pem = base64.b64decode(public_key_b64).decode('utf-8')
            public_key = ECC.import_key(public_key_pem)

            # メッセージのハッシュを計算
            h = SHA256.new(message.encode('utf-8'))

            # 署名を検証
            verifier = DSS.new(public_key, 'fips-186-3')
            verifier.verify(h, signature)

            # 検証成功
            return True, message, signer_id

        except ValueError:
            # 署名が無効
            return False, None, None
        except Exception as e:
            print(f"[署名検証エラー] {e}")
            return False, None, None

    def export_public_key(self) -> str:
        """
        公開鍵をエクスポート（他のノードと共有用）

        Returns:
            Base64エンコードされた公開鍵
        """
        if not self.public_key:
            raise ValueError("公開鍵がロードされていません")

        public_key_pem = self.public_key.export_key(format='PEM')
        return base64.b64encode(public_key_pem.encode('utf-8')).decode('utf-8')

    def import_public_key(self, public_key_b64: str) -> ECC.EccKey:
        """
        公開鍵をインポート（他のノードの公開鍵を受け取る）

        Args:
            public_key_b64: Base64エンコードされた公開鍵

        Returns:
            ECC公開鍵オブジェクト
        """
        public_key_pem = base64.b64decode(public_key_b64).decode('utf-8')
        return ECC.import_key(public_key_pem)


class TrustManager:
    """信頼管理システム - 信頼できるノードを管理"""

    def __init__(self, trust_file: str = "./trusted_nodes.json"):
        """
        信頼管理システムの初期化

        Args:
            trust_file: 信頼されたノード情報のファイル
        """
        self.trust_file = trust_file
        self.trusted_nodes = {}  # {node_id: public_key_b64}
        self.trust_scores = {}   # {node_id: score}
        self.load_trusted_nodes()

    def load_trusted_nodes(self):
        """信頼されたノードを読み込み"""
        if not os.path.exists(self.trust_file):
            return

        try:
            with open(self.trust_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.trusted_nodes = data.get('trusted_nodes', {})
                self.trust_scores = data.get('trust_scores', {})

            print(f"[信頼管理] {len(self.trusted_nodes)} 件の信頼ノードを読み込みました")

        except Exception as e:
            print(f"[信頼管理読み込みエラー] {e}")

    def save_trusted_nodes(self):
        """信頼されたノードを保存"""
        try:
            with open(self.trust_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'trusted_nodes': self.trusted_nodes,
                    'trust_scores': self.trust_scores
                }, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"[信頼管理保存エラー] {e}")

    def add_trusted_node(self, node_id: str, public_key_b64: str, initial_score: int = 50):
        """
        信頼されたノードを追加

        Args:
            node_id: ノードID
            public_key_b64: 公開鍵（Base64）
            initial_score: 初期信頼スコア（0-100）
        """
        self.trusted_nodes[node_id] = public_key_b64
        self.trust_scores[node_id] = initial_score
        self.save_trusted_nodes()

        print(f"[信頼管理] ノード {node_id[:8]}... を信頼リストに追加（スコア: {initial_score}）")

    def is_trusted(self, node_id: str, min_score: int = 30) -> bool:
        """
        ノードが信頼されているか確認

        Args:
            node_id: ノードID
            min_score: 最低信頼スコア

        Returns:
            信頼されている場合True
        """
        if node_id not in self.trusted_nodes:
            return False

        return self.trust_scores.get(node_id, 0) >= min_score

    def update_trust_score(self, node_id: str, delta: int):
        """
        信頼スコアを更新

        Args:
            node_id: ノードID
            delta: スコア変化量（+/-）
        """
        if node_id not in self.trust_scores:
            self.trust_scores[node_id] = 50

        # スコアを更新（0-100の範囲）
        self.trust_scores[node_id] = max(0, min(100, self.trust_scores[node_id] + delta))

        self.save_trusted_nodes()

        print(f"[信頼管理] ノード {node_id[:8]}... のスコアを更新: {self.trust_scores[node_id]}")

    def get_public_key(self, node_id: str) -> Optional[str]:
        """
        信頼されたノードの公開鍵を取得

        Args:
            node_id: ノードID

        Returns:
            公開鍵（Base64）、存在しない場合None
        """
        return self.trusted_nodes.get(node_id)

    def remove_untrusted_nodes(self, threshold: int = 10):
        """
        信頼スコアが低いノードを削除

        Args:
            threshold: 削除する信頼スコアの閾値
        """
        to_remove = [
            node_id for node_id, score in self.trust_scores.items()
            if score < threshold
        ]

        for node_id in to_remove:
            del self.trusted_nodes[node_id]
            del self.trust_scores[node_id]
            print(f"[信頼管理] ノード {node_id[:8]}... を信頼リストから削除（低スコア）")

        if to_remove:
            self.save_trusted_nodes()


if __name__ == "__main__":
    # テスト
    print("=== 認証システムテスト ===\n")

    # 認証マネージャーの作成
    auth = AuthenticationManager(keys_directory="./test_keys")

    # 鍵ペアの生成
    test_node_id = "test-node-123"
    auth.generate_keypair(test_node_id)

    # メッセージに署名
    original_message = "これは災害時の重要なメッセージです"
    print(f"\n元のメッセージ: {original_message}")

    signed_message = auth.sign_message(original_message, test_node_id)
    print(f"\n署名付きメッセージ:\n{signed_message[:100]}...")

    # 署名を検証
    is_valid, message, signer_id = auth.verify_signature(signed_message)
    print(f"\n署名検証結果: {is_valid}")
    print(f"メッセージ: {message}")
    print(f"署名者ID: {signer_id}")

    # 改ざんテスト
    print("\n=== 改ざんテスト ===")
    tampered_message = signed_message.replace("重要", "偽の")
    is_valid, message, signer_id = auth.verify_signature(tampered_message)
    print(f"改ざんされたメッセージの検証結果: {is_valid}")

    # 信頼管理テスト
    print("\n=== 信頼管理テスト ===")
    trust = TrustManager(trust_file="./test_trust.json")

    public_key = auth.export_public_key()
    trust.add_trusted_node(test_node_id, public_key, initial_score=80)

    print(f"信頼されているか: {trust.is_trusted(test_node_id)}")

    trust.update_trust_score(test_node_id, -10)
    print(f"スコア減少後: {trust.trust_scores[test_node_id]}")

    trust.update_trust_score(test_node_id, +20)
    print(f"スコア増加後: {trust.trust_scores[test_node_id]}")
