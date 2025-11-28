"""
メッシュネットワークノードのコア実装
P2P通信、ノード検出、メッセージ中継を実装
"""
import socket
import threading
import json
import time
import uuid
from typing import Dict, List, Callable, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from crypto_utils import CryptoManager


@dataclass
class NodeInfo:
    """ノード情報"""
    node_id: str
    ip_address: str
    port: int
    last_seen: float
    hostname: str


@dataclass
class Message:
    """メッセージ構造"""
    msg_id: str
    source_id: str
    dest_id: str
    payload: str
    timestamp: float
    ttl: int  # Time To Live (最大ホップ数)
    msg_type: str  # "text", "file", "control"
    route: List[str]  # 経由したノードのリスト


class MeshNode:
    """メッシュネットワークノード"""

    DISCOVERY_PORT = 5000
    DATA_PORT = 5001
    BROADCAST_INTERVAL = 30  # 秒
    NODE_TIMEOUT = 90  # 秒
    MAX_TTL = 20

    def __init__(self, hostname: Optional[str] = None):
        """
        メッシュノードの初期化

        Args:
            hostname: ノードの表示名（Noneの場合は自動生成）
        """
        self.node_id = str(uuid.uuid4())
        self.hostname = hostname or socket.gethostname()
        self.crypto = CryptoManager()

        # ノード管理
        self.known_nodes: Dict[str, NodeInfo] = {}
        self.known_nodes_lock = threading.Lock()

        # メッセージ管理
        self.message_cache: Set[str] = set()  # 重複防止用
        self.message_callbacks: List[Callable] = []

        # ソケット
        self.discovery_socket: Optional[socket.socket] = None
        self.data_socket: Optional[socket.socket] = None
        self.running = False

        # スレッド
        self.threads: List[threading.Thread] = []

        print(f"[ノード初期化] ID: {self.node_id[:8]}... / 名前: {self.hostname}")

    def start(self):
        """ノードを起動"""
        self.running = True

        # Discoveryソケットの初期化
        self._init_discovery_socket()

        # データ受信ソケットの初期化
        self._init_data_socket()

        # スレッドの起動
        self.threads = [
            threading.Thread(target=self._discovery_listener, daemon=True),
            threading.Thread(target=self._discovery_broadcaster, daemon=True),
            threading.Thread(target=self._data_listener, daemon=True),
            threading.Thread(target=self._cleanup_old_nodes, daemon=True),
        ]

        for thread in self.threads:
            thread.start()

        print(f"[ノード起動] {self.hostname} が起動しました")

    def stop(self):
        """ノードを停止"""
        self.running = False

        # ソケットのクローズ
        if self.discovery_socket:
            self.discovery_socket.close()
        if self.data_socket:
            self.data_socket.close()

        print(f"[ノード停止] {self.hostname} を停止しました")

    def _init_discovery_socket(self):
        """Discoveryソケットの初期化"""
        self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.discovery_socket.bind(('', self.DISCOVERY_PORT))

    def _init_data_socket(self):
        """データ受信ソケットの初期化"""
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.data_socket.bind(('0.0.0.0', self.DATA_PORT))
        self.data_socket.listen(10)

    def _discovery_broadcaster(self):
        """定期的にノード情報をブロードキャスト"""
        while self.running:
            try:
                discovery_msg = {
                    'type': 'discovery',
                    'node_id': self.node_id,
                    'hostname': self.hostname,
                    'port': self.DATA_PORT,
                    'timestamp': time.time()
                }

                data = json.dumps(discovery_msg).encode('utf-8')
                self.discovery_socket.sendto(data, ('<broadcast>', self.DISCOVERY_PORT))

            except Exception as e:
                print(f"[ブロードキャストエラー] {e}")

            time.sleep(self.BROADCAST_INTERVAL)

    def _discovery_listener(self):
        """他のノードからのDiscoveryメッセージを受信"""
        while self.running:
            try:
                data, addr = self.discovery_socket.recvfrom(1024)
                msg = json.loads(data.decode('utf-8'))

                if msg.get('type') == 'discovery' and msg['node_id'] != self.node_id:
                    node_info = NodeInfo(
                        node_id=msg['node_id'],
                        ip_address=addr[0],
                        port=msg['port'],
                        last_seen=time.time(),
                        hostname=msg['hostname']
                    )

                    with self.known_nodes_lock:
                        if msg['node_id'] not in self.known_nodes:
                            print(f"[新規ノード検出] {node_info.hostname} ({node_info.ip_address})")
                        self.known_nodes[msg['node_id']] = node_info

            except Exception as e:
                if self.running:
                    print(f"[Discovery受信エラー] {e}")

    def _data_listener(self):
        """データメッセージを受信"""
        while self.running:
            try:
                client_socket, addr = self.data_socket.accept()

                # 別スレッドで処理
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, addr),
                    daemon=True
                ).start()

            except Exception as e:
                if self.running:
                    print(f"[データ受信エラー] {e}")

    def _handle_client(self, client_socket: socket.socket, addr):
        """クライアントからのメッセージを処理"""
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
                message.payload = decrypted_payload
            except Exception as e:
                print(f"[復号化エラー] {e}")
                return

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
                    self._forward_message(message)
                else:
                    print(f"[TTL切れ] メッセージ {message.msg_id[:8]}... をドロップ")

        except Exception as e:
            print(f"[クライアント処理エラー] {e}")
        finally:
            client_socket.close()

    def send_message(self, dest_id: str, payload: str, msg_type: str = "text") -> bool:
        """
        メッセージを送信

        Args:
            dest_id: 宛先ノードID（"broadcast"で全ノードへ）
            payload: 送信するデータ
            msg_type: メッセージタイプ

        Returns:
            送信成功時True
        """
        try:
            # 暗号化
            encrypted_payload = self.crypto.encrypt(payload)

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
                # ブロードキャスト
                return self._broadcast_message(message)
            else:
                # ユニキャスト
                return self._forward_message(message)

        except Exception as e:
            print(f"[送信エラー] {e}")
            return False

    def _forward_message(self, message: Message) -> bool:
        """メッセージを転送"""
        with self.known_nodes_lock:
            nodes = list(self.known_nodes.values())

        if not nodes:
            print("[転送失敗] 接続ノードがありません")
            return False

        # 既に経由したノードは除外
        available_nodes = [n for n in nodes if n.node_id not in message.route]

        if not available_nodes:
            print("[転送失敗] 転送可能なノードがありません")
            return False

        # 最初の利用可能なノードに送信（改善の余地あり: 最適経路選択）
        target_node = available_nodes[0]

        return self._send_to_node(target_node, message)

    def _broadcast_message(self, message: Message) -> bool:
        """すべてのノードにメッセージを送信"""
        with self.known_nodes_lock:
            nodes = list(self.known_nodes.values())

        success_count = 0
        for node in nodes:
            if self._send_to_node(node, message):
                success_count += 1

        return success_count > 0

    def _send_to_node(self, node: NodeInfo, message: Message) -> bool:
        """特定のノードにメッセージを送信"""
        try:
            # TCP接続
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((node.ip_address, node.port))

            # メッセージをJSON化
            data = json.dumps(asdict(message)).encode('utf-8')
            data_size = len(data)

            # サイズを送信（4バイト）
            sock.sendall(data_size.to_bytes(4, byteorder='big'))

            # データを送信
            sock.sendall(data)

            sock.close()
            return True

        except Exception as e:
            print(f"[ノード送信エラー] {node.hostname}: {e}")
            return False

    def _cleanup_old_nodes(self):
        """古いノード情報を削除"""
        while self.running:
            time.sleep(30)

            current_time = time.time()
            with self.known_nodes_lock:
                expired_nodes = [
                    node_id for node_id, node in self.known_nodes.items()
                    if current_time - node.last_seen > self.NODE_TIMEOUT
                ]

                for node_id in expired_nodes:
                    node = self.known_nodes.pop(node_id)
                    print(f"[ノード削除] {node.hostname} (タイムアウト)")

    def register_message_callback(self, callback: Callable[[Message], None]):
        """
        メッセージ受信時のコールバックを登録

        Args:
            callback: メッセージを受け取る関数
        """
        self.message_callbacks.append(callback)

    def _trigger_callbacks(self, message: Message):
        """コールバック関数を実行"""
        for callback in self.message_callbacks:
            try:
                callback(message)
            except Exception as e:
                print(f"[コールバックエラー] {e}")

    def get_known_nodes(self) -> List[NodeInfo]:
        """接続中のノード一覧を取得"""
        with self.known_nodes_lock:
            return list(self.known_nodes.values())


if __name__ == "__main__":
    # テスト用
    node = MeshNode("テストノード")
    node.start()

    def on_message(msg: Message):
        print(f"\n[メッセージ受信] {msg.source_id[:8]}...: {msg.payload}")

    node.register_message_callback(on_message)

    print("メッシュノードを起動しました。Ctrl+Cで終了します。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop()
