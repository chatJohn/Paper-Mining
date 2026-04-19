import os
import sys
import tempfile
import shutil

# 同样确保能正确导入项目内容
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from main import WosPipelineManager

def test_full_pipeline():
    print("=== 开始端到端测试: 完整数据管道 (Extract -> Merge -> Analysis) ===")
    
    # 1. 建立临时模拟环境
    temp_base = tempfile.mkdtemp()
    source_dir = os.path.join(temp_base, "raw_data")
    extract_dir = os.path.join(temp_base, "extract")
    os.makedirs(source_dir)
    
    try:
        # 2. 生成多份虚拟 Web of Science 原始数据文件
        mock_data_1 = """PT J
AU Smith, J
DE Machine learning; Artificial Intelligence
C1 [Smith, J] Univ ABC, USA.
ER
"""
        mock_data_2 = """PT J
AU Doe, A
DE Artificial Intelligence; Neural Networks
C1 [Doe, A] Some Univ, Japan.
ER
"""
        with open(os.path.join(source_dir, "file1.txt"), "w", encoding="utf-8") as f:
            f.write(mock_data_1)
        with open(os.path.join(source_dir, "file2.txt"), "w", encoding="utf-8") as f:
            f.write(mock_data_2)

        # 3. 初始化并运行测试 (为了加速测试，选取 DE 和 AU 两个代表字段)
        targets_to_test = ["DE", "AU"]
        manager = WosPipelineManager(source_dir=source_dir, 
                                     base_extract_dir=extract_dir, 
                                     max_workers=2)
        
        # 调用核心方法（调小参数以提升测试速度）
        manager.run_all(targets_to_test, top_k=5, top_freq_k=5, threshold=0.6)

        # 4. 断言 (Assertions) 验证全流程是否走通
        expected_results = {
            "DE": {
                "txt": os.path.join(extract_dir, "keywords", "merged_keywords.txt"),
                "png": os.path.join(extract_dir, "keywords", "merged_keywords_map.png")
            },
            "AU": {
                "txt": os.path.join(extract_dir, "authors", "merged_authors.txt"),
                "png": os.path.join(extract_dir, "authors", "merged_authors_map.png")
            }
        }

        for target, paths in expected_results.items():
            txt_path = paths["txt"]
            png_path = paths["png"]

            # 验证合并文件是否生成且有内容
            assert os.path.exists(txt_path), f"测试失败：目标 {target} 的合并文件 {txt_path} 未生成！"
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) > 0, f"测试失败：目标 {target} 的合并文件为空！"
            
            # 验证最终的 PNG 图像是否被渲染出来
            assert os.path.exists(png_path), f"测试失败：目标 {target} 的分析图像 {png_path} 未生成！"
            print(f"  -> {target} 流程 (提取 + 合并 + 绘图) 验证通过！")

        print("\n=== 所有 Pipeline 测试圆满通过，临时文件已自动清理！ ===")

    finally:
        # 5. 测试结束，无论成功失败都清理占用系统空间的临时数据
        shutil.rmtree(temp_base)


if __name__ == "__main__":
    test_full_pipeline()