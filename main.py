"""
災害用メッシュネットワーク - メインアプリケーション
インターネット遮断時でも使える緊急通信システム
"""
import sys
import argparse
from gui import MeshNetworkGUI


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="災害用メッシュネットワーク - インターネット不要のP2P通信システム"
    )

    parser.add_argument(
        "--cli",
        action="store_true",
        help="CUIモードで起動（GUI非表示）"
    )

    parser.add_argument(
        "--hostname",
        type=str,
        default=None,
        help="ノード名を指定"
    )

    parser.add_argument(
        "--relay-only",
        action="store_true",
        help="中継専用モードで起動（GUI非表示、低リソース消費）"
    )

    parser.add_argument(
        "--secure",
        action="store_true",
        help="セキュア認証モードを有効化（デジタル署名による認証）"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  災害用メッシュネットワーク")
    print("  Disaster Mesh Network - Offline P2P Communication")
    print("=" * 60)
    print()
    print("インターネット回線を使わずに、近くのPC同士で")
    print("メッセージやファイルを転送します。")
    print()

    # 中継専用モード
    if args.relay_only:
        print("[中継専用モード] ヘッドレスモードで起動します")
        print()
        from relay_mode import RelayNode
        relay = RelayNode(hostname=args.hostname or "中継専用ノード")
        relay.start()
        return

    if args.cli:
        print("[CUIモード] 現在未実装 - GUIモードで起動します")
        print()

    # セキュアモードの表示
    if args.secure:
        print("[セキュアモード] デジタル署名認証が有効化されます")
        print()

    # GUIモードで起動
    try:
        app = MeshNetworkGUI(enable_auth=args.secure)
        app.run()
    except KeyboardInterrupt:
        print("\n\nプログラムを終了します...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[エラー] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
