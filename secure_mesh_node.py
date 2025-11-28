"""
セキュア版メッシュノード - デジタル署名による認証を実装
mesh_node.pyを拡張してセキュリティを強化
"""
from mesh_node import MeshNode, Message, NodeInfo
from auth_system import AuthenticationManager, TrustManager
import json
from typing import Optional


class SecureMeshNode(MeshNode):
    """デジタル署名認証を実装したセキュアなメッシュノード"""

    def __init__(self, hostname: Optional[str] = None, enable_auth: bool = True):
        """
        セキュアメッシュノードの初期化

        Args:
            hostname: ノード名
            enable_auth: 認証を有効化するか（Falseの場合は従来の動作）
        """
        super().__init__(hostname)

        self.enable_auth = enable_auth

        if enable_auth:
            # 認証システムの初期化
            self.auth_manager = AuthenticationManager()
            self.trust_manager = TrustManager()

            # 鍵ペアの読み込みまたは生成
            if not self.auth_manager.load_keypair(self.node_id):
                print("[認証] 新規鍵ペアを生成します...")
                self.auth_manager.generate_keypair(self.node_id)
            else:
                print("[認証] 既存の鍵ペアを使用します")

            print(f"[認証] デジタル署名認証が有効化されました")

    def send_message(self, dest_id: str, payload: str, msg_type: str = "text") -> bool:
        """
        メッセージを送信（認証付き）

        Args:
            dest_id: 宛先ノードID（"broadcast"で全ノードへ）
            payload: 送信するデータ
            msg_type: メッセージタイプ

        Returns:
            送信成功時True
        """
        if self.enable_auth:
            # メッセージにデジタル署名を付与
            signed_payload = self.auth_manager.sign_message(payload, self.node_id)

            # 暗号化（従来通り）
            encrypted_payload = self.crypto.encrypt(signed_payload)
        else:
            # 認証なし（従来の動作）
            encrypted_payload = self.crypto.encrypt(payload)

        # Message構造体を作成
        import uuid
        import time
        message = Message(
            msg_id=str(uuid.uuid4()),
            source_id=self.node_id,
            dest_id=dest_id,
            payload=encrypted_payload,
            timestamp=time.time(),
            ttl=self.MAX_TTL,
            msg_type=msg_type,
            route=[self.node_id]
        )

        self.message_cache.add(message.msg_id)

        if dest_id == "broadcast":
            return self._broadcast_message(message)
        else:
            return self._forward_message(message)

    def _handle_client(self, client_socket, addr):
        """
        クライアントからのメッセージを処理（認証チェック付き）

        Args:
            client_socket: クライアントソケット
            addr: クライアントアドレス
        """
        try:
            # データサイズを受信（最初の4バイト）
            size_data = client_socket.recv(4)
            if not size_data:
                return

            data_size = int.from_bytes(size_data, byteorder='big')

            # データを受信
            data = b''
            while len(data) < data_size:
                chunk = client_socket.recv(min(4096, data_size - len(data)))
                if not chunk:
                    break
                data += chunk

            msg_dict = json.loads(data.decode('utf-8'))
            message = Message(**msg_dict)

            # 重複チェック
            if message.msg_id in self.message_cache:
                return

            self.message_cache.add(message.msg_id)

            # 復号化
            try:
                decrypted_payload = self.crypto.decrypt(message.payload)
            except Exception as e:
                print(f"[復号化エラー] {e}")
                return

            # 認証チェック
            if self.enable_auth:
                is_valid, original_message, signer_id = self.auth_manager.verify_signature(decrypted_payload)

                if not is_valid:
                    print(f"[認証失敗] 署名が無効なメッセージを受信: {message.source_id[:8]}...")

                    # 信頼スコアを減少
                    self.trust_manager.update_trust_score(message.source_id, -20)

                    # メッセージを破棄
                    return

                # 署名者IDとメッセージ送信元が一致するか確認
                if signer_id != message.source_id:
                    print(f"[認証失敗] 送信元IDと署名者IDが不一致")
                    self.trust_manager.update_trust_score(message.source_id, -30)
                    return

                # 信頼スコアを増加
                self.trust_manager.update_trust_score(message.source_id, +1)

                # 新規ノードの場合は信頼リストに追加
                if not self.trust_manager.is_trusted(message.source_id, min_score=0):
                    # 公開鍵を抽出してリストに追加
                    signed_data = json.loads(decrypted_payload)
                    public_key_b64 = signed_data.get('public_key')

                    if public_key_b64:
                        self.trust_manager.add_trusted_node(
                            message.source_id,
                            public_key_b64,
                            initial_score=50
                        )

                # 検証済みメッセージを使用
                message.payload = original_message

                print(f"[認証成功] ノード {message.source_id[:8]}... からのメッセージを検証")

            else:
                # 認証なし（従来の動作）
                message.payload = decrypted_payload

            # 経路に自分を追加
            message.route.append(self.node_id)

            # 宛先チェック
            if message.dest_id == self.node_id or message.dest_id == "broadcast":
                # 自分宛てのメッセージ
                self._trigger_callbacks(message)
            else:
                # 中継
                if message.ttl > 0:
                    message.ttl -= 1

                    # 信頼度チェック（認証有効時）
                    if self.enable_auth:
                        if not self.trust_manager.is_trusted(message.source_id, min_score=20):
                            print(f"[中継拒否] ノード {message.source_id[:8]}... の信頼スコアが低いため中継しません")
                            return

                    self._forward_message(message)
                else:
                    print(f"[TTL切れ] メッセージ {message.msg_id[:8]}... をドロップ")

        except Exception as e:
            print(f"[クライアント処理エラー] {e}")
        finally:
            client_socket.close()

    def get_trust_info(self) -> dict:
        """
        信頼情報を取得

        Returns:
            信頼スコア情報の辞書
        """
        if not self.enable_auth:
            return {}

        return {
            'trusted_nodes_count': len(self.trust_manager.trusted_nodes),
            'trust_scores': self.trust_manager.trust_scores
        }

    def cleanup_untrusted_nodes(self):
        """信頼スコアが低いノードを削除"""
        if self.enable_auth:
            self.trust_manager.remove_untrusted_nodes(threshold=10)


if __name__ == "__main__":
    # テスト用
    import time

    node = SecureMeshNode("セキュアテストノード", enable_auth=True)
    node.start()

    def on_message(msg: Message):
        print(f"\n[メッセージ受信] {msg.source_id[:8]}...: {msg.payload}")

    node.register_message_callback(on_message)

    print("セキュアメッシュノードを起動しました。Ctrl+Cで終了します。")
    print("認証システムが有効化されています。")

    try:
        while True:
            time.sleep(5)

            # 定期的に信頼情報を表示
            trust_info = node.get_trust_info()
            print(f"\n[信頼情報] 信頼ノード数: {trust_info.get('trusted_nodes_count', 0)}")

    except KeyboardInterrupt:
        node.stop()
