import threading
import re
import itertools
import math
from collections import Counter

from key_of_topk import topk_clean_interface
import networkx as nx
from networkx.algorithms import community as nx_comm
import matplotlib.pyplot as plt

import os

def process_line_task(line):
    """
    单个线程/任务的处理逻辑：
    解析一行文本，清洗数据，提取关键词列表。
    输入格式示例: "1. large language models, machine learning"
    """
    line = line.strip()
    if not line:
        return []

    # 1. 去除行首的序号 (例如 "1. " 或 "100. ")
    # 使用 split('.', 1) 将行分割为 ["序号", "内容"]
    parts = line.split('.', 1)
    if len(parts) >= 2:
        content = parts[1]
    else:
        content = line
    raw_keywords = re.findall(r'\[(.*?)\]', content)

    clean_keywords = []
    for kw in raw_keywords:
        # 3. 清洗数据：去除首尾空格，转为小写（避免大小写导致统计不准）
        kw = kw.strip()
        if kw:
            clean_keywords.append(kw)

    return clean_keywords




class WeightedGraph:
    def __init__(self, graph_id="root"):
        self.id = graph_id
        self.nodes = set()
        self.edges = {}

    def _get_edge_key(self, u, v):
        return tuple(sorted((u, v)))

    def add_edge(self, u, v, weight=1):
        self.nodes.add(u)
        self.nodes.add(v)
        key = self._get_edge_key(u, v)
        if key in self.edges:
            self.edges[key] += weight
        else:
            self.edges[key] = weight

    def build_complete_graph_from_list(self, keywords):
        # 只有当列表里至少有2个关键词时才能建立边关系
        if len(keywords) < 2:
            # 如果只有一个词，是否要作为孤立节点添加？
            # 这里选择添加节点但不加边
            for k in keywords:
                self.nodes.add(k)
            return

        for u, v in itertools.combinations(keywords, 2):
            self.add_edge(u, v, weight=1)

    def merge_from(self, other_graph):
        self.nodes.update(other_graph.nodes)
        for (u, v), weight in other_graph.edges.items():
            self.add_edge(u, v, weight)


def step1_build_graph(line, result_list, index, valid_keywords_set = None, mapping_dict = None):
    """
    线程任务：构建单行文本的子图
    关键修改：增加 valid_keywords_set 参数，只添加在集合中的关键词
    """
    line = line.strip()
    if not line:
        result_list[index] = None
        return

    # 解析行 (复用 process_line_task 的逻辑或保持原有正则逻辑)
    # 这里为了保持一致性，复用 process_line_task 提取清洗后的关键词
    keywords = process_line_task(line)

    filtered_keywords = []
    assert valid_keywords_set is not None or mapping_dict is not None, \
        "valid_keywords_set and mapping_dict are not None both"
    # [核心修改] 过滤：只保留 Top-K 集合中的词
    if valid_keywords_set is not None:

        filtered_keywords = [k for k in keywords if k in valid_keywords_set]
    if mapping_dict is not None:

        filtered_keywords = [mapping_dict[k] for k in filtered_keywords]

    counts = Counter(filtered_keywords)
    # 找出出现次数大于 1 的关键词
    duplicates = [kw for kw, count in counts.items() if count > 1]
    # if duplicates:
    #     print(f"--- [行 {index}] 发现重复关键词 (已过滤): {duplicates} ---")
    mapped_keywords = list(counts.keys())
    # 如果过滤后没有词了，就不创建图
    if not mapped_keywords:
        result_list[index] = None
        return

    # 为了给图一个ID，尝试提取行号（可选）
    match = re.match(r'^(\d+)', line)
    line_id = match.group(1) if match else str(index)

    graph = WeightedGraph(graph_id=line_id)
    graph.build_complete_graph_from_list(mapped_keywords)
    result_list[index] = graph


def step2_merge_graphs(target_graph, source_graph):
    if target_graph is not None and source_graph is not None:
        target_graph.merge_from(source_graph)


def visualize_to_png(custom_graph, output_file="conspicuous_lines_graph.png"):
    print("正在计算社区发现并优化布局（铺开模式）...")

    if not custom_graph or not custom_graph.nodes:
        print("图为空，无法生成。")
        return

    # --- 设置字体为 Times New Roman ---
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']
    plt.rcParams['axes.unicode_minus'] = False

    # 1. 构建 NetworkX 图
    G = nx.Graph()
    for (u, v), w in custom_graph.edges.items():
        G.add_edge(u, v, weight=w)

    # 2. 社区发现 (Louvain)
    try:
        communities = list(nx_comm.louvain_communities(G, weight='weight', resolution=2, seed=42))
    except AttributeError:
        communities = list(nx_comm.greedy_modularity_communities(G, weight='weight'))

    node_to_community = {}
    # 定义一组更有区分度的深色，用于边框和文字
    colors = ['#E53935', '#1E88E5', '#43A047', '#8E24AA', '#FB8C00',
              '#6D4C41', '#D81B60', '#546E7A', '#00897B', '#C0CA33']

    for i, comm in enumerate(communities):
        color = colors[i % len(colors)]
        for node in comm:
            node_to_community[node] = color

    # 3. 布局计算：优化社区紧凑度和整体铺放度
    layout_G = G.copy()
    for u, v, d in layout_G.edges(data=True):
        if node_to_community[u] == node_to_community[v]:
            # 大幅增强社区内聚力
            d['layout_weight'] = d['weight'] * 10.0
        else:
            # 大幅减弱社区间引力，让它们分得更开
            d['layout_weight'] = d['weight'] * 0.1

    num_nodes = len(G.nodes())
    # 增加 k 值可以让节点之间弹得更远（铺得更开）
    # 这里的 2.5 是一个调节系数，如果觉得不够开，可以改到 3.0 或更高
    k_val = (2.5 / (num_nodes ** 0.5))

    pos = nx.spring_layout(layout_G, weight='layout_weight', k=k_val, iterations=500, seed=42)

    # 4. 绘图设置
    plt.figure(figsize=(35, 25), dpi=300)  # 保持大尺寸确保文字不拥挤
    plt.gca().set_facecolor('white')

    degrees = dict(G.degree())
    max_deg = max(degrees.values()) if degrees else 1
    all_weights = [d['weight'] for u, v, d in G.edges(data=True)]
    max_w = max(all_weights) if all_weights else 1

    # 5. 绘制边
    print("正在绘制边...")
    for (u, v, d) in G.edges(data=True):
        comm_u = node_to_community.get(u, '#888888')
        comm_v = node_to_community.get(v, '#888888')

        # 线宽映射：稍微克制一点，最高 10.0
        line_width = 0.5 + (d['weight'] / max_w) * 10.0

        # 跨社区的线变得非常淡，社区内的线颜色稍深
        if comm_u == comm_v:
            edge_col = comm_u
            alpha = 0.25
        else:
            edge_col = "#CCCCCC"
            alpha = 0.1

        nx.draw_networkx_edges(G, pos,
                               edgelist=[(u, v)],
                               width=line_width,
                               edge_color=edge_col,
                               alpha=alpha,
                               arrows=False)

    # 6. 绘制关键词标签（空心圆圈效果）
    print("正在绘制关键词节点（空心标签）...")
    for node, (x, y) in pos.items():
        deg = degrees[node]
        # 缩小字号：基础 7，最高 18
        f_size = 7 + (deg / max_deg) * 11

        comm_color = node_to_community.get(node, '#333333')

        plt.text(x, y, s=node,
                 fontsize=f_size,
                 family='serif',
                 fontname='Times New Roman',
                 # bbox 设置：facecolor 为白色（防止背景干扰），edgecolor 为社区颜色
                 bbox=dict(facecolor='white',
                           edgecolor=comm_color,
                           linewidth=1.2,
                           boxstyle='round,pad=0.3',
                           alpha=0.8),
                 horizontalalignment='center',
                 verticalalignment='center',
                 color='black',  # 字体改为黑色，更易读
                 fontweight='bold',
                 zorder=10)

    plt.axis('off')
    # 增加边缘留白
    plt.margins(0.1)

    plt.savefig(output_file, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"PNG 已生成：{os.path.abspath(output_file)}")



def analysis_interface(file_path, output_path, target, top_k, top_freq_k, threshold, max_workers):
    if not os.path.exists(file_path):
        print(f"错误：找不到文件 {file_path}")
        return

    valid_keywords_set, mapping_dict = None, None
    if target in ["DE", "ID"]:
        # [步骤 1] 获取 Top-K 关键词集合
        valid_keywords_set, mapping_dict= topk_clean_interface(input_path=file_path, top_k=top_k, threshold=threshold,
                                                               top_freq_k=top_freq_k, max_workers=max_workers, target=target)
    elif target in ["AU", "C1", "CR"]:
        valid_keywords_set = topk_clean_interface(input_path=file_path, top_k=min(top_k, top_freq_k), max_workers=max_workers, target=target)
    if not valid_keywords_set:
        print("未找到有效关键词，程序退出。")
        return

    # 读取文件准备构建图
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_lines = len(lines)
    if total_lines == 0:
        return

    print(f"=== 阶段 1: 多线程初始化子图 ({total_lines} 行) ===")
    graphs = [None] * total_lines
    threads = []

    # [步骤 2] 多线程处理，传入过滤集合
    for i, line in enumerate(lines):
        t = threading.Thread(target=step1_build_graph, args=(line, graphs, i, valid_keywords_set, mapping_dict))
        threads.append(t)
        t.start()

        # 简单的批处理控制，防止一次性开启过多线程导致内存溢出
        if len(threads) >= max_workers:
            for t in threads: t.join()
            threads = []

    # 等待剩余线程
    for t in threads: t.join()

    # 过滤掉 None 的图（即该行没有关键词属于 Top-K 的情况）
    active_graphs = [g for g in graphs if g is not None]
    current_count = len(active_graphs)
    print(f"过滤后有效子图数量: {current_count}")

    if current_count == 0:
        print("没有生成任何有效图节点。")
        return

    print(f"\n=== 阶段 2: 并行归约 (Reduction) ===")

    while current_count > 1:
        stride = math.ceil(current_count / 2)
        merge_threads = []
        for i in range(current_count // 2):
            target_idx = i
            source_idx = i + stride
            if source_idx < current_count:
                t = threading.Thread(target=step2_merge_graphs,
                                     args=(active_graphs[target_idx], active_graphs[source_idx]))
                merge_threads.append(t)
                t.start()

        for t in merge_threads: t.join()
        active_graphs = active_graphs[:stride]
        current_count = stride
        print(f"归约剩余图数量: {current_count}")

    final_graph = active_graphs[0]
    # self_loops = [edge for edge in final_graph.edges if edge[0] == edge[1]]
    # for loop in self_loops:
    #     del final_graph.edges[loop]
    print("\n" + "=" * 50)
    print(f"计算完成。节点数: {len(final_graph.nodes)}, 边数: {len(final_graph.edges)}")

    # visualize_interactive_graph(final_graph)

    visualize_to_png(final_graph, output_path)


if __name__ == "__main__":
    # ================= 配置区域 =================
    FILE_PATH = r"D:\codes\Visual\extract\reference\merged_reference.txt"  # r"E:\China Chem All\extract\keywords\merged_keywords_lower.txt"  #
    OUTPUT_PATH = r"D:\codes\Visual\extract\reference\final_reference_map.png"
    TARGET = "CR"
    TOP_K = 300  # 只保留出现频率最高的前100个词构建图谱(cleaned)
    TOP_FREQ_K = 100
    THRESHOLD = 0.7
    MAX_WORKERS = 1000  # 线程池最大线程数
    # ==========================================
    analysis_interface(FILE_PATH, OUTPUT_PATH, TARGET, TOP_K, TOP_FREQ_K, THRESHOLD, MAX_WORKERS)