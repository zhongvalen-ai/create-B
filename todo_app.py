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

    # ---------- 设计系统 / 调色板 ----------
    BG = "#F1F5F9"            # 内容区背景 (slate-100)
    CARD = "#FFFFFF"
    BORDER = "#E5E7EB"
    TEXT = "#0F172A"          # 主文字 (slate-900)
    MUTED = "#64748B"         # 次要文字 (slate-500)

    SIDEBAR = "#1E1B4B"       # 侧边栏深色 (indigo-950)
    SIDEBAR_TEXT = "#C7D2FE"  # 侧边栏文字 (indigo-200)
    SIDEBAR_HOVER = "#312E81" # indigo-900
    SIDEBAR_ACTIVE = "#4F46E5"# indigo-600

    ACCENT = "#4F46E5"        # 主题色 indigo-600
    ACCENT_DK = "#4338CA"
    SUCCESS = "#10B981"
    SUCCESS_DK = "#059669"
    DANGER = "#EF4444"
    DANGER_DK = "#DC2626"

    STRIPE = "#F8FAFC"        # 斑马纹

    FONT = "Microsoft YaHei UI"

    def __init__(self, root):
        self.root = root
        self.root.title("✨ 待办计划与健康助手")
        self.root.geometry("1040x740")
        self.root.minsize(940, 660)
        self.root.configure(bg=self.BG)

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

        # ---------- 导航 ----------
        self.pages = {}
        self.nav_buttons = {}
        self.active_page = None

        self._status_after_id = None

        self.create_styles()
        self.create_widgets()
        self.create_context_menus()

        self.update_task_display()
        self.update_improvement_display()
        self.show_page("daily")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ================= 样式 =================
    def create_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        base_font = (self.FONT, 10)
        self.style.configure(".", background=self.CARD, foreground=self.TEXT, font=base_font)

        # 主按钮
        self.style.configure("Accent.TButton", font=(self.FONT, 10, "bold"), padding=(14, 8),
                             background=self.ACCENT, foreground="white", borderwidth=0, focusthickness=0)
        self.style.map("Accent.TButton",
                       background=[("active", self.ACCENT_DK), ("disabled", "#A5B4FC")])

        self.style.configure("Success.TButton", font=(self.FONT, 10, "bold"), padding=(14, 8),
                             background=self.SUCCESS, foreground="white", borderwidth=0, focusthickness=0)
        self.style.map("Success.TButton",
                       background=[("active", self.SUCCESS_DK), ("disabled", "#9CA3AF")])

        self.style.configure("Danger.TButton", font=(self.FONT, 10, "bold"), padding=(14, 8),
                             background=self.DANGER, foreground="white", borderwidth=0, focusthickness=0)
        self.style.map("Danger.TButton",
                       background=[("active", self.DANGER_DK), ("disabled", "#9CA3AF")])

        # 次要 / 幽灵按钮
        self.style.configure("Ghost.TButton", font=(self.FONT, 10), padding=(12, 7),
                             background="#EEF2FF", foreground="#4338CA", borderwidth=0, focusthickness=0)
        self.style.map("Ghost.TButton",
                       background=[("active", "#E0E7FF")])

        # 输入框 / 下拉框
        self.style.configure("TEntry", padding=8, relief="flat",
                             fieldbackground="#FFFFFF", bordercolor=self.BORDER, borderwidth=1)
        self.style.map("TEntry", bordercolor=[("focus", self.ACCENT)])
        self.style.configure("TCombobox", padding=6, relief="flat",
                             fieldbackground="#FFFFFF", bordercolor=self.BORDER, borderwidth=1)
        self.style.map("TCombobox", bordercolor=[("focus", self.ACCENT)])

        # Treeview
        self.style.configure("Treeview", rowheight=38, font=(self.FONT, 10),
                             fieldbackground="#FFFFFF", background="#FFFFFF",
                             foreground=self.TEXT, borderwidth=0)
        self.style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # 去掉外边框
        self.style.configure("Treeview.Heading", font=(self.FONT, 10, "bold"),
                             background="#F8FAFC", foreground="#475569",
                             relief="flat", borderwidth=0, padding=(8, 8))
        self.style.map("Treeview.Heading", background=[("active", "#EEF2FF")])
        self.style.map("Treeview",
                       background=[("selected", "#E0E7FF")],
                       foreground=[("selected", "#3730A3")])

        # 滚动条
        self.style.configure("Vertical.TScrollbar", background="#CBD5E1", troughcolor="#F1F5F9",
                             borderwidth=0, arrowcolor="#64748B")

        # 进度条
        self.style.configure("Accent.Horizontal.TProgressbar",
                             background=self.ACCENT, troughcolor="#E2E8F0", thickness=14, borderwidth=0)
        self.style.configure("Green.Horizontal.TProgressbar",
                             background=self.SUCCESS, troughcolor="#E2E8F0", thickness=14, borderwidth=0)

    # ---------- 小组件工厂 ----------
    def _card(self, parent, padx=18, pady=18):
        """返回 (外框, 内容框)。外框带 1px 边框，内容框已加内边距。"""
        outer = tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER,
                         highlightcolor=self.BORDER, highlightthickness=1, bd=0)
        inner = tk.Frame(outer, bg=self.CARD)
        inner.pack(fill="both", expand=True, padx=padx, pady=pady)
        return outer, inner

    def _label(self, parent, text, *, fg=None, size=10, bold=False, bg=None):
        return tk.Label(parent, text=text, bg=bg or self.CARD, fg=fg or self.TEXT,
                        font=(self.FONT, size, "bold" if bold else "normal"))

    def _section_title(self, parent, text):
        return self._label(parent, text, fg=self.ACCENT, size=11, bold=True)

    # ================= 界面骨架 =================
    def create_widgets(self):
        # ---------- 侧边栏 ----------
        sidebar = tk.Frame(self.root, bg=self.SIDEBAR, width=216)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebar = sidebar

        logo = tk.Frame(sidebar, bg=self.SIDEBAR)
        logo.pack(fill="x", pady=(26, 8), padx=20)
        tk.Label(logo, text="✨ 待办助手", bg=self.SIDEBAR, fg="white",
                 font=(self.FONT, 15, "bold")).pack(anchor="w")
        tk.Label(logo, text="Planner & Focus", bg=self.SIDEBAR, fg="#818CF8",
                 font=("Segoe UI", 9)).pack(anchor="w")

        tk.Frame(sidebar, bg="#312E81", height=1).pack(fill="x", padx=18, pady=(14, 10))

        self._add_nav("daily", "📅   每日待办")
        self._add_nav("improvement", "📈   长期计划")
        self._add_nav("pomodoro", "⏱️   番茄时钟")

        # 侧边栏底部时钟
        clock_box = tk.Frame(sidebar, bg=self.SIDEBAR)
        clock_box.pack(side="bottom", fill="x", padx=20, pady=18)
        self.clock_label = tk.Label(clock_box, text="", bg=self.SIDEBAR, fg="#A5B4FC",
                                    font=("Consolas", 9))
        self.clock_label.pack(anchor="w")

        # ---------- 内容区 ----------
        content = tk.Frame(self.root, bg=self.BG)
        content.pack(side="left", fill="both", expand=True)

        self.page_container = tk.Frame(content, bg=self.BG)
        self.page_container.pack(fill="both", expand=True)
        self.page_container.grid_rowconfigure(0, weight=1)
        self.page_container.grid_columnconfigure(0, weight=1)

        for key in ("daily", "improvement", "pomodoro"):
            frame = tk.Frame(self.page_container, bg=self.BG)
            frame.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = frame

        self.create_daily_tab()
        self.create_improvement_tab()
        self.create_pomodoro_tab()

        # ---------- 底部状态栏 ----------
        status_bar = tk.Frame(content, bg="#FFFFFF", highlightbackground=self.BORDER,
                              highlightthickness=1)
        status_bar.pack(fill="x", side="bottom")
        self.status_label = tk.Label(status_bar, text="就绪", bg="#FFFFFF", fg=self.MUTED,
                                     font=(self.FONT, 9))
        self.status_label.pack(side="left", padx=16, pady=6)

        self._tick_clock()

    def _add_nav(self, key, text):
        btn = tk.Label(self.sidebar, text=text, bg=self.SIDEBAR, fg=self.SIDEBAR_TEXT,
                       font=(self.FONT, 11), anchor="w", padx=24, pady=13, cursor="hand2")
        btn.pack(fill="x", padx=10, pady=2)
        btn.bind("<Button-1>", lambda e: self.show_page(key))
        btn.bind("<Enter>", lambda e: self._nav_hover(key, True))
        btn.bind("<Leave>", lambda e: self._nav_hover(key, False))
        self.nav_buttons[key] = btn

    def _nav_hover(self, key, entering):
        if key == self.active_page:
            return
        self.nav_buttons[key].config(bg=self.SIDEBAR_HOVER if entering else self.SIDEBAR)

    def show_page(self, key):
        self.active_page = key
        self.pages[key].tkraise()
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.config(bg=self.SIDEBAR_ACTIVE, fg="white", font=(self.FONT, 11, "bold"))
            else:
                btn.config(bg=self.SIDEBAR, fg=self.SIDEBAR_TEXT, font=(self.FONT, 11))

    def _page_header(self, page, title, subtitle):
        header = tk.Frame(page, bg=self.BG)
        header.pack(fill="x", padx=26, pady=(22, 12))
        tk.Label(header, text=title, bg=self.BG, fg=self.TEXT,
                 font=(self.FONT, 18, "bold")).pack(anchor="w")
        tk.Label(header, text=subtitle, bg=self.BG, fg=self.MUTED,
                 font=(self.FONT, 10)).pack(anchor="w", pady=(2, 0))
        return header

    # ================= 每日待办页 =================
    def create_daily_tab(self):
        page = self.pages["daily"]
        self._page_header(page, "📅 每日待办", "管理今天的任务，未完成的会自动结转到今天")

        body = tk.Frame(page, bg=self.BG)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 14))

        top = tk.Frame(body, bg=self.BG)
        top.pack(fill="x")

        # 日历卡片
        cal_outer, cal_card = self._card(top)
        cal_outer.pack(side="left", fill="y", padx=(0, 16))
        self._section_title(cal_card, "选择日期").pack(anchor="w", pady=(0, 10))
        self.calendar = Calendar(
            cal_card, selectmode='day',
            year=self.current_date.year, month=self.current_date.month, day=self.current_date.day,
            font=(self.FONT, 9), showweeknumbers=False, firstweekday="monday",
            background=self.ACCENT, foreground="white", bordercolor="#FFFFFF",
            headersbackground="#EEF2FF", headersforeground="#4338CA",
            normalbackground="#FFFFFF", normalforeground=self.TEXT,
            weekendbackground="#FFFFFF", weekendforeground=self.TEXT,
            othermonthbackground="#F8FAFC", othermonthforeground="#CBD5E1",
            othermonthwebackground="#F8FAFC", othermonthweforeground="#CBD5E1",
            selectbackground=self.ACCENT, selectforeground="white")
        self.calendar.pack()
        self.calendar.bind("<<CalendarSelected>>", self.on_date_change)
        ttk.Button(cal_card, text="↩ 回到今天", style="Ghost.TButton",
                   command=self.go_to_today).pack(fill="x", pady=(12, 0))

        # 输入卡片
        in_outer, in_card = self._card(top)
        in_outer.pack(side="left", fill="both", expand=True)
        self._section_title(in_card, "添加新任务").pack(anchor="w", pady=(0, 12))

        row = tk.Frame(in_card, bg=self.CARD)
        row.pack(fill="x")
        self.priority_combo = ttk.Combobox(row, values=self.PRIORITY_OPTIONS, width=7, state="readonly")
        self.priority_combo.set("🟡 中")
        self.priority_combo.pack(side="left", padx=(0, 10))
        self.todo_entry = ttk.Entry(row, font=(self.FONT, 11))
        self.todo_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.todo_entry.bind("<Return>", lambda e: self.add_task())
        ttk.Button(row, text="＋ 添加", style="Success.TButton", command=self.add_task).pack(side="right")

        self.daily_stats_label = self._label(in_card, "今日统计：加载中...", fg=self.MUTED)
        self.daily_stats_label.pack(anchor="w", pady=(16, 0))

        # 提示
        self._label(in_card,
                    "提示：双击任务切换完成状态，右键可编辑或删除",
                    fg="#94A3B8", size=9).pack(anchor="w", pady=(10, 0))

        # 任务列表卡片
        list_outer, list_card = self._card(body, padx=14, pady=14)
        list_outer.pack(fill="both", expand=True, pady=(16, 0))

        bar = tk.Frame(list_card, bg=self.CARD)
        bar.pack(fill="x", pady=(0, 10))
        self._label(bar, "📋 任务列表", size=12, bold=True).pack(side="left")
        self.daily_view_btn = ttk.Button(bar, text="👁 查看已完成", style="Ghost.TButton",
                                          command=self.toggle_task_view)
        self.daily_view_btn.pack(side="right")
        ttk.Button(bar, text="📊 统计", style="Ghost.TButton",
                   command=self.show_stats).pack(side="right", padx=(0, 8))
        ttk.Button(bar, text="🧹 清空已完成", style="Danger.TButton",
                   command=self.clear_completed_tasks).pack(side="right", padx=(0, 8))

        tree_wrap = tk.Frame(list_card, bg=self.CARD)
        tree_wrap.pack(fill="both", expand=True)
        self.task_tree = ttk.Treeview(tree_wrap, columns=("status", "task"),
                                      show="headings", selectmode="browse")
        self.task_tree.heading("status", text="状态")
        self.task_tree.heading("task", text="任务内容")
        self.task_tree.column("status", width=80, anchor="center", stretch=False)
        self.task_tree.column("task", width=560, anchor="w")
        self._config_tree_tags(self.task_tree)

        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.task_tree.yview,
                           style="Vertical.TScrollbar")
        self.task_tree.configure(yscrollcommand=sb.set)
        self.task_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.task_tree.bind("<Double-1>", self.toggle_task_status)
        self.task_tree.bind("<Button-3>", self.show_daily_context_menu)

    # ================= 长期计划页 =================
    def create_improvement_tab(self):
        page = self.pages["improvement"]
        self._page_header(page, "📈 长期计划", "追踪你的长期目标与整体进度")

        body = tk.Frame(page, bg=self.BG)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 14))

        # 进度卡片
        prog_outer, prog_card = self._card(body)
        prog_outer.pack(fill="x")
        head = tk.Frame(prog_card, bg=self.CARD)
        head.pack(fill="x", pady=(0, 12))
        self._section_title(head, "🎯 整体进度").pack(side="left")
        self.improvement_prog_label = self._label(head, "0%", fg=self.MUTED, size=11, bold=True)
        self.improvement_prog_label.pack(side="right")
        self.improvement_progress = ttk.Progressbar(prog_card, style="Green.Horizontal.TProgressbar",
                                                     mode="determinate")
        self.improvement_progress.pack(fill="x")

        # 输入卡片
        in_outer, in_card = self._card(body)
        in_outer.pack(fill="x", pady=(16, 0))
        self._section_title(in_card, "添加长期计划").pack(anchor="w", pady=(0, 12))
        row = tk.Frame(in_card, bg=self.CARD)
        row.pack(fill="x")
        self.imp_priority_combo = ttk.Combobox(row, values=self.PRIORITY_OPTIONS, width=7, state="readonly")
        self.imp_priority_combo.set("🟡 中")
        self.imp_priority_combo.pack(side="left", padx=(0, 10))
        self.improvement_entry = ttk.Entry(row, font=(self.FONT, 11))
        self.improvement_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.improvement_entry.bind("<Return>", lambda e: self.add_improvement_task())
        ttk.Button(row, text="＋ 添加", style="Success.TButton",
                   command=self.add_improvement_task).pack(side="right")

        # 列表卡片
        list_outer, list_card = self._card(body, padx=14, pady=14)
        list_outer.pack(fill="both", expand=True, pady=(16, 0))
        bar = tk.Frame(list_card, bg=self.CARD)
        bar.pack(fill="x", pady=(0, 10))
        self._label(bar, "🚀 计划列表", size=12, bold=True).pack(side="left")
        self.imp_view_btn = ttk.Button(bar, text="👁 查看已完成", style="Ghost.TButton",
                                       command=self.toggle_improvement_view)
        self.imp_view_btn.pack(side="right")

        tree_wrap = tk.Frame(list_card, bg=self.CARD)
        tree_wrap.pack(fill="both", expand=True)
        self.improvement_tree = ttk.Treeview(tree_wrap, columns=("status", "task"),
                                             show="headings", selectmode="browse")
        self.improvement_tree.heading("status", text="状态")
        self.improvement_tree.heading("task", text="计划内容")
        self.improvement_tree.column("status", width=80, anchor="center", stretch=False)
        self.improvement_tree.column("task", width=560, anchor="w")
        self._config_tree_tags(self.improvement_tree)

        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.improvement_tree.yview,
                           style="Vertical.TScrollbar")
        self.improvement_tree.configure(yscrollcommand=sb.set)
        self.improvement_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.improvement_tree.bind("<Double-1>", self.toggle_improvement_status)
        self.improvement_tree.bind("<Button-3>", self.show_imp_context_menu)

    def _config_tree_tags(self, tree):
        tree.tag_configure('high', foreground=self.DANGER)
        tree.tag_configure('medium', foreground="#D97706")
        tree.tag_configure('low', foreground=self.SUCCESS_DK)
        tree.tag_configure('done', foreground="#94A3B8")
        tree.tag_configure('empty', foreground="#94A3B8")
        tree.tag_configure('oddrow', background="#FFFFFF")
        tree.tag_configure('evenrow', background=self.STRIPE)

    # ================= 番茄时钟页 =================
    def create_pomodoro_tab(self):
        page = self.pages["pomodoro"]
        self._page_header(page, "⏱️ 番茄时钟", "专注工作，劳逸结合")

        wrap = tk.Frame(page, bg=self.BG)
        wrap.pack(fill="both", expand=True, padx=26, pady=(0, 20))

        # 中央计时卡片
        timer_outer, timer_card = self._card(wrap, padx=40, pady=30)
        timer_outer.pack(pady=(6, 0))

        self.pomodoro_status_label = self._label(timer_card, "准备开始工作",
                                                 fg=self.MUTED, size=12, bold=True)
        self.pomodoro_status_label.pack(pady=(0, 8))

        self.pomodoro_time_display = tk.Label(timer_card, text="25:00", bg=self.CARD,
                                              fg=self.TEXT, font=("Consolas", 72, "bold"))
        self.pomodoro_time_display.pack(pady=(0, 14))

        self.pomodoro_progress = tk.DoubleVar(value=100)
        self.progress_bar = ttk.Progressbar(timer_card, variable=self.pomodoro_progress,
                                            style="Accent.Horizontal.TProgressbar",
                                            length=460, mode="determinate")
        self.progress_bar.pack(pady=(0, 4))

        # 控制按钮
        btns = tk.Frame(timer_card, bg=self.CARD)
        btns.pack(pady=(22, 0))
        self.start_btn = ttk.Button(btns, text="▶ 开始专注", style="Success.TButton",
                                    command=self.toggle_pomodoro, width=14)
        self.start_btn.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(btns, text="⏹ 停止/重置", style="Danger.TButton",
                                   command=self.stop_pomodoro, width=14)
        self.stop_btn.pack(side="left", padx=8)

        # 设置卡片
        set_outer, set_card = self._card(wrap)
        set_outer.pack(pady=(18, 0))
        self._section_title(set_card, "⚙️ 时长设置（分钟）").pack(anchor="w", pady=(0, 12))
        grid = tk.Frame(set_card, bg=self.CARD)
        grid.pack()
        self._label(grid, "工作", fg=self.MUTED).grid(row=0, column=0, padx=(0, 6), pady=4, sticky="e")
        self.work_time_entry = ttk.Entry(grid, width=5, justify="center", font=("Consolas", 12))
        self.work_time_entry.insert(0, "25")
        self.work_time_entry.grid(row=0, column=1, padx=(0, 20), pady=4)
        self._label(grid, "短休息", fg=self.MUTED).grid(row=0, column=2, padx=(0, 6), pady=4, sticky="e")
        self.break_time_entry = ttk.Entry(grid, width=5, justify="center", font=("Consolas", 12))
        self.break_time_entry.insert(0, "5")
        self.break_time_entry.grid(row=0, column=3, padx=(0, 20), pady=4)
        self._label(grid, "长休息", fg=self.MUTED).grid(row=0, column=4, padx=(0, 6), pady=4, sticky="e")
        self.long_break_entry = ttk.Entry(grid, width=5, justify="center", font=("Consolas", 12))
        self.long_break_entry.insert(0, "15")
        self.long_break_entry.grid(row=0, column=5, pady=4)

        self.focus_stats_label = self._label(wrap, "今日已专注: 0 分钟   |   完成番茄: 0 个",
                                             fg=self.SUCCESS_DK, bg=self.BG, size=11, bold=True)
        self.focus_stats_label.pack(pady=(20, 0))

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
            for i, task in enumerate(tasks):
                stripe = 'evenrow' if i % 2 else 'oddrow'
                tag = self._priority_tag(task, self.completed_tasks_shown)
                iid = self.task_tree.insert("", "end", values=(status_icon, task), tags=(tag, stripe))
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
            for i, task in enumerate(tasks):
                stripe = 'evenrow' if i % 2 else 'oddrow'
                tag = self._priority_tag(task, self.improvement_completed_shown)
                iid = self.improvement_tree.insert("", "end", values=(status_icon, task), tags=(tag, stripe))
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
                self.pomodoro_status_label.config(text="🔥 专注工作中...", fg=self.DANGER)
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正整数分钟数！")
            return

        if self.pomodoro_is_break:
            # 每 4 个番茄进入长休息
            if self.completed_pomodoros > 0 and self.completed_pomodoros % 4 == 0:
                mins = self._read_minutes(self.long_break_entry, 15)
                self.pomodoro_status_label.config(text="🌴 长休息时间...", fg=self.SUCCESS_DK)
            else:
                mins = self._read_minutes(self.break_time_entry, 5)
                self.pomodoro_status_label.config(text="☕ 休息时间...", fg=self.SUCCESS_DK)

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
        self.pomodoro_status_label.config(text="⏸ 已暂停", fg=self.MUTED)

    def resume_pomodoro(self):
        self.pomodoro_paused = False
        self.start_btn.config(text="⏸ 暂停")
        if self.pomodoro_is_break:
            self.pomodoro_status_label.config(text="☕ 休息时间...", fg=self.SUCCESS_DK)
        else:
            self.pomodoro_status_label.config(text="🔥 专注工作中...", fg=self.DANGER)
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
                text=f"今日已专注: {self.today_focus_minutes} 分钟   |   完成番茄: {self.completed_pomodoros} 个")
            self.pomodoro_is_break = True
            self.show_notification("🍅 番茄钟结束", "工作完成！休息一下吧。")
            self.start_pomodoro()  # 自动进入休息
        else:
            self.pomodoro_is_break = False
            self.show_notification("☕ 休息结束", "精力恢复！开始下一个番茄钟吧。")
            self._reset_pomodoro_display()
            self.pomodoro_status_label.config(text="准备开始工作", fg=self.MUTED)

    def stop_pomodoro(self):
        self.pomodoro_running = False
        self.pomodoro_paused = False
        self.pomodoro_is_break = False
        if self.pomodoro_after_id:
            self.root.after_cancel(self.pomodoro_after_id)
            self.pomodoro_after_id = None
        self._reset_pomodoro_display()
        self.pomodoro_status_label.config(text="已停止", fg=self.MUTED)

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
        self.daily_menu = tk.Menu(self.root, tearoff=0, font=(self.FONT, 10))
        self.daily_menu.add_command(label="✅ 完成 / 🔄 恢复", command=self.toggle_task_status)
        self.daily_menu.add_command(label="✏️ 编辑任务", command=self.edit_task)
        self.daily_menu.add_separator()
        self.daily_menu.add_command(label="❌ 删除任务", command=self.delete_task)

        self.imp_menu = tk.Menu(self.root, tearoff=0, font=(self.FONT, 10))
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
        self.clock_label.config(text="🕐 " + datetime.now().strftime("%Y-%m-%d\n%H:%M:%S"))
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
