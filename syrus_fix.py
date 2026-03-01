import os
import time
import logging
import smtplib
import requests
from email.message import EmailMessage
from typing import Optional, Dict, Any

try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    TwilioClient = None

# @Scottcjn - Review requested: Miner Alert System implementation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Notifier:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.alert_email = os.getenv("ALERT_EMAIL")
        
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_from = os.getenv("TWILIO_FROM_NUMBER")
        self.twilio_to = os.getenv("TWILIO_TO_NUMBER")
        
        self.twilio_client = None
        if TwilioClient and self.twilio_sid and self.twilio_token:
            self.twilio_client = TwilioClient(self.twilio_sid, self.twilio_token)

    def send_alert(self, subject: str, message: str) -> None:
        logging.warning(f"ALERT: {subject} - {message}")
        self._send_email(subject, message)
        self._send_sms(f"{subject}: {message}")

    def _send_email(self, subject: str, body: str) -> None:
        if not all([self.smtp_user, self.smtp_pass, self.alert_email]):
            return
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = subject
            msg['From'] = self.smtp_user
            msg['To'] = self.alert_email
            
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
        except Exception as e:
            logging.error(f"Failed to send email alert: {e}")

    def _send_sms(self, body: str) -> None:
        if not all([self.twilio_client, self.twilio_from, self.twilio_to]):
            return
        try:
            self.twilio_client.messages.create(
                body=body,
                from_=self.twilio_from,
                to=self.twilio_to
            )
        except Exception as e:
            logging.error(f"Failed to send SMS alert: {e}")

class MinerAlertSystem:
    def __init__(self, node_rpc_url: str, wallet_address: str, large_transfer_threshold: float):
        self.node_rpc_url = node_rpc_url
        self.wallet_address = wallet_address
        self.large_transfer_threshold = large_transfer_threshold
        self.notifier = Notifier()
        
        self.is_offline = False
        self.last_balance = self._get_wallet_balance()
        self.consecutive_attestation_failures = 0

    def _rpc_call(self, method: str, params: list) -> Optional[Any]:
        try:
            payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
            response = requests.post(self.node_rpc_url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json().get("result")
        except Exception as e:
            logging.error(f"RPC Call failed: {e}")
            return None

    def _get_wallet_balance(self) -> float:
        result = self._rpc_call("eth_getBalance", [self.wallet_address, "latest"])
        if result is not None:
            return int(result, 16) / 10**18
        return 0.0

    def check_miner_status(self) -> bool:
        result = self._rpc_call("eth_syncing", [])
        currently_offline = result is None
        
        if currently_offline and not self.is_offline:
            self.notifier.send_alert("CRITICAL: Miner Offline", "The miner node is unreachable or offline.")
            self.is_offline = True
        elif not currently_offline and self.is_offline:
            self.notifier.send_alert("RESOLVED: Miner Online", "The miner node is back online.")
            self.is_offline = False
            
        return not currently_offline

    def check_wallet_activity(self) -> None:
        current_balance = self._get_wallet_balance()
        if current_balance == 0.0 and self.last_balance == 0.0:
            return

        diff = current_balance - self.last_balance

        if diff > 0:
            self.notifier.send_alert("INFO: Rewards Received", f"Miner received {diff:.4f} RTC. New balance: {current_balance:.4f} RTC")
        elif diff < 0:
            abs_diff = abs(diff)
            if abs_diff >= self.large_transfer_threshold:
                self.notifier.send_alert(
                    "WARNING: Large Wallet Transfer", 
                    f"A transfer of {abs_diff:.4f} RTC was detected. Remaining balance: {current_balance:.4f} RTC"
                )
                
        self.last_balance = current_balance

    def check_attestation_status(self) -> None:
        result = self._rpc_call("miner_getAttestationStatus", [])
        if result and not result.get("success", True):
            self.consecutive_attestation_failures += 1
            if self.consecutive_attestation_failures >= 3:
                self.notifier.send_alert(
                    "ERROR: Attestation Failure", 
                    f"Miner failed {self.consecutive_attestation_failures} consecutive attestations."
                )
        else:
            if self.consecutive_attestation_failures >= 3:
                self.notifier.send_alert("RESOLVED: Attestations Resumed", "Miner is successfully attesting again.")
            self.consecutive_attestation_failures = 0

    def run(self, interval_seconds: int = 60) -> None:
        logging.info("Starting Miner Alert System...")
        while True:
            try:
                is_online = self.check_miner_status()
                if is_online:
                    self.check_wallet_activity()
                    self.check_attestation_status()
            except Exception as e:
                logging.error(f"Unexpected error in monitoring loop: {e}")
            
            time.sleep(interval_seconds)

if __name__ == "__main__":
    RPC_URL = os.getenv("NODE_RPC_URL", "http://localhost:8545")
    WALLET = os.getenv("MINER_WALLET_ADDRESS", "0x0000000000000000000000000000000000000000")
    THRESHOLD = float(os.getenv("LARGE_TRANSFER_THRESHOLD", "10.0"))
    
    system = MinerAlertSystem(RPC_URL, WALLET, THRESHOLD)
    system.run()