# extractor.py
import os
import sys
import threading
import re
from concurrent.futures import ThreadPoolExecutor


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.constant import DIR_MAPPING, DOI_PATTERN_STR

class WosFieldExtractor:
    def __init__(self, source_dir, base_output_dir, target_name, max_workers=10):
        """
        初始化提取器
        :param source_dir: 源文件所在目录
        :param base_output_dir: 基础输出目录
        :param target_name: 提取目标字段 (如 DE, AU, C1, CR 等)
        :param max_workers: 线程池最大线程数
        """
        self.source_dir = source_dir
        self.base_output_dir = base_output_dir
        self.target_name = target_name.upper()
        self.max_workers = max_workers
        self.tag_prefix = f"{self.target_name} "
        
        # 预编译 DOI 正则表达式
        self.doi_pattern = re.compile(DOI_PATTERN_STR)
        
        # 确定最终的输出目录
        self.output_dir = self._determine_output_dir()

    def _determine_output_dir(self):
        """根据 target_name 从常量的映射表中获取输出子目录"""
        # 使用 constants.py 中定义的 DIR_MAPPING
        sub_dir = DIR_MAPPING.get(self.target_name, self.target_name.lower())
        return os.path.join(self.base_output_dir, sub_dir)

    def _format_and_save_record(self, results_list, index, content_list):
        """格式化并保存提取到的记录"""
        if not content_list:
            return
        
        items =[]
        full_text = " ".join(content_list).strip()

        if self.target_name in ("DE", "ID"):
            items =[k.strip() for k in full_text.split(';') if k.strip()]
            
        elif self.target_name == "AU":
            items =[it.strip() for it in content_list if it.strip()]
            
        elif self.target_name == "C1":
            for line in content_list:
                if not line.strip():
                    continue
                address_part = line.split(']')[-1] if ']' in line else line
                addr_components = address_part.split(',')
                if addr_components:
                    country = addr_components[-1].strip()
                    if country.endswith('.'):
                        country = country[:-1].strip()
                        
                    if "USA" in country:
                        country = "USA"
                    elif "Taiwan" in country or "taiwan" in country:
                        country = "Peoples R China"
                        
                    if country and country not in items:
                        items.append(country)
                        
        elif self.target_name == "CR":
            for ref in content_list:
                found_dois = self.doi_pattern.findall(ref)
                for doi in found_dois:
                    clean_doi = doi.strip().rstrip('.')
                    if clean_doi not in items:
                        items.append(clean_doi)

        if items:
            formatted_items = [f"[{it}]" for it in items]
            final_line = ", ".join(formatted_items)
            results_list.append(f"{index}. {final_line}\n")

    def _process_single_file(self, file_name):
        """处理单个文件的核心逻辑"""
        file_path = os.path.join(self.source_dir, file_name)
        output_path = os.path.join(self.output_dir, file_name)
        
        results =[]
        idx = 1

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            is_reading_target = False
            current_content =[]

            for line in lines:
                line_content = line.rstrip()
                if not line_content:
                    continue

                if line_content.startswith(self.tag_prefix):
                    if is_reading_target and current_content:
                        self._format_and_save_record(results, idx, current_content)
                        idx += 1
                        current_content =[]
                        
                    is_reading_target = True
                    current_content.append(line_content[3:].strip())

                elif is_reading_target and (line_content.startswith(" ") or line_content.startswith("\t")):
                    current_content.append(line_content.strip())

                elif is_reading_target and line_content[0].isalpha() and not line_content.startswith(" "):
                    self._format_and_save_record(results, idx, current_content)
                    idx += 1
                    is_reading_target = False
                    current_content =[]

            if is_reading_target and current_content:
                self._format_and_save_record(results, idx, current_content)

            if results:
                with open(output_path, 'w', encoding='utf-8') as f_out:
                    f_out.writelines(results)
                print(f"[线程 {threading.current_thread().name}] 处理完成: {file_name} -> 提取了 {len(results)} 条记录")
            else:
                print(f"[线程 {threading.current_thread().name}] 处理完成: {file_name} (无 {self.target_name} 字段)")

        except Exception as e:
            print(f"[错误] 处理文件 {file_name} 时出错: {e}")

    def extract(self):
        """启动多线程提取任务"""
        if not os.path.exists(self.source_dir):
            print(f"错误：源目录不存在 -> {self.source_dir}")
            return

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"创建输出目录: {self.output_dir}")
        else:
            print(f"输出目录已存在: {self.output_dir}")

        txt_files =[f for f in os.listdir(self.source_dir) if f.lower().endswith('.txt')]

        if not txt_files:
            print("源目录下没有找到 .txt 文件。")
            return

        print(f"发现 {len(txt_files)} 个文本文件，开始多线程处理...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for file_name in txt_files:
                executor.submit(self._process_single_file, file_name)

        print("所有任务处理完毕。")


if __name__ == '__main__':
    # 实际运行入口
    SOURCE_DIR = "./data"
    OUTPUT_DIR_NAME = "./extract"
    TARGET_NAME = "AU"
    
    extractor = WosFieldExtractor(
        source_dir=SOURCE_DIR, 
        base_output_dir=OUTPUT_DIR_NAME, 
        target_name=TARGET_NAME,
        max_workers=10
    )
    extractor.extract()