import concurrent.futures
from collections import Counter
import os
import re
import torch
from sentence_transformers import SentenceTransformer, util
from tqdm import tqdm


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


def get_key_of_topk(input_file, top_k, max_workers):
    # 0. 检查文件是否存在
    if not os.path.exists(input_file):
        raise FileExistsError(f"{input_file} is not exist")

    print(f"正在读取文件: {input_file} ...")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return

    total_lines = len(lines)
    print(f"共读取到 {total_lines} 行数据，开始多线程处理...")

    # 全局计数器
    global_counter = Counter()

    # 1. 使用线程池进行并行处理
    # 虽然是处理每一行，但使用线程池来管理资源，防止系统崩溃
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # executor.map 会保持输入顺序返回结果，这里非常适合
        # 每一个 line 都会被分配给 process_line_task 函数处理
        results = executor.map(process_line_task, lines)

        # 2. 汇总结果 (Reduce 阶段)
        # 注意：Counter 的 update 操作在 Python 中对于纯计算通常很快，单线程汇总即可
        for keywords_list in results:
            global_counter.update(keywords_list)

    # 3. 输出 Top-K 结果
    # print(f"\n{'=' * 10} TOP {top_k} 关键词统计结果 {'=' * 10}")
    # print(f"{'排名':<6}{'出现次数':<10}{'关键词'}")
    # print("-" * 40)

    top_k_data = global_counter.most_common(top_k)
    # for rank, (word, count) in enumerate(top_k_data, 1):
    #     print(f"{rank:<6}{count:<10}{word}")
    return top_k_data


def semantic_merge_keywords(keywords_freq_list, threshold=0.75, top_freq_k=100, model_name='all-MiniLM-L6-v2'):
    if not keywords_freq_list:
        return []

    keywords = [item[0] for item in keywords_freq_list]
    frequencies = {item[0]: item[1] for item in keywords_freq_list}
    print("正在加载 AI 模型 (第一次运行需下载，请耐心等待)...")
    try:
        with tqdm(total=1, desc="Loading Model", bar_format="{desc}: {elapsed}") as pbar:
            model = SentenceTransformer(model_name)
            pbar.update(1)

        print("模型加载完成！")
    except Exception as e:
        raise Exception(f"模型加载失败: {e}")
    # encode 过程中通过 show_progress_bar 显示进度
    embeddings = model.encode(keywords, convert_to_tensor=True, show_progress_bar=True)

    # 3. 计算相似度矩阵
    print("正在计算相似度矩阵...")
    cosine_scores = util.cos_sim(embeddings, embeddings)

    # 4. 语义聚类
    clusters = []
    visited = set()

    for i in tqdm(range(len(keywords)), desc="语义聚类中"):
        if i in visited:
            continue

        # 当前词作为簇的起点
        current_cluster_indices = [i]
        visited.add(i)

        for j in range(i + 1, len(keywords)):
            if j in visited:
                continue

            # 如果相似度大于阈值，归为一类
            if cosine_scores[i][j] > threshold:
                current_cluster_indices.append(j)
                visited.add(j)

        clusters.append(current_cluster_indices)

    # 5. 合并频率
    mapping_dict = {}
    merged_results = []
    all_valid_words = set()

    temp_clusters_data = []
    for cluster_indices in clusters:
        # 获取该簇所有的词
        cluster_words = [keywords[idx] for idx in cluster_indices]
        # print(cluster_words)
        # 策略：取簇中原始频率最高的词作为该簇的“代表词”
        representative_word = max(cluster_words, key=lambda x: frequencies[x])

        # 累加簇内所有词的频率
        total_freq = sum(frequencies[word] for word in cluster_words)

        temp_clusters_data.append({
            'rep': representative_word,
            'freq': total_freq,
            'members': cluster_words
        })

    # 6. 按合并后的频率排序
    temp_clusters_data.sort(key=lambda x: x['freq'], reverse=True)

    # 7. 裁剪并返回结果

    final_clusters = temp_clusters_data[:top_freq_k] \
        if len(temp_clusters_data) > top_freq_k \
        else temp_clusters_data
    for item in final_clusters:
        rep = item['rep']
        merged_results.append((item['rep'], item['freq']))
        all_valid_words.add(item['rep'])
        for member in item['members']:
            all_valid_words.add(member)
            mapping_dict[member] = rep
    return merged_results, all_valid_words, mapping_dict

def topk_clean_interface(input_path, top_k, threshold=0.75, top_freq_k=100, max_workers=1000, target = "DE"):
    raw_top_k = get_key_of_topk(input_file=input_path, top_k=top_k, max_workers=max_workers)
    if target in ["DE", "ID"]:
        final_results, valid_keywords_set, mapping_dict = semantic_merge_keywords(
            raw_top_k,
            threshold=threshold,  # similarity threshold
            top_freq_k=top_freq_k  # the length of final res id less_and_equal this.
        )
        # print("\n--- 合并后的结果 ---")
        # print(f"valid set: {valid_keywords_set}")
        # for word, freq in final_results:
        #     print(f"{word}: {freq}")
        return valid_keywords_set, mapping_dict
    elif target in ["AU", "C1", "CR"]:
        if not raw_top_k:
            return []

        keywords = [item[0] for item in raw_top_k]
        return keywords
    else:
        pass


if __name__ == "__main__":
    INPUT_FILE = r"D:\codes\Visual\extract\keywords\merged_keywords_lower.txt"  # r"E:\China Chem All\extract\keywords\merged_keywords_lower.txt"  #
    TOP_K = 300  # 需要返回前多少个高频词
    MAX_WORKERS = 1000  # 线程池最大线程数
    valid_keywords_set, mapping_dict = topk_clean_interface(INPUT_FILE, TOP_K, 0.7, 100, MAX_WORKERS)