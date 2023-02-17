use nix::libc;
use nix::sys::signal::{self, SigHandler, Signal};
use sendfd::{self, SendWithFd};
use serde_json::json;
use std::collections::HashMap;
use std::error::Error;
use std::io::prelude::*;
use std::os::{fd::AsRawFd, fd::RawFd};
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

// SEE https://stackoverflow.com/a/51620853
const WORK_DIR: &str = env!("PWD");

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

    let config = Config::new("handoff", WORK_DIR, None, None);

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
        server::create(&config)?;
    } else if !config.socket_path.exists() {
        server::create(&config)?;
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

    let mut buffer: [u8; 4] = [0, 0, 0, 0];
    let mut got_it: bool = false;

    stream.set_nonblocking(true)?;

    while !got_it {
        match stream.read_exact(&mut buffer) {
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

    let exit_status: i32 = i32::from_ne_bytes(buffer);

    process::exit(exit_status);
}
