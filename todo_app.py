import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkcalendar import Calendar
from datetime import datetime
import json
import os

try:
    from plyer import notification
except Exception:  # plyer 未安装时降级
    notification = None


class TodoApp:
    TASKS_FILE = "tasks.json"
    IMP_FILE = "improvement_tasks.json"

    PRIORITY_OPTIONS = ["🟢 低", "🟡 中", "🔴 高"]
    PRIORITY_TAG = {"🔴": "high", "🟡": "medium", "🟢": "low"}

    def __init__(self, root):
        self.root = root
        self.root.title("✨ 高级待办计划与健康助手")
        self.root.geometry("950x720")
        self.root.minsize(820, 640)
        self.root.configure(bg="#F3F4F6")

        try:
            self.root.iconbitmap("todo_icon.ico")
        except Exception:
            pass

        # ---------- 数据 ----------
        self.current_date = datetime.now().date()
        self.todo_list = self.load_tasks()
        self.completed_tasks_shown = False

        self.improvement_tasks = self.load_improvement_tasks()
        self.improvement_completed_shown = False

        # iid -> 原始任务字符串 的映射，避免用显示文本反查数据
        self.daily_items = {}
        self.improvement_items = {}

        # ---------- 番茄钟 ----------
        self.pomodoro_running = False
        self.pomodoro_paused = False
        self.pomodoro_is_break = False
        self.pomodoro_time_left = 0
        self.pomodoro_total_time = 0
        self.pomodoro_after_id = None
        self.today_focus_minutes = 0
        self.completed_pomodoros = 0

        # ---------- 状态栏定时器 ----------
        self._status_after_id = None

        self.create_styles()
        self.create_widgets()
        self.create_context_menus()

        self.update_task_display()
        self.update_improvement_display()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ================= 样式 =================
    def create_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        default_font = ("Microsoft YaHei UI", 10)
        self.style.configure(".", background="#F3F4F6", font=default_font, foreground="#1F2937")
        self.style.configure("TFrame", background="#F3F4F6")

        self.style.configure("Card.TFrame", background="#FFFFFF", relief="flat")
        self.style.configure("Card.TLabel", background="#FFFFFF", foreground="#1F2937")
        self.style.configure("Card.TCheckbutton", background="#FFFFFF")

        self.style.configure("TNotebook", background="#F3F4F6", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Microsoft YaHei UI", 11, "bold"),
                             padding=[20, 8], background="#E5E7EB", foreground="#4B5563", borderwidth=0)
        self.style.map("TNotebook.Tab",
                       background=[("selected", "#FFFFFF")],
                       foreground=[("selected", "#2563EB")],
                       expand=[("selected", [0, 0, 0, 2])])

        self.style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=6,
                             background="#2563EB", foreground="white", borderwidth=0, focusthickness=0)
        self.style.map("TButton", background=[("active", "#1D4ED8"), ("disabled", "#9CA3AF")])

        self.style.configure("Success.TButton", background="#10B981")
        self.style.map("Success.TButton", background=[("active", "#059669"), ("disabled", "#9CA3AF")])

        self.style.configure("Danger.TButton", background="#EF4444")
        self.style.map("Danger.TButton", background=[("active", "#DC2626"), ("disabled", "#9CA3AF")])

        self.style.configure("TEntry", padding=6, fieldbackground="#FFFFFF", bordercolor="#D1D5DB")
        self.style.configure("TCombobox", padding=6, fieldbackground="#FFFFFF", bordercolor="#D1D5DB")

        self.style.configure("Title.TLabel", font=("Microsoft YaHei UI", 14, "bold"),
                             background="#F3F4F6", foreground="#111827")
        self.style.configure("Subtitle.TLabel", font=("Microsoft YaHei UI", 11, "bold"),
                             background="#FFFFFF", foreground="#2563EB")
        self.style.configure("Muted.TLabel", foreground="#6B7280", background="#FFFFFF")

        self.style.configure("Treeview", rowheight=34, fieldbackground="#FFFFFF", background="#FFFFFF",
                             borderwidth=0, font=default_font)
        self.style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"),
                             background="#F9FAFB", foreground="#374151", borderwidth=0)
        self.style.map("Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", "#1E3A8A")])

        self.style.configure("Custom.Horizontal.TProgressbar",
                             background="#2563EB", troughcolor="#E5E7EB", thickness=12, borderwidth=0)
        self.style.configure("Green.Horizontal.TProgressbar",
                             background="#10B981", troughcolor="#E5E7EB", thickness=12, borderwidth=0)
        self.style.configure("Break.Horizontal.TProgressbar",
                             background="#10B981", troughcolor="#E5E7EB", thickness=12, borderwidth=0)

    # ================= 界面 =================
    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        self.notebook = ttk.Notebook(main_frame)
        self.daily_tab = ttk.Frame(self.notebook, style="TFrame")
        self.improvement_tab = ttk.Frame(self.notebook, style="TFrame")
        self.pomodoro_tab = ttk.Frame(self.notebook, style="TFrame")

        self.notebook.add(self.daily_tab, text='  📅 每日待办  ')
        self.notebook.add(self.improvement_tab, text='  📈 长期计划  ')
        self.notebook.add(self.pomodoro_tab, text='  ⏱️ 番茄时钟  ')
        self.notebook.pack(expand=True, fill="both")

        self.create_daily_tab()
        self.create_improvement_tab()
        self.create_pomodoro_tab()

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill="x", pady=(10, 0))
        self.status_label = ttk.Label(status_frame, text="就绪",
                                       font=("Microsoft YaHei UI", 9), foreground="#6B7280")
        self.status_label.pack(side="left")
        self.clock_label = ttk.Label(status_frame, text="",
                                      font=("Microsoft YaHei UI", 9), foreground="#6B7280")
        self.clock_label.pack(side="right")
        self._tick_clock()

    def create_daily_tab(self):
        top_frame = ttk.Frame(self.daily_tab)
        top_frame.pack(fill="x", padx=10, pady=10)

        cal_card = ttk.Frame(top_frame, style="Card.TFrame", padding=15)
        cal_card.pack(side="left", fill="y", padx=(0, 15))
        ttk.Label(cal_card, text="📅 选择日期", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))

        self.calendar = Calendar(cal_card, selectmode='day',
                                 year=self.current_date.year, month=self.current_date.month,
                                 day=self.current_date.day,
                                 background="#2563EB", foreground="white", bordercolor="#E5E7EB",
                                 headersbackground="#F3F4F6", headersforeground="#1F2937",
                                 normalbackground="#FFFFFF", weekendbackground="#F9FAFB",
                                 othermonthbackground="#F9FAFB", othermonthforeground="#9CA3AF",
                                 font=("Microsoft YaHei UI", 9))
        self.calendar.pack()
        self.calendar.bind("<<CalendarSelected>>", self.on_date_change)

        today_btn = ttk.Button(cal_card, text="↩ 回到今天", command=self.go_to_today)
        today_btn.pack(fill="x", pady=(10, 0))

        input_card = ttk.Frame(top_frame, style="Card.TFrame", padding=15)
        input_card.pack(side="left", fill="both", expand=True)
        ttk.Label(input_card, text="➕ 添加新任务", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))

        entry_row = ttk.Frame(input_card, style="Card.TFrame")
        entry_row.pack(fill="x", pady=(0, 10))

        self.priority_combo = ttk.Combobox(entry_row, values=self.PRIORITY_OPTIONS, width=8, state="readonly")
        self.priority_combo.set("🟡 中")
        self.priority_combo.pack(side="left", padx=(0, 10))

        self.todo_entry = ttk.Entry(entry_row, font=("Microsoft YaHei UI", 11))
        self.todo_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.todo_entry.bind("<Return>", lambda e: self.add_task())

        ttk.Button(entry_row, text="添加任务", style="Success.TButton", command=self.add_task).pack(side="right")

        self.daily_stats_label = ttk.Label(input_card, text="今日统计：加载中...", style="Muted.TLabel")
        self.daily_stats_label.pack(anchor="w")

        list_card = ttk.Frame(self.daily_tab, style="Card.TFrame", padding=10)
        list_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.task_tree = ttk.Treeview(list_card, columns=("status", "task"),
                                      show="headings", selectmode="browse")
        self.task_tree.heading("status", text="状态")
        self.task_tree.heading("task", text="📋 任务列表 (双击切换状态 / 右键更多操作)")
        self.task_tree.column("status", width=70, anchor="center", stretch=False)
        self.task_tree.column("task", width=560, anchor="w")

        self.task_tree.tag_configure('high', foreground="#DC2626")
        self.task_tree.tag_configure('medium', foreground="#D97706")
        self.task_tree.tag_configure('low', foreground="#059669")
        self.task_tree.tag_configure('done', foreground="#9CA3AF")
        self.task_tree.tag_configure('empty', foreground="#9CA3AF")

        scrollbar = ttk.Scrollbar(list_card, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        self.task_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.task_tree.bind("<Double-1>", self.toggle_task_status)
        self.task_tree.bind("<Button-3>", self.show_daily_context_menu)

        btn_frame = ttk.Frame(self.daily_tab)
        btn_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.daily_view_btn = ttk.Button(btn_frame, text="👁 查看已完成", command=self.toggle_task_view)
        self.daily_view_btn.pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="清空已完成", style="Danger.TButton",
                   command=self.clear_completed_tasks).pack(side="left")
        ttk.Button(btn_frame, text="📊 详细统计", command=self.show_stats).pack(side="right")

    def create_improvement_tab(self):
        prog_card = ttk.Frame(self.improvement_tab, style="Card.TFrame", padding=15)
        prog_card.pack(fill="x", padx=10, pady=10)
        ttk.Label(prog_card, text="🎯 长期目标整体进度", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))

        self.improvement_progress = ttk.Progressbar(prog_card, style="Green.Horizontal.TProgressbar",
                                                     mode="determinate")
        self.improvement_progress.pack(fill="x")
        self.improvement_prog_label = ttk.Label(prog_card, text="0%", style="Muted.TLabel")
        self.improvement_prog_label.pack(anchor="e", pady=(5, 0))

        input_card = ttk.Frame(self.improvement_tab, style="Card.TFrame", padding=15)
        input_card.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(input_card, text="➕ 添加长期计划", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))

        entry_row = ttk.Frame(input_card, style="Card.TFrame")
        entry_row.pack(fill="x")

        self.imp_priority_combo = ttk.Combobox(entry_row, values=self.PRIORITY_OPTIONS, width=8, state="readonly")
        self.imp_priority_combo.set("🟡 中")
        self.imp_priority_combo.pack(side="left", padx=(0, 10))

        self.improvement_entry = ttk.Entry(entry_row, font=("Microsoft YaHei UI", 11))
        self.improvement_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.improvement_entry.bind("<Return>", lambda e: self.add_improvement_task())

        ttk.Button(entry_row, text="添加计划", style="Success.TButton",
                   command=self.add_improvement_task).pack(side="right")

        list_card = ttk.Frame(self.improvement_tab, style="Card.TFrame", padding=10)
        list_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.improvement_tree = ttk.Treeview(list_card, columns=("status", "task"),
                                             show="headings", selectmode="browse")
        self.improvement_tree.heading("status", text="状态")
        self.improvement_tree.heading("task", text="🚀 长期计划列表 (双击切换状态 / 右键更多操作)")
        self.improvement_tree.column("status", width=70, anchor="center", stretch=False)
        self.improvement_tree.column("task", width=560, anchor="w")

        self.improvement_tree.tag_configure('high', foreground="#DC2626")
        self.improvement_tree.tag_configure('medium', foreground="#D97706")
        self.improvement_tree.tag_configure('low', foreground="#059669")
        self.improvement_tree.tag_configure('done', foreground="#9CA3AF")
        self.improvement_tree.tag_configure('empty', foreground="#9CA3AF")

        scrollbar = ttk.Scrollbar(list_card, orient="vertical", command=self.improvement_tree.yview)
        self.improvement_tree.configure(yscrollcommand=scrollbar.set)
        self.improvement_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.improvement_tree.bind("<Double-1>", self.toggle_improvement_status)
        self.improvement_tree.bind("<Button-3>", self.show_imp_context_menu)

        btn_frame = ttk.Frame(self.improvement_tab)
        btn_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.imp_view_btn = ttk.Button(btn_frame, text="👁 查看已完成", command=self.toggle_improvement_view)
        self.imp_view_btn.pack(side="left")

    def create_pomodoro_tab(self):
        main_frame = ttk.Frame(self.pomodoro_tab)
        main_frame.pack(fill="both", expand=True, padx=40, pady=20)

        ttk.Label(main_frame, text="🍅 番茄专注时钟", font=("Microsoft YaHei UI", 18, "bold"),
                  foreground="#2563EB").pack(pady=(20, 10))

        self.pomodoro_time_display = ttk.Label(main_frame, text="25:00",
                                               font=("Consolas", 64, "bold"), foreground="#1F2937")
        self.pomodoro_time_display.pack(pady=20)

        self.pomodoro_status_label = ttk.Label(main_frame, text="准备开始工作",
                                               font=("Microsoft YaHei UI", 12), foreground="#6B7280")
        self.pomodoro_status_label.pack(pady=(0, 20))

        self.pomodoro_progress = tk.DoubleVar(value=100)
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.pomodoro_progress,
                                            style="Custom.Horizontal.TProgressbar",
                                            length=500, mode="determinate")
        self.progress_bar.pack(pady=10, fill="x")

        settings_card = ttk.Frame(main_frame, style="Card.TFrame", padding=20)
        settings_card.pack(pady=30)

        ttk.Label(settings_card, text="工作(分):", style="Card.TLabel").grid(row=0, column=0, padx=8, pady=5, sticky="e")
        self.work_time_entry = ttk.Entry(settings_card, width=5, justify="center", font=("Consolas", 12))
        self.work_time_entry.insert(0, "25")
        self.work_time_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(settings_card, text="休息(分):", style="Card.TLabel").grid(row=0, column=2, padx=8, pady=5, sticky="e")
        self.break_time_entry = ttk.Entry(settings_card, width=5, justify="center", font=("Consolas", 12))
        self.break_time_entry.insert(0, "5")
        self.break_time_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(settings_card, text="长休息(分):", style="Card.TLabel").grid(row=0, column=4, padx=8, pady=5, sticky="e")
        self.long_break_entry = ttk.Entry(settings_card, width=5, justify="center", font=("Consolas", 12))
        self.long_break_entry.insert(0, "15")
        self.long_break_entry.grid(row=0, column=5, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        self.start_btn = ttk.Button(btn_frame, text="▶ 开始专注", style="Success.TButton",
                                    command=self.toggle_pomodoro, width=15)
        self.start_btn.pack(side="left", padx=10)
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止/重置", style="Danger.TButton",
                                   command=self.stop_pomodoro, width=15)
        self.stop_btn.pack(side="left", padx=10)

        self.focus_stats_label = ttk.Label(main_frame, text="今日已专注: 0 分钟  |  完成番茄: 0 个",
                                            font=("Microsoft YaHei UI", 11), foreground="#10B981")
        self.focus_stats_label.pack(pady=20)

    # ================= 数据持久化 =================
    def load_tasks(self):
        tasks = {}
        if os.path.exists(self.TASKS_FILE):
            try:
                with open(self.TASKS_FILE, "r", encoding="utf-8") as f:
                    tasks = json.load(f)
                if not isinstance(tasks, dict):
                    tasks = {}
            except Exception:
                tasks = {}
        self.carry_over_tasks(tasks)
        return tasks

    def load_improvement_tasks(self):
        if os.path.exists(self.IMP_FILE):
            try:
                with open(self.IMP_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict) and "not_done" in loaded and "done" in loaded:
                    return loaded
            except Exception:
                pass
        return {"not_done": [], "done": []}

    def carry_over_tasks(self, tasks):
        """智能结转：将过去所有未完成的积压任务结转到今天"""
        today = self.current_date.isoformat()
        tasks.setdefault(today, {"not_done": [], "done": []})

        uncompleted = []
        for date_str, data in tasks.items():
            if date_str < today and data.get("not_done"):
                uncompleted.extend(data["not_done"])
                data["not_done"] = []

        if uncompleted:
            existing = tasks[today]["not_done"]
            for task in uncompleted:
                if task not in existing:
                    existing.append(task)

    def save_tasks(self):
        try:
            with open(self.TASKS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.todo_list, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.set_status(f"⚠️ 保存失败: {e}")

    def save_improvement_tasks(self):
        try:
            with open(self.IMP_FILE, "w", encoding="utf-8") as f:
                json.dump(self.improvement_tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.set_status(f"⚠️ 保存失败: {e}")

    # ================= 每日任务 =================
    def _ensure_date(self, date_key):
        self.todo_list.setdefault(date_key, {"not_done": [], "done": []})
        return self.todo_list[date_key]

    def add_task(self):
        text = self.todo_entry.get().strip()
        if not text:
            messagebox.showwarning("提示", "任务内容不能为空！")
            return

        priority = self.priority_combo.get().split(" ")[0]
        time_str = datetime.now().strftime("%H:%M")
        task_str = f"{priority} {text} | {time_str}"

        date_key = self.current_date.isoformat()
        data = self._ensure_date(date_key)
        if task_str in data["not_done"]:
            self.set_status("⚠️ 该任务已存在")
            return
        data["not_done"].append(task_str)

        self.todo_entry.delete(0, tk.END)
        # 添加任务时如果在已完成视图，自动切回未完成
        if self.completed_tasks_shown:
            self.completed_tasks_shown = False
            self.daily_view_btn.config(text="👁 查看已完成")
        self.update_task_display()
        self.save_tasks()
        self.set_status(f"✅ 任务 '{text}' 已添加")

    def _selected_daily_task(self):
        sel = self.task_tree.selection()
        if not sel:
            return None
        return self.daily_items.get(sel[0])

    def toggle_task_status(self, event=None):
        task = self._selected_daily_task()
        if task is None:
            return
        data = self._ensure_date(self.current_date.isoformat())

        if self.completed_tasks_shown:
            if task in data["done"]:
                data["done"].remove(task)
                data["not_done"].append(task)
                self.set_status("🔄 任务已恢复为未完成")
        else:
            if task in data["not_done"]:
                data["not_done"].remove(task)
                data["done"].append(task)
                self.set_status("🎉 恭喜！任务已完成")

        self.update_task_display()
        self.save_tasks()

    def edit_task(self):
        task = self._selected_daily_task()
        if task is None:
            return
        parts = task.split(" | ")
        head = parts[0]
        raw_text = head.split(" ", 1)[1] if " " in head else head

        new_text = simpledialog.askstring("编辑任务", "修改任务内容:", initialvalue=raw_text, parent=self.root)
        if new_text and new_text.strip():
            cat = "done" if self.completed_tasks_shown else "not_done"
            data = self._ensure_date(self.current_date.isoformat())
            if task in data[cat]:
                idx = data[cat].index(task)
                emoji = task[0]
                time_part = parts[1] if len(parts) > 1 else datetime.now().strftime("%H:%M")
                data[cat][idx] = f"{emoji} {new_text.strip()} | {time_part}"
                self.update_task_display()
                self.save_tasks()
                self.set_status("✏️ 任务已更新")

    def delete_task(self):
        task = self._selected_daily_task()
        if task is None:
            return
        if messagebox.askyesno("确认删除", "确定要删除该任务吗？"):
            cat = "done" if self.completed_tasks_shown else "not_done"
            data = self._ensure_date(self.current_date.isoformat())
            if task in data[cat]:
                data[cat].remove(task)
                self.update_task_display()
                self.save_tasks()
                self.set_status("🗑️ 任务已删除")

    def clear_completed_tasks(self):
        date_key = self.current_date.isoformat()
        data = self.todo_list.get(date_key, {})
        if data.get("done"):
            if messagebox.askyesno("确认清空", "确定清空今日所有已完成的任务吗？"):
                data["done"] = []
                self.update_task_display()
                self.save_tasks()
                self.set_status("🧹 已清空已完成任务")
        else:
            self.set_status("当前没有已完成任务")

    def toggle_task_view(self):
        self.completed_tasks_shown = not self.completed_tasks_shown
        self.daily_view_btn.config(
            text="👁 查看未完成" if self.completed_tasks_shown else "👁 查看已完成")
        self.update_task_display()

    @staticmethod
    def _priority_tag(task, done):
        if done:
            return 'done'
        return TodoApp.PRIORITY_TAG.get(task[0], 'medium')

    def update_task_display(self):
        self.task_tree.delete(*self.task_tree.get_children())
        self.daily_items.clear()

        date_key = self.current_date.isoformat()
        cat = "done" if self.completed_tasks_shown else "not_done"
        tasks = self.todo_list.get(date_key, {}).get(cat, [])

        if not tasks:
            placeholder = "暂无已完成任务 🎯" if self.completed_tasks_shown else "今天还没有任务，添加一个吧 ✨"
            self.task_tree.insert("", "end", values=("", placeholder), tags=('empty',))
        else:
            status_icon = "✅" if self.completed_tasks_shown else "⏳"
            for task in tasks:
                tag = self._priority_tag(task, self.completed_tasks_shown)
                iid = self.task_tree.insert("", "end", values=(status_icon, task), tags=(tag,))
                self.daily_items[iid] = task

        data = self.todo_list.get(date_key, {})
        total = len(data.get("not_done", [])) + len(data.get("done", []))
        done = len(data.get("done", []))
        if total > 0:
            self.daily_stats_label.config(
                text=f"📊 今日统计：共 {total} 项，已完成 {done} 项 (完成率 {done / total * 100:.0f}%)")
        else:
            self.daily_stats_label.config(text="📊 今日暂无任务")

    # ================= 长期计划 =================
    def add_improvement_task(self):
        text = self.improvement_entry.get().strip()
        if not text:
            messagebox.showwarning("提示", "计划内容不能为空！")
            return

        priority = self.imp_priority_combo.get().split(" ")[0]
        task_str = f"{priority} {text}"
        if task_str in self.improvement_tasks["not_done"]:
            self.set_status("⚠️ 该计划已存在")
            return
        self.improvement_tasks["not_done"].append(task_str)
        self.improvement_entry.delete(0, tk.END)
        if self.improvement_completed_shown:
            self.improvement_completed_shown = False
            self.imp_view_btn.config(text="👁 查看已完成")
        self.update_improvement_display()
        self.save_improvement_tasks()
        self.set_status(f"✅ 长期计划 '{text}' 已添加")

    def _selected_imp_task(self):
        sel = self.improvement_tree.selection()
        if not sel:
            return None
        return self.improvement_items.get(sel[0])

    def toggle_improvement_status(self, event=None):
        task = self._selected_imp_task()
        if task is None:
            return
        if self.improvement_completed_shown:
            if task in self.improvement_tasks["done"]:
                self.improvement_tasks["done"].remove(task)
                self.improvement_tasks["not_done"].append(task)
                self.set_status("🔄 计划已恢复为未完成")
        else:
            if task in self.improvement_tasks["not_done"]:
                self.improvement_tasks["not_done"].remove(task)
                self.improvement_tasks["done"].append(task)
                self.set_status("🎉 长期计划已完成")

        self.update_improvement_display()
        self.save_improvement_tasks()

    def edit_improvement_task(self):
        task = self._selected_imp_task()
        if task is None:
            return
        raw_text = task.split(" ", 1)[1] if " " in task else task

        new_text = simpledialog.askstring("编辑计划", "修改计划内容:", initialvalue=raw_text, parent=self.root)
        if new_text and new_text.strip():
            cat = "done" if self.improvement_completed_shown else "not_done"
            if task in self.improvement_tasks[cat]:
                idx = self.improvement_tasks[cat].index(task)
                emoji = task[0]
                self.improvement_tasks[cat][idx] = f"{emoji} {new_text.strip()}"
                self.update_improvement_display()
                self.save_improvement_tasks()
                self.set_status("✏️ 计划已更新")

    def delete_improvement_task(self):
        task = self._selected_imp_task()
        if task is None:
            return
        if messagebox.askyesno("确认删除", "确定要删除该长期计划吗？"):
            cat = "done" if self.improvement_completed_shown else "not_done"
            if task in self.improvement_tasks[cat]:
                self.improvement_tasks[cat].remove(task)
                self.update_improvement_display()
                self.save_improvement_tasks()
                self.set_status("🗑️ 计划已删除")

    def toggle_improvement_view(self):
        self.improvement_completed_shown = not self.improvement_completed_shown
        self.imp_view_btn.config(
            text="👁 查看未完成" if self.improvement_completed_shown else "👁 查看已完成")
        self.update_improvement_display()

    def update_improvement_display(self):
        self.improvement_tree.delete(*self.improvement_tree.get_children())
        self.improvement_items.clear()

        cat = "done" if self.improvement_completed_shown else "not_done"
        tasks = self.improvement_tasks[cat]

        if not tasks:
            placeholder = "暂无已完成计划 🎯" if self.improvement_completed_shown else "还没有长期计划，立个目标吧 🚀"
            self.improvement_tree.insert("", "end", values=("", placeholder), tags=('empty',))
        else:
            status_icon = "✅" if self.improvement_completed_shown else "⏳"
            for task in tasks:
                tag = self._priority_tag(task, self.improvement_completed_shown)
                iid = self.improvement_tree.insert("", "end", values=(status_icon, task), tags=(tag,))
                self.improvement_items[iid] = task

        total = len(self.improvement_tasks["not_done"]) + len(self.improvement_tasks["done"])
        done = len(self.improvement_tasks["done"])
        percent = (done / total * 100) if total > 0 else 0
        self.improvement_progress["value"] = percent
        self.improvement_prog_label.config(text=f"{percent:.0f}% ({done}/{total})")

    # ================= 番茄钟 =================
    def _read_minutes(self, entry, default):
        try:
            val = int(entry.get())
            if val <= 0:
                raise ValueError
            return val
        except ValueError:
            return default

    def toggle_pomodoro(self):
        """开始 / 暂停 / 继续"""
        if not self.pomodoro_running:
            self.start_pomodoro()
        elif self.pomodoro_paused:
            self.resume_pomodoro()
        else:
            self.pause_pomodoro()

    def start_pomodoro(self):
        try:
            mins = int(self.work_time_entry.get()) if not self.pomodoro_is_break else None
            if not self.pomodoro_is_break:
                if mins is None or mins <= 0:
                    raise ValueError
                self.pomodoro_status_label.config(text="🔥 专注工作中...", foreground="#EF4444")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正整数分钟数！")
            return

        if self.pomodoro_is_break:
            # 每 4 个番茄进入长休息
            if self.completed_pomodoros > 0 and self.completed_pomodoros % 4 == 0:
                mins = self._read_minutes(self.long_break_entry, 15)
                self.pomodoro_status_label.config(text="🌴 长休息时间...", foreground="#10B981")
            else:
                mins = self._read_minutes(self.break_time_entry, 5)
                self.pomodoro_status_label.config(text="☕ 休息时间...", foreground="#10B981")

        self.pomodoro_total_time = mins * 60
        self.pomodoro_time_left = self.pomodoro_total_time
        self.pomodoro_running = True
        self.pomodoro_paused = False
        self.start_btn.config(text="⏸ 暂停")
        self._set_inputs_state("disabled")
        self.run_pomodoro_tick()

    def pause_pomodoro(self):
        self.pomodoro_paused = True
        if self.pomodoro_after_id:
            self.root.after_cancel(self.pomodoro_after_id)
            self.pomodoro_after_id = None
        self.start_btn.config(text="▶ 继续")
        self.pomodoro_status_label.config(text="⏸ 已暂停", foreground="#6B7280")

    def resume_pomodoro(self):
        self.pomodoro_paused = False
        self.start_btn.config(text="⏸ 暂停")
        if self.pomodoro_is_break:
            self.pomodoro_status_label.config(text="☕ 休息时间...", foreground="#10B981")
        else:
            self.pomodoro_status_label.config(text="🔥 专注工作中...", foreground="#EF4444")
        self.run_pomodoro_tick()

    def run_pomodoro_tick(self):
        if not self.pomodoro_running or self.pomodoro_paused:
            return

        mins, secs = divmod(self.pomodoro_time_left, 60)
        self.pomodoro_time_display.config(text=f"{mins:02d}:{secs:02d}")

        if self.pomodoro_total_time > 0:
            self.pomodoro_progress.set((self.pomodoro_time_left / self.pomodoro_total_time) * 100)

        if self.pomodoro_time_left <= 0:
            self.pomodoro_finished()
            return

        self.pomodoro_time_left -= 1
        self.pomodoro_after_id = self.root.after(1000, self.run_pomodoro_tick)

    def pomodoro_finished(self):
        self.pomodoro_running = False
        self.pomodoro_paused = False
        self.pomodoro_after_id = None

        if not self.pomodoro_is_break:
            self.today_focus_minutes += self.pomodoro_total_time // 60
            self.completed_pomodoros += 1
            self.focus_stats_label.config(
                text=f"今日已专注: {self.today_focus_minutes} 分钟  |  完成番茄: {self.completed_pomodoros} 个")
            self.pomodoro_is_break = True
            self.show_notification("🍅 番茄钟结束", "工作完成！休息一下吧。")
            self.start_pomodoro()  # 自动进入休息
        else:
            self.pomodoro_is_break = False
            self.show_notification("☕ 休息结束", "精力恢复！开始下一个番茄钟吧。")
            self._reset_pomodoro_display()
            self.pomodoro_status_label.config(text="准备开始工作", foreground="#6B7280")

    def stop_pomodoro(self):
        self.pomodoro_running = False
        self.pomodoro_paused = False
        self.pomodoro_is_break = False
        if self.pomodoro_after_id:
            self.root.after_cancel(self.pomodoro_after_id)
            self.pomodoro_after_id = None
        self._reset_pomodoro_display()
        self.pomodoro_status_label.config(text="已停止", foreground="#6B7280")

    def _reset_pomodoro_display(self):
        mins = self._read_minutes(self.work_time_entry, 25)
        self.start_btn.config(text="▶ 开始专注")
        self._set_inputs_state("normal")
        self.pomodoro_time_display.config(text=f"{mins:02d}:00")
        self.pomodoro_progress.set(100)

    def _set_inputs_state(self, state):
        for entry in (self.work_time_entry, self.break_time_entry, self.long_break_entry):
            entry.config(state=state)

    def show_notification(self, title, message):
        if notification is not None:
            try:
                notification.notify(title=title, message=message, timeout=5)
                return
            except Exception:
                pass
        messagebox.showinfo(title, message)

    # ================= 右键菜单与辅助 =================
    def create_context_menus(self):
        self.daily_menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        self.daily_menu.add_command(label="✅ 完成 / 🔄 恢复", command=self.toggle_task_status)
        self.daily_menu.add_command(label="✏️ 编辑任务", command=self.edit_task)
        self.daily_menu.add_separator()
        self.daily_menu.add_command(label="❌ 删除任务", command=self.delete_task)

        self.imp_menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        self.imp_menu.add_command(label="✅ 完成 / 🔄 恢复", command=self.toggle_improvement_status)
        self.imp_menu.add_command(label="✏️ 编辑计划", command=self.edit_improvement_task)
        self.imp_menu.add_separator()
        self.imp_menu.add_command(label="❌ 删除计划", command=self.delete_improvement_task)

    def show_daily_context_menu(self, event):
        row = self.task_tree.identify_row(event.y)
        if row and row in self.daily_items:
            self.task_tree.selection_set(row)
            self.daily_menu.tk_popup(event.x_root, event.y_root)

    def show_imp_context_menu(self, event):
        row = self.improvement_tree.identify_row(event.y)
        if row and row in self.improvement_items:
            self.improvement_tree.selection_set(row)
            self.imp_menu.tk_popup(event.x_root, event.y_root)

    def on_date_change(self, event=None):
        self.current_date = self.calendar.selection_get()
        self.completed_tasks_shown = False
        self.daily_view_btn.config(text="👁 查看已完成")
        self.update_task_display()
        self.set_status(f"📅 已切换至 {self.current_date_cn()}")

    def go_to_today(self):
        self.current_date = datetime.now().date()
        self.calendar.selection_set(self.current_date)
        self.completed_tasks_shown = False
        self.daily_view_btn.config(text="👁 查看已完成")
        self.update_task_display()
        self.set_status("📅 已回到今天")

    def show_stats(self):
        date_key = self.current_date.isoformat()
        data = self.todo_list.get(date_key, {})
        not_done = len(data.get("not_done", []))
        done = len(data.get("done", []))
        total = not_done + done
        rate = (done / total * 100) if total > 0 else 0
        high_pri = sum(1 for t in data.get("not_done", []) if t.startswith("🔴"))

        msg = (
            f"📅 日期: {self.current_date_cn()}\n"
            f"{'─' * 25}\n"
            f"📊 总任务数: {total}\n"
            f"✅ 已完成: {done}\n"
            f"⏳ 未完成: {not_done}\n"
            f"🔴 高优未完成: {high_pri}\n"
            f"{'─' * 25}\n"
            f"🏆 完成率: {rate:.1f}%"
        )
        messagebox.showinfo("📊 每日任务详细统计", msg)

    def set_status(self, text):
        self.status_label.config(text=text)
        if self._status_after_id:
            self.root.after_cancel(self._status_after_id)
        self._status_after_id = self.root.after(
            3000, lambda: self.status_label.config(
                text=f"当前日期: {self.current_date.strftime('%Y-%m-%d')}"))

    def current_date_cn(self):
        d = self.current_date
        return f"{d.year}年{d.month:02d}月{d.day:02d}日"

    def _tick_clock(self):
        self.clock_label.config(text="🕐 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def on_close(self):
        self.save_tasks()
        self.save_improvement_tasks()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = TodoApp(root)
    root.mainloop()
