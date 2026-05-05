use anyhow::Result;
use chrono::{DateTime, Local};
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span, Text},
    widgets::{Block, Borders, Cell, Paragraph, Row, Table, TableState, Wrap},
    Frame, Terminal,
};
use serde::Deserialize;
use std::{
    collections::HashMap,
    io,
    process::Command,
    sync::atomic::{AtomicBool, Ordering},
    time::{Duration, Instant},
};

#[derive(Debug, Deserialize, Clone)]
#[allow(non_snake_case)]
struct SessionInfo {
    id: String,
    title: String,
    updated: Option<u64>,
    created: Option<u64>,
    #[allow(dead_code)]
    projectId: Option<String>,
    directory: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
enum ViewMode {
    List,
    Details,
    Chat,
    Logs,
}

const SPINNER_FRAMES: &[char] = &['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

struct Spinner {
    frame: usize,
    last_tick: Instant,
    interval: Duration,
}

impl Spinner {
    fn new() -> Self {
        Self {
            frame: 0,
            last_tick: Instant::now(),
            interval: Duration::from_millis(80),
        }
    }

    fn tick(&mut self) {
        if self.last_tick.elapsed() >= self.interval {
            self.frame = (self.frame + 1) % SPINNER_FRAMES.len();
            self.last_tick = Instant::now();
        }
    }

    fn symbol(&self) -> char {
        SPINNER_FRAMES[self.frame]
    }
}

const PULSE_STATES: &[&str] = &["●", "●", "●", "○", "○"];

struct PulseDot {
    state: usize,
    last_tick: Instant,
    interval: Duration,
}

impl PulseDot {
    fn new() -> Self {
        Self {
            state: 0,
            last_tick: Instant::now(),
            interval: Duration::from_millis(400),
        }
    }

    fn tick(&mut self) {
        if self.last_tick.elapsed() >= self.interval {
            self.state = (self.state + 1) % PULSE_STATES.len();
            self.last_tick = Instant::now();
        }
    }

    fn symbol(&self) -> &str {
        PULSE_STATES[self.state]
    }
}

struct RowData {
    status: String,
    status_color: Color,
    sid: String,
    title: String,
    time_str: String,
    activity: String,
    project: String,
}

struct App {
    sessions: Vec<SessionInfo>,
    view: ViewMode,
    table_state: TableState,
    spinner: Spinner,
    pulse: PulseDot,
    last_refresh: Instant,
    refresh_interval: Duration,
    chat_cache: HashMap<String, Vec<String>>,
    logs_cache: HashMap<String, String>,
    activity_cache: HashMap<String, String>,
    running: AtomicBool,
}

impl App {
    fn new() -> Self {
        let mut table_state = TableState::default();
        table_state.select(Some(0));

        Self {
            sessions: Vec::new(),
            view: ViewMode::List,
            table_state,
            spinner: Spinner::new(),
            pulse: PulseDot::new(),
            last_refresh: Instant::now(),
            refresh_interval: Duration::from_secs(5),
            chat_cache: HashMap::new(),
            logs_cache: HashMap::new(),
            activity_cache: HashMap::new(),
            running: AtomicBool::new(true),
        }
    }

    fn refresh_sessions(&mut self) {
        let output = Command::new("opencode")
            .args(["session", "list", "--format", "json", "-n", "50"])
            .output();

        if let Ok(output) = output {
            if let Ok(sessions) = serde_json::from_slice::<Vec<SessionInfo>>(&output.stdout) {
                self.sessions = sessions;
            }
        }
    }

    fn active_sessions(&self) -> Vec<&SessionInfo> {
        let now = chrono::Utc::now().timestamp_millis() as u64;
        let day_ms = 86_400_000;
        self.sessions
            .iter()
            .filter(|s| {
                let updated = s.updated.unwrap_or(0);
                now.saturating_sub(updated) < day_ms
            })
            .collect()
    }

    fn selected_session(&self) -> Option<&SessionInfo> {
        let active = self.active_sessions();
        if let Some(idx) = self.table_state.selected() {
            active.get(idx).copied()
        } else {
            None
        }
    }

    fn detect_activity(&mut self, session: &SessionInfo) -> String {
        if let Some(cached) = self.activity_cache.get(&session.id) {
            return cached.clone();
        }

        if let Some(dir) = &session.directory {
            let output = Command::new("find")
                .args([dir.as_str(), "-type", "f", "-mmin", "-1"])
                .output();

            if let Ok(output) = output {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let files: Vec<String> = stdout
                    .lines()
                    .filter(|l| !l.is_empty())
                    .take(5)
                    .map(String::from)
                    .collect();

                if !files.is_empty() {
                    let name = files[0].split('/').last().unwrap_or(&files[0]);
                    let truncated = if name.len() > 30 {
                        format!("...{}", &name[name.len() - 27..])
                    } else {
                        name.to_string()
                    };
                    let activity = format!("Editing {}", truncated);
                    self.activity_cache
                        .insert(session.id.clone(), activity.clone());
                    return activity;
                }
            }
        }

        "Idle".to_string()
    }

    fn load_chat(&mut self, session_id: &str, dir: &str) {
        if self.chat_cache.contains_key(session_id) {
            return;
        }

        let output = Command::new("opencode")
            .args(["export", session_id])
            .current_dir(dir)
            .output();

        if let Ok(output) = output {
            let raw = String::from_utf8_lossy(&output.stdout);
            let brace_idx = raw.find('{').unwrap_or(0);
            let json_str = &raw[brace_idx..];

            if let Ok(data) = serde_json::from_str::<serde_json::Value>(json_str) {
                if let Some(messages) = data.get("messages").and_then(|m| m.as_array()) {
                    let chat_lines: Vec<String> = messages
                        .iter()
                        .rev()
                        .take(50)
                        .rev()
                        .filter_map(|msg| {
                            let role = msg
                                .get("info")
                                .and_then(|i| i.get("role"))
                                .and_then(|r| r.as_str())
                                .unwrap_or("unknown");

                            let parts = msg.get("parts").and_then(|p| p.as_array())?;
                            let text_parts: Vec<String> = parts
                                .iter()
                                .filter_map(|p| {
                                    let ptype = p.get("type").and_then(|t| t.as_str())?;
                                    match ptype {
                                        "text" => p.get("text").and_then(|t| t.as_str()).map(String::from),
                                        "tool-call" => {
                                            let tool = p
                                                .get("toolName")
                                                .or_else(|| p.get("tool"))
                                                .and_then(|t| t.as_str())
                                                .unwrap_or("?");
                                            Some(format!("[tool:{}]", tool))
                                        }
                                        "tool-result" => Some("[tool:result]".to_string()),
                                        _ => None,
                                    }
                                })
                                .collect();

                            let texts = text_parts.join("\n");
                            if texts.is_empty() {
                                Some(format!("[{}: no text content]", role))
                            } else {
                                let truncated = if texts.len() > 300 {
                                    format!("{}...", &texts[..300])
                                } else {
                                    texts
                                };
                                Some(format!("[{}] {}", role.to_uppercase(), truncated))
                            }
                        })
                        .collect();

                    self.chat_cache.insert(session_id.to_string(), chat_lines);
                }
            }
        }
    }

    fn load_logs(&mut self, session_id: &str) {
        if self.logs_cache.contains_key(session_id) {
            return;
        }

        let output = Command::new("opencode")
            .args(["session", "list", "--format", "json", "--print-logs", "-n", "1"])
            .output();

        if let Ok(output) = output {
            let logs = if output.stderr.is_empty() {
                "No logs available for this session.".to_string()
            } else {
                let text = String::from_utf8_lossy(&output.stderr).to_string();
                if text.len() > 10000 {
                    text[text.len() - 10000..].to_string()
                } else {
                    text
                }
            };
            self.logs_cache.insert(session_id.to_string(), logs);
        }
    }

    fn go_back(&mut self) {
        if self.view != ViewMode::List {
            self.view = ViewMode::List;
            self.chat_cache.clear();
            self.logs_cache.clear();
            self.activity_cache.clear();
        }
    }

    fn quit(&mut self) {
        self.running.store(false, Ordering::Relaxed);
    }

    fn open_session(&self) {
        if let Some(session) = self.selected_session() {
            let _ = Command::new("opencode").arg(&session.id).spawn();
        }
    }

    fn build_rows(&mut self) -> Vec<RowData> {
        let now = chrono::Utc::now().timestamp_millis() as u64;
        let active: Vec<SessionInfo> = self.active_sessions().into_iter().cloned().collect();

        active
            .into_iter()
            .map(|session| {
                let sid = format!("{:.14}", session.id);
                let title = if session.title.len() > 55 {
                    format!("{:.52}...", session.title)
                } else {
                    session.title.clone()
                };

                let updated = session.updated.unwrap_or(0);
                let time_str = if updated > 0 {
                    DateTime::from_timestamp((updated / 1000) as i64, 0)
                        .map(|dt| dt.with_timezone(&Local).format("%H:%M").to_string())
                        .unwrap_or_else(|| "N/A".to_string())
                } else {
                    "N/A".to_string()
                };

                let project = session
                    .directory
                    .as_deref()
                    .and_then(|d| d.split('/').last())
                    .unwrap_or("global")
                    .to_string();

                let age = now.saturating_sub(updated);
                let (status_symbol, status_color) = if age < 60_000 {
                    ("●", Color::Green)
                } else if age < 180_000 {
                    ("●", Color::Blue)
                } else {
                    ("●", Color::Yellow)
                };

                let status_display = if age < 60_000 {
                    self.spinner.tick();
                    format!("{} {}", self.spinner.symbol(), status_symbol)
                } else {
                    status_symbol.to_string()
                };

                let activity = self.detect_activity(&session);

                RowData {
                    status: status_display,
                    status_color,
                    sid,
                    title,
                    time_str,
                    activity,
                    project,
                }
            })
            .collect()
    }
}

fn ui(f: &mut Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .margin(1)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(1),
            Constraint::Length(1),
        ])
        .split(f.area());

    let status_bar = Block::default()
        .borders(Borders::ALL)
        .style(Style::default().bg(Color::Rgb(17, 17, 17)));

    app.pulse.tick();
    let pulse_symbol = app.pulse.symbol();
    let pulse_color = if !app.active_sessions().is_empty() {
        Color::Green
    } else {
        Color::Gray
    };

    let status_text = Line::from(vec![
        Span::styled(
            format!(" {} ", pulse_symbol),
            Style::default()
                .fg(pulse_color)
                .add_modifier(Modifier::BOLD),
        ),
        Span::styled(
            format!("Active: {} ", app.active_sessions().len()),
            Style::default()
                .fg(Color::Green)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("OpenCode Monitor"),
        Span::styled(
            format!(" {}", Local::now().format("%H:%M:%S")),
            Style::default().fg(Color::Gray),
        ),
    ]);

    let status_para = Paragraph::new(status_text).block(status_bar);
    f.render_widget(status_para, chunks[0]);

    match app.view {
        ViewMode::List => render_list(f, app, chunks[1]),
        ViewMode::Details => render_detail(f, app, chunks[1], "OVERVIEW"),
        ViewMode::Chat => render_detail(f, app, chunks[1], "CHAT HISTORY"),
        ViewMode::Logs => render_detail(f, app, chunks[1], "LOGS"),
    }

    let credit = Paragraph::new("Created by Axel Mrak — github.com/axelmrak")
        .style(Style::default().fg(Color::Rgb(75, 85, 99)))
        .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(credit, chunks[2]);
}

fn render_list(f: &mut Frame, app: &mut App, area: ratatui::prelude::Rect) {
    let rows_data = app.build_rows();

    if rows_data.is_empty() {
        let text = Paragraph::new("No active sessions in the last 24 hours")
            .style(Style::default().fg(Color::Gray))
            .alignment(ratatui::layout::Alignment::Center);
        f.render_widget(text, area);
        return;
    }

    let header = Row::new(vec![
        "Status",
        "Session ID",
        "Title",
        "Last Active",
        "Activity",
        "Project",
    ])
    .style(
        Style::default()
            .bg(Color::Rgb(26, 26, 26))
            .fg(Color::Rgb(167, 139, 250))
            .add_modifier(Modifier::BOLD),
    );

    let rows: Vec<Row> = rows_data
        .iter()
        .map(|r| {
            Row::new(vec![
                Cell::from(Span::styled(
                    r.status.clone(),
                    Style::default()
                        .fg(r.status_color)
                        .add_modifier(Modifier::BOLD),
                )),
                Cell::from(r.sid.clone()),
                Cell::from(r.title.clone()),
                Cell::from(r.time_str.clone()),
                Cell::from(Span::styled(
                    r.activity.clone(),
                    if r.activity == "Idle" {
                        Style::default().fg(Color::DarkGray)
                    } else {
                        Style::default().fg(Color::Cyan)
                    },
                )),
                Cell::from(r.project.clone()),
            ])
        })
        .collect();

    let widths = [
        Constraint::Length(10),
        Constraint::Length(16),
        Constraint::Min(30),
        Constraint::Length(10),
        Constraint::Min(25),
        Constraint::Length(15),
    ];

    let table = Table::new(rows, widths)
        .header(header)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("▸ Active Sessions (24h)")
                .title_style(
                    Style::default()
                        .fg(Color::Rgb(139, 92, 246))
                        .add_modifier(Modifier::BOLD),
                ),
        )
        .row_highlight_style(
            Style::default()
                .bg(Color::Rgb(45, 27, 105))
                .add_modifier(Modifier::BOLD),
        )
        .highlight_symbol("▸ ");

    f.render_stateful_widget(table, area, &mut app.table_state);
}

fn render_detail(f: &mut Frame, app: &mut App, area: ratatui::prelude::Rect, title: &str) {
    let Some(session) = app.selected_session() else {
        return;
    };

    let session_clone = session.clone();
    let layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(35), Constraint::Percentage(65)])
        .split(area);

    let sidebar_block = Block::default()
        .borders(Borders::ALL)
        .title("SESSION INFO")
        .title_style(
            Style::default()
                .fg(Color::Rgb(167, 139, 250))
                .add_modifier(Modifier::BOLD),
        );

    let now = chrono::Utc::now().timestamp_millis() as u64;
    let updated_ts = session_clone.updated.unwrap_or(0);
    let created_ts = session_clone.created.unwrap_or(0);
    let age_ms = now.saturating_sub(updated_ts);
    let duration_ms = if updated_ts > 0 && created_ts > 0 {
        updated_ts - created_ts
    } else {
        0
    };

    let (status_text, status_color) = if age_ms < 60_000 {
        ("● ACTIVE", Color::Green)
    } else if age_ms < 180_000 {
        ("● RECENT", Color::Blue)
    } else {
        ("● IDLE", Color::Yellow)
    };

    let duration_str = if duration_ms < 60_000 {
        format!("{:.0}s", duration_ms / 1000)
    } else if duration_ms < 3_600_000 {
        format!("{:.1}m", duration_ms as f64 / 60_000.0)
    } else {
        format!("{:.1}h", duration_ms as f64 / 3_600_000.0)
    };

    let age_str = if age_ms < 60_000 {
        format!("{:.0}s ago", age_ms / 1000)
    } else if age_ms < 3_600_000 {
        format!("{:.1}m ago", age_ms as f64 / 60_000.0)
    } else {
        format!("{:.1}h ago", age_ms as f64 / 3_600_000.0)
    };

    let created_time = if created_ts > 0 {
        DateTime::from_timestamp((created_ts / 1000) as i64, 0)
            .map(|dt| dt.with_timezone(&Local).format("%H:%M:%S").to_string())
            .unwrap_or_else(|| "N/A".to_string())
    } else {
        "N/A".to_string()
    };

    let updated_time = if updated_ts > 0 {
        DateTime::from_timestamp((updated_ts / 1000) as i64, 0)
            .map(|dt| dt.with_timezone(&Local).format("%H:%M:%S").to_string())
            .unwrap_or_else(|| "N/A".to_string())
    } else {
        "N/A".to_string()
    };

    let info_lines = vec![
        Line::from(Span::styled(
            status_text,
            Style::default()
                .fg(status_color)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(""),
        Line::from(vec![
            Span::styled("ID: ", Style::default().fg(Color::Rgb(139, 92, 246))),
            Span::raw(&session_clone.id),
        ]),
        Line::from(vec![
            Span::styled("Project: ", Style::default().fg(Color::Rgb(139, 92, 246))),
            Span::raw(session_clone.directory.as_deref().unwrap_or("global")),
        ]),
        Line::from(vec![
            Span::styled("Created: ", Style::default().fg(Color::Rgb(139, 92, 246))),
            Span::raw(created_time),
        ]),
        Line::from(vec![
            Span::styled("Last Active: ", Style::default().fg(Color::Rgb(139, 92, 246))),
            Span::raw(updated_time),
        ]),
        Line::from(vec![
            Span::styled("Duration: ", Style::default().fg(Color::Rgb(139, 92, 246))),
            Span::raw(duration_str),
        ]),
        Line::from(vec![
            Span::styled("Session age: ", Style::default().fg(Color::Rgb(139, 92, 246))),
            Span::raw(&age_str),
        ]),
    ];

    let sidebar = Paragraph::new(info_lines)
        .block(sidebar_block)
        .wrap(Wrap { trim: false });
    f.render_widget(sidebar, layout[0]);

    let content_block = Block::default()
        .borders(Borders::ALL)
        .title(title)
        .title_style(
            Style::default()
                .fg(Color::Rgb(167, 139, 250))
                .add_modifier(Modifier::BOLD),
        );

    let dir = session_clone
        .directory
        .clone()
        .unwrap_or_else(|| std::env::var("HOME").unwrap_or_default());

    match app.view {
        ViewMode::Details => {
            app.load_chat(&session_clone.id, &dir);
            let content_text = Text::raw(format!(
                "Session — {}\n\nWorking directory: {}\n\nSession age: {}",
                session_clone.title,
                session_clone.directory.as_deref().unwrap_or("global"),
                age_str,
            ));
            let content = Paragraph::new(content_text)
                .block(content_block)
                .wrap(Wrap { trim: false });
            f.render_widget(content, layout[1]);
        }
        ViewMode::Chat => {
            app.load_chat(&session_clone.id, &dir);
            let lines = app
                .chat_cache
                .get(&session_clone.id)
                .cloned()
                .unwrap_or_default();
            let content_text = Text::raw(lines.join("\n\n"));
            let content = Paragraph::new(content_text)
                .block(content_block)
                .wrap(Wrap { trim: false });
            f.render_widget(content, layout[1]);
        }
        ViewMode::Logs => {
            app.load_logs(&session_clone.id);
            let logs = app
                .logs_cache
                .get(&session_clone.id)
                .cloned()
                .unwrap_or_else(|| "No logs available.".to_string());
            let content_text = Text::raw(logs);
            let content = Paragraph::new(content_text)
                .block(content_block)
                .wrap(Wrap { trim: false });
            f.render_widget(content, layout[1]);
        }
        _ => {}
    }
}

fn main() -> Result<()> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut app = App::new();
    app.refresh_sessions();

    let tick_rate = Duration::from_millis(50);

    while app.running.load(Ordering::Relaxed) {
        terminal.draw(|f| ui(f, &mut app))?;

        let timeout = tick_rate
            .checked_sub(app.last_refresh.elapsed())
            .unwrap_or(tick_rate);

        if event::poll(timeout)? {
            if let Event::Key(key) = event::read()? {
                if key.kind == KeyEventKind::Press {
                    match key.code {
                        KeyCode::Char('q') => {
                            if app.view != ViewMode::List {
                                app.go_back();
                            } else {
                                app.quit();
                            }
                        }
                        KeyCode::Esc => {
                            app.go_back();
                        }
                        KeyCode::Char('d') => {
                            if app.view == ViewMode::List && app.selected_session().is_some() {
                                app.view = ViewMode::Details;
                            }
                        }
                        KeyCode::Char('c') => {
                            if app.view == ViewMode::List && app.selected_session().is_some() {
                                app.view = ViewMode::Chat;
                            }
                        }
                        KeyCode::Char('l') => {
                            if app.view == ViewMode::List && app.selected_session().is_some() {
                                app.view = ViewMode::Logs;
                            }
                        }
                        KeyCode::Char('o') => {
                            if app.view == ViewMode::List {
                                app.open_session();
                            }
                        }
                        KeyCode::Char('r') => {
                            app.refresh_sessions();
                        }
                        KeyCode::Up => {
                            if let Some(selected) = app.table_state.selected() {
                                if selected > 0 {
                                    app.table_state.select(Some(selected - 1));
                                }
                            }
                        }
                        KeyCode::Down => {
                            let len = app.active_sessions().len();
                            if let Some(selected) = app.table_state.selected() {
                                if selected < len.saturating_sub(1) {
                                    app.table_state.select(Some(selected + 1));
                                }
                            }
                        }
                        KeyCode::Enter => {
                            if app.view == ViewMode::List && app.selected_session().is_some() {
                                app.view = ViewMode::Details;
                            }
                        }
                        _ => {}
                    }
                }
            }
        }

        if app.last_refresh.elapsed() >= app.refresh_interval {
            app.refresh_sessions();
            app.activity_cache.clear();
            app.last_refresh = Instant::now();
        }
    }

    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    Ok(())
}
