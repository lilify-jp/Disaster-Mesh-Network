"""
中継専用モード（ヘッドレスモード）
GUIなしで最小限のリソース消費でノードを稼働
"""
import time
import signal
import sys
from mesh_node import MeshNode, Message


class RelayNode:
    """中継専用ノード（省電力・低リソース）"""

    def __init__(self, hostname: str = "中継専用ノード"):
        """
        中継専用ノードの初期化

        Args:
            hostname: ノード名
        """
        self.node = MeshNode(hostname)
        self.running = False
        self.stats = {
            'messages_relayed': 0,
            'messages_received': 0,
            'start_time': time.time()
        }

        # シグナルハンドラの設定
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def start(self):
        """中継専用ノードを起動"""
        print("=" * 60)
        print("  中継専用モード (Relay-Only Mode)")
        print("=" * 60)
        print()
        print(f"ノード名: {self.node.hostname}")
        print(f"ノードID: {self.node.node_id}")
        print()
        print("このノードは中継専用で稼働します。")
        print("- GUI非表示")
        print("- 最小限のリソース消費")
        print("- メッセージの自動中継のみ")
        print()
        print("終了: Ctrl+C")
        print("=" * 60)
        print()

        # メッセージ受信コールバック（統計のみ記録）
        self.node.register_message_callback(self._on_message)

        # ノード起動
        self.node.start()
        self.running = True

        # メインループ（定期的な統計表示）
        self._run_loop()

    def _on_message(self, message: Message):
        """
        メッセージ受信時の処理（統計のみ）

        Args:
            message: 受信メッセージ
        """
        self.stats['messages_received'] += 1

        # 自分宛てでない場合は中継としてカウント
        if message.dest_id != self.node.node_id and message.dest_id != "broadcast":
            self.stats['messages_relayed'] += 1

    def _run_loop(self):
        """メインループ（統計表示）"""
        last_stats_time = time.time()

        while self.running:
            try:
                # 30秒ごとに統計を表示
                if time.time() - last_stats_time >= 30:
                    self._print_stats()
                    last_stats_time = time.time()

                # CPU負荷軽減のためスリープ
                time.sleep(1)

            except KeyboardInterrupt:
                break

        self._shutdown()

    def _print_stats(self):
        """統計情報を表示"""
        uptime = time.time() - self.stats['start_time']
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        known_nodes = self.node.get_known_nodes()

        print(f"\n[統計] 稼働時間: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print(f"  接続ノード数: {len(known_nodes)}")
        print(f"  受信メッセージ: {self.stats['messages_received']}")
        print(f"  中継メッセージ: {self.stats['messages_relayed']}")

        if known_nodes:
            print(f"  接続中のノード:")
            for node in known_nodes:
                print(f"    - {node.hostname} ({node.ip_address})")

    def _signal_handler(self, signum, frame):
        """シグナルハンドラ（終了処理）"""
        print("\n\n終了シグナルを受信しました...")
        self.running = False

    def _shutdown(self):
        """シャットダウン処理"""
        print("\n中継専用ノードを停止します...")

        # 最終統計を表示
        self._print_stats()

        # ノードを停止
        self.node.stop()

        print("\n正常に終了しました。")
        sys.exit(0)


def main():
    """メインエントリーポイント"""
    import argparse

    parser = argparse.ArgumentParser(
        description="中継専用モード - GUI非表示・低リソース消費"
    )

    parser.add_argument(
        "--hostname",
        type=str,
        default="中継専用ノード",
        help="ノード名を指定"
    )

    args = parser.parse_args()

    # 中継専用ノードを起動
    relay = RelayNode(hostname=args.hostname)
    relay.start()


if __name__ == "__main__":
    main()
