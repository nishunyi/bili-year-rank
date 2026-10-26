"""Native Windows GUI for the public-search collector."""
from pathlib import Path
import json
import queue
import re
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import webbrowser

import bili_rank


class App:
    def __init__(self, root):
        self.root = root
        root.title('B站年份检索 · 候选播放榜')
        root.geometry('860x690')
        root.minsize(720, 580)
        self.messages = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.report = None
        main = ttk.Frame(root, padding=22)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='按发布年份，找回那些视频', font=('Microsoft YaHei UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(main, text='多关键词采集 → 按年份校验 → 去重排序 → 导出 CSV / 可浏览报告').pack(anchor='w', pady=(6, 14))
        warning = ttk.Label(main, text='结果是已收集候选中的排名。搜索必须带关键词，因此不能保证全站前 100。\n播放量来自搜索接口；可选择额外统计核验。每条结果保留来源和采集时间。', foreground='#8c5700', wraplength=780)
        warning.pack(anchor='w', pady=(0, 16))
        options = ttk.Frame(main)
        options.pack(fill='x')
        self.year = tk.StringVar(value='2018')
        self.pages = tk.StringVar(value='2')
        self.limit = tk.StringVar(value='100')
        for label, variable, low, high in [('发布年份', self.year, 2009, bili_rank.dt.datetime.now(bili_rank.TZ).year), ('每词页数', self.pages, 1, 100), ('显示前几名', self.limit, 1, 10000)]:
            ttk.Label(options, text=label).pack(side='left', padx=(0, 7))
            ttk.Spinbox(options, from_=low, to=high, textvariable=variable, width=7).pack(side='left', padx=(0, 20))
        ttk.Label(main, text='搜索关键词（逗号、顿号或换行分隔；更多词有助于扩充候选）').pack(anchor='w', pady=(16, 5))
        self.keywords = scrolledtext.ScrolledText(main, height=4, font=('Microsoft YaHei UI', 10), wrap='word')
        self.keywords.pack(fill='x')
        self.generated_keywords='、'.join(bili_rank.keywords_for_year(2018))
        self.keywords.insert('1.0',self.generated_keywords)
        self.year.trace_add('write',self.update_year_keywords)
        self.refresh_stats = tk.BooleanVar(value=False)
        ttk.Checkbutton(main, text='逐条核验全部候选的播放统计（耗时更长；接口受限时自动停止）', variable=self.refresh_stats).pack(anchor='w', pady=(12, 10))
        buttons = ttk.Frame(main)
        buttons.pack(fill='x')
        self.start_button = ttk.Button(buttons, text='开始采集并排序', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(buttons, text='停止并保存', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=10)
        ttk.Button(buttons, text='打开已有报告', command=self.open_report).pack(side='left')
        ttk.Button(buttons, text='从本地数据重新导出', command=self.export_existing).pack(side='right')
        self.status = tk.StringVar(value='准备就绪。匿名访问，不需要登录。默认请求间隔 5 秒。')
        ttk.Label(main, textvariable=self.status).pack(anchor='w', pady=10)
        self.log = scrolledtext.ScrolledText(main, font=('Consolas', 10), state='disabled', height=13)
        self.log.pack(fill='both', expand=True)
        ttk.Label(main, text='数据与报告保存在程序所在文件夹的 data / output 中；关闭后可再次打开。', foreground='#657080').pack(anchor='w', pady=(10, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(150, self.poll)

    def update_year_keywords(self,*_):
        try:
            year=int(self.year.get())
            bili_rank.bounds(year)
        except ValueError:return
        if self.keywords.get('1.0','end').strip()!=self.generated_keywords:return
        self.generated_keywords='、'.join(bili_rank.keywords_for_year(year))
        self.keywords.delete('1.0','end')
        self.keywords.insert('1.0',self.generated_keywords)

    def arguments(self):
        args = bili_rank.parser().parse_args([])
        args.year, args.pages, args.limit = int(self.year.get()), int(self.pages.get()), int(self.limit.get())
        bili_rank.bounds(args.year)
        if not 1 <= args.pages <= 100 or not 1 <= args.limit <= 10000:
            raise ValueError('页数须在 1—100 之间，排名数量须在 1—10000 之间')
        args.keywords = [x.strip() for x in re.split(r'[,，、\n]+', self.keywords.get('1.0', 'end')) if x.strip()]
        if not args.keywords:
            raise ValueError('请至少填写一个关键词')
        args.refresh_stats = self.refresh_stats.get()
        return args

    def start(self, export_only=False):
        if self.worker and self.worker.is_alive():
            return
        try:
            args = self.arguments()
        except ValueError as error:
            messagebox.showerror('检查输入', str(error))
            return
        args.export_only = export_only
        self.cancel = threading.Event()
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.status.set('正在处理；已完成的搜索页会立即保存。')

        def work():
            try:
                paths = bili_rank.run(args, lambda msg: self.messages.put(('log', msg)), self.cancel)
                meta = json.loads(paths[1].with_suffix('.json').read_text(encoding='utf-8'))['metadata']
                self.messages.put(('done', (paths[1], meta)))
            except Exception as error:
                self.messages.put(('error', str(error)))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def export_existing(self):
        self.start(export_only=True)

    def stop(self):
        self.cancel.set()
        self.status.set('正在停止，等待当前请求结束后导出已保存的数据……')

    def open_report(self):
        try:
            report = bili_rank.ROOT / 'output' / f'bilibili_{int(self.year.get())}_candidates.html'
        except ValueError:
            return
        if report.exists():
            webbrowser.open(report.as_uri())
        else:
            messagebox.showinfo('还没有报告', '请先采集，或从本地数据重新导出。')

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'log':
                    self.log.configure(state='normal')
                    self.log.insert('end', value + '\n')
                    self.log.see('end')
                    self.log.configure(state='disabled')
                elif kind == 'done':
                    self.report, meta = value
                    prefix = '已停止并导出部分数据' if meta.get('errors') else '采集 / 导出完成'
                    self.status.set(f'{prefix}：共 {meta["candidate_count"]} 个候选，报告显示 {meta["exported_count"]} 个。')
                    self.start_button.configure(state='normal')
                    self.stop_button.configure(state='disabled')
                elif kind == 'error':
                    self.status.set('运行未完成：' + value)
                    self.start_button.configure(state='normal')
                    self.stop_button.configure(state='disabled')
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def close(self):
        if self.worker and self.worker.is_alive():
            self.stop()
            self.root.after(200, self.close)
        else:
            self.root.destroy()


if __name__ == '__main__':
    window = tk.Tk()
    ttk.Style().theme_use('vista')
    App(window)
    window.mainloop()
