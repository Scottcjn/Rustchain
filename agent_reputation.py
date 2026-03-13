"""
agent_reputation.py — RustChain 代理声誉评分引擎
=================================================

Bounty #754: Agent Reputation Score — On-Chain Trust for Agent Economy
RustChain 代理声誉评分系统，基于链上数据计算代理信任度

核心功能:
    - 声誉分数计算：基于工作完成数、争议、交付速度、总收入等
    - 等级系统：newcomer → known → trusted → veteran，决定可接任务上限
    - 缓存机制：避免频繁查询 DB/API，每 epoch (~1 小时) 自动刷新
    - 衰减机制：30 天无活动扣 1 分，鼓励持续参与
    - Flask API：提供 RESTful 接口查询声誉、检查资格、排行榜

集成方式:
    from agent_reputation import reputation_bp, ReputationEngine
    
    # 初始化引擎 (指定 DB 路径和节点 URL)
    engine = ReputationEngine(db_path="rustchain.db", node_url="https://50.28.86.131")
    
    # 启动后台缓存刷新线程
    engine.start_cache_refresh()
    
    # 注册 Flask Blueprint
    app.register_blueprint(reputation_bp)

独立测试:
    python3 agent_reputation.py --agent noxventures_rtc

API 端点:
    GET /agent/reputation?agent_id=wallet          # 查询声誉分数
    GET /agent/reputation/check-eligibility?agent_id=wallet&job_value=20  # 检查资格
    GET /agent/reputation/leaderboard?limit=20     # 声誉排行榜

作者：noxventures_rtc
钱包：noxventures_rtc
"""

import time
import math
import threading
import sqlite3
import os
import json
import ssl
import urllib.request
from flask import Blueprint, jsonify, request

# ─── 配置参数 ─────────────────────────────────────────────────────────────────── #
# 数据库路径：存储代理工作记录、矿工 attest 等链上数据
DB_PATH       = os.environ.get("RUSTCHAIN_DB_PATH", "rustchain.db")

# RustChain 节点 URL：用于 API 回退查询 (当本地 DB 不可用时)
NODE_URL      = os.environ.get("RUSTCHAIN_NODE_URL", "https://50.28.86.131")

# 缓存 TTL：每 3600 秒 (1 小时，约 1 个 epoch) 刷新一次声誉缓存
# 为什么：避免每次请求都查询 DB/API，提高响应速度；1 小时平衡了实时性和性能
CACHE_TTL_S   = 3600

# 衰减周期：连续 30 天无活动扣 1 分
# 为什么：鼓励代理持续参与，防止"一劳永逸"的声誉积累
DECAY_DAYS    = 30

CTX = ssl._create_unverified_context()

# ─── Reputation Levels ───────────────────────────────────────────────────────── #
LEVELS = [
    (81, "veteran",    "Can post high-value jobs (50+ RTC), priority in disputes"),
    (51, "trusted",    "Can claim any job, can post jobs"),
    (21, "known",      "Can claim jobs up to 25 RTC"),
    ( 0, "newcomer",   "Can claim jobs up to 5 RTC"),
]

MAX_JOB_VALUE = {
    "newcomer": 5,
    "known":    25,
    "trusted":  float("inf"),
    "veteran":  float("inf"),
}

CAN_POST_JOBS       = {"trusted", "veteran"}
CAN_POST_HIGH_VALUE = {"veteran"}


def score_to_level(score: float) -> Tuple[str, str]:
    """
    Convert reputation score to level tier.
    
    Args:
        score: Reputation score value
        
    Returns:
        Tuple of (level_name, level_description)
    """
    for threshold, level, desc in LEVELS:
        if score >= threshold:
            return level, desc
    return "newcomer", LEVELS[-1][2]


# ─── ReputationEngine 声誉引擎 ────────────────────────────────────────────────── #
class ReputationEngine:
    """
    RustChain 代理声誉评分引擎
    
    核心职责:
        1. 计算声誉分数：从 DB 或 API 获取代理工作记录，应用评分公式
        2. 缓存管理：内存缓存计算结果，减少重复查询
        3. 后台刷新：守护线程定期刷新过期缓存
        4. 线程安全：使用锁保护缓存并发访问
    
    使用示例:
        engine = ReputationEngine(db_path="rustchain.db", node_url="https://50.28.86.131")
        engine.start_cache_refresh()  # 启动后台刷新
        result = engine.get("wallet_id")  # 获取声誉 (优先缓存)
    """
    
    def __init__(self, db_path=DB_PATH, node_url=NODE_URL):
        """
        初始化声誉引擎
        
        参数:
            db_path: RustChain SQLite 数据库路径，包含 agent_jobs, miner_attest_recent 等表
            node_url: RustChain 节点 URL，用于 API 回退查询
        
        属性:
            _cache: 内存缓存 {wallet: (score_dict, timestamp)}
            _lock: 线程锁，保护 _cache 并发访问
        """
        self.db_path  = db_path
        self.node_url = node_url
        self._cache   = {}          # wallet -> (score_dict, timestamp)
        self._lock    = threading.Lock()

    # ── DB 助手 ──────────────────────────────────────────────────────────── #
    def _query(self, sql: str, params: Tuple=()) -> List[Dict[str, Any]]:
        """
        执行只读 SQL 查询，返回字典列表
        
        为什么：封装 SQLite 连接、错误处理、结果转换，简化上层调用
        
        参数:
            sql: SQL 查询语句，支持参数化 (? 占位符)
            params: 参数元组，防止 SQL 注入
        
        返回:
            list[dict]: 查询结果，每行转换为字典 {column_name: value}
            如果 DB 不存在或查询失败，返回空列表 (静默失败，不影响业务流程)
        
        注意:
            - 超时 5 秒，避免长时间阻塞
            - row_factory=sqlite3.Row 允许通过列名访问
            - 异常时返回空列表，调用方需处理"无数据"情况
        """
        if not os.path.exists(self.db_path):
            return []
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # ── Node API 请求 ──────────────────────────────────────────────────────── #
    def _fetch(self, path: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """
        向 RustChain 节点发送 HTTP GET 请求
        
        为什么：当本地 DB 不可用或需要最新链上数据时，通过 API 回退查询
        
        参数:
            path: API 路径，如 "/agent/jobs?worker_wallet=xxx"
        
        返回:
            dict|list|None: 解析后的 JSON 响应，失败返回 None
        
        注意:
            - 使用未验证 SSL 上下文 (CTX)，因为节点使用自签名证书
            - 超时 8 秒，避免长时间阻塞
            - 异常静默处理，返回 None 由调用方决定回退策略
        """
        url = f"{self.node_url.rstrip('/')}{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rustchain-reputation/1.0"})
            with urllib.request.urlopen(req, timeout=8, context=CTX) as r:
                return json.loads(r.read().decode())
        except Exception:
            return None

    # ── 声誉计算核心 ──────────────────────────────────────────────── #
    def calculate(self, wallet: str) -> dict:
        """
        计算代理声誉分数 (核心方法)
        
        评分公式:
            基础分 = 完成工作数×10 + 接受工作数×5 - 争议数×15
            交付速度bonus = 0-5 分 (平均<1h=5 分，<4h=4 分，<12h=3 分，<24h=2 分，<72h=1 分)
            总收入 bonus = floor(总 RTC/10)
            账户年龄 bonus = floor(账户天数/30)
            硬件认证 bonus = +10 分 (如果矿工 attest)
            衰减 = floor(无活动天数/30)
            最终分 = max(0, 基础分 + bonus - 衰减)
        
        参数:
            wallet: 代理钱包地址
        
        返回:
            dict: 包含声誉分数、等级、详细统计信息
        
        数据源优先级:
            1. 本地 SQLite DB (快速，离线可用)
            2. Node API (回退，需要网络)
        """
        now = time.time()

        # ── 步骤 1: 收集工作数据 (DB 优先，API 回退) ───────────────────────────────────────── #
        # 初始化统计计数器
        jobs_completed = 0      # 完成的工作数 (delivered/accepted/completed)
        jobs_accepted  = 0      # 被接受的工作数 (雇主确认满意)
        jobs_disputed  = 0      # 争议/拒绝的工作数 (扣分项)
        total_earned   = 0.0    # 累计收入 RTC
        delivery_hours = []     # 每次交付用时 (小时)，用于计算速度 bonus
        first_job_ts   = None   # 第一次工作时间，用于计算账户年龄
        
        # 优先从 DB 查询 (本地数据，快速)
        job_rows = self._query(
            """SELECT status, reward_rtc, claimed_at, completed_at, rejection_reason
               FROM agent_jobs
               WHERE worker_wallet = ?""",
            (wallet,)
        )

        if job_rows:
            # DB 有数据，逐行处理
            for row in job_rows:
                status = row.get("status", "")
                reward = float(row.get("reward_rtc", 0) or 0)
                claimed_at   = row.get("claimed_at")
                completed_at = row.get("completed_at")

                # 完成的工作：增加计数和收入
                if status in ("delivered", "accepted", "completed"):
                    jobs_completed += 1
                    total_earned   += reward
                    # 计算交付用时 (小时)，最少 0.1h 避免除零
                    if claimed_at and completed_at:
                        hours = (float(completed_at) - float(claimed_at)) / 3600
                        delivery_hours.append(max(0.1, hours))
                    # 更新第一次工作时间 (取最早)
                    if first_job_ts is None or (claimed_at and float(claimed_at) < first_job_ts):
                        first_job_ts = float(claimed_at) if claimed_at else None

                # 被接受的工作：额外加分 (雇主确认满意)
                if status == "accepted":
                    jobs_accepted += 1

                # 争议/拒绝的工作：扣分 (质量差或纠纷)
                if status in ("rejected", "disputed") or row.get("rejection_reason"):
                    jobs_disputed += 1
        else:
            # DB 无数据，回退到 Node API (网络请求，较慢)
            api_data = self._fetch(f"/agent/jobs?worker_wallet={wallet}&limit=200")
            if api_data and isinstance(api_data, dict):
                for job in api_data.get("jobs", []):
                    status = job.get("status", "")
                    reward = float(job.get("reward_rtc", 0) or 0)
                    claimed_at   = job.get("claimed_at")
                    completed_at = job.get("completed_at")

                    # 处理逻辑与 DB 相同
                    if status in ("delivered", "accepted", "completed"):
                        jobs_completed += 1
                        total_earned   += reward
                        if claimed_at and completed_at:
                            hours = (float(completed_at) - float(claimed_at)) / 3600
                            delivery_hours.append(max(0.1, hours))
                        if first_job_ts is None or (claimed_at and float(claimed_at) < first_job_ts):
                            first_job_ts = float(claimed_at) if claimed_at else None

                    if status == "accepted":
                        jobs_accepted += 1
                    if status in ("rejected", "disputed"):
                        jobs_disputed += 1

        # ── 步骤 2: 硬件认证检查 ─────────────────────────────────────────────── #
        # 为什么：验证代理是否运行真实硬件 (矿工 attest)，+10 分 bonus
        hardware_verified = False
        
        # 先查 DB
        attest_rows = self._query(
            "SELECT wallet_name, created_at FROM miner_attest_recent WHERE wallet_name = ? LIMIT 1",
            (wallet,)
        )
        if attest_rows:
            hardware_verified = True
        else:
            # DB 无记录，尝试 API /api/miners
            miners_data = self._fetch("/api/miners")
            if miners_data:
                miners = miners_data if isinstance(miners_data, list) else miners_data.get("miners", [])
                for m in miners:
                    if m.get("wallet_name") == wallet or m.get("wallet") == wallet:
                        hardware_verified = True
                        break

        # ── 步骤 3: 账户年龄计算 ──────────────────────────────────────────────── #
        # 为什么：长期参与的代理更可信，每 30 天 +1 分
        account_age_days = 0
        if first_job_ts:
            account_age_days = (now - first_job_ts) / 86400  # 秒转天

        # 检查矿工表是否有更早的活动记录 (可能先挖矿后接任务)
        miner_rows = self._query(
            "SELECT MIN(created_at) as first_seen FROM miner_attest_recent WHERE wallet_name = ?",
            (wallet,)
        )
        if miner_rows and miner_rows[0].get("first_seen"):
            miner_age = (now - float(miner_rows[0]["first_seen"])) / 86400
            account_age_days = max(account_age_days, miner_age)  # 取最大值

        # ── 步骤 4: 最后活跃度 (用于衰减计算) ─────────────────────────────────────────── #
        # 为什么：长期不活跃的代理扣分，鼓励持续参与
        last_activity_ts = first_job_ts or now
        all_activity = self._query(
            "SELECT MAX(completed_at) as last FROM agent_jobs WHERE worker_wallet = ?",
            (wallet,)
        )
        if all_activity and all_activity[0].get("last"):
            last_activity_ts = float(all_activity[0]["last"])

        # 计算无活动天数
        days_inactive = max(0, (now - last_activity_ts) / 86400)

        # ── 步骤 5: 分数计算 ────────────────────────────────────────────────── #
        score = 0.0

        # 工作分：完成×10 + 接受×5 - 争议×15
        # 为什么：争议扣分重 (×15)，鼓励高质量交付和良好沟通
        score += jobs_completed * 10
        score += jobs_accepted  * 5
        score -= jobs_disputed  * 15

        # 交付速度 bonus：越快分越高，最高 +5 分
        # 为什么：奖励高效代理，但不过度 penalize 复杂任务
        if delivery_hours:
            avg_hours = sum(delivery_hours) / len(delivery_hours)
            if avg_hours < 1:
                score += 5      # <1h: 极快
            elif avg_hours < 4:
                score += 4      # 1-4h: 很快
            elif avg_hours < 12:
                score += 3      # 4-12h: 正常
            elif avg_hours < 24:
                score += 2      # 12-24h: 稍慢
            elif avg_hours < 72:
                score += 1      # 24-72h: 慢

        # 总收入 bonus：每 10 RTC +1 分
        # 为什么：高收入代理通常更活跃、更可靠
        score += math.floor(total_earned / 10)

        # 账户年龄 bonus：每 30 天 +1 分
        # 为什么：长期参与者更值得信任
        score += math.floor(account_age_days / 30)

        # 硬件认证 bonus：+10 分
        # 为什么：运行真实硬件的代理投入更大，更不可能作恶
        if hardware_verified:
            score += 10

        # ── 步骤 6: 衰减 ────────────────────────────────────────────────────────────── #
        # 为什么：每 30 天无活动扣 1 分，防止"一劳永逸"，鼓励持续参与
        decay = math.floor(days_inactive / DECAY_DAYS)
        score = max(0, score - decay)  # 最低 0 分，不出现负数

        # ── 步骤 7: 确定等级 ────────────────────────────────────────────────────────────── #
        score = int(score)
        level, level_desc = score_to_level(score)  # 根据分数映射到等级

        # ── 步骤 8: 构建结果字典 ────────────────────────────────────────────────────────────── #
        result = {
            "agent_id": wallet,                    # 代理钱包
            "reputation_score": score,             # 最终声誉分数
            "level": level,                        # 等级 (newcomer/known/trusted/veteran)
            "level_description": level_desc,       # 等级描述 (权限说明)
            "max_job_value_rtc": MAX_JOB_VALUE[level],  # 可接任务上限
            "can_post_jobs": level in CAN_POST_JOBS,    # 是否可以发布任务
            "can_post_high_value": level in CAN_POST_HIGH_VALUE,  # 是否可以发布高价值任务
            "jobs_completed": jobs_completed,      # 完成工作数
            "jobs_accepted": jobs_accepted,        # 被接受工作数
            "jobs_disputed": jobs_disputed,        # 争议工作数
            "avg_delivery_hours": round(sum(delivery_hours) / len(delivery_hours), 2) if delivery_hours else None,  # 平均交付用时
            "total_earned_rtc": round(total_earned, 4),  # 累计收入
            "account_age_days": round(account_age_days, 1),  # 账户年龄 (天)
            "days_inactive": round(days_inactive, 1),  # 无活动天数
            "decay_applied": decay,                # 应用的衰减分数
            "hardware_verified": hardware_verified,  # 是否硬件认证
            "calculated_at": now,                  # 计算时间戳
        }

        return result

    # ── 缓存层 ──────────────────────────────────────────────────────────── #
    def get(self, wallet: str) -> dict:
        """
        获取代理声誉 (优先缓存)
        
        逻辑:
            1. 检查缓存是否存在且未过期 (TTL=3600s)
            2. 如果有效，返回缓存数据 (标注 cached=True)
            3. 否则重新计算，更新缓存，返回结果
        
        为什么:
            - 减少 DB/API 查询，提高响应速度
            - 1 小时 TTL 平衡实时性和性能
            - 线程安全：使用锁保护并发访问
        
        参数:
            wallet: 代理钱包
        
        返回:
            dict: 声誉数据，包含 cached 字段标识是否命中缓存
        """
        with self._lock:
            if wallet in self._cache:
                data, ts = self._cache[wallet]
                if time.time() - ts < CACHE_TTL_S:
                    return {**data, "cached": True}  # 缓存命中
        # 缓存未命中或过期，重新计算
        result = self.calculate(wallet)
        with self._lock:
            self._cache[wallet] = (result, time.time())  # 更新缓存
        return result

    def invalidate(self, wallet: str = None):
        """
        使缓存失效
        
        参数:
            wallet: 指定钱包 (可选)
                - 如果提供：仅清除该钱包的缓存
                - 如果 None：清除所有缓存
        
        使用场景:
            - 代理完成新工作后，主动刷新声誉
            - 系统维护或数据修复后
        """
        with self._lock:
            if wallet:
                self._cache.pop(wallet, None)
            else:
                self._cache.clear()

    def _refresh_loop(self):
        """
        后台缓存刷新循环 (守护线程)
        
        逻辑:
            1. 每 CACHE_TTL_S (3600s) 唤醒一次
            2. 找出所有过期的缓存条目
            3. 重新计算并更新缓存
        
        为什么:
            - 主动刷新而非被动等待，提高首次访问速度
            - 只刷新过期条目，节省资源
            - 守护线程：程序退出时自动终止
        """
        while True:
            time.sleep(CACHE_TTL_S)  # 等待 1 小时
            with self._lock:
                # 找出过期条目
                stale = [w for w, (_, ts) in self._cache.items()
                         if time.time() - ts > CACHE_TTL_S]
            # 重新计算并更新
            for w in stale:
                self.calculate(w)
                with self._lock:
                    if w in self._cache:
                        self._cache[w] = (self._cache[w][0], time.time())

    def start_cache_refresh(self):
        """
        启动后台缓存刷新线程
        
        使用示例:
            engine = ReputationEngine(...)
            engine.start_cache_refresh()  # 应用启动时调用一次
        
        注意:
            - 线程是 daemon=True，主程序退出时自动终止
            - 只需调用一次，通常在应用初始化时
        """
        t = threading.Thread(target=self._refresh_loop, daemon=True)
        t.start()


# ─── Global engine instance (override in app init) ──────────────────────────── #
_engine = ReputationEngine()


# ─── Flask Blueprint ─────────────────────────────────────────────────────────── #
reputation_bp = Blueprint("reputation", __name__)


@reputation_bp.route("/agent/reputation")
def get_reputation() -> Response:
    """
    GET /agent/reputation?agent_id=my-wallet
    
    查询代理声誉分数和等级
    
    查询参数:
        agent_id (required): 代理钱包地址
    
    返回:
        JSON: 声誉数据 (包含 score, level, max_job_value 等)
        cached (optional): True 表示命中缓存，False 表示重新计算
    
    示例:
        curl "http://localhost:5000/agent/reputation?agent_id=noxventures_rtc"
    
    错误:
        400: 缺少 agent_id 参数
    """
    agent_id = request.args.get("agent_id", "").strip()
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400

    result = _engine.get(agent_id)
    return jsonify(result)


@reputation_bp.route("/agent/reputation/check-eligibility")
def check_eligibility() -> Response:
    """
    GET /agent/reputation/check-eligibility?agent_id=wallet&job_value=20
    
    检查代理是否有资格接指定价值的工作
    
    查询参数:
        agent_id (required): 代理钱包地址
        job_value (required): 工作价值 (RTC)
    
    返回:
        JSON: {
            eligible: bool,          # 是否有资格
            reason: str|null,        # 拒绝原因 (如果有)
            reputation_score: int,   # 当前声誉分数
            level: str,              # 当前等级
            max_job_value_rtc: float # 该等级可接上限
        }
    
    业务逻辑:
        newcomer: ≤5 RTC
        known:    ≤25 RTC
        trusted:  无上限
        veteran:  无上限
    
    示例:
        curl "http://localhost:5000/agent/reputation/check-eligibility?agent_id=xxx&job_value=20"
    """
    agent_id  = request.args.get("agent_id", "").strip()
    job_value = float(request.args.get("job_value", 0))

    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400

    rep = _engine.get(agent_id)
    max_val = rep["max_job_value_rtc"]
    eligible = job_value <= max_val

    return jsonify({
        "agent_id": agent_id,
        "job_value_rtc": job_value,
        "eligible": eligible,
        "reputation_score": rep["reputation_score"],
        "level": rep["level"],
        "max_job_value_rtc": max_val,
        "reason": None if eligible else f"{rep['level']} level agents can only claim jobs up to {max_val} RTC",
    })


@reputation_bp.route("/agent/reputation/leaderboard")
def leaderboard() -> Response:
    """
    GET /agent/reputation/leaderboard?limit=20
    Returns top agents by reputation (from cache).
    
    Returns:
        JSON: Leaderboard with ranked agents by reputation score
    """
    limit = min(int(request.args.get("limit", 20)), 100)
    with _engine._lock:
        entries = [(w, d["reputation_score"]) for w, (d, _) in _engine._cache.items()]
    entries.sort(key=lambda x: x[1], reverse=True)
    return jsonify({
        "leaderboard": [
            {"rank": i + 1, "agent_id": w, "score": s}
            for i, (w, s) in enumerate(entries[:limit])
        ],
        "total_agents_tracked": len(entries),
    })


# ─── CLI / 独立运行 ─────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    """
    命令行工具：查询代理声誉
    
    使用示例:
        python3 agent_reputation.py --agent noxventures_rtc
        python3 agent_reputation.py --agent xxx --db /path/to/rustchain.db --node https://50.28.86.131
    
    参数:
        --agent (required): 代理钱包地址
        --db (optional): 数据库路径，默认 rustchain.db
        --node (optional): 节点 URL，默认 https://50.28.86.131
    
    输出:
        格式化打印声誉详情 (分数、等级、统计信息等)
    """
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Agent Reputation Engine")
    parser.add_argument("--agent", required=True, help="代理钱包地址 (required)")
    parser.add_argument("--db", default=DB_PATH, help="数据库路径，默认 rustchain.db")
    parser.add_argument("--node", default=NODE_URL, help="节点 URL，默认 https://50.28.86.131")
    args = parser.parse_args()

    # 创建引擎实例 (使用命令行参数)
    engine = ReputationEngine(db_path=args.db, node_url=args.node)
    result = engine.calculate(args.agent)

    # 格式化输出
    print(f"\n{'='*50}")
    print(f"代理声誉报告：{result['agent_id']}")
    print(f"{'='*50}")
    print(f"  声誉分数：      {result['reputation_score']} 分")
    print(f"  等级：          {result['level'].upper()} — {result['level_description']}")
    print(f"  可接任务上限：  {result['max_job_value_rtc']} RTC")
    print(f"  可发布任务：    {'✓' if result['can_post_jobs'] else '✗'}")
    print(f"")
    print(f"  完成工作：      {result['jobs_completed']}")
    print(f"  被接受工作：    {result['jobs_accepted']}")
    print(f"  争议工作：      {result['jobs_disputed']}")
    if result['avg_delivery_hours']:
        print(f"  平均交付用时：  {result['avg_delivery_hours']} 小时")
    print(f"  累计收入：      {result['total_earned_rtc']} RTC")
    print(f"  账户年龄：      {result['account_age_days']} 天")
    print(f"  无活动天数：    {result['days_inactive']} 天")
    print(f"  衰减扣分：      -{result['decay_applied']} 分")
    print(f"  硬件认证：      {'✓' if result['hardware_verified'] else '✗'}")
    print()
