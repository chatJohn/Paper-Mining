import os
import glob
import re
import pandas as pd
from collections import Counter
from sentence_transformers import SentenceTransformer, util
from tqdm import tqdm
import torch
import time

# --- 配置 ---
# 指定文件夹名称
TARGET_FOLDER = r"D:\codes\LLM\extract\keywords"
# 聚类相似度阈值 (0-1)，越低归并越激进，建议 0.75-0.85
SIMILARITY_THRESHOLD = 0.75


def get_file_paths():
    # 使用 os.path.join 确保路径兼容性 (key_words/*.txt)
    search_pattern = os.path.join(TARGET_FOLDER, "Visual *.txt")
    files = glob.glob(search_pattern)
    if not files:
        print(f"错误：在 '{TARGET_FOLDER}' 文件夹下没有找到LLM *.txt 文件！")
        return []
    return files


# 1. 读取所有文件的原始内容
def load_all_words(file_paths):
    all_occurrences = []  # 记录每一次出现，用于统计频次
    unique_words = set()  # 记录唯一词，用于AI聚类

    print(f"正在读取 {len(file_paths)} 个文件...")
    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            # 兼容GBK编码
            with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
                lines = f.readlines()

        for line in lines:
            # 去掉行号 "1. "
            line = re.sub(r'^\d+\.\s*', '', line)
            parts = line.split(',')
            for p in parts:
                k = p.strip().lower()  # 转小写
                # 去除末尾句号
                k = k.rstrip('.')
                if k:
                    all_occurrences.append(k)
                    unique_words.add(k)

    return all_occurrences, list(unique_words)


def batched_cosine_similarity(embeddings, batch_size=500):
    """
    分批次计算相似度并显示进度条
    """
    num_embeddings = len(embeddings)
    all_cosine_scores = []

    # 使用 tqdm 包裹 range，步长为 batch_size
    for i in tqdm(range(0, num_embeddings, batch_size), desc="计算相似度进度"):
        # 取出一个批次的向量
        batch_embeddings = embeddings[i: i + batch_size]

        # 计算该批次与所有向量的相似度
        # 结果维度: [batch_size, num_embeddings]
        batch_scores = util.cos_sim(batch_embeddings, embeddings)

        all_cosine_scores.append(batch_scores)

    # 将所有批次的结果在第 0 维拼接起来
    return torch.cat(all_cosine_scores, dim=0)

# 2. 自动聚类函数 (AI核心部分)
def create_synonym_map(keywords_list, threshold=0.75):
    print("正在加载 AI 模型 (第一次运行需下载，请耐心等待)...")
    try:
        with tqdm(total=1, desc="Loading Model", bar_format="{desc}: {elapsed}") as pbar:
            model = SentenceTransformer('all-MiniLM-L6-v2')
            pbar.update(1)

        print("模型加载完成！")
    except Exception as e:
        print(f"模型加载失败: {e}")
        print("请检查网络或确认已安装: pip install sentence-transformers")
        return {}

    print(f"正在计算 {len(keywords_list)} 个唯一关键词的语义向量...")
    embeddings = model.encode(keywords_list, convert_to_tensor=True)
    print(embeddings[0], embeddings[1])
    print("正在计算相似度并聚类...")
    cosine_scores = batched_cosine_similarity(embeddings, batch_size=500)

    clusters = []
    visited = set()

    for i in tqdm(range(len(keywords_list)), desc="正在聚类"):
        if i in visited:
            continue

        cluster = [keywords_list[i]]
        visited.add(i)

        for j in range(i + 1, len(keywords_list)):
            if j in visited:
                continue

            # 注意：如果 cosine_scores 是 PyTorch Tensor，建议加上 .item()
            # 或者确保 threshold 也是同类型，否则在高版本 torch 中可能会有警告
            if cosine_scores[i][j] > threshold:
                cluster.append(keywords_list[j])
                visited.add(j)

        clusters.append(cluster)

    print(f"聚类完成，共生成 {len(clusters)} 个类别。")

    # 生成映射字典
    mapping = {}
    print("\n=== AI 自动归并结果 ===")
    for cluster in clusters:
        # 选取最长的词作为标准词 (通常全称比缩写长)
        standard_term = max(cluster, key=len)
        if len(cluster) > 1:
            print(f"合并: {cluster} -> {standard_term}")

        for term in cluster:
            mapping[term] = standard_term

    return mapping


# --- 主程序 ---
def main():
    # 1. 获取文件路径
    files = get_file_paths()
    if not files: return

    # 2. 读取数据
    all_raw_words, unique_words_list = load_all_words(files)

    # 3. 生成 AI 映射字典
    synonym_map = create_synonym_map(unique_words_list, threshold=SIMILARITY_THRESHOLD)

    if not synonym_map:
        print("聚类失败，程序终止。")
        return

    # 4. 应用映射并统计
    print("\n正在统计最终频次...")
    cleaned_words = []
    for word in all_raw_words:
        # 如果在映射表里，就替换；否则保持原样
        final_word = synonym_map.get(word, word)
        cleaned_words.append(final_word)

    # 5. 导出结果
    counts = Counter(cleaned_words)
    df = pd.DataFrame(counts.items(), columns=['Keyword', 'Frequency'])
    df = df.sort_values(by='Frequency', ascending=False)

    output_filename = "AI_Clustered_Keywords.xlsx"
    df.to_excel(output_filename, index=False)

    print(f"\n处理完成！")
    print(f"Top 5 高频词: {df.head(5)['Keyword'].tolist()}")
    print(f"结果已保存至: {output_filename}")


if __name__ == "__main__":
    main()