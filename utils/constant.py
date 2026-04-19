# constants.py

"""
全局常量配置文件
"""

# 定义目标提取字段 (Target Name) 到输出子目录 (Sub-directory) 的映射关系
DIR_MAPPING = {
    "DE": "keywords",
    "AU": "authors",
    "ID": "digitwords",
    "C1": "country",
    "CR": "reference"
}

# 你也可以将未来可能用到的其他常量放在这里，例如正则：
DOI_PATTERN_STR = r'10\.\d{4,9}/[^\s,\]]+'