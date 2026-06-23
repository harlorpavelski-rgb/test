import os
import json
import re


def get_html_title(file_path, default_title):
    """读取 HTML 文件提取 <title>，提取不到则用文件名"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            if title_match:
                return title_match.group(1).strip()
    except Exception:
        pass
    return default_title


def is_valid_file(file_name):
    """检查文件是否属于系统所支持的阅读格式"""
    name_lower = file_name.lower()
    if name_lower == "index.html":
        return False
    valid_extensions = ['.html', '.htm', '.txt', '.md', '.docx']
    return any(name_lower.endswith(ext) for ext in valid_extensions)


def generate_menu():
    current_dir = os.getcwd()

    # 临时存放分类数据的字典 { 分类名: { 帖子名: [页面列表] } }
    structure = {}

    # ========================================================
    # 第一步：遍历当前程序根目录
    # ========================================================
    for level1_item in os.listdir(current_dir):
        level1_path = os.path.join(current_dir, level1_item)

        # ─── 1. 如果直接是根目录下的【散落文件】 -> 全部归入“其他” ───
        if os.path.isfile(level1_path):
            if is_valid_file(level1_item):
                category = "其他"
                base_name = os.path.splitext(level1_item)[0]

                if level1_item.lower().endswith(('.html', '.htm')):
                    page_title = get_html_title(level1_path, base_name)
                    post_title = page_title
                else:
                    page_title = base_name
                    ext = os.path.splitext(level1_item)[1].lower()
                    post_title = f"{base_name} ({ext[1:].upper()})"

                if category not in structure: structure[category] = {}
                if post_title not in structure[category]: structure[category][post_title] = []

                structure[category][post_title].append({
                    "title": page_title,
                    "path": f"./{level1_item}"
                })
            continue

        # ─── 2. 如果是根目录下的【文件夹】 -> 内部并行精准扫描 ───
        sub_items = os.listdir(level1_path)

        # 【核心修正 A】：单独提取该文件夹下“直接包含的 HTML 文件”
        # 只要根目录下的文件夹里直接躺着 HTML，它就是你要的“以该文件夹命名的博文”，丢进 -> “其他”
        direct_html_files = [f for f in sub_items if
                             os.path.isfile(os.path.join(level1_path, f)) and f.lower().endswith(
                                 ('.html', '.htm')) and f.lower() != "index.html"]

        if direct_html_files:
            category = "其他"
            post_title = level1_item  # 以这个根目录下的文件夹名字作为博文名

            if category not in structure: structure[category] = {}
            if post_title not in structure[category]: structure[category][post_title] = []

            for file in direct_html_files:
                file_path = os.path.join(level1_path, file)
                page_title = get_html_title(file_path, os.path.splitext(file)[0])
                structure[category][post_title].append({
                    "title": page_title,
                    "path": f"./{level1_item}/{file}"
                })

        # 【核心修正 B】：单独提取该文件夹下“直接包含的 txt/md/docx 文件”
        # 散落的其它非 HTML 格式文档，依照原本规则留在 -> 当前第一层文件夹名的标签下
        direct_other_files = [f for f in sub_items if os.path.isfile(os.path.join(level1_path, f)) and is_valid_file(
            f) and not f.lower().endswith(('.html', '.htm'))]

        if direct_other_files:
            category = level1_item
            if category not in structure: structure[category] = {}

            for file in direct_other_files:
                file_path = os.path.join(level1_path, file)
                base_name = os.path.splitext(file)[0]
                ext = os.path.splitext(file)[1].lower()
                post_title = f"{base_name} ({ext[1:].upper()})"

                if post_title not in structure[category]: structure[category][post_title] = []
                structure[category][post_title].append({
                    "title": base_name,
                    "path": f"./{level1_item}/{file}"
                })

        # 【核心修正 C】：扫描传统标准双层结构（文件夹里的子文件夹）
        # 此时第一层文件夹（level1_item）是分类标签，第二层文件夹（level2_item）是博文名，绝对不打乱！
        for level2_item in sub_items:
            level2_path = os.path.join(level1_path, level2_item)
            if not os.path.isdir(level2_path):
                continue

            category = level1_item  # 标签名
            post_title = level2_item  # 博文名

            if category not in structure: structure[category] = {}
            if post_title not in structure[category]: structure[category][post_title] = []

            for file in os.listdir(level2_path):
                if not is_valid_file(file):
                    continue
                file_path = os.path.join(level2_path, file)
                base_name = os.path.splitext(file)[0]

                if file.lower().endswith(('.html', '.htm')):
                    page_title = get_html_title(file_path, base_name)
                else:
                    ext = os.path.splitext(file)[1].lower()
                    page_title = f"{base_name} ({ext[1:].upper()})"

                structure[category][post_title].append({
                    "title": page_title,
                    "path": f"./{level1_item}/{level2_item}/{file}"
                })

    # ========================================================
    # 第二步：格式化为前端需要的数组结构，并进行排序清洗
    # ========================================================
    menu_data = []

    sorted_categories = sorted([c for c in structure.keys() if c != "其他"])
    if "其他" in structure:
        sorted_categories.append("其他")

    for cat_name in sorted_categories:
        posts_map = structure[cat_name]
        posts_list = []

        for p_title, pages in posts_map.items():
            if not pages:
                continue
            pages.sort(key=lambda x: x['title'])

            posts_list.append({
                "title": p_title,
                "total_pages": len(pages),
                "pages": pages
            })

        if posts_list:
            posts_list.sort(key=lambda x: x['title'])
            menu_data.append({
                "category": cat_name,
                "posts": posts_list
            })

    # 写入 menuData.js 供 index.html 读取
    js_content = f"var thispost = {json.dumps(menu_data, ensure_ascii=False, indent=4)};"
    with open("menuData.js", "w", encoding="utf-8") as js_file:
        js_file.write(js_content)

    print("☀️ 智能目录树完美修复完成！")
    print("-> 根目录下单层文件夹里的 html：已成功以该文件夹命名，并全部放入 '其他' 标签下。")
    print("-> 两层标准博文文件夹：内页回流正常，完整保留在原本的分类标签内，互不干扰。")


if __name__ == "__main__":
    generate_menu()