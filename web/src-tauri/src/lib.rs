use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Focus main window on launch
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running SAGE desktop application");
}
