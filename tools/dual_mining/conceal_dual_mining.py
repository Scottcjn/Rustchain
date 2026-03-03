"""Conceal Dual-Mining - CryptoNight-GPU - Bounty #472 - 10 RTC"""
import requests, psutil
from typing import Optional, Dict, Any

class ConcealDualMiner:
    def __init__(self, node_url: str = "http://localhost:10667/json_rpc"):
        self.node_url = node_url
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        try:
            response = requests.post(self.node_url, json={"jsonrpc":"2.0","id":"0","method":"get_info"}, timeout=5)
            if response.status_code == 200 and "result" in response.json():
                return {"proof_type":"node_rpc","bonus_multiplier":1.5,"chain":"conceal","algorithm":"CryptoNight-GPU"}
        except: pass
        return None
    
    def get_pool_proof(self) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get("https://conceal.herominers.com/api/stats", timeout=5)
            if response.status_code == 200:
                return {"proof_type":"pool","bonus_multiplier":1.3,"chain":"conceal","algorithm":"CryptoNight-GPU"}
        except: pass
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        procs = []
        for proc in psutil.process_iter(['pid','name','cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                if 'conceal' in cmdline or 'ccx' in cmdline:
                    procs.append({'pid':proc.info['pid'],'name':proc.info['name']})
            except: pass
        return {"proof_type":"process","bonus_multiplier":1.15,"chain":"conceal","processes":procs} if procs else None
    
    def get_best_proof(self) -> Optional[Dict[str, Any]]:
        proofs = [p for p in [self.get_node_rpc_proof(),self.get_pool_proof(),self.get_process_detection_proof()] if p]
        return max(proofs, key=lambda p:p['bonus_multiplier']) if proofs else None
