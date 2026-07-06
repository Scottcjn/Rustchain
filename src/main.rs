use std::io::{self, BufRead};
use rustchain_bonus::models::*;
use rustchain_bonus::BonusProgram;

fn main() {
    let mut program = BonusProgram::new();
    println!("RustChain Welcome Bonus Program CLI");
    println!("Enter claims in JSON format. Type 'exit' to quit.");

    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = line.unwrap();
        if line.trim() == "exit" {
            break;
        }
        match serde_json::from_str::<Claim>(&line) {
            Ok(claim) => {
                let result = program.process_claim(claim);
                println!("{}", serde_json::to_string(&result).unwrap());
            }
            Err(e) => {
                eprintln!("Invalid claim JSON: {}", e);
            }
        }
    }
}
