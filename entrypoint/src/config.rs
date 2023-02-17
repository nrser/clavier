use nix::unistd::Pid;
use std::error::Error;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;

pub enum BackoffType {
    Constant,
    // Linear,
    Exponential,
}

pub struct RetryConfig {
    pub max_attempts: u32,
    pub backoff_type: BackoffType,
    pub backoff_base: Duration,
}

impl RetryConfig {
    pub fn new(
        max_attempts: Option<u32>,
        backoff_type: Option<BackoffType>,
        backoff_base: Option<Duration>,
    ) -> RetryConfig {
        RetryConfig {
            max_attempts: max_attempts.unwrap_or(5),
            backoff_type: backoff_type.unwrap_or(BackoffType::Exponential),
            backoff_base: backoff_base.unwrap_or(Duration::from_millis(100)),
        }
    }

    pub fn default() -> RetryConfig {
        RetryConfig::new(None, None, None)
    }

    pub fn sleep_for(&self, attempt_number: u32) -> Duration {
        match self.backoff_type {
            BackoffType::Constant => self.backoff_base,
            // BackoffType::Linear => self.backoff_base * (attempt_number + 1),
            BackoffType::Exponential => {
                self.backoff_base * 2_u32.pow(attempt_number)
            }
        }
    }
}

pub struct Config {
    // name: String,
    pub work_dir: PathBuf,
    pub socket_path: PathBuf,
    pub pid_path: PathBuf,
    pub kill_server: RetryConfig,
    pub connect_server: RetryConfig,
}

impl Config {
    pub fn new(
        name: &str,
        work_dir: &str,
        kill_server: Option<RetryConfig>,
        connect_server: Option<RetryConfig>,
    ) -> Config {
        let wd = Path::new(work_dir);

        Config {
            // name: String::from(name),
            work_dir: PathBuf::from(wd),
            socket_path: wd.join(format!(".{name}.sock")),
            pid_path: wd.join(format!(".{name}.pid")),
            kill_server: kill_server.unwrap_or(RetryConfig::default()),
            connect_server: connect_server.unwrap_or(RetryConfig::new(
                None,
                Some(BackoffType::Constant),
                Some(Duration::from_millis(10)),
            )),
        }
    }

    pub fn read_pid(&self) -> Result<Pid, Box<dyn Error>> {
        let contents = fs::read_to_string(&self.pid_path)?;

        let pid = contents.trim().parse::<i32>()?;

        if pid <= 0 {
            return Err("Bad pid in pid file".into());
        }

        Ok(Pid::from_raw(pid))
    }

    pub fn remove_pid_file(&self) {
        info!("Removing PID file at {:?}", self.pid_path);
        fs::remove_file(self.pid_path.as_os_str()).unwrap_or(());
    }

    pub fn remove_socket_file(&self) {
        info!("Removing socket file at {:?}", self.socket_path);
        fs::remove_file(self.socket_path.as_os_str()).unwrap_or(());
    }
}
