use nix::sys::signal::{self, Signal};
use nix::unistd::Pid;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::error::Error;
use std::os::unix::net::UnixStream;
use std::path::Path;
use std::thread;
use std::time::{Duration, Instant};
use std::{fs, process};
// use serde_json::Result;

use crate::config::Config;

const START_CMD_JSON: &str = env!("ENTRYPOINT_START_CMD_JSON");
const PID_PATH: &str = env!("ENTRYPOINT_PID_PATH");
const SOCKET_PATH: &str = env!("ENTRYPOINT_SOCKET_PATH");

pub const RESTART_SERVER_ARGS: [&str; 2] = ["-_R", "--_RESTART"];
pub const KILL_SERVER_ARGS: [&str; 2] = ["-_K", "--_KILL"];

#[derive(Serialize, Deserialize)]
struct StartCmd {
    env: HashMap<String, String>,
    cwd: String,
    program: String,
    args: Vec<String>,
}

// Public API
// ===========================================================================

pub fn is_restart_arg(arg: &str) -> bool {
    for reset_arg in RESTART_SERVER_ARGS {
        if arg == reset_arg {
            return true;
        }
    }
    false
}

pub fn is_kill_arg(arg: &str) -> bool {
    for kill_arg in KILL_SERVER_ARGS {
        if arg == kill_arg {
            return true;
        }
    }
    false
}

pub fn create() -> Result<(), Box<dyn Error>> {
    let start_cmd: StartCmd = serde_json::from_str(START_CMD_JSON)?;

    let mut command = process::Command::new(start_cmd.program);

    command.envs(start_cmd.env);
    command.args(start_cmd.args);
    command.current_dir(start_cmd.cwd);

    let mut child = command.spawn()?;

    child.wait()?;

    wait_for_socket_file(10)?;

    Ok(())
}

pub fn kill(config: &Config) -> Result<(), Box<dyn Error>> {
    let socket_path = Path::new(SOCKET_PATH);

    if !Path::new(PID_PATH).exists() {
        info!("Server not running -- not pid file at {:?}", PID_PATH);
        return Ok(());
    }

    let pid = read_pid()?;

    if !is_alive(pid) {
        info!(
            "PID file present at {} but server does not apprear to be alive",
            PID_PATH
        );
        remove_pid_file();

        if socket_path.exists() {
            remove_socket_file();
        }

        return Ok(());
    }

    if let Ok(_) = try_to_kill(&config, pid, Signal::SIGTERM) {
        info!("Killed server.");
        return Ok(());
    }

    warn!("Force-killing with SIGKILL");

    if let Ok(_) = try_to_kill(&config, pid, Signal::SIGKILL) {
        info!("Killed server.");

        remove_pid_file();

        if socket_path.exists() {
            remove_socket_file();
        }

        return Ok(());
    }

    Err(format!("Failed to kill server at PID {}", pid).into())
}

pub fn connect(config: &Config) -> Result<UnixStream, Box<dyn Error>> {
    // First do a single connection attempt, returning then and there if it
    // succeeds (the "happy path").
    if let Ok(stream) = UnixStream::connect(SOCKET_PATH) {
        return Ok(stream);
    }

    // We failed to connect. The server may be dead, unresponsive, or something
    // random went wrong. First, see if we know it's PID.
    if let Ok(pid) = read_pid() {
        // We do know the PID. Next see if it's alive.
        if is_alive(pid) {
            // It's alive, try to connect a few more times
            if let Ok(stream) = try_to_connect(&config) {
                return Ok(stream);
            }

            // No dice. Kill it and start over.
            warn!(
                "Failed to connect to server at PID {} through {:?}, \
                killing...",
                pid, SOCKET_PATH
            );
            kill(&config)?;
        } else {
            info!("PID file is present but server does not seem to be alive");

            // Remove the files to get to a clean state.
            remove_pid_file();
            remove_socket_file();
        }
    }

    info!("Creating a new server...");
    create()?;

    if let Ok(stream) = try_to_connect(&config) {
        return Ok(stream);
    }

    Err(format!("Failed to connect to server at {:?}", SOCKET_PATH).into())
}

pub fn socket_exists() -> bool {
    Path::new(SOCKET_PATH).exists()
}

pub fn read_pid() -> Result<Pid, Box<dyn Error>> {
    let contents = fs::read_to_string(PID_PATH)?;

    let pid = contents.trim().parse::<i32>()?;

    if pid <= 0 {
        return Err("Bad pid in pid file".into());
    }

    Ok(Pid::from_raw(pid))
}

pub fn remove_pid_file() {
    info!("Removing PID file at {:?}", PID_PATH);
    fs::remove_file(PID_PATH).unwrap_or(());
}

pub fn remove_socket_file() {
    info!("Removing socket file at {:?}", SOCKET_PATH);
    fs::remove_file(SOCKET_PATH).unwrap_or(());
}

// Private Helpers
// ===========================================================================

fn try_to_connect(config: &Config) -> Result<UnixStream, ()> {
    let t_start = Instant::now();

    let mut attempt_number: u32 = 0;

    while attempt_number < config.connect_server.max_attempts {
        if let Ok(stream) = UnixStream::connect(SOCKET_PATH) {
            return Ok(stream);
        }

        thread::sleep(config.connect_server.sleep_for(attempt_number));

        attempt_number += 1;
    }

    let delta_t = t_start.elapsed();

    warn!("Failed to connect to server at socket {:?}", SOCKET_PATH);
    warn!(
        "Made {} attempts over {:?} seconds",
        attempt_number, delta_t
    );

    Err(())
}

fn is_alive(pid: Pid) -> bool {
    match signal::kill(pid, None) {
        Ok(_) => true,
        Err(_) => false,
    }
}

fn try_to_kill(config: &Config, pid: Pid, signal: Signal) -> Result<(), ()> {
    let t_start = Instant::now();

    let mut attempt_number: u32 = 0;

    while attempt_number < config.kill_server.max_attempts {
        if let Err(_) = signal::kill(pid, signal) {
            return Ok(());
        }

        thread::sleep(Duration::from_millis(50));

        if !is_alive(pid) {
            return Ok(());
        }

        thread::sleep(config.kill_server.sleep_for(attempt_number));

        attempt_number += 1;
    }

    let delta_t = t_start.elapsed();

    warn!(
        "Failed to kill server at PID {} with singal {}",
        pid, signal
    );
    warn!(
        "Made {} attempts over {:?} seconds",
        attempt_number, delta_t
    );

    Err(())
}

fn wait_for_socket_file(max_attempts: usize) -> Result<(), &'static str> {
    let mut attempt_number: usize = 0;
    let dur = Duration::from_millis(100);
    let socket_path = Path::new(SOCKET_PATH);

    while attempt_number < max_attempts {
        if socket_path.exists() {
            return Ok(());
        }

        thread::sleep(dur);
        attempt_number += 1;
    }

    Err("Socket file never appeared")
}
