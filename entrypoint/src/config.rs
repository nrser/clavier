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
    pub kill_server: RetryConfig,
    pub connect_server: RetryConfig,
}

impl Config {
    pub fn new(
        kill_server: Option<RetryConfig>,
        connect_server: Option<RetryConfig>,
    ) -> Config {
        Config {
            kill_server: kill_server.unwrap_or(RetryConfig::default()),
            connect_server: connect_server.unwrap_or(RetryConfig::new(
                None,
                Some(BackoffType::Constant),
                Some(Duration::from_millis(10)),
            )),
        }
    }
}
