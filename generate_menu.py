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


def get_distinct_post_title(file_name, base_title):
    """
    根据文件后缀，为非 HTML 文件生成带格式区分的独立标题，防止同名覆盖
    """
    ext = os.path.splitext(file_name)[1].lower()
    if ext in ['.html', '.htm']:
        return base_title
    elif ext == '.md':
        return f"{base_title} (Markdown)"
    elif ext == '.docx':
        return f"{base_title} (Word)"
    elif ext == '.txt':
        return f"{base_title} (Txt)"
    return f"{base_title} ({ext[1:].upper()})"


def generate_menu():
    current_dir = os.getcwd()

    # 临时存放分类数据的字典 { 分类名: { 帖子名: [页面列表] } }
    structure = {}

    # 辅助函数：统一将文件添加到指定的分类中
    def add_file_to_structure(cat_name, file_name, file_real_path, relative_url_path):
        if cat_name not in structure:
            structure[cat_name] = {}

        base_name = os.path.splitext(file_name)[0]
        if file_name.lower().endswith(('.html', '.htm')):
            page_title = get_html_title(file_real_path, base_name)
        else:
            page_title = base_name

        post_title = get_distinct_post_title(file_name, page_title)

        if post_title not in structure[cat_name]:
            structure[cat_name][post_title] = []

        structure[cat_name][post_title].append({
            "title": page_title,
            "path": relative_url_path
        })

    root_items = os.listdir(current_dir)

    # ========================================================
    # 第一步：直接扫描【真·根目录】下的散落文件 -> 全部归位到“其他”
    # ========================================================
    for file in root_items:
        if os.path.isfile(os.path.join(current_dir, file)) and is_valid_file(file):
            add_file_to_structure(
                cat_name="其他",
                file_name=file,
                file_real_path=os.path.join(current_dir, file),
                relative_url_path=f"./{file}"
            )

    # ========================================================
    # 第二步：循环遍历第一层子文件夹（标签文件夹）
    # ========================================================
    for level1_item in root_items:
        level1_path = os.path.join(current_dir, level1_item)

        # 只处理第一层文件夹
        if not os.path.isdir(level1_path):
            continue

        sub_items = os.listdir(level1_path)

        # ─── 1. 处理第一层文件夹下直接放的文件 ───
        for file in sub_items:
            file_real_path = os.path.join(level1_path, file)
            if not os.path.isfile(file_real_path) or not is_valid_file(file):
                continue

            # 【核心逻辑点】：判断第一层目录下的单个文件格式
            if file.lower().endswith(('.html', '.htm')):
                # 散落的单个 HTML 文件是博文名，分到 -> “其他”
                target_category = "其他"
            else:
                # 散落的 txt/md/docx 依然留在 -> 当前标签文件夹下
                target_category = level1_item

            add_file_to_structure(
                cat_name=target_category,
                file_name=file,
                file_real_path=file_real_path,
                relative_url_path=f"./{level1_item}/{file}"
            )

        # ─── 2. 保留两层子文件夹传统结构（正规的传统博文文件夹） ───
        for level2_item in sub_items:
            level2_path = os.path.join(level1_path, level2_item)
            if not os.path.isdir(level2_path):
                continue

            # 第一层文件夹名 level1_item 作为分类标签
            category = level1_item
            if category not in structure:
                structure[category] = {}

            # 遍历博文文件夹里的 HTML 或其它页面
            for file in os.listdir(level2_path):
                if not is_valid_file(file):
                    continue
                file_real_path = os.path.join(level2_path, file)
                base_name = os.path.splitext(file)[0]

                if file.lower().endswith(('.html', '.htm')):
                    page_title = get_html_title(file_real_path, base_name)
                else:
                    page_title = base_name

                # 正规博文文件夹：用第二层文件夹名（level2_item）作为总标题！
                post_title = get_distinct_post_title(file, level2_item)

                if post_title not in structure[category]:
                    structure[category][post_title] = []

                structure[category][post_title].append({
                    "title": page_title,
                    "path": f"./{level1_item}/{level2_item}/{file}"
                })

    # ────────────────────────────────────────────────────────
    # 第三步：格式化并进行标准排序（确保“其他”永远在最后面）
    # ────────────────────────────────────────────────────────
    menu_data = []

    sorted_categories = sorted([c for c in structure.keys() if c != "其他"])
    if "其他" in structure:
        sorted_categories.append("other_placeholder")  # 用占位符让“其他”垫底

    for cat_name in sorted_categories:
        real_cat_name = "其他" if cat_name == "other_placeholder" else cat_name
        posts_map = structure[real_cat_name]
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
                "category": real_cat_name,
                "posts": posts_list
            })

    # 写入 menuData.js
    js_content = f"var thispost = {json.dumps(menu_data, ensure_ascii=False, indent=4)};"
    with open("menuData.js", "w", encoding="utf-8") as js_file:
        js_file.write(js_content)

    print("☀️ 独立 HTML 已精准切分至“其他”标签，索引树编译圆满成功！")


if __name__ == "__main__":
    generate_menu()