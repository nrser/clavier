use nix::sys::signal::{self, Signal};
use nix::unistd::Pid;
use std::error::Error;
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::process;
use std::thread;
use std::time::{Duration, Instant};

use crate::config::Config;

pub const RESTART_SERVER_ARGS: [&str; 2] = ["-_R", "--_RESTART"];
pub const KILL_SERVER_ARGS: [&str; 2] = ["-_K", "--_KILL"];

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

pub fn create(config: &Config) -> Result<(), Box<dyn Error>> {
    let mut command = process::Command::new(config.python_exe.clone());

    command.env("PYTHONPATH", config.python_path.clone());
    command.env("CLAVIER_SRV", "true");
    command.arg("-m");
    command.arg(config.name.clone());
    command.arg("--_NOOP");

    let mut child = command.spawn()?;

    child.wait()?;

    wait_for_socket_file(&config.socket_path, 10)?;

    Ok(())
}

pub fn kill(config: &Config) -> Result<(), Box<dyn Error>> {
    if !config.pid_path.exists() {
        info!(
            "Server not running -- not pid file at {:?}",
            config.pid_path
        );
        return Ok(());
    }

    let pid = config.read_pid()?;

    if !is_alive(pid) {
        info!(
            "PID file present at {} but server does not apprear to be alive",
            config.pid_path.display()
        );
        config.remove_pid_file();

        if config.socket_path.exists() {
            config.remove_socket_file();
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

        config.remove_pid_file();

        if config.socket_path.exists() {
            config.remove_socket_file();
        }

        return Ok(());
    }

    Err(format!("Failed to kill server at PID {}", pid).into())
}

pub fn connect(config: &Config) -> Result<UnixStream, Box<dyn Error>> {
    // First do a single connection attempt, returning then and there if it
    // succeeds (the "happy path").
    if let Ok(stream) = UnixStream::connect(config.socket_path.clone()) {
        return Ok(stream);
    }

    // We failed to connect. The server may be dead, unresponsive, or something
    // random went wrong. First, see if we know it's PID.
    if let Ok(pid) = config.read_pid() {
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
                pid, config.socket_path
            );
            kill(&config)?;
        } else {
            info!("PID file is present but server does not seem to be alive");

            // Remove the files to get to a clean state.
            config.remove_pid_file();
            config.remove_socket_file();
        }
    }

    info!("Creating a new server...");
    create(&config)?;

    if let Ok(stream) = try_to_connect(&config) {
        return Ok(stream);
    }

    Err(
        format!("Failed to connect to server at {:?}", config.socket_path)
            .into(),
    )
}

// Private Helpers
// ===========================================================================

fn try_to_connect(config: &Config) -> Result<UnixStream, ()> {
    let t_start = Instant::now();

    let mut attempt_number: u32 = 0;

    while attempt_number < config.connect_server.max_attempts {
        if let Ok(stream) = UnixStream::connect(config.socket_path.clone()) {
            return Ok(stream);
        }

        thread::sleep(config.connect_server.sleep_for(attempt_number));

        attempt_number += 1;
    }

    let delta_t = t_start.elapsed();

    warn!(
        "Failed to connect to server at socket {:?}",
        config.socket_path
    );
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

fn wait_for_socket_file(
    socket_path: &PathBuf,
    max_attempts: usize,
) -> Result<(), &'static str> {
    let mut attempt_number: usize = 0;
    let dur = Duration::from_millis(100);

    while attempt_number < max_attempts {
        if socket_path.exists() {
            return Ok(());
        }

        thread::sleep(dur);
        attempt_number += 1;
    }

    Err("Socket file never appeared")
}
