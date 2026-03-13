#!/usr/bin/env python3
"""
Beacon Dashboard v1.1 for RustChain
A real-time dashboard for monitoring RustChain beacon nodes
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BeaconDashboard:
    """Beacon Node Dashboard Manager"""
    
    def __init__(self):
        self.app = web.Application()
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_get('/api/nodes', self.handle_nodes)
        self.app.router.add_static('/static', Path(__file__).parent / 'static')
        self.beacon_nodes: Dict[str, dict] = {}
        
    async def handle_index(self, request):
        """Serve the main dashboard page"""
        content = Path(__file__).parent / 'beacon_dashboard.html'
        if content.exists():
            return web.FileResponse(content)
        return web.Response(text="Beacon Dashboard v1.1 - Loading...", content_type='text/html')
    
    async def handle_status(self, request):
        """API endpoint for overall status"""
        status = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_nodes': len(self.beacon_nodes),
            'active_nodes': sum(1 for n in self.beacon_nodes.values() if n.get('active')),
            'version': '1.1'
        }
        return web.json_response(status)
    
    async def handle_nodes(self, request):
        """API endpoint for node details"""
        return web.json_response({'nodes': list(self.beacon_nodes.values())})
    
    def run(self, host='0.0.0.0', port=8080):
        """Start the dashboard server"""
        logger.info(f"Starting Beacon Dashboard v1.1 on {host}:{port}")
        web.run_app(self.app, host=host, port=port)


if __name__ == '__main__':
    dashboard = BeaconDashboard()
    dashboard.run()
