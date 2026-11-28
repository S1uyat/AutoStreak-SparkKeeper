"""On-demand Windows Tk management interface. Not launched at startup."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog
from core import BASE, LOG_FILE, get_config, get_state, save_config
from app_runtime import install_root, task_command, runner_command

ROOT = install_root()


class Manager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('SparkKeeper · 抖音火花助手')
        self.geometry('840x700')
        self.minsize(720, 590)
        self.config_data = get_config()
        self.events = queue.Queue()
        self.busy = False
        self.protocol('WM_DELETE_WINDOW', self.close_manager)
        self._build()
        self.refresh()
        self.after(130, self.consume_events)

    def _build(self):
        style = ttk.Style(self)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='SparkKeeper  ·  登录及每日零点自动续火', font=('Microsoft YaHei UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='不驻留后台。首次设置完成后，由 Windows 任务计划程序短暂执行，结束立即退出。', foreground='#555').pack(anchor='w', pady=(3, 12))

        line1 = ttk.Frame(frame)
        line1.pack(fill='x', pady=(0, 6))
        ttk.Label(line1, text='登录与好友', font=('Microsoft YaHei UI', 11, 'bold')).pack(side='left')
        ttk.Button(line1, text='扫码登录 / 重新验证', command=self.login).pack(side='right', padx=3)
        ttk.Button(line1, text='读取私信会话', command=self.scan).pack(side='right', padx=3)
        tablewrap = ttk.Frame(frame)
        tablewrap.pack(fill='both', expand=True)
        self.table = ttk.Treeview(tablewrap, columns=('enabled', 'name', 'status'), show='headings', height=10, selectmode='browse')
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
        ttk.Button(ops, text='添加好友', command=self.add_friend).pack(side='left', padx=(0, 7))
        ttk.Button(ops, text='启用 / 暂停', command=self.toggle_friend).pack(side='left', padx=7)
        ttk.Button(ops, text='删除', command=self.delete_friend).pack(side='left', padx=7)
        ttk.Button(ops, text='刷新状态', command=self.refresh).pack(side='right')

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
        ttk.Button(settings, text='保存设置', command=self.save).pack(side='right')

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
        self.status = tk.StringVar(value='准备就绪。')
        ttk.Label(frame, textvariable=self.status, wraplength=780, foreground='#306a79').pack(fill='x', pady=(15, 5))
        ttk.Label(frame, text='提示：登录态仅保存在当前 Windows 用户的本机目录。页面改版、登录过期或风控可能导致发送失败；软件不能保证火花维持。',
                  foreground='#666', wraplength=770).pack(anchor='w')

    def close_manager(self):
        if self.busy:
            messagebox.showinfo('任务进行中', '请等待任务结束，或先关闭扫码浏览器，再退出管理面板。')
            return
        self.destroy()

    def refresh(self):
        state = get_state()['results']
        rows = self.table.get_children()
        if rows:
            self.table.delete(*rows)
        labels = {'sent': '已观察到发送', 'uncertain': '发送状态不确定', 'failed': '执行失败', 'attempting': '执行中'}
        for item in self.config_data['contacts']:
            name = item['name']
            value = state.get(name, {})
            self.table.insert('', 'end', values=('是' if item.get('enabled', True) else '否', name,
                                                labels.get(value.get('status'), '今日未执行')))

    def selected(self):
        picked = self.table.selection()
        return self.table.item(picked[0], 'values')[1] if picked else None

    def add_friend(self):
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
        name = self.selected()
        if not name:
            return
        if not messagebox.askyesno('确认删除', f'从配置中删除「{name}」？'):
            return
        self.config_data['contacts'] = [c for c in self.config_data['contacts'] if c['name'] != name]
        self.save(quiet=True)
        self.refresh()

    def save(self, quiet=False):
        self.config_data['message'] = self.message.get().strip()
        self.config_data['channel'] = self.channel.get()
        self.config_data['headless'] = self.headless.get()
        self.config_data['auto_send'] = self.auto_send.get()
        try:
            save_config(self.config_data)
            self.status.set('配置已保存在本机。')
            if not quiet:
                messagebox.showinfo('成功', '配置已保存。')
            return True
        except Exception as exc:
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
            return (p.stdout or '操作完成').strip()
        self.async_job('正在操作 Windows 任务计划程序……', job)

    def run(self, real):
        if not self.save(quiet=True):
            return
        if real and not messagebox.askyesno('确认真实发送', '即将给今天未执行的已启用好友发送真实私信。\n\n发送结果不明时不会自动重发。确定继续吗？'):
            return
        def job():
            # Called in worker thread. Launches a separate short-lived subprocess like the scheduled task.
            args = runner_command(dry_run=not real)
            creation = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            proc = subprocess.run(args, cwd=str(ROOT), creationflags=creation, timeout=600,
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            return ('任务完成，请查看日志。' if proc.returncode == 0 else '执行存在异常，请点击「查看运行日志」排查。')
        self.async_job('正在' + ('真实发送' if real else '测试聊天窗口') + '，请勿同时打开抖音自动化浏览器……', job)

    def show_logs(self):
        window = tk.Toplevel(self)
        window.title('运行日志')
        window.geometry('930x560')
        text = tk.Text(window, wrap='none', font=('Consolas', 10))
        text.pack(fill='both', expand=True)
        try:
            content = LOG_FILE.read_text(encoding='utf-8') if LOG_FILE.exists() else '暂无日志。'
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
