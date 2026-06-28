fn main() {
    // Only run the Tauri build codegen when the desktop feature is on.
    // Unit test invocations (`cargo test --no-default-features`) skip it
    // so the test binary has no WebView2Loader.dll startup requirement.
    if std::env::var_os("CARGO_FEATURE_DESKTOP").is_some() {
        tauri_build::build()
    }
}
