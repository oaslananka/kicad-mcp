use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::{Manager, State};
use tauri::tray::TrayIconBuilder;

pub struct ServerProcess(pub Mutex<Option<Child>>);

impl Drop for ServerProcess {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.0.lock() {
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
            let candidate = PathBuf::from(home).join(".cargo").join("bin").join("uvx.exe");
            if candidate.exists() {
                return Some(candidate);
            }
        }
    }
    None
}

fn start_server_inner(process: &ServerProcess, port: u16) -> Result<String, String> {
    if check_health(port) {
        return Ok("already_running".to_string());
    }

    let mut guard = process.0.lock().map_err(|error| error.to_string())?;
    if guard.as_mut().is_some_and(|child| child.try_wait().ok().flatten().is_none()) {
        return Ok("already_running".to_string());
    }
    if guard.is_some() {
        *guard = None;
    }

    let uvx = which_uvx()
        .ok_or("uvx was not found. Install uv first: https://docs.astral.sh/uv/")?;
    let child = Command::new(&uvx)
        .args([
            "kicad-mcp-pro",
            "dashboard",
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("Failed to start kicad-mcp-pro with {:?}: {error}", uvx))?;

    *guard = Some(child);
    drop(guard);

    for _ in 0..60 {
        if check_health(port) {
            return Ok("started".to_string());
        }
        thread::sleep(Duration::from_millis(500));
    }

    let _ = stop_server_inner(process);
    Err(format!(
        "Python server at http://{}/api/health did not respond within 30 seconds",
        server_addr(port)
    ))
}

fn stop_server_inner(process: &ServerProcess) -> Result<(), String> {
    let mut guard = process.0.lock().map_err(|error| error.to_string())?;
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
    state.inner().0.lock().ok()?.as_ref().map(|child| child.id())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(ServerProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![start_server, stop_server, server_pid])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .setup(|app| {
            let mut tray = TrayIconBuilder::new()
                .tooltip("KiCad MCP Pro - Running")
                .show_menu_on_left_click(false);
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            let _ = tray.build(app)?;

            let state = app.state::<ServerProcess>();
            let _ = start_server_inner(state.inner(), 3334);
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Failed to start KiCad MCP Pro Tauri app");
}
