import os
import re

class TextFilesMerger:
    def __init__(self, source_dir, output_name):
        """
        初始化合并器
        :param source_dir: 待处理的 txt 文件所在目录
        :param output_name: 合并后输出的文件名
        """
        self.source_dir = source_dir
        self.output_name = output_name
        self.output_full_path = os.path.join(self.source_dir, self.output_name)
        
        # 预编译正则表达式以提升性能 (避免在循环中重复编译)
        # 匹配行首的旧序号：数字 + 可选的空白符 + 可选的点或顿号 + 可选的空白符 + 实际内容
        self.line_pattern = re.compile(r'^\d+\s*[.、]?\s*(.*)')
        # 匹配数字串，用于文件名的自然排序提取
        self.sort_pattern = re.compile(r'([0-9]+)')

    def _natural_sort_key(self, filename):
        """内部方法：自然排序的 key 函数 (确保 Visual 2 在 Visual 10 前面)"""
        return[int(text) if text.isdigit() else text.lower()
                for text in self.sort_pattern.split(filename)]

    def _read_file_lines(self, file_path):
        """内部方法：兼容双重编码读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as infile:
                return infile.readlines()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='gbk') as infile:
                return infile.readlines()

    def merge(self):
        """主执行方法：合并、清洗并重新编号文件"""
        if not os.path.exists(self.source_dir):
            print(f"错误：找不到目录 {self.source_dir}")
            return

        # 1. 获取所有 txt 文件，排除掉输出文件本身
        files =[f for f in os.listdir(self.source_dir)
                 if f.endswith('.txt') and f != self.output_name]

        # 2. 按照自然排序对文件列表进行排序
        files.sort(key=self._natural_sort_key)

        print(f"目录: {self.source_dir}")
        print(f"找到 {len(files)} 个文件，准备处理...")

        global_index = 1  # 全局序号计数器

        try:
            # 3. 统一处理并写入输出文件
            with open(self.output_full_path, 'w', encoding='utf-8') as outfile:
                for filename in files:
                    file_path = os.path.join(self.source_dir, filename)
                    lines = self._read_file_lines(file_path)

                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue

                        # 4. 正则匹配并提取
                        match = self.line_pattern.match(line)
                        if match:
                            content = match.group(1)
                            # 如果需要完全转小写，可以取消下一行的注释
                            # content = content.lower()
                            
                            # 写入新序号 + 内容
                            outfile.write(f"{global_index}. {content}\n")
                            global_index += 1
                        else:
                            # 如果该行没有序号，直接转小写写入
                            outfile.write(f"{line.lower()}\n")

            print("-" * 30)
            print("处理完成！")
            print(f"总行数: {global_index - 1}")
            print(f"文件已保存至: {self.output_full_path}")

        except PermissionError:
            print(f"错误：无法写入文件。请检查文件 {self.output_full_path} 是否被占用。")
        except Exception as e:
            print(f"合并过程中出现未知错误: {e}")


if __name__ == "__main__":
    # 实际运行入口
    TARGET_DIR = r"./extract/reference"
    SAVE_FILENAME = "merged_reference.txt"

    merger = TextFilesMerger(source_dir=TARGET_DIR, output_name=SAVE_FILENAME)
    merger.merge()