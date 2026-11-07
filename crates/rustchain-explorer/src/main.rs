// SPDX-License-Identifier: MIT
//! Read-only RustChain explorer. Run `rustchain-explorer --help` for commands.
//! Node JSON is preserved by `--json`; the default view labels each field.

use clap::{Parser, Subcommand};
use reqwest::{blocking::Client, Url};
use serde_json::Value;
use std::error::Error;
use std::io::{self, Write};
use std::process::ExitCode;
use std::time::Duration;

/// Inspect a RustChain node without a wallet key or any state-changing requests.
#[derive(Debug, Parser)]
#[command(version, about)]
struct Options {
    /// Node origin (HTTP or HTTPS); TLS certificates are verified.
    #[arg(long, global = true, default_value = "https://rustchain.org", value_parser = node_url)]
    node: Url,
    /// Total request timeout in seconds.
    #[arg(long, global = true, default_value = "15", value_parser = clap::value_parser!(u64).range(1..=300))]
    timeout: u64,
    /// Print the complete response as JSON for scripts.
    #[arg(long, global = true)]
    json: bool,
    #[command(subcommand)]
    command: Command,
}

/// Public, read-only endpoints exposed by RustChain nodes.
#[derive(Debug, Subcommand)]
enum Command {
    /// Inspect node health, version and uptime.
    Health,
    /// Inspect the current epoch, slot and reward pot.
    Epoch,
    /// List miners and their hardware/antiquity information.
    Miners,
    /// Inspect the balance of a wallet name or RTC address.
    Balance {
        /// Wallet identifier, passed as one URL-encoded query parameter.
        #[arg(value_parser = wallet_id)]
        wallet: String,
    },
}

/// Reject ambiguous base URLs before sending a request.
fn node_url(input: &str) -> Result<Url, String> {
    let url = Url::parse(input).map_err(|error| error.to_string())?;
    if !matches!(url.scheme(), "http" | "https") || url.host_str().is_none() {
        return Err("node must be an HTTP or HTTPS origin".into());
    }
    if !url.username().is_empty() || url.password().is_some() {
        return Err("node must not contain credentials".into());
    }
    if url.path() != "/" || url.query().is_some() || url.fragment().is_some() {
        return Err("node must be an origin without a path, query or fragment".into());
    }
    Ok(url)
}

/// Wallet aliases are valid; do not impose the address-only format on them.
fn wallet_id(input: &str) -> Result<String, String> {
    if input.trim().is_empty() || input.chars().any(char::is_control) {
        return Err("wallet must be nonempty and contain no control characters".into());
    }
    Ok(input.to_owned())
}

impl Command {
    /// Construct the endpoint using URL query encoding, never interpolation.
    fn url(&self, origin: &Url) -> Url {
        let mut url = origin.clone();
        url.set_path(match self {
            Self::Health => "/health",
            Self::Epoch => "/epoch",
            Self::Miners => "/api/miners",
            Self::Balance { .. } => "/wallet/balance",
        });
        if let Self::Balance { wallet } = self {
            url.query_pairs_mut().append_pair("miner_id", wallet);
        }
        url
    }

    /// Human-readable heading for the selected response.
    fn title(&self) -> &'static str {
        match self {
            Self::Health => "Node health",
            Self::Epoch => "Current epoch",
            Self::Miners => "Miners",
            Self::Balance { .. } => "Wallet balance",
        }
    }
}

/// Fetch JSON and distinguish transport, HTTP, JSON and application errors.
fn fetch(options: &Options) -> Result<Value, Box<dyn Error>> {
    let client = Client::builder()
        .timeout(Duration::from_secs(options.timeout))
        .redirect(reqwest::redirect::Policy::none())
        .user_agent(concat!("rustchain-explorer/", env!("CARGO_PKG_VERSION")))
        .build()?;
    let response = client.get(options.command.url(&options.node)).send()?;
    if !response.status().is_success() {
        return Err(format!("node returned HTTP {}", response.status()).into());
    }
    let value: Value = response.json()?;
    if !value.is_object() && !value.is_array() {
        return Err("node returned JSON that is not an object or array".into());
    }
    if value.get("ok") == Some(&Value::Bool(false)) {
        return Err(format!("node reported failure: {value}").into());
    }
    if let Some(error) = value.get("error").filter(|error| !error.is_null()) {
        return Err(format!("node reported error: {error}").into());
    }
    Ok(value)
}

/// Render all fields, including fields added by newer nodes.
/// JSON string quoting keeps terminal control characters escaped.
fn render(options: &Options, value: &Value, out: &mut impl Write) -> io::Result<()> {
    if options.json {
        writeln!(out, "{}", serde_json::to_string_pretty(value)?)?;
        return Ok(());
    }
    writeln!(out, "{}", options.command.title())?;
    match value {
        Value::Object(fields) => {
            for (key, value) in fields {
                writeln!(out, "{}: {}", serde_json::to_string(key)?, value)?;
            }
        }
        Value::Array(rows) => {
            for (index, row) in rows.iter().enumerate() {
                writeln!(out, "{}: {}", index + 1, row)?;
            }
        }
        _ => writeln!(out, "{value}")?,
    }
    Ok(())
}

/// Keep diagnostics on stderr so stdout can be consumed as JSON.
fn main() -> ExitCode {
    let options = Options::parse();
    let result = fetch(&options).and_then(|value| {
        render(&options, &value, &mut io::stdout().lock())?;
        Ok(())
    });
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            if error
                .downcast_ref::<io::Error>()
                .is_some_and(|error| error.kind() == io::ErrorKind::BrokenPipe)
            {
                return ExitCode::SUCCESS;
            }
            eprintln!("rustchain-explorer: {error}");
            ExitCode::FAILURE
        }
    }
}
