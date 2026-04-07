import os
import threading
from concurrent.futures import ThreadPoolExecutor
import re


def process_single_file(file_path, output_dir, target_name):
    """
    处理单个文件的逻辑
    """
    file_name = os.path.basename(file_path)
    output_path = os.path.join(output_dir, file_name)

    results = []
    idx = 1
    tag_prefix = target_name.upper() + " "

    try:
        # 使用 utf-8 编码读取，如果遇到无法解码的字符则忽略，防止程序中断
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        is_reading_de = False
        current_de_content = []

        for line in lines:
            # 去除行尾换行符
            line_content = line.rstrip()
            if not line_content:
                continue
            # 检查是否以 "DE " 开头 (Web of Science 格式通常是 DE 后跟一个空格)
            if line_content.startswith(tag_prefix):
                # 如果之前正在读取上一个DE（理论上不应该发生，除非没有其他标签隔开），先保存
                if is_reading_de and current_de_content:
                    save_record(results, idx, current_de_content, target_name)
                    idx += 1
                    current_de_content = []
                is_reading_de = True
                # 去掉前3个字符 "DE "
                current_de_content.append(line_content[3:].strip())

            # 检查是否是续行 (以空格开头) 且当前处于读取DE的状态
            elif is_reading_de and (line_content.startswith(" ") or line_content.startswith("\t")):
                current_de_content.append(line_content.strip())

            # 遇到了其他标签 (例如 "ID ", "AB ", "CR " 等，通常是两个大写字母加空格)
            elif is_reading_de and line_content[0].isalpha() and not line_content.startswith(" "):
                # 结束当前DE读取，保存数据
                save_record(results, idx, current_de_content, target_name)
                idx += 1
                # 重置状态
                is_reading_de = False
                current_de_content = []

        # 循环结束后，如果还有未保存的DE（文件以DE结尾的情况）
        if is_reading_de and current_de_content:
            save_record(results, idx, current_de_content, target_name)

        # 将结果写入输出文件
        if results:
            with open(output_path, 'w', encoding='utf-8') as f_out:
                f_out.writelines(results)
            print(f"[线程 {threading.current_thread().name}] 处理完成: {file_name} -> 提取了 {len(results)} 条记录")
        else:
            print(f"[线程 {threading.current_thread().name}] 处理完成: {file_name} (无 DE 字段)")

    except Exception as e:
        print(f"[错误] 处理文件 {file_name} 时出错: {e}")

def save_record(results_list, index, content_list, target_name="DE"):
    """
    辅助函数：格式化并保存提取到的关键词
    """
    if not content_list:
        return
    items = []
    # 将多行内容合并为一行
    full_text = " ".join(content_list).strip()
    if target_name == "DE":
        # Web of Science 的关键词通常用分号 ; 分隔
        # 我们将其分割，去除空白，然后用 ", " 重新连接
        items = [k.strip() for k in full_text.split(';') if k.strip()]
    elif target_name == "AU":
        items = [it.strip() for it in content_list if it.strip()]
    elif target_name == "ID":
        items = [k.strip() for k in full_text.split(';') if k.strip()]
    elif target_name == "C1":
        # process the country
        for line in content_list:
            if not line.strip():
                continue
            # 1. 移除作者部分，即找到最后一个 ']' 之后的内容
            address_part = line.split(']')[-1] if ']' in line else line

            # 2. 地址是以逗号分隔的，国家通常在最后一个逗号后
            addr_components = address_part.split(',')
            if addr_components:
                country = addr_components[-1].strip()
                # 3. 去除末尾的句号
                if country.endswith('.'):
                    country = country[:-1].strip()
                # 美国单独处理
                if "USA" in country:
                    country = "USA"
                elif ("Taiwan" or "taiwan") in country:
                    country = "Peoples R China"
                # 4. 只有当国家名不为空且尚未在 items 中时才添加（去重）
                if country and country not in items:
                    items.append(country)
    elif target_name == "CR":
        doi_pattern = re.compile(r'10\.\d{4,9}/[^\s,\]]+')
        for ref in content_list:
            # 在每一条参考文献中查找所有符合 DOI 格式的字符串
            found_dois = doi_pattern.findall(ref)
            for doi in found_dois:
                # 清洗 DOI：去除末尾的标点符号（如参考文献末尾的句号）
                clean_doi = doi.strip().rstrip('.')
                if clean_doi not in items:
                    items.append(clean_doi)
    else:
        pass

    if items:
        # 给每个项包裹 []
        formatted_items = [f"[{it}]" for it in items]
        # 用逗号连接
        final_line = ", ".join(formatted_items)
        results_list.append(f"{index}. {final_line}\n")

def file_extract(source_dir, output_dir, target_name):
    # 1. 检查源目录是否存在
    if not os.path.exists(source_dir):
        print(f"错误：源目录不存在 -> {source_dir}")
        return

    # 2. 创建输出目录 key_words
    # target_dir = os.path.join(SOURCE_DIR, OUTPUT_DIR_NAME)
    target_dir = output_dir
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"创建输出目录: {target_dir}")
    else:
        print(f"输出目录已存在: {target_dir}")

    # 3. 获取所有txt文件
    txt_files = [f for f in os.listdir(source_dir) if f.lower().endswith('.txt')]

    if not txt_files:
        print("源目录下没有找到 .txt 文件。")
        return

    print(f"发现 {len(txt_files)} 个文本文件，开始多线程处理...")

    # 4. 创建线程池进行处理
    # max_workers 可以根据CPU核心数调整，对于IO密集型任务，设置为 5-10 通常合适
    with ThreadPoolExecutor(max_workers=10) as executor:
        for file_name in txt_files:
            file_path = os.path.join(source_dir, file_name)
            executor.submit(process_single_file, file_path, target_dir, target_name)

    print("所有任务处理完毕。")

if __name__ == '__main__':
    SOURCE_DIR = r"D:\codes\Visual\data"  # r"E:\China Chem All"
    OUTPUT_DIR_NAME = r"D:\codes\Visual\extract"  # r"E:\China Chem All\extract"  #
    TARGET_NAME = "CR"
    if TARGET_NAME == "DE":
        OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "keywords")
    elif TARGET_NAME == "AU":
        OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "authors")
    elif TARGET_NAME == "ID":
        OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "digitwords")
    elif TARGET_NAME == "C1":
        OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "country")
    elif TARGET_NAME == "CR":
        OUTPUT_DIR_NAME = os.path.join(OUTPUT_DIR_NAME, "reference")
    else:
        pass
    file_extract(SOURCE_DIR, OUTPUT_DIR_NAME, TARGET_NAME)