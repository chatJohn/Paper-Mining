import threading
import math
from entity.graph import WeightedGraph
from utils.processor import KeywordProcessor

class GraphAnalysisEngine:
    def __init__(self, max_workers=10):
        self.max_workers = max_workers
        self.processor = KeywordProcessor()

    def _build_single_subgraph(self, line, valid_set, mapping, results, idx):
        keywords = self.processor.parse_line(line)
        # 过滤并映射
        filtered = [mapping.get(k, k) for k in keywords if (not valid_set or k in valid_set)]
        # 去重（一行内重复出现的词只计一次边）
        unique_kws = list(set(filtered))
        
        if not unique_kws:
            results[idx] = None
            return

        g = WeightedGraph(graph_id=str(idx))
        g.build_from_list(unique_kws)
        results[idx] = g

    def run(self, file_path, output_png, target, top_k=300, threshold=0.7):
        # 1. 获取 TopK 和映射关系
        print(f"--- 任务启动: {target} ---")
        raw_top = self.processor.get_top_k_raw(file_path, top_k, self.max_workers)
        
        valid_set, mapping = None, {}
        if target in ["DE", "ID"]:
            valid_set, mapping = self.processor.semantic_merge(raw_top, threshold, 100)
        else:
            valid_set = set([item[0] for item in raw_top])

        # 2. 并行构建子图
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        graphs = [None] * len(lines)
        threads = []
        for i, line in enumerate(lines):
            t = threading.Thread(target=self._build_single_subgraph, 
                                 args=(line, valid_set, mapping, graphs, i))
            threads.append(t)
            t.start()
            if len(threads) >= self.max_workers:
                for t in threads: t.join()
                threads = []
        for t in threads: t.join()

        # 3. 并行归约合并 (Reduction)
        active_graphs = [g for g in graphs if g is not None]
        print(f"初始有效子图: {len(active_graphs)}")
        
        while len(active_graphs) > 1:
            stride = math.ceil(len(active_graphs) / 2)
            temp_threads = []
            for i in range(len(active_graphs) // 2):
                t = threading.Thread(target=active_graphs[i].merge_from, 
                                     args=(active_graphs[i + stride],))
                temp_threads.append(t)
                t.start()
            for t in temp_threads: t.join()
            active_graphs = active_graphs[:stride]

        # 4. 可视化
        if active_graphs:
            final_g = active_graphs[0]
            final_g.visualize(output_png)