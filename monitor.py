#!/usr/bin/env python3
import subprocess
import json
import time
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, DataTable, Label, TextArea
from textual.reactive import reactive
from textual import work
from textual.binding import Binding
from rich.text import Text


class PulseDot(Static):
    PULSE_STATES = ["●", "●", "●", "○", "○"]
    current = reactive(0)

    def on_mount(self) -> None:
        self.set_interval(0.4, self.tick)

    def tick(self) -> None:
        self.current = (self.current + 1) % len(self.PULSE_STATES)

    def render(self) -> str:
        return self.PULSE_STATES[self.current]


class OpenCodeMonitor(App):
    BINDINGS = [
        Binding("d", "show_details", "Details", show=True),
        Binding("c", "show_chat", "Chat", show=True),
        Binding("l", "show_logs", "Logs", show=True),
        Binding("o", "open_session", "Open", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "go_back", "Back", show=True, priority=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    CSS = """
    Screen {
        background: #000000;
    }

    Header {
        background: #000000;
        color: #8b5cf6;
        dock: top;
    }

    Footer {
        background: #000000;
    }

    #main-container {
        layout: vertical;
        margin: 1;
        height: 1fr;
    }

    #status-bar {
        height: 3;
        dock: top;
        background: #111111;
        border: tall #333333;
        margin-bottom: 1;
    }

    #sessions-panel {
        layout: vertical;
        height: 1fr;
    }

    .section-title {
        color: #8b5cf6;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 0;
    }

    DataTable {
        background: #000000;
        border: tall #333333;
        width: 100%;
        height: 1fr;
    }

    DataTable > .datatable--header {
        background: #1a1a1a;
        color: #a78bfa;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #2d1b69;
    }

    #clock {
        dock: right;
        color: #6b7280;
        text-align: right;
        width: auto;
        padding: 0 1;
    }

    #session-count {
        dock: left;
        color: #22c55e;
        width: auto;
        padding: 0 1;
    }

    #empty-state {
        color: #6b7280;
        text-align: center;
        content-align: center middle;
        width: 100%;
        height: 1fr;
    }

    #detail-panel {
        display: none;
        layout: vertical;
        height: 1fr;
    }

    #detail-panel.visible {
        display: block;
    }

    #detail-content {
        background: #111111;
        border: tall #333333;
        height: 1fr;
        padding: 1 2;
    }

    #detail-title {
        color: #a78bfa;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 0;
    }

    TextArea {
        background: #111111;
        border: tall #333333;
        height: 1fr;
    }

    TextArea:focus {
        border: tall #8b5cf6;
    }

    .detail-line {
        color: #e5e7eb;
        padding: 0 2;
    }

    .detail-label {
        color: #8b5cf6;
    }

    .detail-value {
        color: #e5e7eb;
    }

    .chat-user {
        color: #22c55e;
    }

    .chat-assistant {
        color: #8b5cf6;
    }

    .chat-system {
        color: #6b7280;
    }

    #credit-bar {
        height: 1;
        background: #000000;
        color: #4b5563;
        text-align: center;
    }
    """

    sessions = reactive([])
    selected_session = reactive(None)
    view_mode = reactive("list")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="main-container"):
            with Horizontal(id="status-bar"):
                yield PulseDot(id="pulse")
                yield Label(id="session-count")
                yield Label("OpenCode Monitor")
                yield Label(id="clock")
            with Vertical(id="sessions-panel"):
                yield Label("▸ Active Sessions (5 min)", classes="section-title")
                yield DataTable(id="sessions-table")
                yield Label(id="empty-state")
            with Vertical(id="detail-panel"):
                yield Label(id="detail-title")
                yield ScrollableContainer(id="detail-content")
            yield Label("Created by Axel Mrak — github.com/axelmrak", id="credit-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.setup_table()
        self.refresh_data()
        self.set_interval(5, self.refresh_data)

    def setup_table(self) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.add_columns("Status", "Session ID", "Title", "Last Active", "Project")
        table.cursor_type = "row"

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        try:
            result = subprocess.run(
                ["opencode", "session", "list", "--format", "json", "-n", "50"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.sessions = json.loads(result.stdout)
        except Exception:
            pass

        self.update_display()

    def update_display(self) -> None:
        table = self.query_one("#sessions-table", DataTable)
        empty = self.query_one("#empty-state", Label)
        table.clear()

        now = time.time() * 1000
        active_sessions = [s for s in self.sessions if (now - s.get("updated", 0)) < 300000]

        if not active_sessions:
            empty.update("No active sessions in the last 5 minutes")
            empty.display = True
            table.display = False
        else:
            empty.display = False
            table.display = True

            for session in active_sessions:
                sid = session.get("id", "")[:14]
                title = session.get("title", "")[:55]
                updated_ts = session.get("updated", 0)
                if updated_ts:
                    dt = datetime.fromtimestamp(updated_ts / 1000)
                    updated = dt.strftime("%H:%M")
                else:
                    updated = "N/A"
                project = session.get("directory", "").split("/")[-1] or "global"

                age = now - updated_ts
                if age < 60000:
                    status = Text("● ", style="#22c55e bold")
                elif age < 180000:
                    status = Text("● ", style="#3b82f6 bold")
                else:
                    status = Text("● ", style="#eab308 bold")

                table.add_row(status, sid, title, updated, project)

        pulse = self.query_one("#pulse", PulseDot)
        pulse.styles.color = "#22c55e" if active_sessions else "#6b7280"

        count_label = self.query_one("#session-count", Label)
        count_label.update(f"Active: {len(active_sessions)}")

        clock = self.query_one("#clock", Label)
        clock.update(datetime.now().strftime("%H:%M:%S"))

    def get_selected_session(self):
        table = self.query_one("#sessions-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.sessions):
            now = time.time() * 1000
            active = [s for s in self.sessions if (now - s.get("updated", 0)) < 300000]
            if table.cursor_row < len(active):
                return active[table.cursor_row]
        return None

    def action_show_details(self) -> None:
        session = self.get_selected_session()
        if not session:
            return

        self.view_mode = "details"
        self.selected_session = session

        panel = self.query_one("#detail-panel")
        panel.add_class("visible")
        self.query_one("#sessions-panel").display = False

        title = self.query_one("#detail-title", Label)
        title.update(f"▸ Session Details — {session.get('title', 'Unknown')[:50]}")

        content = self.query_one("#detail-content", ScrollableContainer)
        content.remove_children()

        sid = session.get("id", "")
        created_ts = session.get("created", 0)
        updated_ts = session.get("updated", 0)
        directory = session.get("directory", "")
        project_id = session.get("projectId", "")

        if created_ts:
            created = datetime.fromtimestamp(created_ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
        else:
            created = "N/A"

        if updated_ts:
            updated = datetime.fromtimestamp(updated_ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
        else:
            updated = "N/A"

        duration_ms = updated_ts - created_ts if updated_ts and created_ts else 0
        duration_min = duration_ms / 60000

        fields = [
            ("ID", sid),
            ("Title", session.get("title", "")),
            ("Project", directory),
            ("Project ID", project_id),
            ("Created", created),
            ("Last Active", updated),
            ("Duration", f"{duration_min:.1f} min"),
        ]

        for label, value in fields:
            line = Label()
            line.update(f"[detail-label]{label}:[/detail-label] [detail-value]{value}[/detail-value]")
            line.add_class("detail-line")
            content.mount(line)

    def action_show_chat(self) -> None:
        session = self.get_selected_session()
        if not session:
            return

        self.view_mode = "chat"
        self.selected_session = session

        panel = self.query_one("#detail-panel")
        panel.add_class("visible")
        self.query_one("#sessions-panel").display = False

        title = self.query_one("#detail-title", Label)
        title.update(f"▸ Chat Preview — {session.get('title', 'Unknown')[:50]}")

        content = self.query_one("#detail-content", ScrollableContainer)
        content.remove_children()

        try:
            result = subprocess.run(
                ["opencode", "export", session.get("id", "")],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                messages = data.get("messages", [])
                for msg in messages[-30:]:
                    role = msg.get("role", "unknown")
                    content_text = ""
                    if isinstance(msg.get("content"), str):
                        content_text = msg["content"]
                    elif isinstance(msg.get("content"), list):
                        parts = []
                        for p in msg["content"]:
                            if isinstance(p, dict) and p.get("type") == "text":
                                parts.append(p.get("text", ""))
                        content_text = "\n".join(parts)

                    if len(content_text) > 200:
                        content_text = content_text[:200] + "..."

                    role_color = "chat-user" if role == "user" else ("chat-assistant" if role == "assistant" else "chat-system")
                    role_label = Label()
                    role_label.update(f"[{role_color}]{role.upper()}[/{role_color}]")
                    role_label.add_class("detail-line")
                    content.mount(role_label)

                    msg_label = Label()
                    msg_label.update(content_text)
                    msg_label.add_class("detail-line")
                    content.mount(msg_label)

                    sep = Label("─" * 60)
                    sep.styles.color = "#333333"
                    sep.styles.padding = "0 2"
                    content.mount(sep)
            else:
                msg = Label(f"Failed to load chat: {result.stderr[:100]}")
                msg.styles.color = "#ef4444"
                msg.add_class("detail-line")
                content.mount(msg)
        except Exception as e:
            msg = Label(f"Error: {str(e)}")
            msg.styles.color = "#ef4444"
            msg.add_class("detail-line")
            content.mount(msg)

    def action_show_logs(self) -> None:
        session = self.get_selected_session()
        if not session:
            return

        self.view_mode = "logs"
        self.selected_session = session

        panel = self.query_one("#detail-panel")
        panel.add_class("visible")
        self.query_one("#sessions-panel").display = False

        title = self.query_one("#detail-title", Label)
        title.update(f"▸ Session Logs — {session.get('title', 'Unknown')[:50]}")

        content = self.query_one("#detail-content", ScrollableContainer)
        content.remove_children()

        try:
            result = subprocess.run(
                ["opencode", "session", "list", "--format", "json", "--print-logs", "-n", "1"],
                capture_output=True, text=True, timeout=10
            )
            log_text = result.stderr if result.stderr else "No logs available for this session."
            if len(log_text) > 5000:
                log_text = log_text[-5000:]

            textarea = TextArea(log_text, language="log", read_only=True)
            textarea.show_line_numbers = False
            content.mount(textarea)
        except Exception as e:
            msg = Label(f"Error loading logs: {str(e)}")
            msg.styles.color = "#ef4444"
            msg.add_class("detail-line")
            content.mount(msg)

    def action_open_session(self) -> None:
        session = self.get_selected_session()
        if not session:
            return

        self.exit()
        sid = session.get("id", "")
        subprocess.Popen(["opencode", sid])

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_go_back(self) -> None:
        if self.view_mode != "list":
            self.view_mode = "list"
            self.selected_session = None
            panel = self.query_one("#detail-panel")
            panel.remove_class("visible")
            self.query_one("#sessions-panel").display = True
            content = self.query_one("#detail-content", ScrollableContainer)
            content.remove_children()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_show_details()


def main():
    app = OpenCodeMonitor()
    app.run()


if __name__ == "__main__":
    main()
