# RIP-302 Agent Economy - #1646 (100 RTC)
# Agent Economy implementation

class AgentEconomy:
    """Agent Economy for RustChain"""
    
    def __init__(self):
        self.agents = []
        self.transactions = []
    
    def register_agent(self, agent_id, capabilities):
        """Register a new agent"""
        self.agents.append({'id': agent_id, 'capabilities': capabilities})
        return {'status': 'registered', 'agent': agent_id}
    
    def execute_task(self, agent_id, task, reward):
        """Execute a task with reward"""
        self.transactions.append({'agent': agent_id, 'task': task, 'reward': reward})
        return {'status': 'executed', 'agent': agent_id, 'reward': reward}
    
    def get_agents(self):
        """Get all registered agents"""
        return self.agents
    
    def get_transactions(self):
        """Get all transactions"""
        return self.transactions

if __name__ == '__main__':
    economy = AgentEconomy()
    economy.register_agent('agent-1', ['mining', 'trading'])
    economy.execute_task('agent-1', 'mining', 100)
    print(economy.get_agents())
    print(economy.get_transactions())
