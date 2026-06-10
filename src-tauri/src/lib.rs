use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, State};

#[derive(Clone, serde::Serialize)]
pub struct ServerStatus {
    pub running: bool,
    pub message: String,
    pub pid: Option<u32>,
}

pub struct ServerProcess {
    pub child: Mutex<Option<Child>>,
    pub error: Mutex<Option<String>>,
}

impl Drop for ServerProcess {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

fn server_addr(port: u16) -> String {
    format!("127.0.0.1:{port}")
}

fn check_health(port: u16) -> bool {
    let addr: SocketAddr = match server_addr(port).parse() {
        Ok(value) => value,
        Err(_) => return false,
    };
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(750)) {
        Ok(value) => value,
        Err(_) => return false,
    };
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n",
        server_addr(port)
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    let _ = stream.read_to_string(&mut response);
    response.contains("200 OK")
}

fn which_uvx() -> Option<PathBuf> {
    if let Ok(path) = which::which("uvx") {
        return Some(path);
    }
    #[cfg(windows)]
    {
        if let Some(home) = std::env::var_os("USERPROFILE") {
            // uv installed via cargo: ~/.cargo/bin/uvx.exe
            let candidate = PathBuf::from(&home)
                .join(".cargo")
                .join("bin")
                .join("uvx.exe");
            if candidate.exists() {
                return Some(candidate);
            }
            // uv installed via official installer (irm https://astral.sh/uv/install.ps1): ~/.local/bin/uvx.exe
            let candidate = PathBuf::from(&home)
                .join(".local")
                .join("bin")
                .join("uvx.exe");
            if candidate.exists() {
                return Some(candidate);
            }
        }
        // Also check common uv install locations on Windows
        for base in ["LOCALAPPDATA", "APPDATA"] {
            if let Some(var) = std::env::var_os(base) {
                let candidate = PathBuf::from(var).join("uv").join("uvx.exe");
                if candidate.exists() {
                    return Some(candidate);
                }
            }
        }
    }
    None
}

fn start_server_inner(process: &ServerProcess, port: u16) -> Result<String, String> {
    // Clear previous error
    if let Ok(mut err_guard) = process.error.lock() {
        *err_guard = None;
    }

    if check_health(port) {
        return Ok("already_running".to_string());
    }

    let mut guard = process.child.lock().map_err(|error| error.to_string())?;
    if guard
        .as_mut()
        .is_some_and(|child| child.try_wait().ok().flatten().is_none())
    {
        return Ok("already_running".to_string());
    }
    if guard.is_some() {
        *guard = None;
    }

    let uvx = which_uvx().ok_or_else(|| {
        let hint = if cfg!(target_os = "windows") {
            "Install uv from PowerShell: (irm https://astral.sh/uv/install.ps1) | iex"
        } else {
            "Install uv: curl -fsSL https://astral.sh/uv/install.sh | sh"
        };
        format!("uvx was not found. {hint}")
    })?;
    // Use the user's home directory as working dir so uvx can resolve packages
    let cwd = std::env::var_os("USERPROFILE")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(PathBuf::from))
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_default());

    // Log to a file for debugging (especially useful when spawned from Tauri GUI)
    let log_dir = std::env::var_os("TEMP")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    let log_path = log_dir.join("kicad-mcp-pro-server.log");
    let log_file = std::fs::File::create(&log_path)
        .map_err(|e| format!("Failed to create server log {log_path:?}: {e}"))?;

    let child = Command::new(&uvx)
        .current_dir(&cwd)
        .args([
            "kicad-mcp-pro",
            "dashboard",
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
        ])
        .stdout(Stdio::null())
        .stderr(log_file)
        .spawn()
        .map_err(|error| format!("Failed to start kicad-mcp-pro with {uvx:?}: {error}"))?;

    *guard = Some(child);
    drop(guard);

    // Wait up to 60s for server to become healthy (500ms intervals)
    for _ in 0..120 {
        if check_health(port) {
            return Ok("started".to_string());
        }
        // Check if the child process has exited (server crashed)
        if let Ok(mut guard) = process.child.lock() {
            if let Some(ref mut child) = *guard {
                if let Some(status) = child.try_wait().ok().flatten() {
                    let _ = child.wait();
                    drop(guard);
                    return Err(format!(
                        "Python server process exited unexpectedly (code: {}) before binding to port {}.\n\
                         Run manually to debug: uvx kicad-mcp-pro dashboard --host 127.0.0.1 --port {port}",
                        status.code().map(|c| c.to_string()).unwrap_or_else(|| "signal".to_string()),
                        port,
                    ));
                }
            }
        }
        thread::sleep(Duration::from_millis(500));
    }

    let _ = stop_server_inner(process);
    Err(format!(
        "Python server at http://{}/api/health did not respond within 60 seconds.\n\
         This may mean kicad-mcp-pro is not installed. Run: uvx kicad-mcp-pro dashboard --host 127.0.0.1 --port {port}",
        server_addr(port)
    ))
}

fn stop_server_inner(process: &ServerProcess) -> Result<(), String> {
    let mut guard = process.child.lock().map_err(|error| error.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        let _ = child.wait();
    }
    Ok(())
}

#[tauri::command]
fn start_server(state: State<'_, ServerProcess>, port: u16) -> Result<String, String> {
    start_server_inner(state.inner(), port)
}

#[tauri::command]
fn stop_server(state: State<'_, ServerProcess>) -> Result<(), String> {
    stop_server_inner(state.inner())
}

#[tauri::command]
fn server_pid(state: State<'_, ServerProcess>) -> Option<u32> {
    state
        .inner()
        .child
        .lock()
        .ok()?
        .as_ref()
        .map(|child| child.id())
}

#[tauri::command]
fn server_status(state: State<'_, ServerProcess>) -> ServerStatus {
    let pid = state
        .inner()
        .child
        .lock()
        .ok()
        .and_then(|guard| guard.as_ref().map(|child| child.id()));
    let running = pid.is_some();
    let error_msg = state
        .inner()
        .error
        .lock()
        .ok()
        .and_then(|guard| guard.clone());
    ServerStatus {
        running,
        message: error_msg.unwrap_or_else(|| {
            if running {
                "Server is running.".to_string()
            } else {
                "Server is not running.".to_string()
            }
        }),
        pid,
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(ServerProcess {
            child: Mutex::new(None),
            error: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            start_server,
            stop_server,
            server_pid,
            server_status
        ])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .setup(|app| {
            let mut tray = TrayIconBuilder::new()
                .tooltip("KiCad MCP Pro - Starting...")
                .show_menu_on_left_click(false);
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            let _ = tray.build(app)?;

            let state = app.state::<ServerProcess>();
            match start_server_inner(state.inner(), 3334) {
                Ok(status) => {
                    eprintln!("[kicad-mcp-pro] Server started: {status}");
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.set_focus();
                    }
                    let _ = state.error.lock().map(|mut e| *e = None);
                }
                Err(error) => {
                    eprintln!("[kicad-mcp-pro] ERROR: {error}");
                    let _ = state.error.lock().map(|mut e| *e = Some(error.clone()));
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Failed to start KiCad MCP Pro Tauri app");
}
