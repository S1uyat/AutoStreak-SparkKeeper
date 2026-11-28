"""On-demand Windows Tk management interface. Not launched at startup."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from copy import deepcopy
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog
from core import BASE, LOG_FILE, get_config, get_state, save_config, ExecutionLock
from app_runtime import install_root, task_command, runner_command

ROOT = install_root()


class Manager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('SparkKeeper · 抖音火花助手')
        self.geometry('1080x820')
        self.minsize(1000, 780)
        self.config_data = get_config()
        self.saved_config = deepcopy(self.config_data)
        self.events = queue.Queue()
        self.busy = False
        self.protocol('WM_DELETE_WINDOW', self.close_manager)
        self._build()
        self.apply_theme()
        self.refresh()
        self.after(130, self.consume_events)
        threading.Thread(target=self.probe_schedule, daemon=True).start()

    def probe_schedule(self):
        try:
            p = subprocess.run(task_command('status'), capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
            self.events.put(('schedule', p.stdout.strip() if p.returncode == 0 else '任务状态读取失败，请在设置页检查。'))
        except Exception:
            self.events.put(('schedule', '任务状态暂不可用，请在设置页检查。'))

    def _build(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        frame = ttk.Frame(self, padding=28)
        frame.pack(fill='both', expand=True)
        header = ttk.Frame(frame)
        header.pack(fill='x')
        ttk.Label(header, text='SparkKeeper', style='Brand.TLabel', font=('Segoe UI', 26, 'bold')).pack(side='left')
        self.theme = tk.StringVar(value=self.config_data.get('theme', 'light'))
        ttk.Button(header, text='切换浅色 / 深色', command=self.toggle_theme).pack(side='right')
        ttk.Label(frame, text='让每天的联系，简单一点。  ·  登录与零点触发，结束即退出', style='Muted.TLabel').pack(anchor='w', pady=(4, 16))
        self.summary = tk.StringVar()
        ttk.Label(frame, textvariable=self.summary, style='Card.TLabel', padding=16).pack(fill='x', pady=(0, 12))
        self.schedule_status = tk.StringVar(value='任务时间可通过下方「查看任务状态」检查；临时网络失败最多补跑两次。')
        ttk.Label(frame, textvariable=self.schedule_status, style='Muted.TLabel').pack(anchor='w', pady=(0, 12))
        tabs = ttk.Notebook(frame)
        tabs.pack(fill='both', expand=True)
        friends = ttk.Frame(tabs, padding=16)
        settings_page = ttk.Frame(tabs, padding=16)
        tabs.add(friends, text='好友与今日状态')
        tabs.add(settings_page, text='计划与设置')
        frame = friends

        line1 = ttk.Frame(frame)
        line1.pack(fill='x', pady=(0, 6))
        ttk.Label(line1, text='登录与好友', font=('Microsoft YaHei UI', 11, 'bold')).pack(side='left')
        ttk.Button(line1, text='扫码登录 / 重新验证', style='Accent.TButton', command=self.login).pack(side='right', padx=3)
        ttk.Button(line1, text='读取私信会话', command=self.scan).pack(side='right', padx=3)
        tablewrap = ttk.Frame(frame)
        tablewrap.pack(fill='both', expand=True)
        self.table = ttk.Treeview(tablewrap, columns=('enabled', 'name', 'status'), show='headings', height=7, selectmode='browse')
        self.table.heading('enabled', text='启用')
        self.table.heading('name', text='好友备注 / 昵称（准确匹配）')
        self.table.heading('status', text='今日状态')
        self.table.column('enabled', width=62, stretch=False, anchor='center')
        self.table.column('name', width=360, stretch=True)
        self.table.column('status', width=165, stretch=False)
        scroll = ttk.Scrollbar(tablewrap, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        ops = ttk.Frame(frame)
        ops.pack(fill='x', pady=(5, 10))
        ttk.Button(ops, text='添加好友', style='Accent.TButton', command=self.add_friend).pack(side='left', padx=(0, 7))
        ttk.Button(ops, text='启用 / 暂停', command=self.toggle_friend).pack(side='left', padx=7)
        ttk.Button(ops, text='删除', command=self.delete_friend).pack(side='left', padx=7)
        ttk.Button(ops, text='检查所选', command=lambda: self.run(False, single=True)).pack(side='left', padx=7)
        ttk.Button(ops, text='补发所选', command=lambda: self.run(True, single=True)).pack(side='left', padx=7)
        ttk.Button(ops, text='刷新状态', command=self.refresh).pack(side='right')
        self.friend_detail = tk.StringVar(value='选择好友查看原因。已确认或结果不确定的消息不会自动重发。')
        ttk.Label(frame, textvariable=self.friend_detail, style='Muted.TLabel', wraplength=920).pack(fill='x', pady=10)
        self.table.bind('<<TreeviewSelect>>', self.describe_friend)

        frame = settings_page
        ttk.Label(frame, text='发送内容', font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w')
        self.message = tk.StringVar(value=self.config_data['message'])
        ttk.Entry(frame, textvariable=self.message).pack(fill='x', pady=(5, 7))
        settings = ttk.Frame(frame)
        settings.pack(fill='x', pady=(0, 11))
        ttk.Label(settings, text='浏览器').pack(side='left')
        self.channel = tk.StringVar(value=self.config_data['channel'])
        ttk.Combobox(settings, textvariable=self.channel, state='readonly', width=15,
                     values=['msedge', 'chrome', 'chromium']).pack(side='left', padx=(8, 14))
        self.headless = tk.BooleanVar(value=bool(self.config_data['headless']))
        ttk.Checkbutton(settings, text='自动运行时隐藏浏览器窗口（推荐）', variable=self.headless).pack(side='left')
        ttk.Button(settings, text='保存设置', style='Accent.TButton', command=self.save).pack(side='right')

        self.auto_send = tk.BooleanVar(value=self.config_data.get('auto_send', False))
        ttk.Checkbutton(frame, text='允许每日自动任务真实发送（未勾选时仅检查）', variable=self.auto_send).pack(anchor='w')

        ttk.Separator(frame).pack(fill='x', pady=4)
        ttk.Label(frame, text='开机任务与运行检查', font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', pady=(7, 5))
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='安装开机自启', command=lambda: self.task('install')).pack(side='left', padx=(0, 6))
        ttk.Button(buttons, text='取消开机自启', command=lambda: self.task('uninstall')).pack(side='left', padx=6)
        ttk.Button(buttons, text='测试（不发送）', command=lambda: self.run(False)).pack(side='left', padx=6)
        ttk.Button(buttons, text='立即执行（真的发送）', command=lambda: self.run(True)).pack(side='left', padx=6)
        buttons2 = ttk.Frame(frame)
        buttons2.pack(fill='x', pady=(8, 0))
        ttk.Button(buttons2, text='查看运行日志', command=self.show_logs).pack(side='left', padx=(0, 6))
        ttk.Button(buttons2, text='打开本地数据目录', command=self.open_data).pack(side='left', padx=6)
        ttk.Button(buttons2, text='查看任务状态', command=lambda: self.task('status')).pack(side='left', padx=6)
        ttk.Button(buttons2, text='启停记录', command=self.show_audit).pack(side='left', padx=6)
        ttk.Button(buttons2, text='撤销上次启停', command=self.undo_toggle).pack(side='left', padx=6)
        self.status = tk.StringVar(value='准备就绪。')
        ttk.Label(tabs.master, textvariable=self.status, wraplength=980, style='Muted.TLabel').pack(fill='x', pady=(15, 5))
        ttk.Label(frame, text='提示：登录态仅保存在当前 Windows 用户的本机目录。页面改版、登录过期或风控可能导致发送失败；软件不能保证火花维持。',
                  style='Muted.TLabel', wraplength=980).pack(anchor='w')

    def apply_theme(self):
        dark = self.theme.get() == 'dark'
        bg, card, fg, muted = ('#000002', '#221f23', '#c8c8c8', '#a2a2ac') if dark else ('#ffffff', '#ffffff', '#1d1d1f', '#606068')
        accent = '#0450d3' if dark else '#0533B0'
        border = '#45454b' if dark else '#c8c8c8'
        self.palette = (bg, card, fg, muted)
        self.configure(bg=bg)
        s = ttk.Style(self)
        s.configure('.', font=('Microsoft YaHei UI', 10), background=bg, foreground=fg)
        s.configure('TFrame', background=bg)
        s.configure('TNotebook', background=bg, borderwidth=0, bordercolor=border, lightcolor=bg, darkcolor=bg)
        s.configure('TNotebook.Tab', background=bg, foreground=muted, padding=(20, 10), bordercolor=border, lightcolor=bg, darkcolor=bg)
        s.map('TNotebook.Tab', background=[('selected', accent)], foreground=[('selected', '#ffffff')])
        s.configure('TLabel', background=bg, foreground=fg)
        s.configure('Brand.TLabel', background=bg, foreground='#f5f5f7' if dark else accent)
        s.configure('Muted.TLabel', background=bg, foreground=muted)
        s.configure('Card.TLabel', background=accent, foreground='#ffffff', bordercolor=accent, relief='flat', borderwidth=0, font=('Microsoft YaHei UI', 11, 'bold'))
        s.configure('TButton', background=card, foreground=fg, padding=(12, 8), borderwidth=1, bordercolor=border, lightcolor=card, darkcolor=card)
        s.map('TButton', background=[('active', accent)], foreground=[('active', '#ffffff')], bordercolor=[('active', accent)])
        s.configure('Accent.TButton', background=accent, foreground='#ffffff', bordercolor=accent)
        s.map('Accent.TButton', background=[('active', '#082b8b')], foreground=[('active', '#ffffff')])
        s.configure('TSeparator', background=border)
        s.configure('TEntry', fieldbackground=card, foreground=fg, insertcolor=fg, padding=7, bordercolor=border, lightcolor=border, darkcolor=border)
        s.configure('TCombobox', fieldbackground=card, background=card, foreground=fg, arrowcolor=fg, bordercolor=border, lightcolor=card, darkcolor=card)
        s.map('TCombobox', fieldbackground=[('readonly', card)], foreground=[('readonly', fg)])
        s.configure('TCheckbutton', background=bg, foreground=fg, indicatorbackground=card, indicatorforeground=accent)
        s.map('TCheckbutton', background=[('active', bg)], foreground=[('active', fg)])
        s.configure('Treeview', background=bg, fieldbackground=bg, foreground=fg, rowheight=34, borderwidth=1, bordercolor=border, lightcolor=border, darkcolor=border)
        s.configure('Vertical.TScrollbar', background=card, troughcolor=bg, bordercolor=bg, arrowcolor=muted, lightcolor=card, darkcolor=card)
        s.map('Vertical.TScrollbar', background=[('active', border)])
        s.configure('Treeview.Heading', background=accent, foreground='#ffffff', padding=10, borderwidth=0, lightcolor=accent, darkcolor=accent)
        s.map('Treeview.Heading', background=[('active', accent)], foreground=[('active', '#ffffff')])
        s.map('Treeview', background=[('selected', accent)], foreground=[('selected', 'white')])
        self.option_add('*TCombobox*Listbox.background', card)
        self.option_add('*TCombobox*Listbox.foreground', fg)
        self.option_add('*TCombobox*Listbox.selectBackground', accent)
        self.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        for win in self.winfo_children():
            if isinstance(win, tk.Toplevel):
                win.configure(bg=bg)
                for child in win.winfo_children():
                    if isinstance(child, tk.Text):
                        child.configure(bg=card, fg=fg, insertbackground=fg)

    def toggle_theme(self):
        self.theme.set('light' if self.theme.get() == 'dark' else 'dark')
        if self.save(quiet=True):
            self.apply_theme()
        else:
            self.theme.set(self.saved_config.get('theme', 'light'))

    def show_audit(self):
        rows = get_config().get('audit', [])
        labels = {True: '启用', False: '暂停', None: '不存在'}
        self.show_text('好友启停记录', '\n'.join(f"{r['at']}  {r['name']}：{labels[r['before']]} → {labels[r['after']]}" for r in reversed(rows)) or '暂无记录。')

    def undo_toggle(self):
        if self.busy:
            return
        rows = get_config().get('audit', [])
        if not rows or rows[-1]['before'] is None or rows[-1]['after'] is None:
            return messagebox.showinfo('无法撤销', '最近一条不是启用或暂停操作。')
        row = rows[-1]
        if messagebox.askyesno('撤销启停', f"撤销「{row['name']}」的最近一次启停操作？"):
            for c in self.config_data['contacts']:
                if c['name'] == row['name'] and c.get('enabled', True) == row['after']:
                    c['enabled'] = row['before']
                    self.save(quiet=True)
                    self.refresh()
                    return

    def close_manager(self):
        if self.busy:
            messagebox.showinfo('任务进行中', '请等待任务结束，或先关闭扫码浏览器，再退出管理面板。')
            return
        self.destroy()

    def refresh(self):
        state = get_state()['results']
        selected = self.selected()
        rows = self.table.get_children()
        if rows:
            self.table.delete(*rows)
        labels = {'sent': '已观察到发送', 'uncertain': '结果不确定 · 请核对', 'retryable': '网络超时 · 可补跑', 'failed': '需处理 · 查看日志', 'attempting': '执行中'}
        enabled = [c for c in self.config_data['contacts'] if c.get('enabled', True)]
        count = lambda status: sum(state.get(c['name'], {}).get('status') == status for c in enabled)
        self.summary.set(f"今日概览    启用 {len(enabled)}    暂停 {len(self.config_data['contacts'])-len(enabled)}    已确认 {count('sent')}    未尝试 {sum(c['name'] not in state for c in enabled)}    待处理 {count('failed')+count('retryable')}    不确定 {count('uncertain')}")
        for item in self.config_data['contacts']:
            name = item['name']
            value = state.get(name, {})
            iid = self.table.insert('', 'end', values=('是' if item.get('enabled', True) else '否', name,
                                                labels.get(value.get('status'), '今日未执行') if item.get('enabled', True) else '已暂停，不会发送'))
            if name == selected:
                self.table.selection_set(iid)

    def selected(self):
        picked = self.table.selection()
        return self.table.item(picked[0], 'values')[1] if picked else None

    def describe_friend(self, event=None):
        name = self.selected()
        if name:
            result = get_state()['results'].get(name, {})
            self.friend_detail.set(f"{name}  {result.get('at', '')}\n{result.get('detail', '暂无发送记录；请检查启用状态。')}")

    def add_friend(self):
        if self.busy:
            return
        name = simpledialog.askstring('添加好友', '请输入抖音私信列表显示的完整备注或昵称：', parent=self)
        if not name:
            return
        name = name.strip()
        if any(c['name'] == name for c in self.config_data['contacts']):
            return messagebox.showwarning('已存在', '不能添加重复昵称。')
        self.config_data['contacts'].append({'name': name, 'enabled': True})
        self.save(quiet=True)
        self.refresh()

    def toggle_friend(self):
        if self.busy:
            return
        name = self.selected()
        if not name:
            return
        for c in self.config_data['contacts']:
            if c['name'] == name:
                c['enabled'] = not c.get('enabled', True)
                break
        self.save(quiet=True)
        self.refresh()

    def delete_friend(self):
        if self.busy:
            return
        name = self.selected()
        if not name:
            return
        if not messagebox.askyesno('确认删除', f'从配置中删除「{name}」？'):
            return
        self.config_data['contacts'] = [c for c in self.config_data['contacts'] if c['name'] != name]
        self.save(quiet=True)
        self.refresh()

    def save(self, quiet=False):
        if self.busy:
            messagebox.showinfo('任务进行中', '请等待任务结束后再修改设置。')
            return False
        self.config_data['message'] = self.message.get().strip()
        self.config_data['channel'] = self.channel.get()
        self.config_data['headless'] = self.headless.get()
        self.config_data['auto_send'] = self.auto_send.get()
        self.config_data['theme'] = self.theme.get()
        try:
            with ExecutionLock():
                if get_config() != self.saved_config:
                    self.config_data = get_config()
                    self.saved_config = deepcopy(self.config_data)
                    self.message.set(self.config_data['message'])
                    self.channel.set(self.config_data['channel'])
                    self.headless.set(self.config_data['headless'])
                    self.auto_send.set(self.config_data['auto_send'])
                    self.theme.set(self.config_data.get('theme', 'light'))
                    self.apply_theme()
                    self.refresh()
                    raise RuntimeError('配置已被其他窗口修改，已重新载入，请检查后重试。')
                save_config(self.config_data)
                self.saved_config = deepcopy(self.config_data)
            self.status.set('配置已保存在本机。')
            if not quiet:
                messagebox.showinfo('成功', '配置已保存。')
            return True
        except Exception as exc:
            self.config_data = deepcopy(self.saved_config)
            self.refresh()
            messagebox.showerror('保存失败', str(exc))
            return False

    def async_job(self, label, fn):
        if self.busy:
            messagebox.showwarning('任务进行中', '请先等待正在执行的任务结束。')
            return
        self.busy = True
        self.status.set(label)
        def job():
            try:
                result = fn()
                self.events.put(('done', result))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=job, daemon=True).start()

    def consume_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == 'names':
                    self.busy = False
                    existing = {c['name'] for c in self.config_data['contacts']}
                    new = [name for name in payload if name not in existing]
                    if new and messagebox.askyesno('读取完成', f'发现 {len(payload)} 条会话，其中 {len(new)} 条尚未加入管理。\n\n要全部加入为「暂停」状态，随后手动启用需要续火的人吗？'):
                        self.config_data['contacts'].extend({'name': name, 'enabled': False} for name in new[:max(0, 60-len(existing))])
                        self.save(quiet=True)
                        self.refresh()
                elif kind == 'status':
                    self.status.set(str(payload))
                elif kind == 'done':
                    self.busy = False
                    self.status.set(str(payload) if payload is not None else '任务完成。')
                    self.refresh()
                elif kind == 'schedule':
                    self.schedule_status.set(str(payload))
                else:
                    self.busy = False
                    self.status.set('失败：' + str(payload))
                    messagebox.showerror('任务失败', str(payload))
        except queue.Empty:
            pass
        self.after(130, self.consume_events)

    def login(self):
        if not self.save(quiet=True):
            return
        channel = self.channel.get()
        def job():
            from browser import interactive_login
            okay = interactive_login(channel, lambda text: self.events.put(('status', text)))
            return '扫码登录完成。' if okay else '未检测到成功登录；请再次登录。'
        self.async_job('正在打开抖音官方登录页面……', job)

    def scan(self):
        if not self.save(quiet=True):
            return
        channel = self.channel.get()
        def job():
            from browser import fetch_contacts
            names = fetch_contacts(channel)
            self.events.put(('names', names))
            return f'已读取到 {len(names)} 条可见会话。请勾选需要续火的好友。'
        self.async_job('正在读取最近会话列表……', job)

    def task(self, verb):
        if not self.save(quiet=True):
            return
        def job():
            creation = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            p = subprocess.run(task_command(verb),
                               capture_output=True, text=True, encoding='utf-8', errors='replace',
                               creationflags=creation, timeout=35)
            if p.returncode:
                raise RuntimeError((p.stderr or p.stdout or '任务计划程序设置失败').strip())
            if verb == 'status':
                self.events.put(('schedule', (p.stdout or '').strip()))
            return (p.stdout or '操作完成').strip()
        self.async_job('正在操作 Windows 任务计划程序……', job)

    def run(self, real, single=False):
        target = self.selected() if single else None
        if single and not target:
            return messagebox.showinfo('选择好友', '请先选择一位好友。')
        if not self.save(quiet=True):
            return
        if real and not messagebox.askyesno('确认真实发送', f'发送范围：{target or "今天尚未执行或发送前网络失败的已启用好友"}。\n\n已发送、结果不明和其他失败不会重发。确定继续吗？'):
            return
        def job():
            # Called in worker thread. Launches a separate short-lived subprocess like the scheduled task.
            args = runner_command(dry_run=not real)
            if target:
                args += ['--target', target]
            creation = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            proc = subprocess.run(args, cwd=str(ROOT), creationflags=creation, timeout=600,
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            return ('任务完成，请查看日志。' if proc.returncode == 0 else '执行存在异常，请点击「查看运行日志」排查。')
        self.async_job('正在' + ('真实发送' if real else '测试聊天窗口') + '，请勿同时打开抖音自动化浏览器……', job)

    def show_logs(self):
        self.show_text('运行日志', LOG_FILE.read_text(encoding='utf-8')[-60000:] if LOG_FILE.exists() else '暂无日志。')

    def show_text(self, title, content):
        window = tk.Toplevel(self)
        window.title(title)
        window.geometry('930x560')
        text = tk.Text(window, wrap='word', font=('Microsoft YaHei UI', 10), bg=self.palette[1], fg=self.palette[2], padx=20, pady=20)
        text.pack(fill='both', expand=True)
        try:
            text.insert('1.0', content[-60_000:])
        except Exception as exc:
            text.insert('1.0', '无法读取：' + str(exc))
        text.configure(state='disabled')

    def open_data(self):
        BASE.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            os.startfile(BASE)
        else:
            messagebox.showinfo('本地数据目录', str(BASE))


if __name__ == '__main__':
    Manager().mainloop()
