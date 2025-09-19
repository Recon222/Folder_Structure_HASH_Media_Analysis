// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use std::fs;
use std::path::Path;

#[tauri::command]
fn get_ws_port() -> u16 {
    // Debug: Print all args
    let args: Vec<String> = std::env::args().collect();
    println!("Command line args: {:?}", args);

    // Get port from command line args or environment
    let port = std::env::args().nth(1)
        .and_then(|arg| {
            println!("Processing arg: {}", arg);
            // Parse --ws-port=8765 format
            if arg.starts_with("--ws-port=") {
                let port_str = arg.strip_prefix("--ws-port=").unwrap();
                println!("Extracted port string: {}", port_str);
                port_str.parse().ok()
            } else {
                arg.parse().ok()
            }
        })
        .or_else(|| {
            // Check environment variable
            if let Ok(port_str) = std::env::var("TAURI_WS_PORT") {
                println!("Got port from env: {}", port_str);
                port_str.parse().ok()
            } else {
                None
            }
        })
        .unwrap_or(8765);

    println!("Final WebSocket port: {}", port);

    // Write the port to a config file
    write_ws_config(port);

    port
}

fn write_ws_config(port: u16) {
    // Get the path to the src directory
    let exe_path = std::env::current_exe().unwrap();
    let exe_dir = exe_path.parent().unwrap();

    // Go up to find the src directory (from target/release to src)
    let src_path = exe_dir
        .parent() // target
        .and_then(|p| p.parent()) // src-tauri
        .and_then(|p| p.parent()) // tauri-map
        .map(|p| p.join("src").join("ws-config.js"));

    if let Some(config_path) = src_path {
        let config_content = format!(
            "// Auto-generated WebSocket configuration\n\
             window.WS_CONFIG = {{\n\
             \tport: {},\n\
             \ttimestamp: '{}'\n\
             }};\n\
             console.log('[ws-config.js] WebSocket port configured:', {});",
            port,
            chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
            port
        );

        if let Err(e) = fs::write(&config_path, config_content) {
            eprintln!("Failed to write ws-config.js: {}", e);
        } else {
            println!("WebSocket config written to: {:?}", config_path);
        }
    }
}

#[tauri::command]
fn get_map_config() -> serde_json::Value {
    serde_json::json!({
        "mapboxToken": std::env::var("MAPBOX_TOKEN").ok(),
        "wsPort": get_ws_port()
    })
}

fn main() {
    // Get the WebSocket port from command line or environment
    // This also writes the config file
    let ws_port = get_ws_port();

    println!("Starting Tauri with WebSocket port: {}", ws_port);

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_ws_port, get_map_config])
        .setup(move |app| {
            use tauri::Manager;

            // Navigate to mapbox.html with port parameter
            if let Some(window) = app.get_window("main") {
                // Navigate with port parameter
                let window_nav = window.clone();
                let port_for_nav = ws_port;
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(100));
                    let script = format!("window.location.href = 'mapbox.html?port={}'", port_for_nav);
                    window_nav.eval(&script).ok();
                    println!("Navigated to mapbox.html with port: {}", port_for_nav);
                });

                // Automatically open DevTools in release builds for debugging
                #[cfg(feature = "devtools")]
                {
                    let window_devtools = window.clone();
                    std::thread::spawn(move || {
                        std::thread::sleep(std::time::Duration::from_millis(1500));
                        window_devtools.open_devtools();
                        println!("DevTools opened automatically");
                    });
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}