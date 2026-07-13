//! Sidecar process manager.
//!
//! Owns the Python sidecar child process: spawns it, writes JSON-RPC
//! requests to its stdin, correlates responses by `id`, and respawns on
//! unexpected exit with exponential backoff (1s → 3s → 9s, then gives up
//! and surfaces `SidecarDown` to the UI).
//!
//! Concurrency model: a single background task owns the stdout reader
//! and uses a `DashMap<String, oneshot::Sender<...>>` to route responses
//! to awaiting callers. Writers serialize through a `Mutex<ChildStdin>`.
//! This keeps the implementation small — Phase 1 doesn't need request
//! pipelining.

use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, Command};
use tokio::sync::{oneshot, Mutex};
use tokio::time::{sleep, Duration};
use tracing::{error, info, warn};

use crate::errors::DesktopError;
use crate::rpc::{parse_response_line, RpcRequest};

type PendingMap = Arc<Mutex<HashMap<String, oneshot::Sender<Result<Value, DesktopError>>>>>;

/// Fired once when the sidecar exits WITHOUT going through
/// [`Sidecar::replace_solution`] (i.e. a genuine crash, not an intentional
/// respawn). Deliberately Tauri-free (`sidecar.rs` stays unit-testable under
/// `--no-default-features`) — the `desktop` feature supplies the actual
/// closure, which emits a Tauri event and drives [`respawn_with_backoff`].
pub type CrashHook = Arc<dyn Fn() + Send + Sync>;

#[derive(Clone)]
pub struct SidecarConfig {
    /// Absolute path to the python interpreter to use.
    pub python: PathBuf,
    /// Absolute path to the `sidecar` package directory (contains __main__.py).
    pub sidecar_dir: PathBuf,
    /// Optional solution name to pass via --solution-name.
    pub solution_name: Option<String>,
    /// Optional solution path to pass via --solution-path.
    pub solution_path: Option<PathBuf>,
    /// Absolute path to the SAGE repo root (so `from src.core...` resolves).
    pub sage_root: PathBuf,
}

/// The live connection to a running sidecar child. Absent when the sidecar
/// is offline (initial spawn failed) — see [`Sidecar::offline`].
struct Connection {
    stdin: Arc<Mutex<ChildStdin>>,
    pending: PendingMap,
    child: Arc<Mutex<Child>>,
    /// Set to `true` by [`Sidecar::replace_solution`] just before it closes
    /// stdin, so the reader task can tell "we did this on purpose" apart
    /// from "the child actually died" and only fire `on_crash` for the
    /// latter.
    shutting_down: Arc<AtomicBool>,
}

pub struct Sidecar {
    /// `None` means the sidecar is offline: no child process is running and
    /// every `call` returns `SidecarDown`.
    conn: Option<Connection>,
    cfg: SidecarConfig,
    /// Re-armed on every (re)spawn so a solution switch keeps crash recovery
    /// live for the new child too.
    on_crash: Option<CrashHook>,
}

impl Sidecar {
    /// Spawn the sidecar with no crash hook — the Phase 1 behavior every
    /// existing caller (including all tests) still gets unchanged.
    pub async fn spawn(cfg: SidecarConfig) -> Result<Self, DesktopError> {
        Self::spawn_with_hook(cfg, None).await
    }

    /// Spawn the sidecar and arm `on_crash` to fire if the child exits
    /// without going through [`Sidecar::replace_solution`] first. The
    /// stdout reader task is detached — it runs until the child exits.
    pub async fn spawn_with_hook(
        cfg: SidecarConfig,
        on_crash: Option<CrashHook>,
    ) -> Result<Self, DesktopError> {
        let mut cmd = Command::new(&cfg.python);
        // `-u` forces unbuffered stdio so we don't deadlock on flushing.
        cmd.arg("-u")
            .arg("-m")
            .arg("sidecar")
            .env("SAGE_ROOT", &cfg.sage_root)
            .env("PYTHONUNBUFFERED", "1")
            .current_dir(
                cfg.sidecar_dir
                    .parent()
                    .unwrap_or(&cfg.sidecar_dir)
                    .to_path_buf(),
            )
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        if let Some(name) = &cfg.solution_name {
            cmd.arg("--solution-name").arg(name);
        }
        if let Some(path) = &cfg.solution_path {
            cmd.arg("--solution-path").arg(path);
        }

        let mut child = cmd.spawn().map_err(|e| DesktopError::SidecarDown {
            message: format!("failed to spawn sidecar: {e}"),
        })?;

        let stdin = child.stdin.take().ok_or_else(|| DesktopError::SidecarDown {
            message: "no stdin on sidecar".into(),
        })?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| DesktopError::SidecarDown {
                message: "no stdout on sidecar".into(),
            })?;
        let stderr = child.stderr.take();

        let pending: PendingMap = Arc::new(Mutex::new(HashMap::new()));
        let pending_for_reader = pending.clone();
        let shutting_down = Arc::new(AtomicBool::new(false));
        let shutting_down_for_reader = shutting_down.clone();
        let on_crash_for_reader = on_crash.clone();

        // Detached: reads one NDJSON line at a time, routes by id.
        tokio::spawn(async move {
            let mut reader = BufReader::new(stdout).lines();
            loop {
                match reader.next_line().await {
                    Ok(Some(line)) => {
                        if line.trim().is_empty() {
                            continue;
                        }
                        match parse_response_line(&line) {
                            Ok(resp) => {
                                let id = resp.id.clone();
                                let result = resp.into_result();
                                if let Some(id) = id {
                                    let mut map = pending_for_reader.lock().await;
                                    if let Some(tx) = map.remove(&id) {
                                        let _ = tx.send(result);
                                    } else {
                                        warn!("orphan sidecar response id={id}");
                                    }
                                } else {
                                    // Error frames with null id (parse error, etc.)
                                    warn!("sidecar error with null id: {:?}", result.err());
                                }
                            }
                            Err(e) => {
                                error!("failed to parse sidecar line: {e}");
                            }
                        }
                    }
                    Ok(None) => {
                        info!("sidecar stdout closed");
                        break;
                    }
                    Err(e) => {
                        error!("sidecar stdout read error: {e}");
                        break;
                    }
                }
            }

            // Drain pending callers with SidecarDown
            let mut map = pending_for_reader.lock().await;
            for (_, tx) in map.drain() {
                let _ = tx.send(Err(DesktopError::SidecarDown {
                    message: "sidecar exited".into(),
                }));
            }
            drop(map);

            // Only a genuine crash (not an intentional replace_solution
            // shutdown) should trigger recovery.
            if !shutting_down_for_reader.load(Ordering::SeqCst) {
                if let Some(hook) = on_crash_for_reader {
                    warn!("sidecar exited unexpectedly — firing crash hook");
                    hook();
                }
            }
        });

        // Detached stderr drain (logs only).
        if let Some(stderr) = stderr {
            tokio::spawn(async move {
                let mut reader = BufReader::new(stderr).lines();
                while let Ok(Some(line)) = reader.next_line().await {
                    info!(target: "sage_desktop::sidecar::stderr", "{line}");
                }
            });
        }

        Ok(Self {
            conn: Some(Connection {
                stdin: Arc::new(Mutex::new(stdin)),
                pending,
                child: Arc::new(Mutex::new(child)),
                shutting_down,
            }),
            cfg,
            on_crash,
        })
    }

    /// Construct an offline sidecar handle that owns no child process.
    ///
    /// Used when the initial spawn fails: the Tauri state is still registered
    /// (so commands return a recoverable `SidecarDown` error the UI can show
    /// instead of Tauri's opaque unmanaged-state rejection). A subsequent
    /// `replace_solution` can spawn a fresh process and bring it back online.
    pub fn offline(cfg: SidecarConfig) -> Self {
        Self { conn: None, cfg, on_crash: None }
    }

    /// Whether this sidecar currently has a live child process.
    pub fn is_online(&self) -> bool {
        self.conn.is_some()
    }

    /// The config this sidecar was spawned with (name/path may be None).
    pub fn config(&self) -> &SidecarConfig {
        &self.cfg
    }

    /// Gracefully shut down the current sidecar and respawn with a new solution.
    ///
    /// Closes stdin → waits up to 3 s for the child to exit → kills it if it
    /// doesn't → spawns a new sidecar with the caller's name/path overrides.
    /// The current `Sidecar` is mutated in-place so callers holding an
    /// `RwLock<Sidecar>` can swap without moving the value out of the lock.
    pub async fn replace_solution(
        &mut self,
        name: String,
        path: PathBuf,
    ) -> Result<(), DesktopError> {
        self.respawn(Some(name), Some(path)).await
    }

    /// Gracefully shut down the current sidecar and respawn with *no* solution.
    ///
    /// The operator's "close this solution" action: the fresh sidecar runs in
    /// minimal mode (`handshake` still answers, `solutions.list` still works),
    /// releasing every `.sage/` SQLite handle the previous child held, and the
    /// UI falls back to the picker. Framework control — executes immediately
    /// (SOUL.md Law 1), no proposal queue.
    pub async fn unload_solution(&mut self) -> Result<(), DesktopError> {
        self.respawn(None, None).await
    }

    /// Tear down the current child (if any) and spawn a fresh one with the
    /// given solution override. `None`/`None` means minimal mode.
    async fn respawn(
        &mut self,
        name: Option<String>,
        path: Option<PathBuf>,
    ) -> Result<(), DesktopError> {
        use std::time::Duration as StdDuration;

        // Gracefully tear down the current child if one is running. When the
        // sidecar is offline (`conn` is None) there is nothing to close — we
        // proceed straight to spawning a fresh process.
        if let Some(conn) = &self.conn {
            // Mark this as an intentional shutdown BEFORE closing stdin, so
            // the reader task's EOF doesn't get mistaken for a crash and
            // fire on_crash (which would race this method's own respawn).
            conn.shutting_down.store(true, Ordering::SeqCst);
            // Close stdin so the sidecar's reader hits EOF and exits.
            {
                let mut s = conn.stdin.lock().await;
                let _ = s.shutdown().await;
            }
            // Wait for clean exit, force-kill on timeout.
            {
                let mut c = conn.child.lock().await;
                let _ = tokio::time::timeout(StdDuration::from_secs(3), c.wait()).await;
                let _ = c.start_kill();
            }
        }

        // The old child (if any) is now dead — reflect that immediately so a
        // failed respawn below can't leave is_online() reporting a stale,
        // already-exited process as still connected.
        self.conn = None;

        let mut cfg = self.cfg.clone();
        cfg.solution_name = name;
        cfg.solution_path = path;
        // Re-arm the same crash hook for the fresh child.
        let fresh = Self::spawn_with_hook(cfg, self.on_crash.clone()).await?;

        self.conn = fresh.conn;
        self.cfg = fresh.cfg;
        Ok(())
    }

    /// Send a JSON-RPC request and wait for its correlated response.
    pub async fn call(&self, method: &str, params: Value) -> Result<Value, DesktopError> {
        // Offline sidecar: no child to talk to. Surface a recoverable error
        // rather than panicking or blocking.
        let conn = self.conn.as_ref().ok_or_else(|| DesktopError::SidecarDown {
            message: "sidecar offline".into(),
        })?;

        let req = RpcRequest::new(method, params);
        let id = req.id.clone();
        let line = req.to_ndjson_line().map_err(|e| DesktopError::SidecarDown {
            message: format!("request serialize failed: {e}"),
        })?;

        let (tx, rx) = oneshot::channel();
        {
            let mut map = conn.pending.lock().await;
            map.insert(id.clone(), tx);
        }

        {
            let mut stdin = conn.stdin.lock().await;
            stdin
                .write_all(line.as_bytes())
                .await
                .map_err(|e| DesktopError::SidecarDown {
                    message: format!("stdin write failed: {e}"),
                })?;
            stdin
                .flush()
                .await
                .map_err(|e| DesktopError::SidecarDown {
                    message: format!("stdin flush failed: {e}"),
                })?;
        }

        rx.await.unwrap_or_else(|_| {
            Err(DesktopError::SidecarDown {
                message: "response channel closed".into(),
            })
        })
    }
}

/// Respawn policy: 1s, 3s, 9s, then give up. `on_crash` is re-armed on the
/// freshly-spawned sidecar so a second crash can also be recovered from.
pub async fn respawn_with_backoff(
    cfg: SidecarConfig,
    on_crash: Option<CrashHook>,
) -> Result<Sidecar, DesktopError> {
    let delays = [Duration::from_secs(1), Duration::from_secs(3), Duration::from_secs(9)];
    let mut last_err = DesktopError::SidecarDown {
        message: "not attempted".into(),
    };
    for delay in delays {
        sleep(delay).await;
        match Sidecar::spawn_with_hook(cfg.clone(), on_crash.clone()).await {
            Ok(s) => return Ok(s),
            Err(e) => {
                warn!("sidecar respawn failed after {:?}: {e}", delay);
                last_err = e;
            }
        }
    }
    Err(last_err)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    use std::path::PathBuf;

    fn repo_root() -> PathBuf {
        // src-tauri/src/sidecar.rs → ../..  → sage-desktop/  → ..  → SAGE/
        let here = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        here.parent().unwrap().parent().unwrap().to_path_buf()
    }

    fn python_exe() -> PathBuf {
        // Let CI/devs override; default to `python` on PATH.
        env::var("PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("python"))
    }

    #[tokio::test]
    async fn handshake_round_trip_through_real_sidecar() {
        let root = repo_root();
        let sidecar_dir = root.join("sage-desktop").join("sidecar");
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir,
            solution_name: None,
            solution_path: None,
            sage_root: root,
        };
        let sidecar = match Sidecar::spawn(cfg).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("skipping: could not spawn sidecar: {e}");
                return;
            }
        };
        let result = sidecar
            .call("handshake", serde_json::json!({}))
            .await
            .expect("handshake should succeed");
        assert!(result.get("sidecar_version").is_some());
        assert!(result.get("warnings").is_some());
    }

    #[tokio::test]
    async fn on_crash_hook_fires_when_child_dies_unexpectedly() {
        let root = repo_root();
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir: root.join("sage-desktop").join("sidecar"),
            solution_name: None,
            solution_path: None,
            sage_root: root,
        };
        let fired = Arc::new(AtomicBool::new(false));
        let fired_clone = fired.clone();
        let hook: CrashHook = Arc::new(move || {
            fired_clone.store(true, Ordering::SeqCst);
        });

        let sidecar = match Sidecar::spawn_with_hook(cfg, Some(hook)).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("skipping: could not spawn sidecar: {e}");
                return;
            }
        };
        // Force-kill the child directly (NOT via replace_solution) to
        // simulate a genuine crash.
        if let Some(conn) = &sidecar.conn {
            let mut c = conn.child.lock().await;
            let _ = c.start_kill();
        }
        // Give the detached reader task a moment to observe EOF and fire.
        tokio::time::sleep(Duration::from_millis(500)).await;
        assert!(
            fired.load(Ordering::SeqCst),
            "on_crash hook should fire after an unexpected exit"
        );
    }

    #[tokio::test]
    async fn on_crash_hook_does_not_fire_during_replace_solution() {
        let root = repo_root();
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir: root.join("sage-desktop").join("sidecar"),
            solution_name: None,
            solution_path: None,
            sage_root: root.clone(),
        };
        let fired = Arc::new(AtomicBool::new(false));
        let fired_clone = fired.clone();
        let hook: CrashHook = Arc::new(move || {
            fired_clone.store(true, Ordering::SeqCst);
        });

        let mut sidecar = match Sidecar::spawn_with_hook(cfg, Some(hook)).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("skipping: could not spawn sidecar: {e}");
                return;
            }
        };
        let swap_path = root.join("solutions").join("starter");
        sidecar
            .replace_solution("starter".into(), swap_path)
            .await
            .expect("replace_solution");
        tokio::time::sleep(Duration::from_millis(300)).await;
        assert!(
            !fired.load(Ordering::SeqCst),
            "on_crash must NOT fire for an intentional replace_solution"
        );
        // The fresh sidecar (with the hook re-armed) should still work.
        let result = sidecar
            .call("handshake", serde_json::json!({}))
            .await
            .expect("post-swap handshake");
        assert!(result.get("sidecar_version").is_some());
    }

    #[tokio::test]
    async fn replace_solution_spawns_fresh_sidecar() {
        let root = repo_root();
        let sidecar_dir = root.join("sage-desktop").join("sidecar");
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir,
            solution_name: None,
            solution_path: None,
            sage_root: root.clone(),
        };
        let mut sidecar = match Sidecar::spawn(cfg).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("skipping: could not spawn sidecar: {e}");
                return;
            }
        };
        // Initial handshake OK
        let _ = sidecar
            .call("handshake", serde_json::json!({}))
            .await
            .expect("initial handshake");

        // Swap to a dummy solution path — sidecar will warn but still run
        let swap_path = root.join("solutions").join("starter");
        sidecar
            .replace_solution("starter".into(), swap_path)
            .await
            .expect("replace_solution");

        // Handshake after swap still works
        let result = sidecar
            .call("handshake", serde_json::json!({}))
            .await
            .expect("post-swap handshake");
        assert!(result.get("sidecar_version").is_some());
    }

    #[tokio::test]
    async fn replace_solution_resets_conn_on_spawn_failure() {
        let root = repo_root();
        let sidecar_dir = root.join("sage-desktop").join("sidecar");
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir,
            solution_name: None,
            solution_path: None,
            sage_root: root.clone(),
        };
        let mut sidecar = match Sidecar::spawn(cfg).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("skipping: could not spawn sidecar: {e}");
                return;
            }
        };
        assert!(sidecar.is_online());

        // Point at a nonexistent interpreter so the respawn inside
        // replace_solution fails deterministically.
        sidecar.cfg.python = PathBuf::from("this-binary-does-not-exist-xyz-12345");
        let swap_path = root.join("solutions").join("starter");
        let result = sidecar.replace_solution("starter".into(), swap_path).await;

        assert!(result.is_err(), "spawn with a bad interpreter must fail");
        assert!(
            !sidecar.is_online(),
            "a failed respawn must leave the sidecar reporting offline, \
             not pointing at the old (already-torn-down) connection"
        );
    }

    #[tokio::test]
    async fn offline_sidecar_call_returns_sidecar_down() {
        let cfg = SidecarConfig {
            python: PathBuf::from("python"),
            sidecar_dir: PathBuf::from("."),
            solution_name: None,
            solution_path: None,
            sage_root: PathBuf::from("."),
        };
        let sidecar = Sidecar::offline(cfg);
        assert!(!sidecar.is_online());
        let err = sidecar
            .call("status.get", serde_json::json!({}))
            .await
            .expect_err("offline sidecar call should error");
        assert!(matches!(err, DesktopError::SidecarDown { .. }));
    }

    #[tokio::test]
    async fn unknown_method_returns_method_not_found() {
        let root = repo_root();
        let cfg = SidecarConfig {
            python: python_exe(),
            sidecar_dir: root.join("sage-desktop").join("sidecar"),
            solution_name: None,
            solution_path: None,
            sage_root: root,
        };
        let sidecar = match Sidecar::spawn(cfg).await {
            Ok(s) => s,
            Err(_) => return,
        };
        let err = sidecar
            .call("does.not.exist", serde_json::json!({}))
            .await
            .expect_err("should error");
        assert!(matches!(err, DesktopError::MethodNotFound { .. }));
    }
}
