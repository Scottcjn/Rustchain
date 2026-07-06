mod leaderboard;
mod models;
mod tier;

use actix_web::{web, App, HttpServer, Responder, HttpResponse};
use models::{Contributor, Tier};
use chrono::NaiveDate;
use std::sync::Mutex;

struct AppState {
    contributors: Mutex<Vec<Contributor>>,
}

async fn get_leaderboard(data: web::Data<AppState>) -> impl Responder {
    let contributors = data.contributors.lock().unwrap();
    let entries = leaderboard::build_leaderboard(&contributors);
    HttpResponse::Ok().json(entries)
}

#[derive(serde::Deserialize)]
struct ClaimRequest {
    contributor_id: String,
}

async fn claim_tier(data: web::Data<AppState>, req: web::Json<ClaimRequest>) -> impl Responder {
    let mut contributors = data.contributors.lock().unwrap();
    if let Some(c) = contributors.iter_mut().find(|c| c.id == req.contributor_id) {
        let new_tier = tier::determine_tier(c);
        if new_tier != c.current_tier {
            let bonus = new_tier.bonus();
            c.current_tier = new_tier;
            HttpResponse::Ok().json(serde_json::json!({
                "message": "Tier upgraded",
                "new_tier": format!("{:?}", c.current_tier),
                "bonus": bonus
            }))
        } else {
            HttpResponse::Ok().json(serde_json::json!({
                "message": "No tier change",
                "current_tier": format!("{:?}", c.current_tier)
            }))
        }
    } else {
        HttpResponse::NotFound().json(serde_json::json!({"error": "Contributor not found"}))
    }
}

async fn get_tiers() -> impl Responder {
    let tiers = vec![
        ("Explorer", Tier::Explorer.bonus(), Tier::Explorer.max_bounty()),
        ("Miner", Tier::Miner.bonus(), Tier::Miner.max_bounty()),
        ("Foreman", Tier::Foreman.bonus(), Tier::Foreman.max_bounty()),
        ("Architect", Tier::Architect.bonus(), Tier::Architect.max_bounty()),
        ("Guardian", Tier::Guardian.bonus(), Tier::Guardian.max_bounty()),
    ];
    HttpResponse::Ok().json(tiers)
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let data = AppState {
        contributors: Mutex::new(vec![
            Contributor {
                id: "createkr".into(),
                merged_prs: 26,
                active_since: NaiveDate::from_ymd_opt(2026, 2, 1).unwrap(),
                current_tier: Tier::Foreman,
                reviews_given: 5,
                major_contributions: false,
                security_vuln_found: false,
            },
            Contributor {
                id: "liu971227-sys".into(),
                merged_prs: 23,
                active_since: NaiveDate::from_ymd_opt(2025, 12, 1).unwrap(),
                current_tier: Tier::Foreman,
                reviews_given: 3,
                major_contributions: false,
                security_vuln_found: false,
            },
            Contributor {
                id: "David-code-tang".into(),
                merged_prs: 20,
                active_since: NaiveDate::from_ymd_opt(2026, 2, 1).unwrap(),
                current_tier: Tier::Miner,
                reviews_given: 0,
                major_contributions: false,
                security_vuln_found: false,
            },
            Contributor {
                id: "autonomy414941".into(),
                merged_prs: 7,
                active_since: NaiveDate::from_ymd_opt(2026, 2, 1).unwrap(),
                current_tier: Tier::Miner,
                reviews_given: 0,
                major_contributions: false,
                security_vuln_found: false,
            },
            Contributor {
                id: "erdogan98".into(),
                merged_prs: 5,
                active_since: NaiveDate::from_ymd_opt(2026, 2, 1).unwrap(),
                current_tier: Tier::Miner,
                reviews_given: 0,
                major_contributions: false,
                security_vuln_found: false,
            },
        ]),
    };

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(data.clone()))
            .route("/leaderboard", web::get().to(get_leaderboard))
            .route("/claim-tier", web::post().to(claim_tier))
            .route("/tiers", web::get().to(get_tiers))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}
