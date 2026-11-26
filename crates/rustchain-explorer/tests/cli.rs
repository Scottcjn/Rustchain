// SPDX-License-Identifier: MIT
//! End-to-end CLI contracts against a local HTTP node, without internet access.
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::process::{Command, Output};
use std::thread;
use std::time::{Duration, Instant};

fn binary() -> Command {
    Command::new(env!("CARGO_BIN_EXE_rustchain-explorer"))
}

fn request(args: &[&str], status: &str, body: &str) -> (Output, String) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    listener.set_nonblocking(true).unwrap();
    let origin = format!("http://{}", listener.local_addr().unwrap());
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let server = thread::spawn(move || {
        let deadline = Instant::now() + Duration::from_secs(10);
        let mut stream = loop {
            match listener.accept() {
                Ok((stream, _)) => break stream,
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    assert!(Instant::now() < deadline, "CLI did not contact node");
                    thread::sleep(Duration::from_millis(10));
                }
                Err(error) => panic!("{error}"),
            }
        };
        stream.set_nonblocking(false).unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(5)))
            .unwrap();
        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let mut first_line = String::new();
        reader.read_line(&mut first_line).unwrap();
        loop {
            let mut line = String::new();
            if reader.read_line(&mut line).unwrap() == 0 || line == "\r\n" {
                break;
            }
        }
        stream.write_all(response.as_bytes()).unwrap();
        first_line
    });
    let output = binary()
        .args(["--node", &origin, "--timeout", "2"])
        .args(args)
        .env("NO_PROXY", "*")
        .output()
        .unwrap();
    (output, server.join().unwrap())
}

#[test]
fn live_response_shapes_and_endpoint_paths() {
    let cases = [
        (
            "health",
            "/health",
            json!({"ok":true,"uptime_s":177638,"version":"2.2.1-rip200"}),
        ),
        (
            "epoch",
            "/epoch",
            json!({"epoch":305,"slot":43935,"epoch_pot":1.5}),
        ),
        (
            "miners",
            "/api/miners",
            json!({"miners":[{"miner":"vintage","antiquity_multiplier":2.5,"last_attest":1791068239}]}),
        ),
        ("miners", "/api/miners", json!([{"miner":"vintage"}])),
    ];
    for (command, path, value) in cases {
        let (output, line) = request(&[command, "--json"], "200 OK", &value.to_string());
        assert!(output.status.success(), "{:?}", output);
        assert_eq!(line, format!("GET {path} HTTP/1.1\r\n"));
        assert_eq!(
            serde_json::from_slice::<Value>(&output.stdout).unwrap(),
            value
        );
        assert!(output.stderr.is_empty());
    }
}

#[test]
fn balance_preserves_amounts_and_encodes_wallet_as_one_parameter() {
    let value = json!({"amount_i64":1234567,"amount_rtc":1.234567,"miner_id":"a &b#?+"});
    let (output, line) = request(
        &["--json", "balance", "a &b#?+"],
        "200 OK",
        &value.to_string(),
    );
    assert!(output.status.success());
    assert_eq!(
        line,
        "GET /wallet/balance?miner_id=a+%26b%23%3F%2B HTTP/1.1\r\n"
    );
    assert_eq!(
        serde_json::from_slice::<Value>(&output.stdout).unwrap(),
        value
    );
}

#[test]
fn errors_have_nonzero_exit_and_no_stdout() {
    for (status, body, expected) in [
        ("503 Unavailable", "{}", "HTTP 503"),
        ("302 Found", "{}", "HTTP 302"),
        ("200 OK", "not json", "decoding response body"),
        ("200 OK", "null", "not an object or array"),
        ("200 OK", "{\"ok\":false}", "reported failure"),
        ("200 OK", "{\"error\":\"unknown wallet\"}", "unknown wallet"),
    ] {
        let (output, _) = request(&["health"], status, body);
        assert!(!output.status.success());
        assert!(output.stdout.is_empty());
        assert!(
            String::from_utf8_lossy(&output.stderr).contains(expected),
            "{:?}",
            output
        );
    }
}

#[test]
fn text_output_has_heading_and_escapes_control_characters() {
    let (output, _) = request(
        &["health"],
        "200 OK",
        "{\"ok\":true,\"version\":\"x\\u001b[31m\"}",
    );
    assert!(output.status.success());
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.starts_with("Node health\n"));
    assert!(text.contains("\\u001b"));
    assert!(!text.contains('\x1b'));
}

#[test]
fn argument_validation_and_help_need_no_node() {
    for args in [
        vec!["--node", "file:///tmp/node", "health"],
        vec!["--node", "https://host/path", "health"],
        vec!["--node", "https://user:pass@host", "health"],
        vec!["--node", "https://host/?query=1", "health"],
        vec!["--timeout", "0", "health"],
        vec!["--timeout", "301", "health"],
        vec!["balance", " "],
        vec!["balance", "bad\nwallet"],
        vec!["unknown"],
    ] {
        let output = binary().args(args).output().unwrap();
        assert_eq!(output.status.code(), Some(2));
    }
    let output = binary().arg("--help").output().unwrap();
    assert!(output.status.success());
    assert!(String::from_utf8_lossy(&output.stdout).contains("balance"));
}

#[test]
fn connection_failure_is_reported() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let origin = format!("http://{}", listener.local_addr().unwrap());
    drop(listener);
    let output = binary()
        .args(["--node", &origin, "--timeout", "1", "health"])
        .env("NO_PROXY", "*")
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
}
