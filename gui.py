"""
メッシュネットワークのGUIインターフェース
Tkinterを使用した直感的な操作画面
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
from datetime import datetime
from typing import Optional
from mesh_node import MeshNode, Message
from file_transfer import FileTransferManager


class MeshNetworkGUI:
    """メッシュネットワークGUI"""

    def __init__(self, enable_auth: bool = False):
        """
        GUIの初期化

        Args:
            enable_auth: デジタル署名認証を有効化
        """
        self.root = tk.Tk()
        self.root.title("災害用メッシュネットワーク" + (" [セキュア]" if enable_auth else ""))
        self.root.geometry("900x700")

        self.enable_auth = enable_auth

        # ノードとファイル転送マネージャー
        self.node: Optional[MeshNode] = None
        self.file_manager = FileTransferManager()

        # GUI要素の作成
        self._create_widgets()
        self._setup_layout()

        # ノードの初期化と起動
        self._init_node()

    def _create_widgets(self):
        """GUI要素を作成"""
        # === ステータスフレーム ===
        self.status_frame = ttk.LabelFrame(self.root, text="ノード状態", padding=10)

        self.status_label = ttk.Label(
            self.status_frame,
            text="未接続",
            font=("Arial", 12, "bold"),
            foreground="red"
        )

        self.node_id_label = ttk.Label(
            self.status_frame,
            text="ノードID: ---"
        )

        self.hostname_entry = ttk.Entry(self.status_frame, width=30)
        self.hostname_entry.insert(0, "避難所A")

        ttk.Button(
            self.status_frame,
            text="ノード名変更",
            command=self._change_hostname
        ).grid(row=0, column=2, padx=5)

        # === 接続ノードリスト ===
        self.nodes_frame = ttk.LabelFrame(self.root, text="接続中のノード", padding=10)

        self.nodes_listbox = tk.Listbox(
            self.nodes_frame,
            height=8,
            font=("Courier", 10)
        )

        nodes_scrollbar = ttk.Scrollbar(
            self.nodes_frame,
            orient="vertical",
            command=self.nodes_listbox.yview
        )
        self.nodes_listbox.config(yscrollcommand=nodes_scrollbar.set)

        ttk.Button(
            self.nodes_frame,
            text="更新",
            command=self._update_nodes_list
        ).pack(side=tk.BOTTOM, pady=5)

        # === メッセージ表示エリア ===
        self.messages_frame = ttk.LabelFrame(self.root, text="メッセージ履歴", padding=10)

        self.messages_text = scrolledtext.ScrolledText(
            self.messages_frame,
            height=15,
            font=("Courier", 9),
            state=tk.DISABLED
        )

        # === メッセージ送信エリア ===
        self.send_frame = ttk.LabelFrame(self.root, text="メッセージ送信", padding=10)

        ttk.Label(self.send_frame, text="宛先:").grid(row=0, column=0, sticky=tk.W)

        self.dest_var = tk.StringVar(value="broadcast")
        self.dest_combo = ttk.Combobox(
            self.send_frame,
            textvariable=self.dest_var,
            width=40,
            state="readonly"
        )
        self.dest_combo['values'] = ["broadcast (全員)"]

        ttk.Label(self.send_frame, text="メッセージ:").grid(row=1, column=0, sticky=tk.W)

        self.message_entry = ttk.Entry(self.send_frame, width=50)
        self.message_entry.bind('<Return>', lambda e: self._send_message())

        ttk.Button(
            self.send_frame,
            text="送信",
            command=self._send_message
        ).grid(row=1, column=2, padx=5)

        ttk.Button(
            self.send_frame,
            text="ファイル送信",
            command=self._send_file
        ).grid(row=2, column=0, columnspan=3, pady=5)

    def _setup_layout(self):
        """レイアウトを配置"""
        # ステータスフレーム
        self.status_frame.pack(fill=tk.X, padx=10, pady=5)
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        self.node_id_label.grid(row=1, column=0, sticky=tk.W)
        ttk.Label(self.status_frame, text="ノード名:").grid(row=0, column=1, padx=(20, 5))
        self.hostname_entry.grid(row=0, column=2)

        # 接続ノードリスト
        self.nodes_frame.pack(fill=tk.BOTH, padx=10, pady=5)
        self.nodes_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # メッセージ履歴
        self.messages_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.messages_text.pack(fill=tk.BOTH, expand=True)

        # メッセージ送信
        self.send_frame.pack(fill=tk.X, padx=10, pady=5)
        self.dest_combo.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=2)
        self.message_entry.grid(row=1, column=1, sticky=tk.EW, pady=2)
        self.send_frame.columnconfigure(1, weight=1)

    def _init_node(self):
        """メッシュノードを初期化"""
        hostname = self.hostname_entry.get()

        if self.enable_auth:
            # セキュアノードを使用
            from secure_mesh_node import SecureMeshNode
            self.node = SecureMeshNode(hostname, enable_auth=True)
        else:
            # 通常ノードを使用
            self.node = MeshNode(hostname)

        # メッセージ受信コールバック
        self.node.register_message_callback(self._on_message_received)

        # ファイル受信完了コールバック
        self.file_manager.register_completion_callback(self._on_file_received)

        # ノードを起動
        self.node.start()

        # ステータス更新
        status_text = "接続中 [セキュア]" if self.enable_auth else "接続中"
        self.status_label.config(text=status_text, foreground="green")
        self.node_id_label.config(text=f"ノードID: {self.node.node_id[:16]}...")

        # 定期的な更新を開始
        self._start_periodic_updates()

    def _change_hostname(self):
        """ノード名を変更"""
        new_hostname = self.hostname_entry.get()
        if new_hostname and self.node:
            self.node.hostname = new_hostname
            messagebox.showinfo("成功", f"ノード名を '{new_hostname}' に変更しました")

    def _update_nodes_list(self):
        """接続ノードリストを更新"""
        if not self.node:
            return

        self.nodes_listbox.delete(0, tk.END)

        nodes = self.node.get_known_nodes()

        if not nodes:
            self.nodes_listbox.insert(tk.END, "接続中のノードがありません")
            self.dest_combo['values'] = ["broadcast (全員)"]
            return

        # リストボックスに表示
        for node in nodes:
            self.nodes_listbox.insert(
                tk.END,
                f"{node.hostname} ({node.ip_address}) - ID: {node.node_id[:8]}..."
            )

        # 宛先コンボボックスを更新
        dest_options = ["broadcast (全員)"]
        for node in nodes:
            dest_options.append(f"{node.hostname} [{node.node_id[:8]}...]")

        self.dest_combo['values'] = dest_options

    def _send_message(self):
        """メッセージを送信"""
        message = self.message_entry.get().strip()
        if not message:
            return

        # 宛先を取得
        dest_selection = self.dest_var.get()

        if dest_selection.startswith("broadcast"):
            dest_id = "broadcast"
        else:
            # ノードIDを抽出
            import re
            match = re.search(r'\[(.+?)\.\.\.\]', dest_selection)
            if match:
                # 完全なノードIDを検索
                short_id = match.group(1)
                nodes = self.node.get_known_nodes()
                dest_id = None
                for node in nodes:
                    if node.node_id.startswith(short_id):
                        dest_id = node.node_id
                        break

                if not dest_id:
                    messagebox.showerror("エラー", "宛先ノードが見つかりません")
                    return
            else:
                dest_id = "broadcast"

        # メッセージ送信
        success = self.node.send_message(dest_id, message, "text")

        if success:
            self._add_message_to_display(
                f"[送信 → {dest_selection}] {message}",
                "blue"
            )
            self.message_entry.delete(0, tk.END)
        else:
            messagebox.showerror("エラー", "メッセージの送信に失敗しました")

    def _send_file(self):
        """ファイルを送信"""
        file_path = filedialog.askopenfilename(
            title="送信するファイルを選択",
            filetypes=[("すべてのファイル", "*.*")]
        )

        if not file_path:
            return

        # ファイルをチャンクに分割
        try:
            chunks = self.file_manager.prepare_file_for_transfer(file_path)
        except Exception as e:
            messagebox.showerror("エラー", f"ファイル準備エラー: {e}")
            return

        # 各チャンクを送信
        dest_selection = self.dest_var.get()

        if dest_selection.startswith("broadcast"):
            dest_id = "broadcast"
        else:
            # ノードIDを抽出（メッセージ送信と同じロジック）
            import re
            match = re.search(r'\[(.+?)\.\.\.\]', dest_selection)
            if match:
                short_id = match.group(1)
                nodes = self.node.get_known_nodes()
                dest_id = None
                for node in nodes:
                    if node.node_id.startswith(short_id):
                        dest_id = node.node_id
                        break

                if not dest_id:
                    messagebox.showerror("エラー", "宛先ノードが見つかりません")
                    return
            else:
                dest_id = "broadcast"

        # 別スレッドで送信
        threading.Thread(
            target=self._send_file_chunks,
            args=(chunks, dest_id, dest_selection),
            daemon=True
        ).start()

    def _send_file_chunks(self, chunks, dest_id, dest_name):
        """ファイルチャンクを送信（バックグラウンド）"""
        filename = chunks[0].filename
        self._add_message_to_display(
            f"[ファイル送信開始] {filename} → {dest_name} ({len(chunks)} チャンク)",
            "purple"
        )

        for i, chunk in enumerate(chunks):
            chunk_json = self.file_manager.chunk_to_json(chunk)
            success = self.node.send_message(dest_id, chunk_json, "file")

            if not success:
                self._add_message_to_display(
                    f"[送信失敗] チャンク {i+1}/{len(chunks)}",
                    "red"
                )
                return

        self._add_message_to_display(
            f"[ファイル送信完了] {filename}",
            "green"
        )

    def _on_message_received(self, message: Message):
        """メッセージ受信時の処理"""
        # ファイルチャンクの場合
        if message.msg_type == "file":
            try:
                chunk = self.file_manager.json_to_chunk(message.payload)
                is_complete = self.file_manager.process_chunk(chunk)

                self._add_message_to_display(
                    f"[ファイル受信] {chunk.filename} - "
                    f"チャンク {chunk.chunk_index+1}/{chunk.total_chunks}",
                    "purple"
                )

                if is_complete:
                    # 完了通知は _on_file_received で行う
                    pass

            except Exception as e:
                self._add_message_to_display(
                    f"[ファイル受信エラー] {e}",
                    "red"
                )

        # テキストメッセージの場合
        elif message.msg_type == "text":
            timestamp = datetime.fromtimestamp(message.timestamp).strftime("%H:%M:%S")
            sender_id = message.source_id[:8]

            self._add_message_to_display(
                f"[{timestamp}] {sender_id}...: {message.payload}",
                "black"
            )

    def _on_file_received(self, filename: str, file_path: str):
        """ファイル受信完了時の処理"""
        self._add_message_to_display(
            f"[ファイル保存完了] {filename} → {file_path}",
            "green"
        )

        messagebox.showinfo(
            "ファイル受信完了",
            f"{filename}\n\n保存先:\n{file_path}"
        )

    def _add_message_to_display(self, message: str, color: str = "black"):
        """メッセージ表示エリアに追加"""
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.insert(tk.END, message + "\n", color)
        self.messages_text.tag_config(color, foreground=color)
        self.messages_text.see(tk.END)
        self.messages_text.config(state=tk.DISABLED)

    def _start_periodic_updates(self):
        """定期的な更新を開始"""
        def update():
            if self.node and self.node.running:
                self._update_nodes_list()
                self.root.after(5000, update)  # 5秒ごと

        update()

    def run(self):
        """GUIを実行"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()

    def _on_closing(self):
        """ウィンドウを閉じる時の処理"""
        if self.node:
            self.node.stop()
        self.root.destroy()


if __name__ == "__main__":
    app = MeshNetworkGUI()
    app.run()
