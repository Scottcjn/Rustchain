// Import necessary dependencies
use actix_web::{web, App, HttpServer};

// Define the main function
#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Start the HTTP server
    HttpServer::new(|| {
        App::new()
            .route("/wallet/balance", web::get().to(wallet_balance))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}