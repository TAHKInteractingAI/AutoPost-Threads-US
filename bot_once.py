#!/usr/bin/env python3
import os, time, json, base64
os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
time.tzset()

SHEET_ID   = os.environ.get('SHEET_ID', 'SHEET_ID')
SHEET_NAME = os.environ.get('SHEET_NAME', 'SHEET_NAME')
THREADS_URL = 'https://www.threads.com'
CREDENTIALS_FILE = '/tmp/credentials.json'
SESSION_FILE     = '/tmp/threads_session.json'

import subprocess, sys, random
from datetime import datetime, timedelta

print(f"⏰ Múi giờ: {time.strftime('%Z %z')}")
print(f"🕐 Giờ hiện tại: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

def restore_secrets():
    creds_b64 = os.environ.get('CREDENTIALS_JSON_B64', '')
    if not creds_b64:
        print('❌ Thiếu secret CREDENTIALS_JSON_B64')
        sys.exit(1)
    with open(CREDENTIALS_FILE, 'wb') as f:
        f.write(base64.b64decode(creds_b64))
    print(f'✅ Khôi phục credentials.json → {CREDENTIALS_FILE}')

    session_b64 = os.environ.get('THREADS_SESSION_B64', '')
    if not session_b64:
        print('❌ Thiếu secret THREADS_SESSION_B64')
        sys.exit(1)
    with open(SESSION_FILE, 'wb') as f:
        f.write(base64.b64decode(session_b64))
    print(f'✅ Khôi phục threads_session.json → {SESSION_FILE}')

def connect_sheet():
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

def get_pending_posts(sheet):
    records = sheet.get_all_records(expected_headers=['content', 'image_url', 'hashtags', 'topic', 'scheduled_time', 'status'])
    now = datetime.now()
    result = []
    for i, row in enumerate(records, start=2):
        status = str(row.get('status', '')).strip().lower()
        if status != 'pending':
            continue
        content = str(row.get('content', '')).strip()
        if not content:
            continue
        scheduled = str(row.get('scheduled_time', '')).strip()
        should_post = False
        if not scheduled:
            should_post = True
        else:
            try:
                scheduled_dt = datetime.strptime(scheduled, '%d/%m/%Y %H:%M')
                if now >= scheduled_dt - timedelta(minutes=5):
                    should_post = True
            except ValueError:
                print(f'⚠️ Row {i}: Sai định dạng thời gian: {scheduled}')
        if should_post:
            result.append({
                'row': i,
                'content': content,
                'image_url': str(row.get('image_url', '')).strip(),
                'hashtags': str(row.get('hashtags', '')).strip(),
                'topic': str(row.get('topic', '')).strip(),
                'scheduled_time': scheduled
            })
    return result

def update_status(sheet, row_num, status, post_id=''):
    sheet.update_cell(row_num, 6, status)
    if post_id:
        sheet.update_cell(row_num, 7, post_id)
    sheet.update_cell(row_num, 8, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print(f'   📝 Cập nhật row {row_num}: {status}')

def _write_pw_worker():
    path = '/tmp/pw_worker.py'
    lines = [
        'import sys, json, random, time, os, re\n',
        'import urllib.request\n',
        'from playwright.sync_api import sync_playwright\n',
        '\n',
        'args         = json.loads(os.environ["PW_PAYLOAD"])\n',
        'content      = args["content"]\n',
        'image_url    = args.get("image_url", "")\n',
        'hashtags     = args.get("hashtags", "").strip()\n',
        'SESSION_FILE = args["session_file"]\n',
        'THREADS_URL  = args["threads_url"]\n',
        '\n',
        'def log(msg): print(msg, flush=True)\n',
        '\n',
        'def get_direct_image_url(url):\n',
        '    if not url: return ""\n',
        '    m = re.search(r"/file/d/([^/]+)", url)\n',
        '    if m: return f"https://drive.google.com/uc?export=download&id={m.group(1)}"\n',
        '    m = re.search(r"[?&]id=([^&]+)", url)\n',
        '    if m: return f"https://drive.google.com/uc?export=download&id={m.group(1)}"\n',
        '    return url\n',
        '\n',
        'def download_image(url):\n',
        '    if not url: return None\n',
        '    try:\n',
        '        direct = get_direct_image_url(url)\n',
        '        log(f"   🖼️ Tải ảnh: {direct[:80]}")\n',
        '        dest = "/tmp/post_image.jpg"\n',
        '        req = urllib.request.Request(direct, headers={"User-Agent": "Mozilla/5.0"})\n',
        '        with urllib.request.urlopen(req, timeout=30) as resp:\n',
        '            with open(dest, "wb") as f:\n',
        '                f.write(resp.read())\n',
        '        size = os.path.getsize(dest)\n',
        '        log(f"   ✅ Tải ảnh xong ({size} bytes)")\n',
        '        return dest if size > 1000 else None\n',
        '    except Exception as e:\n',
        '        log(f"   ⚠️ Không tải được ảnh: {e}")\n',
        '        return None\n',
        '\n',
        'def dismiss_popups(page):\n',
        '    """Tắt popup/dialog/cookie banner trước khi thao tác"""\n',
        '    popup_sels = [\n',
        '        \'button:has-text("Allow")\',\n',
        '        \'button:has-text("Accept")\',\n',
        '        \'button:has-text("OK")\',\n',
        '        \'button:has-text("Đồng ý")\',\n',
        '        \'button:has-text("Không bây giờ")\',\n',
        '        \'button:has-text("Not Now")\',\n',
        '        \'button:has-text("Close")\',\n',
        '        \'button:has-text("Đóng")\',\n',
        '        \'[aria-label="Close"]\',\n',
        '        \'[aria-label="Đóng"]\',\n',
        '    ]\n',
        '    for sel in popup_sels:\n',
        '        try:\n',
        '            btn = page.locator(sel).first\n',
        '            if btn.is_visible():\n',
        '                btn.click()\n',
        '                log(f"   🚫 Đóng popup: {sel}")\n',
        '                time.sleep(0.5)\n',
        '        except:\n',
        '            pass\n',
        '\n',
        'if not hashtags:\n',
        '    log("ERR:NO_TOPIC")\n',
        '    sys.exit(6)\n',
        '\n',
        'if not os.path.exists(SESSION_FILE):\n',
        '    log("ERR:NO_SESSION")\n',
        '    sys.exit(1)\n',
        '\n',
        'INIT_SCRIPT = (\n',
        '    "Object.defineProperty(navigator, \\"webdriver\\", {get: () => undefined});"\n',
        '    " window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};"\n',
        '    " Object.defineProperty(navigator, \\"plugins\\", {get: () => [1,2,3,4,5]});"\n',
        '    " Object.defineProperty(navigator, \\"languages\\", {get: () => [\\"vi-VN\\",\\"vi\\",\\"en-US\\",\\"en\\"]});"\n',
        ')\n',
        '\n',
        'with sync_playwright() as p:\n',
        '    browser = p.chromium.launch(\n',
        '        headless=True,\n',
        '        args=["--no-sandbox", "--disable-dev-shm-usage",\n',
        '              "--disable-blink-features=AutomationControlled",\n',
        '              "--window-size=1280,800"]\n',
        '    )\n',
        '    context = browser.new_context(\n',
        '        storage_state=SESSION_FILE,\n',
        '        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",\n',
        '        viewport={"width": 1280, "height": 800},\n',
        '        locale="vi-VN",\n',
        '        timezone_id="Asia/Ho_Chi_Minh",\n',
        '    )\n',
        '    context.add_init_script(INIT_SCRIPT)\n',
        '    page = context.new_page()\n',
        '    try:\n',
        '        log("   🌐 Mở Threads...")\n',
        '        page.goto(THREADS_URL, wait_until="networkidle", timeout=30000)\n',
        '        time.sleep(random.uniform(1.5, 3.0))\n',
        '\n',
        '        # ── Log URL & title để debug ──\n',
        '        log(f"   🔗 URL: {page.url}")\n',
        '        log(f"   📄 Title: {page.title()}")\n',
        '\n',
        '        if "login" in page.url:\n',
        '            page.screenshot(path="/tmp/debug_login.png")\n',
        '            log("ERR:SESSION_EXPIRED")\n',
        '            sys.exit(2)\n',
        '\n',
        '        log("   ✅ Đã đăng nhập")\n',
        '\n',
        '        # ── Tắt popup ngay sau khi load ──\n',
        '        dismiss_popups(page)\n',
        '\n',
        '        compose_clicked = False\n',
        '        for sel in [\'a[href*="/compose"]\', \'[aria-label*="Tạo"]\', \'[aria-label*="Create"]\', \'[aria-label*="New thread"]\']:\n',
        '            try:\n',
        '                btn = page.locator(sel).first\n',
        '                btn.wait_for(state="visible", timeout=5000)\n',
        '                btn.click()\n',
        '                log(f"   🖱️ Click compose: {sel}")\n',
        '                compose_clicked = True\n',
        '                break\n',
        '            except:\n',
        '                pass\n',
        '        if not compose_clicked:\n',
        '            page.goto(THREADS_URL + "/compose", wait_until="networkidle")\n',
        '\n',
        '        time.sleep(random.uniform(2.2, 3.2))\n',
        '\n',
        '        # ── Tắt popup lần 2 (sau khi mở compose) ──\n',
        '        dismiss_popups(page)\n',
        '\n',
        '        text_area = page.locator(\'[contenteditable="true"], div[role="textbox"], textarea\').first\n',
        '        text_area.wait_for(state="visible", timeout=10000)\n',
        '        log("   ⌨️ Đang gõ nội dung...")\n',
        '        text_area.click()\n',
        '        time.sleep(0.7)\n',
        '        page.keyboard.type(content, delay=random.randint(40, 85))\n',
        '        time.sleep(random.uniform(1.2, 2.0))\n',
        '        log("   ✅ Gõ xong nội dung")\n',
        '\n',
        '        # ── Đính kèm ảnh nếu có ──\n',
        '        local_image = download_image(image_url)\n',
        '        if local_image:\n',
        '            try:\n',
        '                # Tìm input file ẩn hoặc nút đính kèm ảnh\n',
        '                img_input = page.locator(\'input[type="file"][accept*="image"]\').first\n',
        '                if img_input.count() > 0:\n',
        '                    img_input.set_input_files(local_image)\n',
        '                    log("   🖼️ Đính kèm ảnh qua input file")\n',
        '                else:\n',
        '                    # Click nút ảnh trong toolbar compose\n',
        '                    for img_sel in [\'[aria-label*="ảnh"]\', \'[aria-label*="Photo"]\', \'[aria-label*="image"]\', \'[data-testid*="photo"]\']:\n',
        '                        try:\n',
        '                            btn_img = page.locator(img_sel).first\n',
        '                            btn_img.wait_for(state="visible", timeout=3000)\n',
        '                            # Intercept file chooser\n',
        '                            with page.expect_file_chooser() as fc_info:\n',
        '                                btn_img.click()\n',
        '                            fc_info.value.set_files(local_image)\n',
        '                            log(f"   🖼️ Đính kèm ảnh qua file chooser: {img_sel}")\n',
        '                            break\n',
        '                        except:\n',
        '                            pass\n',
        '                time.sleep(2)\n',
        '                page.screenshot(path="/tmp/debug_after_image.png")\n',
        '                log("   📸 Screenshot sau đính ảnh: /tmp/debug_after_image.png")\n',
        '            except Exception as e:\n',
        '                log(f"   ⚠️ Lỗi đính ảnh: {e}")\n',
        '        else:\n',
        '            if image_url:\n',
        '                log("   ⚠️ Bỏ qua ảnh (tải thất bại)")\n',
        '\n',
        '        page.screenshot(path="/tmp/debug_after_type.png")\n',
        '        log("   📸 Screenshot: /tmp/debug_after_type.png")\n',
        '\n',
        '        topic      = args.get("topic", "").strip()\n',
        '        topic_text = topic if topic else " ".join([tag.lstrip("#").strip() for tag in hashtags.split() if tag.strip()][:3])\n',
        '        log(f"   🏷️ Đang thêm chủ đề: {topic_text}")\n',
        '        page.mouse.wheel(0, 180)\n',
        '        time.sleep(1.5)\n',
        '\n',
        '        topic_clicked = False\n',
        '        for try_sel in [\'[placeholder*="Thêm chủ đề"]\', \'[placeholder*="chủ đề"]\', \'[aria-label*="chủ đề"]\']:\n',
        '            try:\n',
        '                topic_el = page.locator(try_sel).first\n',
        '                topic_el.wait_for(state="visible", timeout=4000)\n',
        '                topic_el.click()\n',
        '                log(f"   ✅ Click bằng selector: {try_sel}")\n',
        '                topic_clicked = True\n',
        '                break\n',
        '            except:\n',
        '                continue\n',
        '\n',
        '        if not topic_clicked:\n',
        '            try:\n',
        '                topic_el = page.get_by_text("Thêm chủ đề", exact=True).first\n',
        '                topic_el.wait_for(state="visible", timeout=8000)\n',
        '                topic_el.click()\n',
        '                log("   ✅ Click Thêm chủ đề bằng get_by_text")\n',
        '                topic_clicked = True\n',
        '            except:\n',
        '                pass\n',
        '\n',
        '        if topic_clicked:\n',
        '            time.sleep(random.uniform(0.6, 1.1))\n',
        '            page.keyboard.type(topic_text, delay=random.randint(45, 90))\n',
        '            time.sleep(random.uniform(0.8, 1.4))\n',
        '            try:\n',
        '                first_suggest = page.locator(\'[role="option"], [role="listitem"]\').first\n',
        '                first_suggest.wait_for(state="visible", timeout=3000)\n',
        '                first_suggest.click()\n',
        '                log("   ✅ Chọn gợi ý đầu tiên")\n',
        '            except:\n',
        '                page.keyboard.press("Enter")\n',
        '                log("   ✅ Nhấn Enter để xác nhận chủ đề")\n',
        '        else:\n',
        '            log("   ⚠️ Không tìm thấy ô chủ đề, tiếp tục đăng không có chủ đề")\n',
        '\n',
        '        time.sleep(random.uniform(1.0, 1.8))\n',
        '\n',
        '        # ── Screenshot trước khi click Đăng ──\n',
        '        page.screenshot(path="/tmp/debug_before_post.png")\n',
        '        log("   📸 Screenshot trước đăng: /tmp/debug_before_post.png")\n',
        '\n',
        '        # ── DEBUG: Dump tất cả buttons để xem text/aria thực tế ──\n',
        '        try:\n',
        '            btn_info = page.evaluate("""\n',
        '                () => {\n',
        '                    return Array.from(document.querySelectorAll("button")).map(b => ({\n',
        '                        text: (b.innerText || b.textContent || "").trim().slice(0, 40),\n',
        '                        aria: b.getAttribute("aria-label") || "",\n',
        '                        visible: b.offsetParent !== null,\n',
        '                        disabled: b.disabled\n',
        '                    })).filter(b => b.visible);\n',
        '                }\n',
        '            """)\n',
        '            log("   🔍 [DEBUG] Tất cả buttons visible trên trang:")\n',
        '            for bi in btn_info:\n',
        '                log(f\'      text="{bi["text"]}" aria="{bi["aria"]}" disabled={bi["disabled"]}\')\n',
        '        except Exception as e:\n',
        '            log(f"   ⚠️ Không dump được buttons: {e}")\n',
        '\n',
        '        # ── Tìm và click nút Đăng ──\n',
        '        posted = False\n',
        '\n',
        '        # Bước 1: JavaScript - tìm mọi button visible, in ra rồi click cái đúng\n',
        '        try:\n',
        '            clicked = page.evaluate("""\n',
        '                () => {\n',
        '                    const btns = Array.from(document.querySelectorAll("button"));\n',
        '                    const targets = btns.filter(b => {\n',
        '                        if (b.offsetParent === null || b.disabled) return false;\n',
        '                        const txt = (b.innerText || b.textContent || "").trim();\n',
        '                        const aria = (b.getAttribute("aria-label") || "").trim();\n',
        '                        return txt === "Đăng" || txt === "Post"\n',
        '                            || aria === "Đăng" || aria === "Post"\n',
        '                            || txt.startsWith("Đăng") || txt.startsWith("Post");\n',
        '                    });\n',
        '                    if (targets.length === 0) return 0;\n',
        '                    targets[targets.length - 1].click();\n',
        '                    return targets.length;\n',
        '                }\n',
        '            """)\n',
        '            if clicked:\n',
        '                posted = True\n',
        '                log(f"   🚀 Click Đăng via JS (found {clicked} buttons)")\n',
        '            else:\n',
        '                log("   ⚠️ JS: Không match được button nào (xem DEBUG ở trên)")\n',
        '        except Exception as e:\n',
        '            log(f"   ⚠️ JS click lỗi: {e}")\n',
        '\n',
        '        # Bước 2: Playwright fallback với nhiều selector hơn\n',
        '        if not posted:\n',
        '            log("   🔄 Thử Playwright selectors...")\n',
        '            extra_sels = [\n',
        '                \'button:has-text("Đăng")\',\n',
        '                \'button:has-text("Post")\',\n',
        '                \'[aria-label="Đăng"]\',\n',
        '                \'[aria-label="Post"]\',\n',
        '                \'div[role="button"]:has-text("Đăng")\',\n',
        '                \'div[role="button"]:has-text("Post")\',\n',
        '                \'[data-testid*="post"]\',\n',
        '                \'[data-testid*="submit"]\',\n',
        '            ]\n',
        '            for sel in extra_sels:\n',
        '                if posted:\n',
        '                    break\n',
        '                try:\n',
        '                    btns = page.locator(sel).all()\n',
        '                    visible_btns = [b for b in btns if b.is_visible()]\n',
        '                    if not visible_btns:\n',
        '                        log(f"      {sel}: 0 visible")\n',
        '                        continue\n',
        '                    log(f"      {sel}: {len(visible_btns)} visible → click cuối")\n',
        '                    visible_btns[-1].scroll_into_view_if_needed()\n',
        '                    time.sleep(0.3)\n',
        '                    visible_btns[-1].click(force=True)\n',
        '                    posted = True\n',
        '                    log(f"   🚀 Click Đăng Playwright: {sel}")\n',
        '                except Exception as e:\n',
        '                    log(f"      {sel}: lỗi {e}")\n',
        '\n',
        '        if not posted:\n',
        '            page.screenshot(path="/tmp/debug_no_post_btn.png")\n',
        '            log("ERR:NO_POST_BTN")\n',
        '            sys.exit(4)\n',
        '\n',
        '        # ── Chờ lâu hơn và xác nhận bài đã đăng ──\n',
        '        log("   ⏳ Chờ xác nhận bài đăng...")\n',
        '        time.sleep(8)\n',
        '\n',
        '        # Chụp screenshot SAU KHI đăng — quan trọng nhất\n',
        '        page.screenshot(path="/tmp/debug_after_post.png")\n',
        '        log(f"   📸 Screenshot sau đăng: /tmp/debug_after_post.png")\n',
        '        log(f"   🔗 URL sau đăng: {page.url}")\n',
        '\n',
        '        # Kiểm tra có dialog lỗi không\n',
        '        error_sels = [\n',
        '            \'[role="alert"]\',\n',
        '            \'div:has-text("Something went wrong")\',\n',
        '            \'div:has-text("Đã xảy ra lỗi")\',\n',
        '            \'div:has-text("Try again")\',\n',
        '        ]\n',
        '        for err_sel in error_sels:\n',
        '            try:\n',
        '                el = page.locator(err_sel).first\n',
        '                if el.is_visible():\n',
        '                    log(f"   ❌ Phát hiện lỗi trên trang: {err_sel}")\n',
        '                    log("ERR:POST_FAILED_UI_ERROR")\n',
        '                    sys.exit(7)\n',
        '            except:\n',
        '                pass\n',
        '\n',
        '        context.storage_state(path=SESSION_FILE)\n',
        '        post_id = "pw_" + str(int(time.time()))\n',
        '        if "/post/" in page.url or "@" in page.url:\n',
        '            post_id = page.url\n',
        '            log(f"   ✅ Xác nhận URL bài đăng: {post_id}")\n',
        '        else:\n',
        '            log(f"   ⚠️ URL không đổi sau đăng ({page.url}), có thể đã đăng hoặc lỗi")\n',
        '        log(f"OK:{post_id}")\n',
        '        browser.close()\n',
        '\n',
        '    except Exception as e:\n',
        '        import traceback\n',
        '        traceback.print_exc()\n',
        '        try: page.screenshot(path="/tmp/err_exception.png")\n',
        '        except: pass\n',
        '        log(f"ERR:EXCEPTION:{str(e)[:150]}")\n',
        '        browser.close()\n',
        '        sys.exit(5)\n',
    ]
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    return path

def post_to_threads_browser(content, image_url='', hashtags='', topic=''):
    if not topic or not topic.strip():
        print('❌ Thiếu topic!')
        return None
    if len(content) > 500:
        content = content[:497] + '...'

    pw_worker = _write_pw_worker()
    env = os.environ.copy()
    env['PW_PAYLOAD'] = json.dumps({
        'content': content,
        'image_url': image_url,
        'hashtags': hashtags,
        'topic': topic,
        'session_file': SESSION_FILE,
        'threads_url': THREADS_URL,
    })

    result = subprocess.run(
        [sys.executable, pw_worker],
        capture_output=True, text=True, encoding='utf-8',
        timeout=180, env=env
    )

    for line in result.stdout.splitlines():
        if line.startswith('OK:'):
            print(f'   ✅ Đăng thành công: {line[3:]}')
            return line[3:]
        else:
            print(line)

    if result.stderr:
        print('--- stderr ---')
        print(result.stderr[-1000:])
    return None

def process_and_post(sheet, post_data):
    row       = post_data['row']
    content   = post_data['content']
    image_url = post_data['image_url']
    hashtags  = post_data['hashtags']
    topic     = post_data['topic']

    print(f'\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print(f'📌 Xử lý bài post (row {row}):')
    print(f'   Nội dung: {content[:80]}...' if len(content) > 80 else f'   Nội dung: {content}')

    post_id = post_to_threads_browser(content, image_url, hashtags, topic)

    if post_id:
        update_status(sheet, row, 'done', str(post_id))
        print('✅ Đăng bài thành công!')
    else:
        update_status(sheet, row, 'error')
        print('❌ Đăng bài thất bại!')
        sys.exit(1)

    wait_sec = random.randint(30, 60)
    print(f'   ⏳ Chờ {wait_sec}s trước bài kế tiếp...')
    time.sleep(wait_sec)

if __name__ == '__main__':
    print('\n🤖 Threads AutoPost Bot (GitHub Actions mode) đang khởi động...')
    restore_secrets()

    try:
        sheet = connect_sheet()
        posts = get_pending_posts(sheet)
        if not posts:
            print('📭 Không có bài nào cần đăng lúc này.')
            sys.exit(0)
        print(f'📋 Tìm thấy {len(posts)} bài cần đăng')
        for post in posts:
            process_and_post(sheet, post)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'❌ Lỗi: {e}')
        sys.exit(1)

    print(f'\n✅ Hoàn thành lúc {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')