'use client';

import React, { useState, useEffect, useCallback } from 'react';

// Types
interface MinerStats {
  hashrate: number;
  hashrateUnit: string;
  rewards: number;
  rewardsUnit: string;
  uptime: number;
  uptimeUnit: string;
  blocksMined: number;
  lastBlockTime: string;
}

interface RewardHistory {
  timestamp: string;
  amount: number;
  blockHeight: number;
}

interface HardwareInfo {
  cpu: string;
  cpuCores: number;
  cpuUsage: number;
  memory: string;
  memoryUsage: number;
  os: string;
  gpu?: string;
  temperature: number;
}

// Mock Data
const generateMockStats = (): MinerStats => ({
  hashrate: Math.floor(Math.random() * 500 + 100),
  hashrateUnit: 'H/s',
  rewards: parseFloat((Math.random() * 50 + 10).toFixed(4)),
  rewardsUnit: 'RTC',
  uptime: Math.floor(Math.random() * 720 + 1),
  uptimeUnit: 'hours',
  blocksMined: Math.floor(Math.random() * 25 + 1),
  lastBlockTime: new Date(Date.now() - Math.random() * 3600000).toLocaleString(),
});

const generateMockRewardHistory = (): RewardHistory[] => {
  const history: RewardHistory[] = [];
  const now = Date.now();
  for (let i = 0; i < 14; i++) {
    history.push({
      timestamp: new Date(now - i * 24 * 60 * 60 * 1000).toLocaleDateString(),
      amount: parseFloat((Math.random() * 5 + 0.5).toFixed(4)),
      blockHeight: 1000000 - i * 100,
    });
  }
  return history.reverse();
};

const mockHardwareInfo: HardwareInfo = {
  cpu: 'Intel Core i7-10700K @ 3.80GHz',
  cpuCores: 8,
  cpuUsage: 67,
  memory: '32GB DDR4',
  memoryUsage: 45,
  os: 'Ubuntu 22.04 LTS',
  gpu: 'NVIDIA RTX 3070',
  temperature: 62,
};

// Utility Components
const StatCard: React.FC<{ 
  title: string; 
  value: string | number; 
  unit: string; 
  icon: string;
  trend?: 'up' | 'down' | 'stable';
}> = ({ title, value, unit, icon, trend }) => (
  <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-xl p-6 border border-gray-700 hover:border-orange-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-orange-500/10">
    <div className="flex items-center justify-between mb-3">
      <span className="text-gray-400 text-sm font-medium">{title}</span>
      <span className="text-2xl">{icon}</span>
    </div>
    <div className="flex items-baseline gap-2">
      <span className="text-3xl font-bold text-white">{value}</span>
      <span className="text-gray-400 text-sm">{unit}</span>
      {trend && (
        <span className={`ml-auto text-sm ${trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400'}`}>
          {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
        </span>
      )}
    </div>
  </div>
);

const ProgressBar: React.FC<{ value: number; label: string; color?: string }> = ({ 
  value, 
  label, 
  color = 'bg-orange-500' 
}) => (
  <div className="mb-4">
    <div className="flex justify-between text-sm mb-1">
      <span className="text-gray-400">{label}</span>
      <span className="text-white font-medium">{value}%</span>
    </div>
    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
      <div 
        className={`h-full ${color} transition-all duration-500 ease-out`}
        style={{ width: `${value}%` }}
      />
    </div>
  </div>
);

const RewardChart: React.FC<{ data: RewardHistory[] }> = ({ data }) => {
  const maxAmount = Math.max(...data.map(d => d.amount));
  
  return (
    <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
        <span>📈</span> Reward History (14 Days)
      </h3>
      <div className="flex items-end gap-1 h-48">
        {data.map((item, index) => {
          const height = (item.amount / maxAmount) * 100;
          return (
            <div 
              key={index} 
              className="flex-1 flex flex-col items-center group"
            >
              <div className="w-full relative">
                <div 
                  className="w-full bg-gradient-to-t from-orange-600 to-orange-400 rounded-t-sm transition-all duration-300 group-hover:from-orange-500 group-hover:to-orange-300 cursor-pointer"
                  style={{ height: `${height}%`, minHeight: '4px' }}
                />
                <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-gray-900 px-2 py-1 rounded text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10 border border-gray-600">
                  {item.amount} RTC
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between mt-2 text-xs text-gray-500">
        <span>{data[0]?.timestamp}</span>
        <span>{data[data.length - 1]?.timestamp}</span>
      </div>
    </div>
  );
};

const HardwareCard: React.FC<{ info: HardwareInfo }> = ({ info }) => (
  <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-xl p-6 border border-gray-700">
    <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
      <span>🖥️</span> Hardware Information
    </h3>
    
    <div className="space-y-4">
      {/* CPU */}
      <div className="bg-gray-900/50 rounded-lg p-4">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-2xl">⚡</span>
          <div>
            <p className="text-white font-medium">{info.cpu}</p>
            <p className="text-gray-400 text-sm">{info.cpuCores} Cores</p>
          </div>
        </div>
        <ProgressBar value={info.cpuUsage} label="CPU Usage" color="bg-blue-500" />
      </div>
      
      {/* Memory */}
      <div className="bg-gray-900/50 rounded-lg p-4">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-2xl">💾</span>
          <div>
            <p className="text-white font-medium">{info.memory}</p>
          </div>
        </div>
        <ProgressBar value={info.memoryUsage} label="Memory Usage" color="bg-purple-500" />
      </div>
      
      {/* GPU (if available) */}
      {info.gpu && (
        <div className="bg-gray-900/50 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎮</span>
            <div>
              <p className="text-white font-medium">{info.gpu}</p>
              <p className="text-gray-400 text-sm">GPU Acceleration</p>
            </div>
          </div>
        </div>
      )}
      
      {/* OS & Temperature */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-900/50 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🐧</span>
            <div>
              <p className="text-gray-400 text-xs">Operating System</p>
              <p className="text-white text-sm font-medium">{info.os}</p>
            </div>
          </div>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🌡️</span>
            <div>
              <p className="text-gray-400 text-xs">Temperature</p>
              <p className={`text-sm font-medium ${info.temperature > 80 ? 'text-red-400' : info.temperature > 60 ? 'text-yellow-400' : 'text-green-400'}`}>
                {info.temperature}°C
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// Main Component
const MinerDashboard: React.FC = () => {
  const [stats, setStats] = useState<MinerStats>(generateMockStats());
  const [rewardHistory, setRewardHistory] = useState<RewardHistory[]>(generateMockRewardHistory());
  const [hardwareInfo] = useState<HardwareInfo>(mockHardwareInfo);
  const [isConnected, setIsConnected] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [isLoading, setIsLoading] = useState(false);

  // Fetch updated stats (simulated)
  const fetchStats = useCallback(async () => {
    setIsLoading(true);
    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 500));
    setStats(generateMockStats());
    setLastUpdate(new Date());
    setIsConnected(true);
    setIsLoading(false);
  }, []);

  // Polling every 30 seconds
  useEffect(() => {
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  // Connection status indicator
  const ConnectionStatus: React.FC = () => (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
      <span className="text-sm text-gray-400">
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
      {isLoading && (
        <span className="text-sm text-orange-400 animate-pulse">Updating...</span>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-orange-400 to-red-500 bg-clip-text text-transparent">
              RustChain Miner Dashboard
            </h1>
            <p className="text-gray-400 mt-1">Real-time mining statistics and performance</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <ConnectionStatus />
            <button 
              onClick={fetchStats}
              disabled={isLoading}
              className="px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-gray-600 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            >
              <span className={isLoading ? 'animate-spin' : ''}>🔄</span>
              Refresh Now
            </button>
            <span className="text-xs text-gray-500">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard 
            title="Hashrate" 
            value={stats.hashrate} 
            unit={stats.hashrateUnit}
            icon="⛏️"
            trend="up"
          />
          <StatCard 
            title="Total Rewards" 
            value={stats.rewards.toFixed(4)} 
            unit={stats.rewardsUnit}
            icon="💎"
            trend="up"
          />
          <StatCard 
            title="Uptime" 
            value={stats.uptime} 
            unit={stats.uptimeUnit}
            icon="⏱️"
            trend="stable"
          />
          <StatCard 
            title="Blocks Mined" 
            value={stats.blocksMined} 
            unit="blocks"
            icon="🧱"
            trend="up"
          />
        </div>

        {/* Last Block Info */}
        <div className="bg-gradient-to-r from-orange-500/10 to-red-500/10 border border-orange-500/30 rounded-xl p-4 mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🎉</span>
              <div>
                <p className="text-white font-medium">Last Block Mined</p>
                <p className="text-gray-400 text-sm">{stats.lastBlockTime}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-orange-400 font-bold">+{(Math.random() * 2 + 0.5).toFixed(4)} RTC</p>
              <p className="text-gray-400 text-sm">Block Reward</p>
            </div>
          </div>
        </div>

        {/* Charts and Hardware */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RewardChart data={rewardHistory} />
          <HardwareCard info={hardwareInfo} />
        </div>

        {/* Recent Activity */}
        <div className="mt-8 bg-gradient-to-br from-gray-800 to-gray-900 rounded-xl p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <span>📋</span> Recent Activity
          </h3>
          <div className="space-y-3">
            {[
              { action: 'Block mined', reward: '+1.25 RTC', time: '2 min ago', status: 'success' },
              { action: 'Share accepted', reward: '', time: '5 min ago', status: 'success' },
              { action: 'Difficulty adjusted', reward: '', time: '15 min ago', status: 'info' },
              { action: 'Block mined', reward: '+1.18 RTC', time: '32 min ago', status: 'success' },
              { action: 'Connection restored', reward: '', time: '1 hour ago', status: 'warning' },
            ].map((activity, index) => (
              <div 
                key={index}
                className="flex items-center justify-between py-2 border-b border-gray-700/50 last:border-0"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    activity.status === 'success' ? 'bg-green-400' : 
                    activity.status === 'warning' ? 'bg-yellow-400' : 'bg-blue-400'
                  }`} />
                  <span className="text-gray-300">{activity.action}</span>
                </div>
                <div className="flex items-center gap-4">
                  {activity.reward && (
                    <span className="text-green-400 font-medium">{activity.reward}</span>
                  )}
                  <span className="text-gray-500 text-sm">{activity.time}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>RustChain Miner Dashboard v1.0.0 • Issue #501</p>
          <p className="mt-1">Auto-refresh every 30 seconds</p>
        </div>
      </div>
    </div>
  );
};

export default MinerDashboard;
