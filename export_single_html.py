import argparse
import base64
import hashlib
import mimetypes
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
# 直接全选替换莴苣同名文件内容然后删掉，防止误点

OUTPUT_DIR_NAME = "_single_html_exports"
IMAGE_ATTRS = (
    "data-archived-original-url",
    "data-original",
    "data-origin-src",
    "data-photo-url",
    "data-orig",
    "data-raw-src",
    "data-src",
    "src",
)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"}
IMAGE_MAGIC = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",
    b"BM": ".bmp",
}
DOUBANIO_HOSTS = ("img1.doubanio.com", "img2.doubanio.com", "img3.doubanio.com", "img9.doubanio.com")
DECORATION_URL_MARKERS = (
    "/group-static/pics/uploader.png",
    "/pics/nav/",
    "/pics/icon/",
    "/favicon",
)
DECORATION_CLASSES = {
    "upload-icon",
    "remove-img",
}
VISIBILITY_WARNING_MARKERS = (
    "含有违规或引发不良讨论的内容，内容仅自己可见，请勿发布同类信息",
    "含有违规或引发不良讨论的内容, 内容仅自己可见, 请勿发布同类信息",
)
POLL_SELECTED_MARKERS = (
    "（已选）",
    "(已选)",
    "（我已选）",
    "(我已选)",
)


try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


LOCAL_STYLE = """
html {
  background: #f4f3ee;
  /* 关键点 1：防止页面整体出现因微小溢出导致的横向空白滚动条 */
  overflow-x: hidden; 
}
body {
  box-sizing: border-box;
  max-width: 960px;
  min-height: 100vh;
  margin: 0 auto;
  padding: 20px 30px;
  color: #1f2a2a;
  background: #fff;
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  /* 关键点 2：防止 body 子元素溢出导致页面整体被撑开出现大面积空白 */
  overflow-x: hidden; 
}
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
a {
  /* 关键点 3：修复原代码中非法的 '//' 注释，它会导致后面的样式解析失败 */
  color: #00715d; /* 页码 */
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
img {
  /* 关键点 4：限制最大宽度为 100%，防止大图撑破母容器 */
  max-width: 100%;
  height: auto;
  cursor: zoom-in;
}

/* 放大正文段落之间的上下间距，提升阅读舒适度 */
p {
  margin: 0 0 10px 0 !important;
  padding: 0 !important;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.45;
}
h1 {
  margin: 0 0 14px 0;
  padding: 12px 0 8px 0;
  color: #111;
  font-size: 22px;
  line-height: 1.3;
  font-weight: 700;
  border-bottom: 1px solid #e5e1d9;
}
h2 {
  margin: 8px 0 6px 0;
  color: #333;
  font-size: 16px;
}

h3, h4 {
  margin: 0 0 6px 0 !important;
  padding: 0 !important;
  color: #667071; /* 用户名 */
  font-size: 13px;
  line-height: 1.2;
  font-weight: bold;
}
h3 .from a, h4 > a:first-child, .from a {
  color: #00715d;
  font-weight: 700;
}
.pubtime, .topic-meta, .create-time, .update-time, .ip-location {
  color: #697577; /* 日期 */
  font-size: 12px;
  margin-left: 6px;
}

/* 引用块：只保留最外面那道竖线，留出舒适的呼吸内边距 */
blockquote,
.reply-quote {
  margin: 6px 0 10px 0 ;
  padding: 8px 12px ;
  color: #4a5a5a; /* 被回复内容 */
  border-left: 3px solid #d7ded4 ;
  background: #f4f5f1 ; /* 被回复背景框 */
}
pre, code {
  white-space: pre-wrap;
  word-break: break-word;
}
table {
  max-width: 100%;
  border-collapse: collapse;
}

/* 剥离内部嵌套节点的所有竖线和重复背景 */
.reply-quote-content,
.ref-comment,
.markdown blockquote {
  margin: 0 !important;
  padding: 0 !important;
  border-left: none !important;
  background: transparent !important;
  color: inherit !important;
  font-size: inherit !important;
  line-height: inherit !important;
}

/* 放大每条评论之间的上下间距 */
#topic-content.topic-content,
.comment-item {
  display: block !important;
  position: relative;
  padding: 16px 0 16px 54px !important; /* 明显的上下留白，杜绝拥挤 */
  margin: 0 !important;
  border-bottom: 1px solid #e5e1d9;
  min-height: 52px;
  /* 关键点 5：防止头像绝对定位（left:0）或负 margins 在特定极端情况下产生的微小溢出 */
  overflow: hidden; 
}

.user-face, .avatar {
  position: absolute;
  left: 0;
  top: 16px; /* 随内边距完美平移对齐 */
  width: 40px !important;
  margin: 0 !important;
  padding: 0 !important;
}
.user-face img, .avatar img, img.pil {
  display: block;
  width: 36px !important;
  height: 36px !important;
  object-fit: cover;
  border-radius: 4px;
  background: #e8e5dd;
}

.reply-doc, .topic-doc, .rich-content, .topic-richtext, .reply-content, .markdown {
  margin: 0 !important;
  padding: 0 !important;
  line-height: 1.45;
  /* 关键点 6：确保长英文字符或无空格文本不会横向撑开母容器 */
  word-break: break-word; 
  letter-spacing: 0.5px; /* ← 加在这里，全局正文及评论字距生效 */
}
.reply-content, .topic-richtext {
  color: #1f2a2a;/*评论字*/
  font-size: 16px;
  margin-top: 4px !important;
}

.topic-richtext img, .reply-content img, .markdown img, .content img:not(.pil) {
  display: block;
  max-width: min(100%, 640px) !important;
  height: auto !important;
  margin: 8px 0 !important;
}
.comment-photos {
  display: block !important;
  margin: 6px 0 !important;
}
.cmt-img img, .comment-photos img {
  display: block !important;
  max-width: 100% !important; /* 关键点 8：同上，移除固定 px 上限防溢出 */
  margin: 6px 0 !important;
}

.single-file-lightbox {
  position: fixed;
  inset: 0;
  z-index: 999999;
  display: none;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.82);
}
.single-file-lightbox img {
  max-width: 96vw;
  max-height: 94vh;
  cursor: zoom-out;
}
.single-file-lightbox.is-open {
  display: flex;
}

#db-global-nav, #db-nav-group, .global-nav, .nav, .nav-wrap, .footer, #footer,
.comment-vote, .lnk-reply, .lnk-delete-comment, .lnk-reaction, .report {
  display: none !important;
}
"""


LIGHTBOX_SCRIPT = """
(function () {
  if (window.__doubanSingleFileLightbox) return;
  window.__doubanSingleFileLightbox = true;

  var overlay = document.createElement('div');
  overlay.className = 'single-file-lightbox';
  var enlarged = document.createElement('img');
  overlay.appendChild(enlarged);
  document.body.appendChild(overlay);

  function close() {
    overlay.classList.remove('is-open');
    enlarged.removeAttribute('src');
  }

  document.addEventListener('click', function (event) {
    var target = event.target;
    if (target && target.tagName === 'IMG' && target.currentSrc) {
      event.preventDefault();
      enlarged.src = target.currentSrc;
      overlay.classList.add('is-open');
    }
  });

  overlay.addEventListener('click', close);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') close();
  });
}());
"""


def is_remote_url(value):
    return value.startswith("http://") or value.startswith("https://") or value.startswith("//")


def is_data_url(value):
    return value.startswith("data:")


def guess_mime(path):
    mime, _encoding = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def file_to_data_uri(path):
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{guess_mime(path)};base64,{encoded}"


def normalize_remote_url(value):
    if value.startswith("//"):
        return "https:" + value
    return value


def image_filename(img_url):
    parsed = urlparse(img_url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext not in IMAGE_EXTS:
        ext = ".jpg"

    digest = hashlib.md5(img_url.encode("utf-8")).hexdigest()[:12]
    return f"img_{digest}{ext}"


def image_url_candidates(img_url):
    candidates = []

    def add_candidate(url):
        if url and url not in candidates:
            candidates.append(url)

    img_url = normalize_remote_url(img_url)
    add_candidate(img_url)

    replacements = [
        ("/view/richtext/s/", "/view/richtext/large/"),
        ("/view/richtext/s/", "/view/richtext/raw/"),
        ("/view/richtext/s/", "/view/richtext/l/"),
        ("/view/richtext/m/", "/view/richtext/large/"),
        ("/view/richtext/m/", "/view/richtext/raw/"),
        ("/view/richtext/l/", "/view/richtext/large/"),
        ("/view/richtext/l/", "/view/richtext/raw/"),
        ("/view/richtext/large/", "/view/richtext/raw/"),
        ("/view/richtext/large/", "/view/richtext/l/"),
        ("/view/richtext/large/", "/view/richtext/s/"),
        ("/view/richtext/large/public/", "/view/richtext/public/"),
        ("/view/richtext/raw/", "/view/richtext/large/"),
        ("/view/richtext/raw/", "/view/richtext/l/"),
        ("/view/richtext/raw/", "/view/richtext/s/"),
        ("/view/richtext/raw/public/", "/view/richtext/public/"),
        ("/view/photo/l/public/", "/view/photo/raw/public/"),
        ("/view/photo/m/public/", "/view/photo/l/public/"),
        ("/view/group_topic/l/public/", "/view/group_topic/raw/public/"),
    ]
    for old, new in replacements:
        if old in img_url:
            add_candidate(img_url.replace(old, new))

    for candidate in list(candidates):
        parsed = urlparse(candidate)
        if parsed.netloc in DOUBANIO_HOSTS:
            for host in DOUBANIO_HOSTS:
                if host != parsed.netloc:
                    add_candidate(parsed._replace(netloc=host).geturl())

    return candidates


def candidate_local_files(images_dir, img_url):
    for candidate_url in image_url_candidates(img_url):
        filename = image_filename(candidate_url)
        path = images_dir / filename
        yield path

        base = path.with_suffix("")
        for ext in IMAGE_EXTS:
            if ext != path.suffix.lower():
                yield base.with_suffix(ext)


def find_archived_remote_image(html_path, img_url):
    images_dir = html_path.parent / "images"
    if not images_dir.is_dir():
        return None

    seen = set()
    for path in candidate_local_files(images_dir, img_url):
        if path in seen:
            continue
        seen.add(path)
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def detect_image_ext(data):
    for magic, ext in IMAGE_MAGIC.items():
        if data.startswith(magic):
            if ext == ".webp" and b"WEBP" not in data[:16]:
                continue
            return ext
    return None


def save_downloaded_image(images_dir, img_url, data):
    filename = image_filename(img_url)
    detected_ext = detect_image_ext(data)
    if detected_ext:
        filename = Path(filename).with_suffix(detected_ext).name

    images_dir.mkdir(parents=True, exist_ok=True)
    path = images_dir / filename
    path.write_bytes(data)
    return path


def fetch_archived_remote_image(html_path, remote_urls, session):
    images_dir = html_path.parent / "images"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://www.douban.com/",
    }

    seen = set()
    for remote_url in remote_urls:
        for candidate_url in image_url_candidates(remote_url):
            if candidate_url in seen:
                continue
            seen.add(candidate_url)
            try:
                response = session.get(candidate_url, headers=headers, timeout=30, allow_redirects=True)
            except requests.RequestException:
                continue

            content_type = response.headers.get("Content-Type", "").lower()
            data = response.content
            if response.status_code != 200 or not data:
                continue
            if "image" not in content_type and not detect_image_ext(data):
                continue

            return save_downloaded_image(images_dir, candidate_url, data)

    return None


def resolve_local_path(html_path, raw_src):
    if not raw_src or is_remote_url(raw_src) or is_data_url(raw_src):
        return None

    parsed = urlparse(raw_src)
    local_part = unquote(parsed.path or raw_src)
    local_part = local_part.split("#", 1)[0].split("?", 1)[0]
    if not local_part:
        return None

    candidate = (html_path.parent / local_part).resolve()
    try:
        candidate.relative_to(html_path.parent.resolve())
    except ValueError:
        return None

    return candidate if candidate.is_file() else None


def remove_remote_dependencies(soup):
    for tag in soup.find_all("script"):
        src = tag.get("src", "").strip()
        if src and is_remote_url(src):
            tag.decompose()

    for tag in soup.find_all(["link", "source"]):
        href = tag.get("href", "").strip()
        srcset = tag.get("srcset", "").strip()
        if (href and is_remote_url(href)) or (srcset and "http" in srcset):
            tag.decompose()

    for tag in soup.find_all(True):
        for attr in ("srcset", "data-srcset"):
            if attr in tag.attrs:
                del tag.attrs[attr]


def remove_douban_chrome_and_actions(soup):
    selectors = [
        "#db-global-nav",
        "#db-nav-group",
        ".global-nav",
        ".nav-wrap",
        ".nav-primary",
        ".nav-items",
        ".nav-search",
        ".top-nav-info",
        ".nav-user-account",
        ".top-nav-reminder",
        ".top-nav-doubanapp",
        "#footer",
        ".footer",
        ".back-to-top",
        ".sns-bar",
        ".tabs",
        ".topic-opts-bar",
        ".action-react",
        ".operation-div",
        ".operation-more",
        ".comment-report-wrapper",
        ".report",
        ".image-download-failed",
        ".single-file-missing-image",
        ".reply-form",
        ".comment-form",
        "#last",
        "#reply_form",
    ]
    for selector in selectors:
        for tag in soup.select(selector):
            tag.decompose()

    interaction_classes = {
        "comment-vote",
        "lnk-reply",
        "lnk-delete-comment",
        "lnk-reaction",
        "react-btn",
        "react-cancel-like",
        "react-num",
        "react-text",
    }
    for tag in list(soup.find_all(True)):
        classes = set(tag.get("class") or [])
        if classes & interaction_classes:
            tag.decompose()

    remove_text_markers = {
        "赞",
        "已赞",
        "回复",
        "投诉",
        "删除",
        "你的回复",
    }
    for tag in list(soup.find_all(["a", "button", "span", "h2"])):
        text = tag.get_text(" ", strip=True)
        if text in remove_text_markers:
            tag.decompose()


def remove_douban_people_links(soup):
    for link in list(soup.find_all("a", href=True)):
        href = link.get("href", "").strip()
        if re.search(r"(^https?://www\.douban\.com/people/|^https?://www\.douban\.com/people$|^/people/)", href):
            link.unwrap()


def remove_visibility_warning_lines(soup):
    block_tags = {"p", "div", "li", "span", "td", "blockquote"}

    for text_node in list(soup.find_all(string=lambda text: text and any(marker in text for marker in VISIBILITY_WARNING_MARKERS))):
        parent = text_node.parent
        if not parent or parent.name in ("script", "style", "noscript"):
            continue

        original_text = str(text_node)
        kept_lines = [
            line for line in original_text.splitlines()
            if not any(marker in line for marker in VISIBILITY_WARNING_MARKERS)
        ]

        if not kept_lines:
            if parent.name in block_tags and parent.get_text(strip=True) == original_text.strip():
                parent.decompose()
            else:
                text_node.extract()
            continue

        text_node.replace_with("\n".join(kept_lines))


def normalize_poll_blocks(soup):
    for text_node in list(soup.find_all(string=lambda text: text and any(marker in text for marker in POLL_SELECTED_MARKERS))):
        cleaned = str(text_node)
        for marker in POLL_SELECTED_MARKERS:
            cleaned = cleaned.replace(marker, "")
        text_node.replace_with(cleaned)

    for tag in list(soup.find_all(["button", "input", "a", "span"])):
        text = tag.get_text(" ", strip=True)
        value = tag.get("value", "")
        classes = set(tag.get("class") or [])
        if text in {"已投票", "投票", "提交投票", "我要投票"} or value in {"已投票", "投票", "提交投票", "我要投票"}:
            tag.decompose()
            continue
        if classes & {"selected", "is-selected", "checked", "is-checked", "voted"}:
            tag["class"] = [cls for cls in tag.get("class", []) if cls not in {"selected", "is-selected", "checked", "is-checked", "voted"}]

    poll_candidates = []
    for text_node in soup.find_all(string=lambda text: text and ("人参与" in text or "已投票" in text or "（单选）" in text or "（多选）" in text or "(单选)" in text or "(多选)" in text)):
        parent = text_node.parent
        if not parent or parent.name in ("script", "style", "noscript"):
            continue

        candidate = None
        for ancestor in [parent] + list(parent.parents):
            if not getattr(ancestor, "name", None) or ancestor.name in ("body", "html"):
                break
            marker = " ".join(
                str(value) for key, value in ancestor.attrs.items()
                if key in ("id", "class", "data-type")
            ).lower()
            text = ancestor.get_text(" ", strip=True)
            if ("poll" in marker or "vote" in marker or ("人参与" in text and ("单选" in text or "多选" in text))) and len(text) < 2500:
                candidate = ancestor
                break

        if candidate and candidate not in poll_candidates:
            poll_candidates.append(candidate)

    for poll in poll_candidates:
        classes = poll.get("class") or []
        if "douban-archive-poll" not in classes:
            poll["class"] = classes + ["douban-archive-poll"]

        existing_title = poll.select_one(".douban-archive-poll-title")
        if not existing_title:
            title = soup.new_tag("div")
            title["class"] = "douban-archive-poll-title"
            title.string = "投票结果"
            poll.insert(0, title)


def normalize_archive_layout(soup):
    for quote in soup.select(".reply-quote-content"):
        short_content = quote.select_one(".short.ref-content")
        full_content = quote.select_one(".all.ref-content")
        if full_content:
            if short_content:
                short_content.decompose()
            full_content.attrs.pop("style", None)
            classes = [cls for cls in full_content.get("class", []) if cls != "all"]
            full_content["class"] = classes or ["ref-content"]

        for toggle in quote.select(".toggle-reply"):
            toggle.decompose()

    for tag in soup.select(".comment-photos, .cmt-img-wrapper, .cmt-img"):
        if "style" in tag.attrs:
            del tag.attrs["style"]

    for img in soup.find_all("img"):
        classes = set(img.get("class") or [])
        if "pil" in classes:
            continue
        for attr in ("style", "width", "height"):
            if attr in img.attrs:
                del img.attrs[attr]

    for p in soup.find_all("p"):
        if not p.get_text(strip=True) and not p.find_all("img"):
            p.decompose()


def remote_image_urls(img):
    urls = []
    for attr in IMAGE_ATTRS:
        value = (img.get(attr) or "").strip()
        if is_remote_url(value):
            normalized = normalize_remote_url(value)
            if normalized not in urls:
                urls.append(normalized)
    return urls


def is_decoration_image(img):
    classes = set(img.get("class") or [])
    if classes & DECORATION_CLASSES:
        return True

    src = normalize_remote_url((img.get("src") or "").strip()).lower()
    if any(marker in src for marker in DECORATION_URL_MARKERS):
        return True

    parent = img.parent
    while parent and parent.name != "[document]":
        parent_classes = set(parent.get("class") or [])
        parent_id = (parent.get("id") or "").lower()
        if "img-uploader-wrapper" in parent_classes or "uploader" in parent_id:
            return True
        parent = parent.parent

    return False


def remove_image_node(img):
    parent = img.parent
    if parent and parent.name == "a" and not parent.get_text(strip=True) and len(parent.find_all("img")) == 1:
        parent.decompose()
    else:
        img.decompose()


def clean_image_attrs(img):
    for attr in IMAGE_ATTRS:
        if attr in img.attrs and attr != "src":
            del img.attrs[attr]
    for attr in ("srcset", "loading", "data-original-url", "data-lazy-src"):
        if attr in img.attrs:
            del img.attrs[attr]


def embed_images(soup, html_path, fetch_missing=False):
    embedded = 0
    recovered_remote = 0
    fetched_remote = 0
    skipped_decoration = 0
    missing_local = 0
    session = requests.Session() if fetch_missing else None

    for img in list(soup.find_all("img")):
        src = (img.get("src") or "").strip()

        if not src:
            continue

        if is_data_url(src):
            continue

        if is_remote_url(src):
            local_path = None
            remote_urls = remote_image_urls(img)
            for remote_url in remote_urls:
                local_path = find_archived_remote_image(html_path, remote_url)
                if local_path:
                    break

            if local_path:
                img["src"] = file_to_data_uri(local_path)
                clean_image_attrs(img)
                recovered_remote += 1
                continue

            if fetch_missing and session:
                local_path = fetch_archived_remote_image(html_path, remote_urls, session)
                if local_path:
                    img["src"] = file_to_data_uri(local_path)
                    clean_image_attrs(img)
                    fetched_remote += 1
                    continue

            if is_decoration_image(img):
                remove_image_node(img)
                skipped_decoration += 1
                continue

            remove_image_node(img)
            missing_local += 1
            continue

        local_path = resolve_local_path(html_path, src)
        if not local_path:
            missing_local += 1
            continue

        img["src"] = file_to_data_uri(local_path)
        clean_image_attrs(img)
        embedded += 1

    return embedded, recovered_remote, fetched_remote, skipped_decoration, missing_local


def inject_local_assets(soup):
    if soup.head is None:
        head = soup.new_tag("head")
        if soup.html:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)

    style = soup.new_tag("style")
    style.string = LOCAL_STYLE
    soup.head.append(style)

    if soup.body is None:
        body = soup.new_tag("body")
        body.extend(soup.contents)
        soup.append(body)

    script = soup.new_tag("script")
    script.string = LIGHTBOX_SCRIPT
    soup.body.append(script)


def export_html(html_path, output_path, fetch_missing=False):
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")

    remove_remote_dependencies(soup)
    remove_douban_chrome_and_actions(soup)
    remove_douban_people_links(soup)
    remove_visibility_warning_lines(soup)
    normalize_poll_blocks(soup)
    normalize_archive_layout(soup)
    embedded, recovered_remote, fetched_remote, skipped_decoration, missing_local = embed_images(
        soup,
        html_path,
        fetch_missing=fetch_missing,
    )
    inject_local_assets(soup)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(str(soup), encoding="utf-8")

    return {
        "embedded": embedded,
        "recovered_remote": recovered_remote,
        "fetched_remote": fetched_remote,
        "skipped_decoration": skipped_decoration,
        "missing_local": missing_local,
    }


def iter_html_files(target):
    if target.is_file() and target.suffix.lower() in {".html", ".htm"}:
        yield target
        return

    for path in target.rglob("*"):
        if any(part.startswith("_single_html") for part in path.parts):
            continue
        if path.suffix.lower() in {".html", ".htm"}:
            yield path


def make_output_path(target, html_path, output_dir):
    if target.is_file():
        return output_dir / f"{html_path.stem}_single.html"

    relative = html_path.relative_to(target)
    return output_dir / relative


def parse_args():
    parser = argparse.ArgumentParser(
        description="把已下载的帖子 HTML 和 images/ 图片批量导出为单文件 HTML。",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="要导出的 HTML 文件或目录。默认处理当前目录。",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=f"输出目录。默认在目标目录下生成 {OUTPUT_DIR_NAME}/。",
    )
    parser.add_argument(
        "--fetch-missing",
        action="store_true",
        help="导出时尝试联网补下载本地缺失的豆瓣图片。",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    target = Path(args.target).resolve()

    if not target.exists():
        print(f"找不到目标：{target}")
        return

    if args.output:
        output_dir = Path(args.output).resolve()
    elif target.is_file():
        output_dir = target.parent / OUTPUT_DIR_NAME
    else:
        output_dir = target / OUTPUT_DIR_NAME

    html_files = list(iter_html_files(target))
    if not html_files:
        print("没有找到 HTML 文件。")
        return

    total_embedded = 0
    total_recovered_remote = 0
    total_fetched_remote = 0
    total_skipped_decoration = 0
    total_missing = 0

    print(f"准备导出 {len(html_files)} 个 HTML")
    print(f"输出目录：{output_dir}")

    for html_path in html_files:
        output_path = make_output_path(target, html_path, output_dir)
        stats = export_html(html_path, output_path, fetch_missing=args.fetch_missing)
        total_embedded += stats["embedded"]
        total_recovered_remote += stats["recovered_remote"]
        total_fetched_remote += stats["fetched_remote"]
        total_skipped_decoration += stats["skipped_decoration"]
        total_missing += stats["missing_local"]
        print(f"已导出：{output_path}")

    print("\n完成")
    print(f"嵌入本地图片：{total_embedded}")
    print(f"从远程地址恢复本地图片：{total_recovered_remote}")
    print(f"联网补下载图片：{total_fetched_remote}")
    print(f"跳过页面装饰图片：{total_skipped_decoration}")
    print(f"本地未找到图片：{total_missing}")


if __name__ == "__main__":
    main()