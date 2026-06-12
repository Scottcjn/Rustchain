use actix_web::{web, HttpResponse, HttpRequest};
use serde::{Serialize, Deserialize};

// Define a struct to hold the wallet balance response
#[derive(Serialize, Deserialize)]
struct WalletBalanceResponse {
    miner_id: String,
    amount_i64: i64,
    amount_rtc: f64,
}

// Define a function to handle the GET /wallet/balance request
async fn get_wallet_balance(req: HttpRequest) -> HttpResponse {
    // Get the miner_id query parameter from the request
    let miner_id = req.match_info().get("miner_id").unwrap_or("");

    // Check if the miner_id contains any whitespace or wildcard characters
    if miner_id.contains(|c: char| !c.is_alphanumeric()) || miner_id.contains('*') {
        // If it does, return a 400 Bad Request response
        return HttpResponse::BadRequest().body("Invalid miner_id");
    }

    // Otherwise, proceed with the original logic to retrieve the wallet balance
    // ...

    // Create a WalletBalanceResponse struct to hold the response data
    let response = WalletBalanceResponse {
        miner_id: miner_id.to_string(),
        amount_i64: 0, // Replace with the actual amount
        amount_rtc: 0.0, // Replace with the actual amount
    };

    // Return the response as JSON
    HttpResponse::Ok().json(response)
}

// Define the route for the GET /wallet/balance request
pub fn routes(cfg: &mut web::ServiceConfig) {
    cfg.route("/wallet/balance", web::get().to(get_wallet_balance));
}