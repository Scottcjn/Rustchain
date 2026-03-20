# RustChain Tools & Features - #1656 (100 RTC)
# Build RustChain tools and features

class RustChainTools:
    """RustChain tools and features"""
    
    def __init__(self):
        self.tools = []
        self.features = []
    
    def add_tool(self, name, description):
        """Add a new tool"""
        self.tools.append({'name': name, 'description': description})
        return {'status': 'added', 'tool': name}
    
    def add_feature(self, name, description):
        """Add a new feature"""
        self.features.append({'name': name, 'description': description})
        return {'status': 'added', 'feature': name}
    
    def list_tools(self):
        """List all tools"""
        return self.tools
    
    def list_features(self):
        """List all features"""
        return self.features

if __name__ == '__main__':
    tools = RustChainTools()
    tools.add_tool('Miner', 'RustChain miner')
    tools.add_feature('Staking', 'RTC staking')
    print(tools.list_tools())
    print(tools.list_features())
