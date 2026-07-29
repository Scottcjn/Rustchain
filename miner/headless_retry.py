import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

class RetryStatus(Enum):
    SUCCESS = "success"
    RETRY = "retry"
    FAILURE = "failure"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"

@dataclass
class RetryConfig:
    max_retries: int = 5
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    jitter: float = 0.1

class HeadlessMinerRetryHandler:
    \"\"\"Manejador de retry con retroceso exponencial para el minero headless.\"\"\"

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(__name__)

    def should_retry(self, response: Dict[str, Any]) -> bool:
        \"\"\"Determina si se debe reintentar basado en la respuesta del servidor.\"\"\"
        status_code = response.get('status_code', 0)
        if status_code in [429, 500, 502, 503, 504]:
            self.logger.warning(f"Transient error {status_code}, retrying...")
            return True
        if response.get('headers_rejected', False):
            self.logger.warning("Headers rejected, retrying...")
            return True
        return False

    def execute_with_retry(self, func, *args, **kwargs) -> Dict[str, Any]:
        \"\"\"Ejecuta una función con retry automático.\"\"\"
        attempt = 0
        delay = self.config.initial_delay

        while attempt < self.config.max_retries:
            try:
                result = func(*args, **kwargs)
                if not self.should_retry(result):
                    return {'status': RetryStatus.SUCCESS, 'data': result}
                server_info = result.get('server_info', {})
                self.logger.info(f"Server diagnostic: {server_info}")

            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                result = {'status': RetryStatus.RETRY, 'error': str(e)}

            attempt += 1
            if attempt >= self.config.max_retries:
                return {'status': RetryStatus.MAX_RETRIES_EXCEEDED, 'attempts': attempt}

            sleep_time = min(delay, self.config.max_delay)
            sleep_time += self.config.jitter * sleep_time
            time.sleep(sleep_time)
            delay *= self.config.backoff_factor

        return {'status': RetryStatus.FAILURE, 'attempts': attempt}
