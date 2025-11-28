"""
ファイル転送機能
大容量ファイルをチャンク分割して転送
"""
import os
import base64
import json
from typing import Dict, Optional, Callable
from dataclasses import dataclass
import threading


@dataclass
class FileChunk:
    """ファイルチャンク"""
    file_id: str
    filename: str
    chunk_index: int
    total_chunks: int
    data: str  # Base64エンコード
    file_size: int


@dataclass
class FileTransferState:
    """ファイル転送状態"""
    file_id: str
    filename: str
    total_chunks: int
    received_chunks: Dict[int, bytes]
    file_size: int
    complete: bool


class FileTransferManager:
    """ファイル転送マネージャー"""

    CHUNK_SIZE = 64 * 1024  # 64KB per chunk

    def __init__(self, save_directory: str = "./received_files"):
        """
        ファイル転送マネージャーの初期化

        Args:
            save_directory: 受信ファイルの保存先ディレクトリ
        """
        self.save_directory = save_directory
        self.transfer_states: Dict[str, FileTransferState] = {}
        self.transfer_lock = threading.Lock()
        self.completion_callbacks: list[Callable[[str, str], None]] = []

        # 保存ディレクトリの作成
        os.makedirs(save_directory, exist_ok=True)

    def prepare_file_for_transfer(self, file_path: str) -> list[FileChunk]:
        """
        ファイルを転送用のチャンクに分割

        Args:
            file_path: 送信するファイルのパス

        Returns:
            FileChunkのリスト
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)

        # ファイルIDを生成（ファイル名+サイズのハッシュ）
        import hashlib
        file_id = hashlib.sha256(f"{filename}{file_size}".encode()).hexdigest()[:16]

        chunks = []
        chunk_index = 0

        with open(file_path, 'rb') as f:
            while True:
                chunk_data = f.read(self.CHUNK_SIZE)
                if not chunk_data:
                    break

                # Base64エンコード
                encoded_data = base64.b64encode(chunk_data).decode('utf-8')

                chunk = FileChunk(
                    file_id=file_id,
                    filename=filename,
                    chunk_index=chunk_index,
                    total_chunks=0,  # 後で更新
                    data=encoded_data,
                    file_size=file_size
                )

                chunks.append(chunk)
                chunk_index += 1

        # 総チャンク数を更新
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total_chunks

        print(f"[ファイル準備] {filename} を {total_chunks} チャンクに分割")
        return chunks

    def process_chunk(self, chunk: FileChunk) -> bool:
        """
        受信したチャンクを処理

        Args:
            chunk: 受信したファイルチャンク

        Returns:
            ファイル転送が完了した場合True
        """
        with self.transfer_lock:
            # 転送状態を取得または作成
            if chunk.file_id not in self.transfer_states:
                self.transfer_states[chunk.file_id] = FileTransferState(
                    file_id=chunk.file_id,
                    filename=chunk.filename,
                    total_chunks=chunk.total_chunks,
                    received_chunks={},
                    file_size=chunk.file_size,
                    complete=False
                )

            state = self.transfer_states[chunk.file_id]

            # チャンクをデコードして保存
            chunk_data = base64.b64decode(chunk.data)
            state.received_chunks[chunk.chunk_index] = chunk_data

            # 進捗表示
            progress = len(state.received_chunks) / state.total_chunks * 100
            print(
                f"[ファイル受信] {state.filename} - "
                f"{len(state.received_chunks)}/{state.total_chunks} "
                f"({progress:.1f}%)"
            )

            # すべてのチャンクを受信したか確認
            if len(state.received_chunks) == state.total_chunks:
                self._save_complete_file(state)
                state.complete = True
                return True

            return False

    def _save_complete_file(self, state: FileTransferState):
        """
        完全に受信したファイルを保存

        Args:
            state: ファイル転送状態
        """
        file_path = os.path.join(self.save_directory, state.filename)

        # ファイルが既に存在する場合、連番を付ける
        if os.path.exists(file_path):
            base_name, ext = os.path.splitext(state.filename)
            counter = 1
            while os.path.exists(file_path):
                file_path = os.path.join(
                    self.save_directory,
                    f"{base_name}_{counter}{ext}"
                )
                counter += 1

        # チャンクを順番に結合して保存
        with open(file_path, 'wb') as f:
            for i in range(state.total_chunks):
                if i in state.received_chunks:
                    f.write(state.received_chunks[i])

        print(f"[ファイル保存完了] {file_path}")

        # コールバックを実行
        for callback in self.completion_callbacks:
            try:
                callback(state.filename, file_path)
            except Exception as e:
                print(f"[コールバックエラー] {e}")

    def chunk_to_json(self, chunk: FileChunk) -> str:
        """
        FileChunkをJSON文字列に変換

        Args:
            chunk: ファイルチャンク

        Returns:
            JSON文字列
        """
        return json.dumps({
            'file_id': chunk.file_id,
            'filename': chunk.filename,
            'chunk_index': chunk.chunk_index,
            'total_chunks': chunk.total_chunks,
            'data': chunk.data,
            'file_size': chunk.file_size
        })

    def json_to_chunk(self, json_str: str) -> FileChunk:
        """
        JSON文字列をFileChunkに変換

        Args:
            json_str: JSON文字列

        Returns:
            ファイルチャンク
        """
        data = json.loads(json_str)
        return FileChunk(**data)

    def register_completion_callback(
        self, callback: Callable[[str, str], None]
    ):
        """
        ファイル受信完了時のコールバックを登録

        Args:
            callback: コールバック関数（filename, file_pathを受け取る）
        """
        self.completion_callbacks.append(callback)

    def get_transfer_progress(self, file_id: str) -> Optional[float]:
        """
        ファイル転送の進捗を取得

        Args:
            file_id: ファイルID

        Returns:
            進捗率（0.0-1.0）、転送が存在しない場合None
        """
        with self.transfer_lock:
            state = self.transfer_states.get(file_id)
            if not state:
                return None

            return len(state.received_chunks) / state.total_chunks

    def cleanup_completed_transfers(self):
        """完了した転送を削除（メモリ節約）"""
        with self.transfer_lock:
            completed_ids = [
                file_id for file_id, state in self.transfer_states.items()
                if state.complete
            ]

            for file_id in completed_ids:
                del self.transfer_states[file_id]

            if completed_ids:
                print(f"[クリーンアップ] {len(completed_ids)} 件の完了転送を削除")


if __name__ == "__main__":
    # テスト用
    manager = FileTransferManager("./test_received")

    # ファイル転送のテスト（このファイル自身を送信）
    test_file = __file__

    print(f"テストファイル: {test_file}")

    # チャンクに分割
    chunks = manager.prepare_file_for_transfer(test_file)

    print(f"\n{len(chunks)} チャンクに分割されました\n")

    # チャンクを処理（送信と受信をシミュレート）
    def on_complete(filename, path):
        print(f"\n完了コールバック: {filename} -> {path}")

    manager.register_completion_callback(on_complete)

    for chunk in chunks:
        # JSON変換テスト
        json_str = manager.chunk_to_json(chunk)
        restored_chunk = manager.json_to_chunk(json_str)

        # チャンク処理
        is_complete = manager.process_chunk(restored_chunk)

        if is_complete:
            print("\nファイル転送完了!")
