from .wallet_history import wallet_history_bp

def init_api(app):
    app.register_blueprint(wallet_history_bp)
