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

    #detail-layout {
        layout: horizontal;
        height: 1fr;
    }

    #detail-sidebar {
        width: 35%;
        min-width: 30;
        background: #0a0a0a;
        border: tall #333333;
        margin-right: 1;
        layout: vertical;
    }

    #detail-main {
        width: 1fr;
        layout: vertical;
    }

    #detail-title {
        color: #a78bfa;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 0;
        height: 1;
    }

    .detail-section {
        margin: 0 1;
    }

    .detail-section-title {
        color: #6b7280;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 0;
        height: 1;
    }

    .detail-field {
        padding: 0 2;
        height: auto;
    }

    .detail-label {
        color: #8b5cf6;
    }

    .detail-value {
        color: #e5e7eb;
    }

    .detail-value-dim {
        color: #6b7280;
    }

    #detail-content {
        background: #111111;
        border: tall #333333;
        height: 1fr;
    }

    #detail-chat {
        background: #111111;
        border: tall #333333;
        height: 1fr;
    }

    #detail-logs {
        background: #111111;
        border: tall #333333;
        height: 1fr;
    }

    TextArea {
        background: #111111;
        border: none;
        height: 1fr;
    }

    .chat-message {
        padding: 0 2;
        margin: 0 1;
    }

    .chat-role-user {
        color: #22c55e;
        text-style: bold;
    }

    .chat-role-assistant {
        color: #8b5cf6;
        text-style: bold;
    }

    .chat-role-system {
        color: #6b7280;
        text-style: bold;
    }

    .chat-role-tool {
        color: #eab308;
        text-style: bold;
    }

    .chat-text {
        color: #e5e7eb;
    }

    .chat-separator {
        color: #1f2937;
        height: 1;
    }

    .status-badge {
        padding: 0 2;
        height: 1;
    }

    .status-active {
        color: #22c55e;
        text-style: bold;
    }

    .status-recent {
        color: #3b82f6;
        text-style: bold;
    }

    .status-idle {
        color: #eab308;
        text-style: bold;
    }

    #credit-bar {
        height: 1;
        background: #000000;
        color: #4b5563;
        text-align: center;
    }

    .panel-header {
        background: #1a1a1a;
        color: #a78bfa;
        text-style: bold;
        padding: 0 2;
        height: 1;
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
                with Horizontal(id="detail-layout"):
                    with Vertical(id="detail-sidebar"):
                        yield Label("SESSION INFO", classes="panel-header")
                        yield ScrollableContainer(id="detail-info")
                    with Vertical(id="detail-main"):
                        yield Label("CONTENT", classes="panel-header")
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
        active_sessions = [s for s in self.sessions if (now - s.get("updated", 0)) < 86400000]

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
            active = [s for s in self.sessions if (now - s.get("updated", 0)) < 86400000]
            if table.cursor_row < len(active):
                return active[table.cursor_row]
        return None

    def _hide_list(self):
        self.query_one("#sessions-panel").display = False
        self.query_one("#detail-panel").add_class("visible")

    def _show_list(self):
        self.query_one("#sessions-panel").display = True
        self.query_one("#detail-panel").remove_class("visible")
        content = self.query_one("#detail-content", ScrollableContainer)
        content.remove_children()
        info = self.query_one("#detail-info", ScrollableContainer)
        info.remove_children()

    def _format_duration(self, ms):
        if ms < 60000:
            return f"{ms/1000:.0f}s"
        elif ms < 3600000:
            return f"{ms/60000:.1f}m"
        else:
            return f"{ms/3600000:.1f}h"

    def action_show_details(self) -> None:
        session = self.get_selected_session()
        if not session:
            return

        self.view_mode = "details"
        self.selected_session = session
        self._hide_list()

        title = self.query_one("#detail-title", Label)
        title.update(f"▸ {session.get('title', 'Unknown')}")

        info = self.query_one("#detail-info", ScrollableContainer)
        info.remove_children()

        sid = session.get("id", "")
        created_ts = session.get("created", 0)
        updated_ts = session.get("updated", 0)
        directory = session.get("directory", "")
        project_id = session.get("projectId", "")
        now = time.time() * 1000
        duration_ms = updated_ts - created_ts if updated_ts and created_ts else 0
        age_ms = now - updated_ts if updated_ts else 0

        if age_ms < 60000:
            status_style = "status-active"
            status_text = "ACTIVE"
        elif age_ms < 180000:
            status_style = "status-recent"
            status_text = "RECENT"
        else:
            status_style = "status-idle"
            status_text = "IDLE"

        status_label = Label()
        status_label.update(f"[{status_style}]● {status_text}[/{status_style}]")
        status_label.add_class("status-badge")
        info.mount(status_label)

        fields = [
            ("ID", sid),
            ("Project", directory),
            ("Created", datetime.fromtimestamp(created_ts / 1000).strftime("%H:%M:%S") if created_ts else "N/A"),
            ("Last Active", datetime.fromtimestamp(updated_ts / 1000).strftime("%H:%M:%S") if updated_ts else "N/A"),
            ("Duration", self._format_duration(duration_ms)),
        ]

        for label, value in fields:
            line = Label()
            line.update(f"[detail-label]{label}:[/detail-label] [detail-value]{value}[/detail-value]")
            line.add_class("detail-field")
            info.mount(line)

        content = self.query_one("#detail-content", ScrollableContainer)
        content.remove_children()

        header = self.query_one("#detail-main").query_one(".panel-header", Label)
        header.update("OVERVIEW")

        overview = Label()
        overview.update(
            f"[detail-value]Session[/detail-value] [detail-value-dim]— {session.get('title', 'Unknown')}[/detail-value-dim]\n\n"
            f"[detail-value]Working directory:[/detail-value] [detail-value-dim]{directory}[/detail-value-dim]\n\n"
            f"[detail-value]Session age:[/detail-value] [detail-value-dim]{self._format_duration(age_ms)} ago[/detail-value-dim]"
        )
        overview.add_class("detail-field")
        content.mount(overview)

    def action_show_chat(self) -> None:
        session = self.get_selected_session()
        if not session:
            return

        self.view_mode = "chat"
        self.selected_session = session
        self._hide_list()

        title = self.query_one("#detail-title", Label)
        title.update(f"▸ {session.get('title', 'Unknown')}")

        info = self.query_one("#detail-info", ScrollableContainer)
        info.remove_children()

        header = self.query_one("#detail-main").query_one(".panel-header", Label)
        header.update("CHAT HISTORY")

        content = self.query_one("#detail-content", ScrollableContainer)
        content.remove_children()

        try:
            result = subprocess.run(
                ["opencode", "export", session.get("id", "")],
                capture_output=True, text=True, timeout=30,
                cwd=session.get("directory", os.path.expanduser("~"))
            )
            if result.returncode == 0:
                raw = result.stdout
                brace_idx = raw.find("{")
                if brace_idx > 0:
                    raw = raw[brace_idx:]
                data = json.loads(raw)
                messages = data.get("messages", [])
                total = len(messages)
                count_label = Label()
                count_label.update(f"[detail-value-dim]Showing last 50 of {total} messages[/detail-value-dim]")
                count_label.add_class("detail-field")
                content.mount(count_label)

                for msg in messages[-50:]:
                    info = msg.get("info", {})
                    role = info.get("role", "unknown")
                    parts = msg.get("parts", [])

                    text_parts = []
                    for p in parts:
                        if isinstance(p, dict):
                            ptype = p.get("type", "")
                            if ptype == "text":
                                text_parts.append(p.get("text", ""))
                            elif ptype == "tool-call":
                                tool = p.get("toolName", p.get("tool", "?"))
                                text_parts.append(f"[tool:{tool}]")
                            elif ptype == "tool-result":
                                text_parts.append("[tool:result]")

                    content_text = "\n".join(text_parts) if text_parts else f"[{role}: no text content]"

                    if len(content_text) > 300:
                        content_text = content_text[:300] + "..."

                    role_color = {
                        "user": "chat-role-user",
                        "assistant": "chat-role-assistant",
                        "system": "chat-role-system",
                        "tool": "chat-role-tool",
                    }.get(role, "chat-role-system")

                    role_label = Label()
                    role_label.update(f"[{role_color}]{role.upper()}[/{role_color}]")
                    role_label.add_class("chat-message")
                    content.mount(role_label)

                    msg_label = Label()
                    msg_label.update(content_text)
                    msg_label.add_class("chat-text")
                    msg_label.add_class("chat-message")
                    content.mount(msg_label)

                    sep = Label("─" * 80)
                    sep.add_class("chat-separator")
                    content.mount(sep)
            else:
                msg = Label(f"[detail-value]Failed to load chat[/detail-value]")
                msg.add_class("detail-field")
                content.mount(msg)
        except json.JSONDecodeError as e:
            msg = Label(f"[detail-value]JSON parse error: {str(e)[:80]}[/detail-value]")
            msg.add_class("detail-field")
            content.mount(msg)
        except Exception as e:
            msg = Label(f"[detail-value]Error: {str(e)}[/detail-value]")
            msg.add_class("detail-field")
            content.mount(msg)

    def action_show_logs(self) -> None:
        session = self.get_selected_session()
        if not session:
            return

        self.view_mode = "logs"
        self.selected_session = session
        self._hide_list()

        title = self.query_one("#detail-title", Label)
        title.update(f"▸ {session.get('title', 'Unknown')}")

        info = self.query_one("#detail-info", ScrollableContainer)
        info.remove_children()

        header = self.query_one("#detail-main").query_one(".panel-header", Label)
        header.update("LOGS")

        content = self.query_one("#detail-content", ScrollableContainer)
        content.remove_children()

        try:
            result = subprocess.run(
                ["opencode", "session", "list", "--format", "json", "--print-logs", "-n", "1"],
                capture_output=True, text=True, timeout=10
            )
            log_text = result.stderr if result.stderr else "No logs available for this session."
            if len(log_text) > 10000:
                log_text = log_text[-10000:]

            textarea = TextArea(log_text, language="log", read_only=True)
            textarea.show_line_numbers = False
            content.mount(textarea)
        except Exception as e:
            msg = Label(f"[detail-value]Error loading logs: {str(e)}[/detail-value]")
            msg.add_class("detail-field")
            content.mount(msg)

    def action_open_session(self) -> None:
        session = self.get_selected_session()
        if not session:
            return

        sid = session.get("id", "")
        subprocess.Popen(["opencode", sid])
        self.call_later(self.exit)

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_go_back(self) -> None:
        if self.view_mode != "list":
            self.view_mode = "list"
            self.selected_session = None
            self._show_list()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_show_details()


def main():
    app = OpenCodeMonitor()
    app.run()


if __name__ == "__main__":
    main()
