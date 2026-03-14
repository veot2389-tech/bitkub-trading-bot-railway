import hmac
import hashlib
import time
import json
import logging
import asyncio
import requests
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger("BitkubAsync")

def remove_exponent(d):
    if not isinstance(d, Decimal):
        d = Decimal(str(d))
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()

class BitkubAsyncDriver:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.bitkub.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = requests.Session()

    async def _get_server_time(self) -> int:
        try:
            loop = asyncio.get_event_loop()
            r = await loop.run_in_executor(None, lambda: self.session.get(f"{self.base_url}/api/v3/servertime", timeout=5))
            return int(r.json())
        except Exception as e:
            logger.warning(f"Could not get server time: {e}. Using local time.")
            return int(time.time() * 1000)

    def _sign_payload(self, method: str, path: str, payload: Dict[str, Any], ts: int):
        method = method.upper()
        if method == "GET":
            body_str = ""
            if payload:
                query_parts = [f"{k}={v}" for k, v in payload.items()]
                path = f"{path}?{'&'.join(query_parts)}"
        else:
            clean_payload = {}
            for k, v in payload.items():
                if isinstance(v, (int, float, Decimal)):
                    clean_val = remove_exponent(v)
                    clean_payload[k] = int(clean_val) if clean_val == clean_val.to_integral() else float(clean_val)
                else:
                    clean_payload[k] = v
            body_str = json.dumps(clean_payload, separators=(',', ':'))

        message = f"{ts}{method}{path}{body_str}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return path, body_str, signature

    async def send_request(self, method: str, path: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        if payload is None: payload = {}
        
        loop = asyncio.get_event_loop()
        wait_time = 1
        max_retries = 3
        
        for i in range(max_retries):
            try:
                ts = await self._get_server_time()
                if method.upper() == "POST":
                    payload['ts'] = ts
                    
                final_path, body_str, signature = self._sign_payload(method, path, payload, ts)
                
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-BTK-APIKEY": self.api_key,
                    "X-BTK-TIMESTAMP": str(ts),
                    "X-BTK-SIGN": signature
                }
                
                full_url = f"{self.base_url}{final_path}"
                
                def do_request():
                    if method.upper() == "POST":
                        return self.session.post(full_url, headers=headers, data=body_str, timeout=10)
                    else:
                        return self.session.get(full_url, headers=headers, timeout=10)

                r = await loop.run_in_executor(None, do_request)
                
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 429:
                    await asyncio.sleep(wait_time)
                    wait_time *= 2
                    continue
                else:
                    return {"error": r.status_code, "message": r.text}
                
            except Exception as e:
                logger.error(f"Request error attempt {i+1}: {e}")
                await asyncio.sleep(wait_time)
                wait_time *= 2
        
        return {"error": 999, "message": "Max retries exceeded"}

    def clean_amount(self, amount):
        clean_val = remove_exponent(amount)
        return int(clean_val) if clean_val == clean_val.to_integral() else float(clean_val)

    @staticmethod
    def fix_symbol(symbol: str) -> str:
        if "_" in symbol:
            parts = symbol.lower().split("_")
            if parts[0] == "thb":
                return f"{parts[1]}_thb"
        return symbol.lower()
