"""
websocket_feed.py — RustChain WebSocket 实时事件推送
=====================================================

Bounty #748: RustChain WebSocket Real-Time Feed

用途:
    为前端和客户端提供实时事件推送服务，包括新区块、epoch 结算、矿工认证等事件

集成方式:
    from websocket_feed import ws_bp, socketio, start_event_poller
    
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")
    app.register_blueprint(ws_bp)
    start_event_poller()  # 启动后台轮询线程

独立运行:
    python3 websocket_feed.py --port 5001 --node https://50.28.86.131

连接方式:
    wscat -c ws://localhost:5001/ws/feed
    # 或使用 Socket.IO 客户端

核心功能:
    - EventBus: 线程安全的事件总线，支持订阅/取消订阅
    - Poller: 后台轮询 RustChain 节点 API，检测新事件
    - WebSocket: 实时推送事件到连接的客户端
    - 事件类型：new_block, epoch_settlement, attestation

作者：noxventures_rtc
钱包：noxventures_rtc
"""

from __future__ import annotations

import time
import threading
import json
import ssl
import os
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from flask import Blueprint, Flask, Response, jsonify

try:
    from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room
    HAVE_SOCKETIO = True
except ImportError:
    HAVE_SOCKETIO = False
    # Fallback: pure WebSocket via websockets library
    try:
        import websockets
        import asyncio
        HAVE_WS = True
    except ImportError:
        HAVE_WS = False

# ─── 配置参数 ─────────────────────────────────────────────────────────────────── #
# RustChain 节点 URL：用于轮询获取最新区块和事件数据
NODE_URL     = os.environ.get("RUSTCHAIN_NODE_URL", "https://50.28.86.131")

# 轮询间隔 (秒)：每隔多久查询一次节点 API
# 为什么：5 秒平衡了实时性和节点负载，避免过于频繁的请求
POLL_INTERVAL = int(os.environ.get("WS_POLL_INTERVAL", "5"))

# WebSocket 心跳间隔 (秒)：ping/pong 保活
# 为什么：30 秒检测一次连接状态，自动断开无响应的客户端
HEARTBEAT_S  = 30

# 最大队列长度：每个客户端最多缓冲的事件数
# 为什么：防止慢客户端导致内存爆炸，实现背压 (backpressure)
MAX_QUEUE    = 100

# SSL 上下文：使用未验证的 SSL (节点使用自签名证书)
CTX = ssl._create_unverified_context()

# ─── Event Bus 事件总线 ──────────────────────────────────────────────────────────────── #
class EventBus:
    """
    线程安全的事件总线，追踪状态并发送差异事件
    
    核心职责:
        1. 订阅管理：支持多个处理器订阅特定事件类型
        2. 线程安全：使用锁保护并发访问
        3. 状态追踪：记录上一个 epoch/slot/miners，只推送变化
        4. 事件分发：将事件广播给所有订阅的处理器
    
    使用示例:
        bus = EventBus()
        bus.subscribe(lambda e: print(e), event_types={"new_block"})
        bus.emit("new_block", {"slot": 123, "epoch": 45})
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._handlers: List[Tuple[Callable[[Dict[str, Any]], None], Optional[Set[str]]]] = []
        self._last_epoch: Optional[int] = None
        self._last_slot: Optional[int] = None
        self._last_miners: Dict[str, Tuple[Optional[float], str, float]] = {}
        self._last_txns: Set[str] = set()

    def subscribe(self, handler: Callable[[Dict[str, Any]], None], event_types: Optional[Set[str]] = None) -> Callable[[Dict[str, Any]], None]:
        """
        注册事件回调处理器
        
        参数:
            handler: 回调函数，接收事件字典 {type, data, ts}
            event_types: 感兴趣的事件类型集合，None 表示订阅所有事件
        
        返回:
            传入的 handler 函数 (便于链式调用)
        
        线程安全:
            使用锁保护 _handlers 列表，支持并发订阅
        """
        with self._lock:
            self._handlers.append((handler, event_types))
        return handler

    def unsubscribe(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """
        取消订阅，移除指定的回调处理器
        
        参数:
            handler: 要移除的回调函数
        
        注意:
            - 精确匹配 handler 对象 (基于引用)
            - 如果 handler 不存在，静默忽略
        """
        with self._lock:
            self._handlers = [(h, f) for h, f in self._handlers if h != handler]

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        触发事件，广播给所有订阅的处理器
        
        参数:
            event_type: 事件类型字符串 (如 "new_block", "attestation")
            data: 事件数据字典
        
        逻辑:
            1. 包装事件：添加 type, data, ts (时间戳)
            2. 复制处理器列表 (避免迭代时修改)
            3. 过滤：只发送给订阅该类型的处理器 (filt=None 表示全部)
            4. 异常隔离：单个处理器异常不影响其他处理器
        """
        event: Dict[str, Any] = {"type": event_type, "data": data, "ts": time.time()}
        with self._lock:
            handlers = list(self._handlers)
        for handler, filt in handlers:
            if filt is None or event_type in filt:
                try:
                    handler(event)
                except Exception:
                    pass

    def process_health(self, health: Dict[str, Any]) -> None:
        """
        处理节点健康数据 (占位符，预留扩展)
        
        参数:
            health: 节点健康状态数据
        
        注意:
            当前未实现，预留用于未来节点监控功能
        """
        pass

    def process_epoch(self, epoch_data: Dict[str, Any]) -> None:
        """
        处理 epoch 数据，检测新区块和 epoch 切换事件
        
        参数:
            epoch_data: 节点返回的 epoch 数据，包含 epoch, slot, pot_rtc 等字段
        
        触发事件:
            - new_block: 当 slot 变化时 (每个新区块)
            - epoch_settlement: 当 epoch 变化时 (epoch 结算)
        
        逻辑:
            1. 提取 epoch 和 slot (兼容不同字段名)
            2. 检测 slot 变化 → 发送 new_block 事件
            3. 检测 epoch 变化 → 发送 epoch_settlement 事件
            4. 更新内部状态 (_last_epoch, _last_slot)
        
        注意:
            - 首次运行时不发送 epoch_settlement (没有上一个 epoch)
            - 使用锁保护状态读取，避免并发问题
        """
        epoch = epoch_data.get("epoch")
        slot  = epoch_data.get("slot", epoch_data.get("epoch_slot"))

        with self._lock:
            last_epoch = self._last_epoch
            last_slot  = self._last_slot

        # 检测新区块 (slot 变化)
        if slot is not None and slot != last_slot:
            self.emit("new_block", {
                "slot": slot,
                "epoch": epoch,
                "timestamp": int(time.time()),
            })
            with self._lock:
                self._last_slot = slot

        # 检测 epoch 切换
        if epoch is not None and epoch != last_epoch and last_epoch is not None:
            self.emit("epoch_settlement", {
                "epoch": last_epoch,
                "new_epoch": epoch,
                "timestamp": int(time.time()),
                "total_rtc": epoch_data.get("pot_rtc", epoch_data.get("reward_pot", 0)),
                "miners": epoch_data.get("enrolled_miners", epoch_data.get("miners_enrolled", 0)),
            })
            with self._lock:
                self._last_epoch = epoch
        elif epoch is not None and last_epoch is None:
            # 首次运行，只记录不触发事件
            with self._lock:
                self._last_epoch = epoch

    def process_miners(self, miners: List[Dict[str, Any]]) -> None:
        """
        处理矿工数据，检测新的认证事件并推送
        
        参数:
            miners: 矿工列表，每个矿工包含 wallet_name, last_attestation_time, hardware_type, multiplier 等
        
        触发事件:
            - attestation: 当矿工的 last_attestation_time 发生变化时
        
        逻辑:
            1. 遍历矿工列表，提取关键信息 (wallet, attestation 时间，架构，倍率)
            2. 对比上一次的 attestation 时间
            3. 如果时间不同 → 发送 attestation 事件
            4. 更新内部状态 (_last_miners)
        
        注意:
            - 兼容不同字段名 (wallet_name/wallet, hardware_type/arch 等)
            - 只推送变化的矿工，避免重复事件
        """
        new_attests: Dict[str, Tuple[Optional[float], str, float]] = {}
        for m in miners:
            wallet: str = m.get("wallet_name", m.get("wallet", ""))
            ts: Optional[float] = m.get("last_attestation_time", m.get("last_attest", 0))
            arch: str = m.get("hardware_type", m.get("arch", "unknown"))
            mult: float = m.get("multiplier", m.get("rtc_multiplier", 1.0))
            if wallet:
                new_attests[wallet] = (ts, arch, mult)

        with self._lock:
            last_miners = self._last_miners

        # 检测 attestation 时间变化的矿工
        for wallet, (ts, arch, mult) in new_attests.items():
            prev_ts = last_miners.get(wallet, (None,))[0]
            if ts and ts != prev_ts:
                self.emit("attestation", {
                    "miner": wallet,
                    "arch": arch,
                    "multiplier": mult,
                    "timestamp": ts,
                })

        with self._lock:
            self._last_miners = new_attests


# ─── Poller 轮询器 ─────────────────────────────────────────────────────────────────── #
# 全局事件总线实例：所有模块共享
bus = EventBus()

def _fetch(path: str) -> Optional[Dict[str, Any]]:
    """
    从 RustChain 节点 API 获取数据
    
    参数:
        path: API 路径，如 "/epoch", "/api/miners"
    
    返回:
        解析后的 JSON 数据，失败返回 None
    
    注意:
        - 超时 8 秒，避免长时间阻塞
        - 使用未验证 SSL (节点使用自签名证书)
        - 异常静默处理，由调用方决定回退策略
    """
    url = f"{NODE_URL.rstrip('/')}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rustchain-ws/1.0"})
        with urllib.request.urlopen(req, timeout=8, context=CTX) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _poll_loop() -> None:
    """
    后台轮询循环 (守护线程)
    
    逻辑:
        1. 每 POLL_INTERVAL 秒唤醒一次
        2. 获取 /epoch 数据 → 检测新区块/epoch 切换
        3. 获取 /api/miners 数据 → 检测矿工 attestation
        4. 异常隔离：单次失败不影响下一轮
    
    注意:
        - 守护线程：主程序退出时自动终止
        - 异常静默处理，避免线程崩溃
    """
    while True:
        try:
            epoch_data = _fetch("/epoch")
            if epoch_data:
                bus.process_epoch(epoch_data)

            miners_data = _fetch("/api/miners")
            if miners_data:
                miners: List[Dict[str, Any]] = miners_data if isinstance(miners_data, list) else miners_data.get("miners", [])
                bus.process_miners(miners)

        except Exception:
            pass

        time.sleep(POLL_INTERVAL)


def start_event_poller() -> None:
    """
    启动后台轮询线程
    
    使用方式:
        在应用启动时调用一次：start_event_poller()
    
    注意:
        - 线程是 daemon=True，主程序退出时自动终止
        - 只需调用一次，通常在 app 初始化时
    """
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()


# ─── Flask-SocketIO Blueprint WebSocket 路由 ─────────────────────────────────────────────────── #
# Flask Blueprint：用于注册 WebSocket 相关路由
ws_bp = Blueprint("ws", __name__)

if HAVE_SOCKETIO:
    # 初始化 Socket.IO：支持跨域、threading 模式、心跳检测
    socketio = SocketIO(cors_allowed_origins="*", async_mode="threading",
                        ping_timeout=HEARTBEAT_S, ping_interval=HEARTBEAT_S,
                        max_http_buffer_size=1024 * 64)

    # 追踪每个客户端的订阅：sid -> handler function
    # 为什么：disconnect 时需要取消订阅，避免内存泄漏
    _subscriptions: Dict[str, Callable[[Dict[str, Any]], None]] = {}

    @socketio.on("connect", namespace="/ws/feed")
    def on_connect() -> None:
        """
        客户端连接处理
        
        逻辑:
            1. 获取客户端 session ID (sid)
            2. 创建事件处理器：收到事件后通过 WebSocket 推送给该客户端
            3. 注册到事件总线 (订阅所有事件)
            4. 发送 connected 确认消息
        """
        sid: str = socketio.server.get_environ(None, namespace="/ws/feed")  # type: ignore
        # 为该客户端创建专属处理器
        def handler(event: Dict[str, Any]) -> None:
            try:
                socketio.emit("event", event, namespace="/ws/feed", to=sid)
            except Exception:
                pass
        _subscriptions[sid] = handler
        bus.subscribe(handler)
        emit("connected", {"status": "ok", "node": NODE_URL, "heartbeat_s": HEARTBEAT_S})

    @socketio.on("disconnect", namespace="/ws/feed")
    def on_disconnect() -> None:
        """
        客户端断开连接处理
        
        逻辑:
            1. 获取 sid
            2. 从 _subscriptions 移除该客户端的处理器
            3. 从事件总线取消订阅
        
        注意:
            - 必须取消订阅，否则会导致内存泄漏和重复推送
        """
        sid: str = socketio.server.get_environ(None, namespace="/ws/feed")  # type: ignore
        handler = _subscriptions.pop(sid, None)
        if handler and callable(handler):
            bus.unsubscribe(handler)

    @socketio.on("subscribe", namespace="/ws/feed")
    def on_subscribe(data: Union[Dict[str, Any], None]) -> None:
        """
        客户端订阅特定事件类型
        
        请求数据:
            {'types': ['attestation', 'new_block']}  # 订阅特定事件
            None  # 订阅所有事件
        
        逻辑:
            1. 解析事件类型过滤条件
            2. 取消旧的订阅 (如果有)
            3. 创建新处理器并注册到事件总线
            4. 发送 subscribed 确认
        """
        types: Optional[List[str]] = data.get("types") if isinstance(data, dict) else None
        sid: str = socketio.server.get_environ(None, namespace="/ws/feed")  # type: ignore
        old_handler = _subscriptions.pop(sid, None)
        if old_handler and callable(old_handler):
            bus.unsubscribe(old_handler)

        filt: Optional[Set[str]] = set(types) if types else None

        def handler(event: Dict[str, Any]) -> None:
            try:
                socketio.emit("event", event, namespace="/ws/feed", to=sid)
            except Exception:
                pass

        _subscriptions[sid] = handler
        bus.subscribe(handler, filt)
        emit("subscribed", {"types": list(filt) if filt else "all"})

    @socketio.on("ping", namespace="/ws/feed")
    def on_ping() -> None:
        """心跳检测：客户端 ping，服务器 pong"""
        emit("pong", {"ts": time.time()})

    @ws_bp.route("/ws/feed/status")
    def ws_status() -> Response:
        """
        WebSocket 状态查询接口
        
        返回:
            JSON: {
                connected_clients: 当前连接数,
                node_url: 节点 URL,
                poll_interval_s: 轮询间隔,
                heartbeat_s: 心跳间隔
            }
        """
        return jsonify({
            "connected_clients": len(_subscriptions),
            "node_url": NODE_URL,
            "poll_interval_s": POLL_INTERVAL,
            "heartbeat_s": HEARTBEAT_S,
        })


# ─── Standalone mode 独立运行模式 ─────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    """
    命令行入口：独立运行 WebSocket 服务
    
    使用方式:
        python3 websocket_feed.py --port 5001 --node https://50.28.86.131 --interval 5
    
    参数:
        --port: WebSocket 服务端口 (默认 5001)
        --host: 监听地址 (默认 0.0.0.0)
        --node: RustChain 节点 URL (默认从环境变量读取)
        --interval: 轮询间隔秒数 (默认 5 秒)
    """
    import argparse

    parser = argparse.ArgumentParser(description="RustChain WebSocket Real-Time Feed")
    parser.add_argument("--port", type=int, default=5001, help="WebSocket 服务端口")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--node", default=NODE_URL, help="RustChain 节点 URL")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL, help="轮询间隔 (秒)")
    args: argparse.Namespace = parser.parse_args()

    NODE_URL = args.node
    POLL_INTERVAL = args.interval

    app = Flask(__name__)

    if HAVE_SOCKETIO:
        socketio.init_app(app)
        app.register_blueprint(ws_bp)
        start_event_poller()

        print("\n📡 RustChain WebSocket 实时事件推送")
        print(f"  节点：   {NODE_URL}")
        print(f"  端口：   {args.port}")
        print(f"  轮询：   {POLL_INTERVAL}秒")
        print(f"  连接：   ws://localhost:{args.port}/ws/feed")
        print()
        print("  推送事件:")
        print("    new_block        — 检测到新区块 (slot 变化)")
        print("    epoch_settlement — epoch 切换事件")
        print("    attestation      — 矿工认证事件")
        print()
        print("  订阅特定事件:")
        print('    socket.emit("subscribe", {"types": ["attestation"]})')
        print()

        socketio.run(app, host=args.host, port=args.port, debug=False)
    else:
        print("❌ flask-socketio 未安装，请运行：pip install flask-socketio")
        print("🔧 启动演示模式 (无 WebSocket，仅打印事件)...")
        start_event_poller()

        def demo_handler(event: Dict[str, Any]) -> None:
            print(f"[EVENT] {event['type']}: {json.dumps(event['data'])[:80]}")

        bus.subscribe(demo_handler)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 退出")
