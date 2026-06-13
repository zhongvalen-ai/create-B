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
    RECUR_FILE = "recurring.json"

    PRIORITY_OPTIONS = ["🟢 低", "🟡 中", "🔴 高"]
    PRIORITY_TAG = {"🔴": "high", "🟡": "medium", "🟢": "low"}
    PRIORITY_COLOR = {"🔴": "#EF4444", "🟡": "#D97706", "🟢": "#059669"}
    WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    # ---------- 设计系统 / 调色板 ----------
    BG = "#F1F5F9"
    CARD = "#FFFFFF"
    BORDER = "#E5E7EB"
    TEXT = "#0F172A"
    MUTED = "#64748B"

    SIDEBAR = "#1E1B4B"
    SIDEBAR_TEXT = "#C7D2FE"
    SIDEBAR_HOVER = "#312E81"
    SIDEBAR_ACTIVE = "#4F46E5"

    ACCENT = "#4F46E5"
    ACCENT_DK = "#4338CA"
    SUCCESS = "#10B981"
    SUCCESS_DK = "#059669"
    DANGER = "#EF4444"
    DANGER_DK = "#DC2626"

    STRIPE = "#F8FAFC"
    FONT = "Microsoft YaHei UI"

    def __init__(self, root):
        self.root = root
        self.root.title("✨ 待办计划与健康助手")
        self.root.geometry("1040x760")
        self.root.minsize(960, 680)
        self.root.configure(bg=self.BG)

        try:
            self.root.iconbitmap("todo_icon.ico")
        except Exception:
            pass

        # ---------- 数据 ----------
        self.current_date = datetime.now().date()
        self.todo_list = self.load_tasks()
        self.completed_tasks_shown = False

        # 长期计划：list[{"text","priority","progress"}]
        self.improvement_tasks = self.load_improvement_tasks()
        self.show_incomplete_only = False
        # 循环任务规则：list[{"text","priority","freq","weekday"?}]
        self.recurring = self.load_recurring()

        self.daily_items = {}

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

        self.generate_recurring()          # 生成今天的循环任务实例
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

        self.style.configure("Accent.TButton", font=(self.FONT, 10, "bold"), padding=(14, 8),
                             background=self.ACCENT, foreground="white", borderwidth=0, focusthickness=0)
        self.style.map("Accent.TButton", background=[("active", self.ACCENT_DK), ("disabled", "#A5B4FC")])

        self.style.configure("Success.TButton", font=(self.FONT, 10, "bold"), padding=(14, 8),
                             background=self.SUCCESS, foreground="white", borderwidth=0, focusthickness=0)
        self.style.map("Success.TButton", background=[("active", self.SUCCESS_DK), ("disabled", "#9CA3AF")])

        self.style.configure("Danger.TButton", font=(self.FONT, 10, "bold"), padding=(14, 8),
                             background=self.DANGER, foreground="white", borderwidth=0, focusthickness=0)
        self.style.map("Danger.TButton", background=[("active", self.DANGER_DK), ("disabled", "#9CA3AF")])

        self.style.configure("Ghost.TButton", font=(self.FONT, 10), padding=(12, 7),
                             background="#EEF2FF", foreground="#4338CA", borderwidth=0, focusthickness=0)
        self.style.map("Ghost.TButton", background=[("active", "#E0E7FF")])

        # 行内小按钮
        self.style.configure("Mini.TButton", font=(self.FONT, 9), padding=(6, 3),
                             background="#EEF2FF", foreground="#4338CA", borderwidth=0, focusthickness=0)
        self.style.map("Mini.TButton", background=[("active", "#E0E7FF")])

        self.style.configure("TEntry", padding=8, relief="flat",
                             fieldbackground="#FFFFFF", bordercolor=self.BORDER, borderwidth=1)
        self.style.map("TEntry", bordercolor=[("focus", self.ACCENT)])
        self.style.configure("TCombobox", padding=6, relief="flat",
                             fieldbackground="#FFFFFF", bordercolor=self.BORDER, borderwidth=1)
        self.style.map("TCombobox", bordercolor=[("focus", self.ACCENT)])

        self.style.configure("Treeview", rowheight=38, font=(self.FONT, 10),
                             fieldbackground="#FFFFFF", background="#FFFFFF",
                             foreground=self.TEXT, borderwidth=0)
        self.style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        self.style.configure("Treeview.Heading", font=(self.FONT, 10, "bold"),
                             background="#F8FAFC", foreground="#475569",
                             relief="flat", borderwidth=0, padding=(8, 8))
        self.style.map("Treeview.Heading", background=[("active", "#EEF2FF")])
        self.style.map("Treeview", background=[("selected", "#E0E7FF")], foreground=[("selected", "#3730A3")])

        self.style.configure("Vertical.TScrollbar", background="#CBD5E1", troughcolor="#F1F5F9",
                             borderwidth=0, arrowcolor="#64748B")

        self.style.configure("Accent.Horizontal.TProgressbar",
                             background=self.ACCENT, troughcolor="#E2E8F0", thickness=14, borderwidth=0)
        self.style.configure("Green.Horizontal.TProgressbar",
                             background=self.SUCCESS, troughcolor="#E2E8F0", thickness=14, borderwidth=0)
        self.style.configure("Plan.Horizontal.TProgressbar",
                             background=self.ACCENT, troughcolor="#E2E8F0", thickness=10, borderwidth=0)
        self.style.configure("PlanDone.Horizontal.TProgressbar",
                             background=self.SUCCESS, troughcolor="#E2E8F0", thickness=10, borderwidth=0)

        self.style.configure("TScale", background=self.CARD, troughcolor="#E2E8F0", borderwidth=0)

    # ---------- 组件工厂 ----------
    def _card(self, parent, padx=18, pady=18):
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

        clock_box = tk.Frame(sidebar, bg=self.SIDEBAR)
        clock_box.pack(side="bottom", fill="x", padx=20, pady=18)
        self.clock_label = tk.Label(clock_box, text="", bg=self.SIDEBAR, fg="#A5B4FC",
                                    font=("Consolas", 9), justify="left")
        self.clock_label.pack(anchor="w")

        content = tk.Frame(self.root, bg=self.BG)
        content.pack(side="left", fill="both", expand=True)

        # 状态栏先创建，确保 status_label 在任何 set_status / 页面构建之前就绪
        status_bar = tk.Frame(content, bg="#FFFFFF", highlightbackground=self.BORDER, highlightthickness=1)
        status_bar.pack(fill="x", side="bottom")
        self.status_label = tk.Label(status_bar, text="就绪", bg="#FFFFFF", fg=self.MUTED, font=(self.FONT, 9))
        self.status_label.pack(side="left", padx=16, pady=6)

        self.page_container = tk.Frame(content, bg=self.BG)
        self.page_container.pack(fill="both", expand=True)

        for key in ("daily", "improvement", "pomodoro"):
            self.pages[key] = tk.Frame(self.page_container, bg=self.BG)

        self.create_daily_tab()
        self.create_improvement_tab()
        self.create_pomodoro_tab()

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
        for f in self.pages.values():
            f.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.config(bg=self.SIDEBAR_ACTIVE, fg="white", font=(self.FONT, 11, "bold"))
            else:
                btn.config(bg=self.SIDEBAR, fg=self.SIDEBAR_TEXT, font=(self.FONT, 11))

    def _page_header(self, page, title, subtitle):
        header = tk.Frame(page, bg=self.BG)
        header.pack(fill="x", padx=26, pady=(22, 12))
        tk.Label(header, text=title, bg=self.BG, fg=self.TEXT, font=(self.FONT, 18, "bold")).pack(anchor="w")
        tk.Label(header, text=subtitle, bg=self.BG, fg=self.MUTED, font=(self.FONT, 10)).pack(anchor="w", pady=(2, 0))
        return header

    # ================= 每日待办页 =================
    def create_daily_tab(self):
        page = self.pages["daily"]
        self._page_header(page, "📅 每日待办", "管理今天的任务，未完成的会自动结转；🔁 为循环任务")

        body = tk.Frame(page, bg=self.BG)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 14))

        top = tk.Frame(body, bg=self.BG)
        top.pack(fill="x")

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

        in_outer, in_card = self._card(top)
        in_outer.pack(side="left", fill="both", expand=True)
        self._section_title(in_card, "添加新任务").pack(anchor="w", pady=(0, 12))

        row = tk.Frame(in_card, bg=self.CARD)
        row.pack(fill="x")
        self.priority_combo = ttk.Combobox(row, values=self.PRIORITY_OPTIONS, width=7, state="readonly")
        self.priority_combo.set("🟡 中")
        self.priority_combo.pack(side="left", padx=(0, 8))
        self.freq_combo = ttk.Combobox(row, values=["一次性", "每日", "每周"], width=7, state="readonly")
        self.freq_combo.set("一次性")
        self.freq_combo.pack(side="left", padx=(0, 8))
        self.todo_entry = ttk.Entry(row, font=(self.FONT, 11))
        self.todo_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.todo_entry.bind("<Return>", lambda e: self.add_task())
        ttk.Button(row, text="＋ 添加", style="Success.TButton", command=self.add_task).pack(side="right")

        self.daily_stats_label = self._label(in_card, "今日统计：加载中...", fg=self.MUTED)
        self.daily_stats_label.pack(anchor="w", pady=(16, 0))
        self._label(in_card, "提示：选「每日/每周」即可创建循环任务，双击切换状态，右键可编辑/删除",
                    fg="#94A3B8", size=9).pack(anchor="w", pady=(8, 0))

        list_outer, list_card = self._card(body, padx=14, pady=14)
        list_outer.pack(fill="both", expand=True, pady=(16, 0))

        bar = tk.Frame(list_card, bg=self.CARD)
        bar.pack(fill="x", pady=(0, 10))
        self._label(bar, "📋 任务列表", size=12, bold=True).pack(side="left")
        ttk.Button(bar, text="🔁 循环任务", style="Ghost.TButton",
                   command=self.manage_recurring).pack(side="left", padx=(12, 0))
        self.daily_view_btn = ttk.Button(bar, text="👁 查看已完成", style="Ghost.TButton",
                                          command=self.toggle_task_view)
        self.daily_view_btn.pack(side="right")
        ttk.Button(bar, text="📊 统计", style="Ghost.TButton",
                   command=self.show_stats).pack(side="right", padx=(0, 8))
        ttk.Button(bar, text="🧹 清空已完成", style="Danger.TButton",
                   command=self.clear_completed_tasks).pack(side="right", padx=(0, 8))

        tree_wrap = tk.Frame(list_card, bg=self.CARD)
        tree_wrap.pack(fill="both", expand=True)
        self.task_tree = ttk.Treeview(tree_wrap, columns=("status", "task"), show="headings", selectmode="browse")
        self.task_tree.heading("status", text="状态")
        self.task_tree.heading("task", text="任务内容")
        self.task_tree.column("status", width=80, anchor="center", stretch=False)
        self.task_tree.column("task", width=560, anchor="w")
        self._config_tree_tags(self.task_tree)

        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.task_tree.yview, style="Vertical.TScrollbar")
        self.task_tree.configure(yscrollcommand=sb.set)
        self.task_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.task_tree.bind("<Double-1>", self.toggle_task_status)
        self.task_tree.bind("<Button-3>", self.show_daily_context_menu)

    # ================= 长期计划页 =================
    def create_improvement_tab(self):
        page = self.pages["improvement"]
        self._page_header(page, "📈 长期计划", "为每个目标拖动滑块设置进度，随时掌握完成情况")

        body = tk.Frame(page, bg=self.BG)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 14))

        prog_outer, prog_card = self._card(body)
        prog_outer.pack(fill="x")
        head = tk.Frame(prog_card, bg=self.CARD)
        head.pack(fill="x", pady=(0, 12))
        self._section_title(head, "🎯 平均进度").pack(side="left")
        self.improvement_prog_label = self._label(head, "0%", fg=self.MUTED, size=11, bold=True)
        self.improvement_prog_label.pack(side="right")
        self.improvement_progress = ttk.Progressbar(prog_card, style="Green.Horizontal.TProgressbar",
                                                     mode="determinate")
        self.improvement_progress.pack(fill="x")

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

        list_outer, list_card = self._card(body, padx=14, pady=14)
        list_outer.pack(fill="both", expand=True, pady=(16, 0))
        bar = tk.Frame(list_card, bg=self.CARD)
        bar.pack(fill="x", pady=(0, 10))
        self._label(bar, "🚀 计划列表", size=12, bold=True).pack(side="left")
        self.plan_filter_btn = ttk.Button(bar, text="👁 只看未完成", style="Ghost.TButton",
                                           command=self.toggle_plan_filter)
        self.plan_filter_btn.pack(side="right")

        # 可滚动区域
        canvas_wrap = tk.Frame(list_card, bg=self.CARD)
        canvas_wrap.pack(fill="both", expand=True)
        self.plan_canvas = tk.Canvas(canvas_wrap, bg=self.CARD, highlightthickness=0)
        sb = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.plan_canvas.yview,
                           style="Vertical.TScrollbar")
        self.plan_canvas.configure(yscrollcommand=sb.set)
        self.plan_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.plans_inner = tk.Frame(self.plan_canvas, bg=self.CARD)
        self._plan_window = self.plan_canvas.create_window((0, 0), window=self.plans_inner, anchor="nw")
        self.plans_inner.bind("<Configure>",
                              lambda e: self.plan_canvas.configure(scrollregion=self.plan_canvas.bbox("all")))
        self.plan_canvas.bind("<Configure>",
                             lambda e: self.plan_canvas.itemconfig(self._plan_window, width=e.width))
        self.plan_canvas.bind("<Enter>", lambda e: self.plan_canvas.bind_all("<MouseWheel>", self._on_plan_wheel))
        self.plan_canvas.bind("<Leave>", lambda e: self.plan_canvas.unbind_all("<MouseWheel>"))

    def _on_plan_wheel(self, event):
        self.plan_canvas.yview_scroll(int(-event.delta / 120), "units")

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

        timer_outer, timer_card = self._card(wrap, padx=40, pady=30)
        timer_outer.pack(pady=(6, 0))

        self.pomodoro_status_label = self._label(timer_card, "准备开始工作", fg=self.MUTED, size=12, bold=True)
        self.pomodoro_status_label.pack(pady=(0, 8))
        self.pomodoro_time_display = tk.Label(timer_card, text="25:00", bg=self.CARD, fg=self.TEXT,
                                              font=("Consolas", 72, "bold"))
        self.pomodoro_time_display.pack(pady=(0, 14))

        self.pomodoro_progress = tk.DoubleVar(value=100)
        self.progress_bar = ttk.Progressbar(timer_card, variable=self.pomodoro_progress,
                                            style="Accent.Horizontal.TProgressbar", length=460, mode="determinate")
        self.progress_bar.pack(pady=(0, 4))

        btns = tk.Frame(timer_card, bg=self.CARD)
        btns.pack(pady=(22, 0))
        self.start_btn = ttk.Button(btns, text="▶ 开始专注", style="Success.TButton",
                                    command=self.toggle_pomodoro, width=14)
        self.start_btn.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(btns, text="⏹ 停止/重置", style="Danger.TButton",
                                   command=self.stop_pomodoro, width=14)
        self.stop_btn.pack(side="left", padx=8)

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
        """返回 list[dict]。兼容旧的 {not_done, done} 字符串格式。"""
        if os.path.exists(self.IMP_FILE):
            try:
                with open(self.IMP_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except Exception:
                return []
            # 新格式
            if isinstance(loaded, list):
                plans = []
                for d in loaded:
                    if isinstance(d, dict) and "text" in d:
                        plans.append({
                            "text": d.get("text", ""),
                            "priority": d.get("priority", "🟡"),
                            "progress": int(d.get("progress", 0)),
                        })
                return plans
            # 旧格式迁移
            if isinstance(loaded, dict):
                plans = []
                for s in loaded.get("not_done", []):
                    plans.append(self._parse_legacy_plan(s, 0))
                for s in loaded.get("done", []):
                    plans.append(self._parse_legacy_plan(s, 100))
                return plans
        return []

    def _parse_legacy_plan(self, s, progress):
        emoji = s[0] if s and s[0] in self.PRIORITY_COLOR else "🟡"
        text = s.split(" ", 1)[1].strip() if " " in s else s
        return {"text": text, "priority": emoji, "progress": progress}

    def load_recurring(self):
        if os.path.exists(self.RECUR_FILE):
            try:
                with open(self.RECUR_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    return [r for r in loaded if isinstance(r, dict) and "text" in r]
            except Exception:
                pass
        return []

    def carry_over_tasks(self, tasks):
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

    def save_recurring(self):
        try:
            with open(self.RECUR_FILE, "w", encoding="utf-8") as f:
                json.dump(self.recurring, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.set_status(f"⚠️ 保存失败: {e}")

    # ================= 循环任务 =================
    def generate_recurring(self):
        """根据循环规则，为「今天」生成尚不存在的任务实例。"""
        today = datetime.now().date()
        key = today.isoformat()
        data = self._ensure_date(key)
        wd = today.weekday()
        changed = False
        for rec in self.recurring:
            if rec.get("freq") == "weekly" and rec.get("weekday", wd) != wd:
                continue
            inst = f"{rec.get('priority', '🟡')} 🔁 {rec['text']}"
            if inst not in data["not_done"] and inst not in data["done"]:
                data["not_done"].append(inst)
                changed = True
        if changed:
            self.save_tasks()

    def add_recurring(self, text, priority, freq, weekday=None):
        rule = {"text": text, "priority": priority, "freq": freq}
        if freq == "weekly":
            rule["weekday"] = weekday if weekday is not None else datetime.now().weekday()
        for r in self.recurring:
            if r["text"] == text and r.get("freq") == freq and r.get("weekday") == rule.get("weekday"):
                self.set_status("⚠️ 该循环任务已存在")
                return
        self.recurring.append(rule)
        self.save_recurring()
        self.generate_recurring()
        self.update_task_display()
        name = "每日" if freq == "daily" else f"每周{self.WEEKDAYS[rule['weekday']]}"
        self.set_status(f"🔁 已创建{name}循环任务 '{text}'")

    def manage_recurring(self):
        win = tk.Toplevel(self.root)
        win.title("🔁 循环任务管理")
        win.configure(bg=self.BG)
        win.geometry("440x360")
        win.transient(self.root)

        tk.Label(win, text="循环任务规则", bg=self.BG, fg=self.TEXT,
                 font=(self.FONT, 12, "bold")).pack(anchor="w", padx=16, pady=(14, 8))

        wrap = tk.Frame(win, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=16)
        tree = ttk.Treeview(wrap, columns=("freq", "task"), show="headings", selectmode="browse")
        tree.heading("freq", text="频率")
        tree.heading("task", text="任务内容")
        tree.column("freq", width=110, anchor="center", stretch=False)
        tree.column("task", width=290, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview, style="Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        def refresh():
            tree.delete(*tree.get_children())
            for i, r in enumerate(self.recurring):
                if r.get("freq") == "weekly":
                    freq = f"每周{self.WEEKDAYS[r.get('weekday', 0)]}"
                else:
                    freq = "每日"
                tree.insert("", "end", iid=str(i), values=(freq, f"{r.get('priority', '🟡')} {r['text']}"))

        def delete_sel():
            sel = tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            if 0 <= idx < len(self.recurring):
                if messagebox.askyesno("确认删除", "删除该循环规则？（已生成的今日任务不受影响）", parent=win):
                    self.recurring.pop(idx)
                    self.save_recurring()
                    refresh()
                    self.set_status("🗑️ 已删除循环规则")

        refresh()
        btn_row = tk.Frame(win, bg=self.BG)
        btn_row.pack(fill="x", padx=16, pady=12)
        ttk.Button(btn_row, text="🗑️ 删除选中", style="Danger.TButton", command=delete_sel).pack(side="left")
        ttk.Button(btn_row, text="关闭", style="Ghost.TButton", command=win.destroy).pack(side="right")

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
        freq = self.freq_combo.get()

        if freq == "每日":
            self.add_recurring(text, priority, "daily")
            self.todo_entry.delete(0, tk.END)
            self.freq_combo.set("一次性")
            return
        if freq == "每周":
            self.add_recurring(text, priority, "weekly", datetime.now().weekday())
            self.todo_entry.delete(0, tk.END)
            self.freq_combo.set("一次性")
            return

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
        is_recurring = "🔁" in head
        raw_text = head.split(" ", 1)[1] if " " in head else head
        raw_text = raw_text.replace("🔁", "").strip()

        new_text = simpledialog.askstring("编辑任务", "修改任务内容:", initialvalue=raw_text, parent=self.root)
        if new_text and new_text.strip():
            cat = "done" if self.completed_tasks_shown else "not_done"
            data = self._ensure_date(self.current_date.isoformat())
            if task in data[cat]:
                idx = data[cat].index(task)
                emoji = task[0]
                if is_recurring:
                    data[cat][idx] = f"{emoji} 🔁 {new_text.strip()}"
                else:
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
        self.daily_view_btn.config(text="👁 查看未完成" if self.completed_tasks_shown else "👁 查看已完成")
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
        if any(p["text"] == text for p in self.improvement_tasks):
            self.set_status("⚠️ 该计划已存在")
            return
        self.improvement_tasks.append({"text": text, "priority": priority, "progress": 0})
        self.improvement_entry.delete(0, tk.END)
        self.update_improvement_display()
        self.save_improvement_tasks()
        self.set_status(f"✅ 长期计划 '{text}' 已添加")

    def edit_improvement_task(self, index):
        if not (0 <= index < len(self.improvement_tasks)):
            return
        plan = self.improvement_tasks[index]
        new_text = simpledialog.askstring("编辑计划", "修改计划内容:", initialvalue=plan["text"], parent=self.root)
        if new_text and new_text.strip():
            plan["text"] = new_text.strip()
            self.update_improvement_display()
            self.save_improvement_tasks()
            self.set_status("✏️ 计划已更新")

    def delete_improvement_task(self, index):
        if not (0 <= index < len(self.improvement_tasks)):
            return
        if messagebox.askyesno("确认删除", "确定要删除该长期计划吗？"):
            self.improvement_tasks.pop(index)
            self.update_improvement_display()
            self.save_improvement_tasks()
            self.set_status("🗑️ 计划已删除")

    def toggle_plan_done(self, index):
        if not (0 <= index < len(self.improvement_tasks)):
            return
        plan = self.improvement_tasks[index]
        if plan.get("progress", 0) >= 100:
            plan["progress"] = 0
            self.set_status("🔄 计划已恢复为未完成")
        else:
            plan["progress"] = 100
            self.set_status("🎉 长期计划已完成")
        self.update_improvement_display()
        self.save_improvement_tasks()

    def _pct_color(self, progress):
        if progress >= 100:
            return self.SUCCESS_DK
        if progress > 0:
            return self.ACCENT
        return self.MUTED

    def _on_plan_scale(self, index, value, bar, pct_label):
        v = int(round(float(value)))
        if 0 <= index < len(self.improvement_tasks):
            self.improvement_tasks[index]["progress"] = v
        bar["value"] = v
        bar.configure(style="PlanDone.Horizontal.TProgressbar" if v >= 100 else "Plan.Horizontal.TProgressbar")
        pct_label.config(text=f"{v}%", fg=self._pct_color(v))
        self._update_avg_progress()

    def _on_plan_scale_release(self, event=None):
        # 延迟刷新，避免在滑块自身的事件回调中销毁该控件导致报错
        self.save_improvement_tasks()
        self.root.after_idle(self.update_improvement_display)

    def _update_avg_progress(self):
        plans = self.improvement_tasks
        avg = sum(p["progress"] for p in plans) / len(plans) if plans else 0
        done = sum(1 for p in plans if p["progress"] >= 100)
        self.improvement_progress["value"] = avg
        self.improvement_prog_label.config(text=f"{avg:.0f}%   ({done}/{len(plans)} 已完成)")

    def toggle_plan_filter(self):
        self.show_incomplete_only = not self.show_incomplete_only
        self.plan_filter_btn.config(
            text="👁 查看全部" if self.show_incomplete_only else "👁 只看未完成")
        self.update_improvement_display()

    def update_improvement_display(self):
        for child in self.plans_inner.winfo_children():
            child.destroy()

        if not self.improvement_tasks:
            self._label(self.plans_inner, "还没有长期计划，立个目标吧 🚀",
                        fg="#94A3B8", size=11).pack(pady=30)
            self._update_avg_progress()
            return

        shown = 0
        for i, plan in enumerate(self.improvement_tasks):
            if self.show_incomplete_only and plan.get("progress", 0) >= 100:
                continue
            self._build_plan_card(i, plan)
            shown += 1

        if shown == 0:
            self._label(self.plans_inner, "所有计划都已完成，太棒了 🎉",
                        fg="#94A3B8", size=11).pack(pady=30)
        self._update_avg_progress()

    def _build_plan_card(self, index, plan):
        progress = int(plan.get("progress", 0))
        emoji = plan.get("priority", "🟡")
        done = progress >= 100

        card = tk.Frame(self.plans_inner, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        card.pack(fill="x", pady=5, padx=2)

        top = tk.Frame(card, bg=self.CARD)
        top.pack(fill="x", padx=14, pady=(10, 4))
        dot = tk.Label(top, text="●", bg=self.CARD, fg=self.PRIORITY_COLOR.get(emoji, self.MUTED),
                       font=(self.FONT, 11))
        dot.pack(side="left", padx=(0, 6))
        title_txt = ("✅ " if done else "") + plan.get("text", "")
        title = tk.Label(top, text=title_txt, bg=self.CARD,
                         fg=(self.MUTED if done else self.TEXT),
                         font=(self.FONT, 11, "bold"), anchor="w")
        title.pack(side="left", fill="x", expand=True)

        ttk.Button(top, text="🗑", style="Mini.TButton", width=3,
                   command=lambda i=index: self.delete_improvement_task(i)).pack(side="right", padx=(6, 0))
        ttk.Button(top, text="✏", style="Mini.TButton", width=3,
                   command=lambda i=index: self.edit_improvement_task(i)).pack(side="right")
        done_style = "Success.TButton" if not done else "Ghost.TButton"
        ttk.Button(top, text="↩ 恢复" if done else "✓ 完成", style=done_style,
                   command=lambda i=index: self.toggle_plan_done(i)).pack(side="right", padx=(8, 8))
        pct_label = tk.Label(top, text=f"{progress}%", bg=self.CARD, fg=self._pct_color(progress),
                             font=(self.FONT, 11, "bold"))
        pct_label.pack(side="right", padx=(0, 10))

        mid = tk.Frame(card, bg=self.CARD)
        mid.pack(fill="x", padx=14, pady=(0, 12))
        bar = ttk.Progressbar(mid, mode="determinate", maximum=100,
                              style="PlanDone.Horizontal.TProgressbar" if done else "Plan.Horizontal.TProgressbar")
        bar["value"] = progress
        bar.pack(fill="x", pady=(0, 6))

        scale = ttk.Scale(mid, from_=0, to=100, orient="horizontal", value=progress,
                          command=lambda v, i=index, b=bar, p=pct_label: self._on_plan_scale(i, v, b, p))
        scale.pack(fill="x")
        scale.bind("<ButtonRelease-1>", self._on_plan_scale_release)

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
            self.start_pomodoro()
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

    def show_daily_context_menu(self, event):
        row = self.task_tree.identify_row(event.y)
        if row and row in self.daily_items:
            self.task_tree.selection_set(row)
            self.daily_menu.tk_popup(event.x_root, event.y_root)

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
        if not hasattr(self, "status_label"):
            return
        self.status_label.config(text=text)
        if self._status_after_id:
            self.root.after_cancel(self._status_after_id)
        self._status_after_id = self.root.after(
            3000, lambda: self.status_label.config(text=f"当前日期: {self.current_date.strftime('%Y-%m-%d')}"))

    def current_date_cn(self):
        d = self.current_date
        return f"{d.year}年{d.month:02d}月{d.day:02d}日"

    def _tick_clock(self):
        self.clock_label.config(text="🕐 " + datetime.now().strftime("%Y-%m-%d\n%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def on_close(self):
        self.save_tasks()
        self.save_improvement_tasks()
        self.save_recurring()
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
