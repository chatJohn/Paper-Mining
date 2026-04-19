import re
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from sentence_transformers import SentenceTransformer, util

class KeywordProcessor:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self._model = None
        self.model_name = model_name

    @property
    def model(self):
        if self._model is None:
            print("正在初始化 AI 模型...")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @staticmethod
    def parse_line(line):
        """解析 WOS 提取后的单行格式 [xxx], [yyy]"""
        line = line.strip()
        if not line: return []
        content = line.split('.', 1)[-1] if '.' in line else line
        return [kw.strip().lower() for kw in re.findall(r'\[(.*?)\]', content) if kw.strip()]

    def get_top_k_raw(self, input_file, top_k, max_workers):
        counter = Counter()
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(tqdm(executor.map(self.parse_line, lines), total=len(lines), desc="统计词频"))
            for tags in results: counter.update(tags)
        
        return counter.most_common(top_k)

    def semantic_merge(self, raw_freq_list, threshold, top_freq_k):
        """语义聚类逻辑"""
        if not raw_freq_list: return set(), {}
        
        words = [item[0] for item in raw_freq_list]
        freqs = {item[0]: item[1] for item in raw_freq_list}
        
        embeddings = self.model.encode(words, convert_to_tensor=True, show_progress_bar=True)
        cosine_scores = util.cos_sim(embeddings, embeddings)

        visited = set()
        mapping_dict = {}
        valid_words = set()

        for i in range(len(words)):
            if i in visited: continue
            
            # 找到相似的索引
            similar_indices = [j for j in range(i, len(words)) 
                               if cosine_scores[i][j] >= threshold and j not in visited]
            
            cluster_words = [words[idx] for idx in similar_indices]
            rep_word = max(cluster_words, key=lambda x: freqs[x])
            
            for idx in similar_indices:
                visited.add(idx)
                mapping_dict[words[idx]] = rep_word
                valid_words.add(words[idx])
        
        # 这里可以根据 top_freq_k 进一步筛选，逻辑同原代码
        return valid_words, mapping_dict