import os
import itertools
import networkx as nx
from networkx.algorithms import community as nx_comm
import matplotlib.pyplot as plt

class WeightedGraph:
    def __init__(self, graph_id="root"):
        self.id = graph_id
        self.nodes = set()
        self.edges = {} # Key: tuple(sorted((u, v))), Value: weight

    def _get_edge_key(self, u, v):
        return tuple(sorted((u, v)))

    def add_edge(self, u, v, weight=1):
        if u == v: return # 忽略自环
        self.nodes.add(u)
        self.nodes.add(v)
        key = self._get_edge_key(u, v)
        self.edges[key] = self.edges.get(key, 0) + weight

    def build_from_list(self, keywords):
        """从关键词列表构建全连接子图"""
        if len(keywords) < 2:
            for k in keywords: self.nodes.add(k)
            return
        for u, v in itertools.combinations(keywords, 2):
            self.add_edge(u, v, weight=1)

    def merge_from(self, other_graph):
        """合并另一个图对象"""
        if not other_graph: return
        self.nodes.update(other_graph.nodes)
        for (u, v), weight in other_graph.edges.items():
            key = (u, v)
            self.edges[key] = self.edges.get(key, 0) + weight

    def visualize(self, output_file):
        """可视化逻辑封装"""
        if not self.nodes:
            print("图为空，跳过可视化。")
            return

        print(f"正在生成可视化图谱: {output_file}")
        # 设置字体
        plt.rcParams['font.family'] = 'serif'
        plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']
        
        G = nx.Graph()
        for (u, v), w in self.edges.items():
            G.add_edge(u, v, weight=w)

        # 社区发现
        try:
            communities = list(nx_comm.louvain_communities(G, weight='weight', resolution=2, seed=42))
        except:
            communities = list(nx_comm.greedy_modularity_communities(G, weight='weight'))

        # 颜色和布局计算
        colors = ['#E53935', '#1E88E5', '#43A047', '#8E24AA', '#FB8C00', '#D81B60']
        node_to_community = {}
        for i, comm in enumerate(communities):
            color = colors[i % len(colors)]
            for node in comm: node_to_community[node] = color

        # 针对社区优化的布局
        num_nodes = len(G.nodes())
        k_val = 2.5 / (num_nodes ** 0.5) if num_nodes > 0 else 0.1
        pos = nx.spring_layout(G, k=k_val, iterations=500, seed=42)

        plt.figure(figsize=(30, 20), dpi=300)
        
        # 绘制边
        max_w = max([d['weight'] for u, v, d in G.edges(data=True)]) if G.edges else 1
        for (u, v, d) in G.edges(data=True):
            alpha = 0.25 if node_to_community.get(u) == node_to_community.get(v) else 0.05
            nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], 
                                   width=0.5 + (d['weight']/max_w)*8,
                                   edge_color=node_to_community.get(u, "#CCCCCC"), 
                                   alpha=alpha)

        # 绘制标签
        degrees = dict(G.degree())
        max_deg = max(degrees.values()) if degrees else 1
        for node, (x, y) in pos.items():
            plt.text(x, y, s=node, fontsize=7 + (degrees[node]/max_deg)*11,
                     bbox=dict(facecolor='white', edgecolor=node_to_community.get(node), boxstyle='round', alpha=0.8),
                     ha='center', va='center', fontweight='bold')

        plt.axis('off')
        plt.savefig(output_file, bbox_inches='tight')
        plt.close()


def test_graph_logic():
    g1 = WeightedGraph("1")
    g1.build_from_list(["apple", "banana", "cherry"])
    
    g2 = WeightedGraph("2")
    g2.build_from_list(["apple", "banana"])
    
    g1.merge_from(g2)
    
    # 验证边权重：apple-banana 应该为 2 (g1贡献1, g2贡献1)
    weight = g1.edges.get(tuple(sorted(("apple", "banana"))))
    assert weight == 2
    print("Graph logic test passed!")

if __name__ == "__main__":
    test_graph_logic()