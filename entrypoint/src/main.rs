use nix::libc;
use nix::sys::signal::{self, SigHandler, Signal};
use sendfd::{self, SendWithFd};
use serde_json::json;
use std::collections::HashMap;
use std::error::Error;
use std::io::prelude::*;
use std::os::unix::process::CommandExt;
use std::os::{fd::AsRawFd, fd::RawFd};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::Duration;
use std::{env, io, process};

#[macro_use]
extern crate lazy_static;
#[macro_use]
extern crate log;

mod config;
mod server;

use config::Config;

const DOTENV_PATH: Option<&str> = option_env!("ENTRYPOINT_DOTENV_PATH");

lazy_static! {
    static ref SIGNALED: AtomicBool = AtomicBool::new(false);
}

// https://docs.rs/nix/latest/nix/sys/signal/fn.signal.html
extern "C" fn handle_sigint(signal: libc::c_int) {
    let signal = Signal::try_from(signal).unwrap();

    SIGNALED.store(signal == Signal::SIGINT, Ordering::Relaxed);
}

fn main() -> Result<(), Box<dyn Error>> {
    env_logger::init();

    if let Some(dotenv_path) = DOTENV_PATH {
        if Path::new(dotenv_path).exists() {
            dotenvy::from_filename(dotenv_path)?;
        }
    }

    let config = Config::new(None, None);

    let cwd = env::current_dir()?;

    let mut env_map: HashMap<String, String> = HashMap::new();
    for (name, value) in env::vars() {
        env_map.insert(name, value);
    }

    let mut argv: Vec<String> = env::args().collect();

    let mut restart: bool = false;
    let mut kill: bool = false;

    let mut i: usize = 0;
    while i < argv.len() {
        if server::is_restart_arg(&argv[i]) {
            restart = true;
            argv.remove(i);
        } else if server::is_kill_arg(&argv[i]) {
            kill = true;
            argv.remove(i);
        } else {
            i += 1;
        }
    }

    if kill {
        return server::kill(&config);
    }

    if restart {
        server::kill(&config)?;
        server::create()?;
    } else if !server::socket_exists() {
        server::create()?;
    }

    let payload = json!({
        "argv": argv,
        "env": env_map,
        "cwd": cwd,
    });

    let mut stream = server::connect(&config)?;

    let mut fds: Vec<RawFd> = vec![
        io::stdin().as_raw_fd(),
        io::stdout().as_raw_fd(),
        io::stderr().as_raw_fd(),
    ];

    if let Ok(_) = env::var("_ARGCOMPLETE") {
        fds.push(8);
        fds.push(9);
    }

    stream.send_with_fd(payload.to_string().as_bytes(), &fds[..])?;

    let handler = SigHandler::Handler(handle_sigint);
    unsafe { signal::signal(Signal::SIGINT, handler) }.unwrap();

    let mut length_buffer: [u8; 4] = [0, 0, 0, 0];
    let mut got_it: bool = false;

    stream.set_nonblocking(true)?;

    while !got_it {
        match stream.read_exact(&mut length_buffer) {
            Ok(_) => got_it = true,
            Err(e) if e.kind() == io::ErrorKind::WouldBlock => {
                if SIGNALED.load(Ordering::Relaxed) == true {
                    let sig_num: i32 = Signal::SIGINT as i32;
                    stream.write(&sig_num.to_ne_bytes())?;
                }
                thread::sleep(Duration::from_millis(10));
            }
            result => result?,
        }
    }

    let response_length: i32 = i32::from_ne_bytes(length_buffer);

    debug!("Read response size {:?}", response_length);

    let mut response_buffer: Vec<u8> = std::iter::repeat(0u8)
        .take(response_length.try_into().unwrap())
        .collect::<Vec<_>>();

    stream.set_nonblocking(false)?;
    stream.read_exact(&mut response_buffer)?;

    debug!("Read response bytes: {:?}", response_buffer);

    let response: server::Response = serde_json::from_slice(&response_buffer)?;

    debug!("Parsed response {:?}", response);

    match response.replace_process {
        Some(rp) => {
            let mut command = process::Command::new(rp.program);

            if let Some(env) = rp.env {
                command.envs(env);
            }

            if let Some(args) = rp.args {
                command.args(args);
            }

            if let Some(cwd) = rp.cwd {
                command.current_dir(cwd);
            }

            command.exec();

            Ok(())
        }
        None => {
            debug!("Exiting with status {:?}", response.exit_status);
            process::exit(response.exit_status);
        }
    }
}
