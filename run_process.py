import os

from FileProcess import file_extract, file_merge
from visualize import analysis


def start_pipeline(source_dir, output_dir_name, file_path, output_path, target, top_k, top_freq_k, threshold, max_workers):
    """
    自动化工作流：提取 -> 合并 -> 分析
    """
    # --- 步骤 1: 提取数据 (file_extract.py) ---
    print(f"\n[Step 1] 正在提取 {target} 数据...")
    file_extract.file_extract(source_dir, output_dir_name, target)
    # --- 步骤 2: 合并文件 (file_merge.py) ---
    print(f"\n[Step 2] 正在合并文件至: {file_path}")
    file_merge.merge_text_files(output_dir_name, f"merged_{TYPE_MAP[target]}_lower.txt")
    # --- 步骤 3: 运行可视化分析 (run_analysis.py) ---
    print(f"\n[Step 3] 正在启动可视化分析...")
    analysis.analysis_interface(file_path, output_path, target, top_k,top_freq_k, threshold, max_workers)
    print("\n" + "=" * 50)
    print(f"工作流执行完毕！")
    print(f"最终结果目录: {output_path}")
    print("=" * 50)

if __name__ == "__main__":
    TYPE_MAP = {
        "DE": "keywords",
        "AU": "authors",
        "ID": "digitwords",
        "C1": "country"
    }
    TYPE_LIST = ["DE", "AU", "ID", "C1"]
    # ================= 配置区域 =================
    # file_extract configs
    SOURCE_DIR = r"E:\China Chem All"

    # file_merge configs

    # analysis configs
    FILE_PATH = None
    OUTPUT_PATH = None
    TARGET = None
    TOP_K = 300  # 只保留出现频率最高的前100个词构建图谱(cleaned)
    TOP_FREQ_K = 100
    THRESHOLD = 0.7
    MAX_WORKERS = 1000  # 线程池最大线程数

    # ==========================================
    for target in TYPE_LIST:
        OUTPUT_DIR_NAME = r"E:\China Chem All\extract"
        print(f"\n>>> 开始处理任务目标: {target} <<<")
        TARGET = target
        if TARGET == "DE":
            OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "keywords")
        elif TARGET == "AU":
            OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "authors")
        elif TARGET == "ID":
            OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "digitwords")
        elif TARGET == "C1":
            OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "country")
        else:
            pass
        FILE_PATH = os.path.join(OUTPUT_DIR_NAME, f"merged_{TYPE_MAP[target]}.txt")
        OUTPUT_PATH = os.path.join(OUTPUT_DIR_NAME, f"merged_{TYPE_MAP[target]}_map.png")
        start_pipeline(SOURCE_DIR, OUTPUT_DIR_NAME, FILE_PATH, OUTPUT_PATH, TARGET, TOP_K, TOP_FREQ_K, THRESHOLD, MAX_WORKERS)