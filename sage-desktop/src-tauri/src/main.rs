// Prevents a second console window on Windows release builds; release
// builds should show only the Tauri window itself.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(feature = "desktop")]
fn main() {
    sage_desktop_lib::run();
}

#[cfg(not(feature = "desktop"))]
fn main() {
    eprintln!("Built without the 'desktop' feature — nothing to run.");
}
