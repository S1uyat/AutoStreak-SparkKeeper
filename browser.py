"""Own-account Douyin web chat automation. Does not use private APIs or bypass verification."""
from __future__ import annotations

import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from core import PROFILE, ExecutionLock

CHAT_URL = 'https://www.douyin.com/chat'
SEARCH = ('input[placeholder*="搜索"]', '[role="textbox"][placeholder*="搜索"]', 'input[aria-label*="搜索"]')
TITLES = '.conversationConversationItemtitle:visible'
EDITOR = ('[contenteditable="true"][data-slate-editor="true"].messageEditorinputArea',
          '[contenteditable="true"][data-placeholder*="发送消息"]',
          '.DraftEditor-editor [contenteditable="true"]',
          '[contenteditable="true"][aria-label*="消息"]',
          '[contenteditable="true"]')
HEADER = ('[class*="RightPanelHeader"]', '[class*="chatHeader"]', '[class*="ChatHeader"]')
SEND = ('[class*="messageMsgInputpublishBtn"]', '.e2e-send-msg-bt', 'button[aria-label*="发送"]')
OWN = '[class*="messageMessageBoxisFromMe"]'
RISK = ('安全验证', '完成验证', '验证身份', '拖动滑块', '账号异常')
SEND_CONFIRM_SECONDS = 40


class NeedLogin(RuntimeError):
    pass


class VerificationRequired(RuntimeError):
    pass


class TargetNotFound(RuntimeError):
    pass


class UncertainSend(RuntimeError):
    pass


def browser_context(playwright, channel='msedge', headless=True):
    """Persist login in private local profile; keep the same browser channel between runs."""
    PROFILE.mkdir(parents=True, exist_ok=True)
    kw = {'user_data_dir': str(PROFILE), 'headless': headless,
          'accept_downloads': False, 'viewport': {'width': 1280, 'height': 900},
          'locale': 'zh-CN'}
    if channel != 'chromium':
        kw['channel'] = channel
    return playwright.chromium.launch_persistent_context(**kw)


def visible(page, selector, timeout=700):
    try:
        node = page.locator(selector).first
        node.wait_for(state='visible', timeout=timeout)
        return node
    except PWTimeout:
        return None


def first_visible(page, selectors, timeout=1500):
    # One shared wait budget, including fallback selectors.
    return visible(page, ', '.join(f'{sel}:visible' for sel in selectors), timeout)


def check_guard(page):
    # Collect both warning categories in one browser round-trip; keep risk priority.
    risk = re.compile('|'.join(map(re.escape, RISK)))
    login = re.compile('扫码登录|验证码登录')
    texts = page.get_by_text(re.compile(risk.pattern + '|' + login.pattern)).locator('visible=true').evaluate_all("nodes => nodes.map(n => (n.textContent || '') + ' ' + (n.value || ''))")
    if any(risk.search(text) for text in texts):
        raise VerificationRequired('发现抖音安全验证，请手动打开管理面板重新登录或验证。')
    if any(login.search(text) for text in texts):
        raise NeedLogin('登录状态失效，请打开管理面板扫码登录。')


def open_chat(page):
    page.goto(CHAT_URL, wait_until='domcontentloaded', timeout=45000)
    # The SPA can load slowly after browser startup. Allow time without refreshing
    # away a partially loaded page; ready pages continue immediately.
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        check_guard(page)
        if first_visible(page, SEARCH, 500) is not None:
            visible(page, TITLES, 10000)
            check_guard(page)
            return
    check_guard(page)
    raise NeedLogin('抖音私信页面没有正常显示。可能需要重新登录，或页面发生改版。')


def _scroll_conversations(page):
    try:
        first = page.locator(TITLES).first
        if first.count() == 0:
            return False
        return bool(first.evaluate('''(el) => {
          let node = el.parentElement;
          while (node && node !== document.body) {
            const s = getComputedStyle(node);
            if ((s.overflowY === 'scroll' || s.overflowY === 'auto') &&
                  node.scrollHeight > node.clientHeight + 10) {
              const old = node.scrollTop;
              node.scrollTop += node.clientHeight * 0.9;
              return node.scrollTop > old;
            }
            node = node.parentElement;
          }
          return false;
        }'''))
    except Exception:
        return False


def scan_conversations(page, max_pages=40, navigate=True):
    """Gather conversation titles from currently accessible sidebar; no account scraping API."""
    if navigate:
        open_chat(page)
    names = []
    seen = set()
    for _ in range(max_pages):
        for raw in page.locator(TITLES).all_text_contents():
            name = raw.strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        if not _scroll_conversations(page):
            break
        page.wait_for_timeout(500)
    return names


def _matching_title(page, name):
    # Filter in the browser instead of transferring every conversation name.
    matches = page.locator(TITLES).filter(has_text=re.compile(r'^\s*' + re.escape(name) + r'\s*$'))
    count = matches.count()
    if count > 1:
        raise TargetNotFound(f'存在多个同名会话「{name}」，请使用唯一备注。')
    return matches if count == 1 else None


def _title_row(page, name):
    match = _matching_title(page, name)
    if match is not None:
        return match
    first = page.locator(TITLES).first
    if first.count():
        first.evaluate("""el => {
            for (let n = el.parentElement; n; n = n.parentElement) {
                if (['auto', 'scroll'].includes(getComputedStyle(n).overflowY) && n.scrollHeight > n.clientHeight + 10) {
                    n.scrollTop = 0; break;
                }
            }
        }""")
        page.wait_for_timeout(350)
    for _ in range(40):
        match = _matching_title(page, name)
        if match is not None:
            return match
        if not _scroll_conversations(page):
            break
        page.wait_for_timeout(350)
    return None


def _search_result(page, name):
    field = first_visible(page, SEARCH, 1300)
    if field is None:
        return None
    field.fill('')
    field.fill(name)
    # Search responses arrive asynchronously; return as soon as an exact result is ready.
    items = page.locator('[class*="SearchPanelitem"]:visible').filter(
        has=page.get_by_text(name, exact=True))
    buttons = items.locator('[class*="SearchPanelitemchat_btn"]:visible')
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        check_guard(page)
        count = buttons.count()
        if count > 1:
            raise TargetNotFound(f'搜索结果有多个「{name}」，请使用唯一备注。')
        if count == 1:
            return buttons
        page.wait_for_timeout(100)
    return None


def _confirmed_header(page, name):
    headers = page.locator(', '.join(f'{selector}:visible' for selector in HEADER))
    if not headers.get_by_text(name, exact=True).locator('visible=true').count():
        return False
    return first_visible(page, EDITOR, 300) is not None


def open_target(page, name):
    check_guard(page)
    # Clear the previous search overlay.
    field = first_visible(page, SEARCH, 450)
    if field:
        try:
            if field.input_value():
                field.fill('')
                page.wait_for_timeout(250)
        except Exception:
            pass
    row = _title_row(page, name)
    if row is None:
        # _title_row has already loaded the sidebar. Do not scan it a second time.
        row = _search_result(page, name)
    if row is None:
        raise TargetNotFound(f'找不到与「{name}」完全匹配的会话。')
    row.click(timeout=8000)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        check_guard(page)
        if _confirmed_header(page, name):
            return
        page.wait_for_timeout(100)
    raise TargetNotFound(f'无法确认右侧窗口是「{name}」，为避免误发已跳过。')


def _editor(page):
    loc = first_visible(page, EDITOR, 1600)
    if loc is None:
        raise RuntimeError('没有找到消息输入框。')
    # [data-contents] inner wrapper is not always contenteditable; selectors target editor.
    return loc


def _own_message_snapshot(page):
    # New bubble detection is intentionally conservative.
    return page.locator(OWN).evaluate_all('nodes => ({count:nodes.length, first:nodes.slice(0,3).map(n => n.outerHTML), last:nodes.slice(-3).map(n => n.outerHTML)})')


def _matching_own_count(page, message):
    expected = re.sub(r'[\s\u200b\ufeff]+', '', message)
    return page.locator(OWN + ':visible').evaluate_all(
        r"(nodes, expected) => nodes.filter(n => (n.innerText || '').replace(/[\s\u200b\ufeff]+/g, '').includes(expected)).length", expected)


def send_message(page, message, before_send):
    """Return confirmed boolean; never retry after the click on an uncertain outcome."""
    check_guard(page)
    editor = _editor(page)
    editor.click(timeout=5000)
    # Clear draft, to avoid corrupting another draft message.
    editor.press('ControlOrMeta+A')
    editor.press('Backspace')
    # Text only. No hidden APIs / bypassing UI.
    page.keyboard.insert_text(message)
    try:
        drafted = editor.inner_text(timeout=2000)
    except Exception:
        drafted = ''
    plain = re.sub(r'[\s\u200b\ufeff]+', '', drafted)
    expected = re.sub(r'[\s\u200b\ufeff]+', '', message)
    if not plain or expected != plain:
        raise RuntimeError('输入框内容校验失败，未触发发送。')
    before = _matching_own_count(page, message)
    # Commit the pending status before touching the send button.
    before_send()
    btn = first_visible(page, SEND, 300)
    if btn is not None:
        btn.click(timeout=5000)
    else:
        editor.press('Enter')
    deadline = time.monotonic() + SEND_CONFIRM_SECONDS
    while time.monotonic() < deadline:
        check_guard(page)
        newer = _matching_own_count(page, message)
        cleared = not re.sub(r'[\s\u200b\ufeff]+', '', editor.inner_text(timeout=2000))
        if newer > before and cleared:
            page.wait_for_timeout(1000)
            check_guard(page)
            if page.get_by_text('发送失败', exact=False).locator('visible=true').count():
                raise UncertainSend('已出现发送失败提示；不能确定是否已送达。')
            if _matching_own_count(page, message) > before:
                return True
        page.wait_for_timeout(100)
    raise UncertainSend('已点击发送，但没有观察到新的己方消息气泡；为防重复，今天不再自动重试。')


def interactive_login(channel, report, max_seconds=300):
    """Visible browser; user manually scans / handles any required verification."""
    with ExecutionLock(), sync_playwright() as p:
        ctx = browser_context(p, channel, headless=False)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(CHAT_URL, wait_until='domcontentloaded', timeout=45000)
            report('浏览器已打开，请在抖音官方页面扫码登录。')
            deadline = time.monotonic() + max_seconds
            while time.monotonic() < deadline:
                if page.is_closed():
                    report('浏览器已关闭；请重新尝试登录。')
                    return False
                if first_visible(page, SEARCH, 600) is not None and not visible(page, 'text=扫码登录', 150):
                    page.wait_for_timeout(1500)
                    report('已检测到私信列表，登录会话已保存在本机。')
                    return True
                page.wait_for_timeout(1200)
            report('等待登录超时。请重新点击扫码登录。')
            return False
        finally:
            ctx.close()


def fetch_contacts(channel):
    with ExecutionLock(), sync_playwright() as p:
        ctx = browser_context(p, channel, headless=False)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            return scan_conversations(page)
        finally:
            ctx.close()
