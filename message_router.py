"""
メッセージルーティングシステム
Dijkstra法による最短経路探索を実装
"""
import heapq
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from mesh_node import NodeInfo


@dataclass
class RouteInfo:
    """経路情報"""
    destination: str
    next_hop: str
    hop_count: int
    total_latency: float


class MessageRouter:
    """メッシュネットワークのルーティングエンジン"""

    def __init__(self):
        """ルーティングエンジンの初期化"""
        self.routing_table: Dict[str, RouteInfo] = {}
        self.link_latencies: Dict[Tuple[str, str], float] = {}

    def update_topology(self, node_id: str, known_nodes: List[NodeInfo]):
        """
        ネットワークトポロジーを更新し、ルーティングテーブルを再計算

        Args:
            node_id: 自ノードのID
            known_nodes: 接続中のノード一覧
        """
        # グラフ構築（隣接ノードリスト）
        graph: Dict[str, List[Tuple[str, float]]] = {}

        # 自ノードと隣接ノードの接続
        graph[node_id] = []
        for node in known_nodes:
            # レイテンシは仮で1.0（実際はpingなどで計測可能）
            latency = self.link_latencies.get((node_id, node.node_id), 1.0)
            graph[node_id].append((node.node_id, latency))

            # 双方向リンクを想定
            if node.node_id not in graph:
                graph[node.node_id] = []
            graph[node.node_id].append((node_id, latency))

        # Dijkstra法で最短経路を計算
        self.routing_table = self._compute_routes(node_id, graph)

    def _compute_routes(
        self, source: str, graph: Dict[str, List[Tuple[str, float]]]
    ) -> Dict[str, RouteInfo]:
        """
        Dijkstra法による最短経路計算

        Args:
            source: 始点ノードID
            graph: ネットワークグラフ（隣接リスト形式）

        Returns:
            ルーティングテーブル
        """
        # 距離とホップ数を記録
        distances: Dict[str, float] = {source: 0.0}
        hop_counts: Dict[str, int] = {source: 0}
        previous: Dict[str, Optional[str]] = {source: None}

        # 優先度キュー（距離、ノードID）
        pq: List[Tuple[float, str]] = [(0.0, source)]

        while pq:
            current_dist, current_node = heapq.heappop(pq)

            # すでに処理済みの場合スキップ
            if current_dist > distances.get(current_node, float('inf')):
                continue

            # 隣接ノードを探索
            for neighbor, weight in graph.get(current_node, []):
                distance = current_dist + weight
                hop_count = hop_counts[current_node] + 1

                # より短い経路が見つかった場合
                if distance < distances.get(neighbor, float('inf')):
                    distances[neighbor] = distance
                    hop_counts[neighbor] = hop_count
                    previous[neighbor] = current_node
                    heapq.heappush(pq, (distance, neighbor))

        # ルーティングテーブルを構築
        routing_table: Dict[str, RouteInfo] = {}

        for dest_node in distances:
            if dest_node == source:
                continue

            # 次ホップを逆算
            next_hop = self._find_next_hop(source, dest_node, previous)

            if next_hop:
                routing_table[dest_node] = RouteInfo(
                    destination=dest_node,
                    next_hop=next_hop,
                    hop_count=hop_counts[dest_node],
                    total_latency=distances[dest_node]
                )

        return routing_table

    def _find_next_hop(
        self, source: str, destination: str, previous: Dict[str, Optional[str]]
    ) -> Optional[str]:
        """
        次ホップノードを特定

        Args:
            source: 始点ノード
            destination: 宛先ノード
            previous: 経路の前ノード情報

        Returns:
            次ホップノードID（到達不可能な場合None）
        """
        if destination not in previous:
            return None

        # 宛先から始点へ逆順に経路をたどる
        current = destination
        while previous.get(current) != source:
            current = previous.get(current)
            if current is None:
                return None

        return current

    def get_next_hop(self, destination: str) -> Optional[str]:
        """
        宛先への次ホップノードを取得

        Args:
            destination: 宛先ノードID

        Returns:
            次ホップノードID（経路がない場合None）
        """
        route = self.routing_table.get(destination)
        return route.next_hop if route else None

    def get_route_info(self, destination: str) -> Optional[RouteInfo]:
        """
        宛先への経路情報を取得

        Args:
            destination: 宛先ノードID

        Returns:
            経路情報（経路がない場合None）
        """
        return self.routing_table.get(destination)

    def update_link_latency(self, node1: str, node2: str, latency: float):
        """
        リンクのレイテンシを更新

        Args:
            node1: ノード1のID
            node2: ノード2のID
            latency: レイテンシ（秒）
        """
        self.link_latencies[(node1, node2)] = latency
        self.link_latencies[(node2, node1)] = latency

    def print_routing_table(self):
        """ルーティングテーブルを表示（デバッグ用）"""
        print("\n=== ルーティングテーブル ===")
        if not self.routing_table:
            print("（空）")
            return

        for dest, route in self.routing_table.items():
            print(
                f"宛先: {dest[:8]}... | "
                f"次ホップ: {route.next_hop[:8]}... | "
                f"ホップ数: {route.hop_count} | "
                f"レイテンシ: {route.total_latency:.2f}秒"
            )
        print("=" * 50)


if __name__ == "__main__":
    # テスト用
    router = MessageRouter()

    # テストグラフ
    # A -- B -- C
    #  \       /
    #   \-- D--/
    test_graph = {
        'A': [('B', 1.0), ('D', 2.0)],
        'B': [('A', 1.0), ('C', 1.0)],
        'C': [('B', 1.0), ('D', 1.0)],
        'D': [('A', 2.0), ('C', 1.0)],
    }

    # ノードAからの最短経路を計算
    routes = router._compute_routes('A', test_graph)

    print("ノードAからの最短経路:")
    for dest, route in routes.items():
        print(
            f"宛先: {dest} | 次ホップ: {route.next_hop} | "
            f"ホップ数: {route.hop_count} | レイテンシ: {route.total_latency}"
        )
