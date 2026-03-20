# Bounty Bot PRO - #2126 (25 RTC)

class BountyBotPRO:
    def __init__(self):
        self.bounties = []
    
    def add_bounty(self, title, reward):
        self.bounties.append({'title': title, 'reward': reward})
        return {'status': 'added', 'title': title}
    
    def list_bounties(self):
        return self.bounties

if __name__ == '__main__':
    bot = BountyBotPRO()
    bot.add_bounty('Test Bounty', 100)
    print(bot.list_bounties())
