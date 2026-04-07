import os
import re


def merge_text_files(source_dir, output_name):
    # print(source_dir)
    """
    读取指定目录下的所有txt文件，去除旧序号，转小写，重新排序写入新文件。
    """
    # 1. 拼接完整的保存路径
    output_full_path = os.path.join(source_dir, output_name)

    if not os.path.exists(source_dir):
        print(f"错误：找不到目录 {source_dir}")
        return

    # 2. 获取目录下所有txt文件，排除输出文件本身
    files = [f for f in os.listdir(source_dir)
             if f.endswith('.txt') and f != output_name]

    # 3. 自然排序 (确保 Visual 2 在 Visual 10 前面)
    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower()
                for text in re.split('([0-9]+)', s)]

    files.sort(key=natural_sort_key)

    print(f"目录: {source_dir}")
    print(f"找到 {len(files)} 个文件，准备处理...")

    global_index = 1  # 全局计数器

    try:
        # 4. 打开输出文件
        with open(output_full_path, 'w', encoding='utf-8') as outfile:

            for filename in files:
                file_path = os.path.join(source_dir, filename)

                # 兼容编码读取 (优先utf-8，失败尝试gbk)
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        lines = infile.readlines()
                except UnicodeDecodeError:
                    with open(file_path, 'r', encoding='gbk') as infile:
                        lines = infile.readlines()

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # 5. 正则匹配：提取序号后的内容
                    # 匹配 "数字" + "点/顿号/空格" + "内容"
                    match = re.match(r'^\d+\s*[.、]?\s*(.*)', line)

                    if match:
                        content = match.group(1)
                        # content = content.lower()
                        # 写入新序号 + 小写内容
                        outfile.write(f"{global_index}. {content}\n")
                        global_index += 1
                    else:
                        # 如果该行没有序号，直接转小写写入
                        outfile.write(f"{line.lower()}\n")

        print("-" * 30)
        print(f"处理完成！")
        print(f"总行数: {global_index - 1}")
        print(f"文件已保存至: {output_full_path}")  # 这里打印出最终的保存路径

    except PermissionError:
        print(f"错误：无法写入文件。请检查文件 {output_full_path} 是否被占用。")

if __name__ == "__main__":
    target_dir = r"D:\codes\Visual\extract\reference"  # r"E:\China Chem All\extract\keywords"  #
    # save_dir = r"D:\codes\Visual\extract\clean"
    # os.makedirs(save_dir, exist_ok=True)
    # 2. 保存的文件名
    save_filename = "merged_reference.txt"

    # --- 开始执行 ---
    merge_text_files(target_dir, output_name=save_filename)