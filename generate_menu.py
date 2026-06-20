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


def generate_menu():
    current_dir = os.getcwd()
    current_script = os.path.basename(__file__)

    # 临时存放分类数据的字典 { 分类名: { 帖子名: [页面列表] } }
    structure = {}

    # 遍历当前目录下的第一层
    for level1_item in os.listdir(current_dir):
        level1_path = os.path.join(current_dir, level1_item)

        # 只处理文件夹
        if not os.path.isdir(level1_path):
            continue

        # 检查这一层里面有没有 html 文件，或者全都是文件夹
        sub_items = os.listdir(level1_path)
        has_html_directly = any(f.lower().endswith('.html') and f != "index.html" for f in sub_items)
        has_sub_dirs = any(os.path.isdir(os.path.join(level1_path, s)) for s in sub_items)

        # ─── 情况 A：只有一层文件夹 (当前文件夹内直接含有 HTML) ───
        if has_html_directly:
            category = "其他"
            post_title = level1_item  # 第一层文件夹名作为帖子标题

            if category not in structure: structure[category] = {}
            if post_title not in structure[category]: structure[category][post_title] = []

            for file in sub_items:
                if file.lower() == "index.html" or not file.lower().endswith('.html'):
                    continue
                file_path = os.path.join(level1_path, file)
                page_title = get_html_title(file_path, os.path.splitext(file)[0])

                structure[category][post_title].append({
                    "title": page_title,
                    "path": f"./{level1_item}/{file}"
                })

        # ─── 情况 B：有两层文件夹 (第一层里全是夹子，第二层才是 HTML) ───
        elif has_sub_dirs:
            category = level1_item  # 第一层文件夹名作为【分类标签】

            if category not in structure: structure[category] = {}

            # 遍历第二层文件夹（帖子文件夹）
            for level2_item in sub_items:
                level2_path = os.path.join(level1_path, level2_item)
                if not os.path.isdir(level2_path):
                    continue

                post_title = level2_item  # 第二层文件夹名作为【帖子标题】
                if post_title not in structure[category]: structure[category][post_title] = []

                for file in os.listdir(level2_path):
                    if file.lower() == "index.html" or not file.lower().endswith('.html'):
                        continue
                    file_path = os.path.join(level2_path, file)
                    page_title = get_html_title(file_path, os.path.splitext(file)[0])

                    structure[category][post_title].append({
                        "title": page_title,
                        "path": f"./{level1_item}/{level2_item}/{file}"
                    })

    # ────────────────────────────────────────────────────────
    # 格式化为前端需要的数组结构，并进行排序清洗
    # ────────────────────────────────────────────────────────
    menu_data = []

    # 确保如果有“其他”，把它放在最后面排布，常规分类放前面
    sorted_categories = sorted([c for c in structure.keys() if c != "其他"],
                               key=lambda x: x.localeCompare if hasattr(str, 'localeCompare') else x)
    if "其他" in structure:
        sorted_categories.append("其他")

    for cat_name in sorted_categories:
        posts_map = structure[cat_name]
        posts_list = []

        for p_title, pages in posts_map.items():
            if not pages:
                continue
            # 每篇帖子的内部具体 HTML 页面按标题/文件名排序
            pages.sort(key=lambda x: x['title'])

            posts_list.append({
                "title": p_title,
                "total_pages": len(pages),
                "pages": pages
            })

        if posts_list:
            # 帖子列表按名字排序
            posts_list.sort(key=lambda x: x['title'])
            menu_data.append({
                "category": cat_name,
                "posts": posts_list
            })

    # 写入 menuData.js 供 index.html 读取
    js_content = f"var thispost = {json.dumps(menu_data, ensure_ascii=False, indent=4)};"
    with open("menuData.js", "w", encoding="utf-8") as js_file:
        js_file.write(js_content)

    print("☀️ 智能双层目录树 menuData.js 重新生成成功！")
    print("-> 两层文件夹已自动提取第一层为标签")
    print("-> 单层文件夹已全部自动归纳至 '其他' 标签")


if __name__ == "__main__":
    generate_menu()