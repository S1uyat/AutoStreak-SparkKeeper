import unittest
from playwright.sync_api import sync_playwright
import browser

class BrowserSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.engine = cls.pw.chromium.launch(channel='msedge', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.engine.close()
        cls.pw.stop()

    def setUp(self):
        self.page = self.engine.new_page()
        self.addCleanup(self.page.close)

    def test_visible_security_and_login_prompts_stop(self):
        for text, error in [('安全验证', browser.VerificationRequired), ('扫码登录', browser.NeedLogin)]:
            self.page.set_content(f'<div style="display:none">{text}</div>')
            browser.check_guard(self.page)
            self.page.set_content(f'<div>{text}</div>')
            with self.assertRaises(error):
                browser.check_guard(self.page)

    def test_duplicate_exact_titles_rejected(self):
        self.page.set_content('<div class="conversationConversationItemtitle">A</div>' * 2)
        with self.assertRaises(browser.TargetNotFound):
            browser._matching_title(self.page, 'A')

    def test_exact_name_excludes_substrings_and_hidden_titles(self):
        self.page.set_content('<div class="conversationConversationItemtitle">AB</div><div class="conversationConversationItemtitle" style="display:none">A</div>')
        self.assertIsNone(browser._matching_title(self.page, 'A'))

    def test_delayed_target_header_is_checked(self):
        self.page.set_content('''<div class="conversationConversationItemtitle" onclick="setTimeout(()=>{document.querySelector('header').innerHTML='<span>A</span>'},300)">A</div>
        <header class="chatHeader"><span>B</span></header>
        <div contenteditable="true" data-slate-editor="true" class="messageEditorinputArea"></div>''')
        browser.open_target(self.page, 'A')
        self.assertTrue(browser._confirmed_header(self.page, 'A'))

    def test_hidden_header_cannot_confirm_target(self):
        self.page.set_content('<header class="chatHeader" style="display:none"><span>A</span></header><div contenteditable="true"></div>')
        self.assertFalse(browser._confirmed_header(self.page, 'A'))

    def test_local_send_commits_before_click_and_confirms_bubble(self):
        # Offline fixture only: no network, account, or real recipient.
        self.page.set_content('''<div contenteditable="true" data-slate-editor="true" class="messageEditorinputArea"></div>
        <button aria-label="发送" onclick="const d=document.createElement('div');d.className='messageMessageBoxisFromMe';d.textContent=document.querySelector('[contenteditable]').innerText;document.body.append(d)">发送</button>''')
        calls=[]
        def before():
            self.assertEqual(self.page.locator(browser.OWN).count(),0)
            calls.append('pending')
        self.assertTrue(browser.send_message(self.page,'local test',before))
        self.assertEqual(calls,['pending'])
        self.assertEqual(self.page.locator(browser.OWN).inner_text(),'local test')

    def test_search_waits_for_delayed_exact_result(self):
        self.page.set_content("""<input placeholder="搜索" oninput="setTimeout(()=>{document.querySelector('section').innerHTML='<div class=searchSearchPanelitem><span>A</span><button class=searchSearchPanelitemchat_btn>发消息</button></div>'},300)"><section></section>""")
        result = browser._search_result(self.page, 'A')
        self.assertIsNotNone(result)
        self.assertEqual(result.count(), 1)

    def test_search_rejects_duplicate_names(self):
        self.page.set_content('<input placeholder="搜索">' + '<div class="searchSearchPanelitem"><span>A</span><button class="searchSearchPanelitemchat_btn">发消息</button></div>' * 2)
        with self.assertRaises(browser.TargetNotFound):
            browser._search_result(self.page, 'A')

    def test_input_value_security_and_login_prompts_stop(self):
        for text, error in [('安全验证', browser.VerificationRequired), ('扫码登录', browser.NeedLogin)]:
            for kind in ('button', 'submit'):
                self.page.set_content(f'<input type="{kind}" value="{text}">')
                with self.assertRaises(error):
                    browser.check_guard(self.page)

    def test_security_prompt_has_priority_over_login(self):
        self.page.set_content('<span>扫码登录</span><input type="button" value="完成验证">')
        with self.assertRaises(browser.VerificationRequired):
            browser.check_guard(self.page)

    def test_exact_name_treats_regex_characters_literally(self):
        self.page.set_content('<div class="conversationConversationItemtitle">A.B</div><div class="conversationConversationItemtitle">AxB</div>')
        match = browser._matching_title(self.page, 'A.B')
        self.assertEqual(match.count(), 1)
        self.assertEqual(match.inner_text(), 'A.B')

    def test_closed_page_propagates_instead_of_waiting(self):
        self.page.close()
        with self.assertRaises(Exception):
            browser.visible(self.page, 'input')

if __name__ == '__main__':
    unittest.main()
