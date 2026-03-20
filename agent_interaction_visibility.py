# BoTTube Agent Interaction Visibility - #2158 (20 RTC)

class AgentInteractionVisibility:
    def __init__(self):
        self.activities = []
    
    def add_activity(self, agent_id, action, target):
        self.activities.append({'agent': agent_id, 'action': action, 'target': target})
        return {'status': 'added', 'activity': {'agent': agent_id, 'action': action}}
    
    def get_activity_feed(self, limit=10):
        return self.activities[-limit:]

if __name__ == '__main__':
    aiv = AgentInteractionVisibility()
    aiv.add_activity('agent-1', 'comment', 'video-1')
    print(aiv.get_activity_feed())
