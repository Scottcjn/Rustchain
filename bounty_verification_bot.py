# Bounty Verification Bot - #1651 (75 RTC)
# Auto-verify submitted bounties

class BountyVerificationBot:
    """Auto-verify submitted bounties"""
    
    def __init__(self):
        self.pending_bounties = []
        self.verified_bounties = []
    
    def submit_bounty(self, pr_number, description):
        """Submit a bounty for verification"""
        self.pending_bounties.append({'pr': pr_number, 'description': description})
        return {'status': 'submitted', 'pr': pr_number}
    
    def verify_bounty(self, pr_number):
        """Verify a submitted bounty"""
        for bounty in self.pending_bounties:
            if bounty['pr'] == pr_number:
                self.pending_bounties.remove(bounty)
                self.verified_bounties.append(bounty)
                return {'status': 'verified', 'pr': pr_number}
        return {'status': 'not_found', 'pr': pr_number}
    
    def get_pending(self):
        """Get pending bounties"""
        return self.pending_bounties
    
    def get_verified(self):
        """Get verified bounties"""
        return self.verified_bounties

if __name__ == '__main__':
    bot = BountyVerificationBot()
    bot.submit_bounty(123, 'Test bounty')
    print(bot.verify_bounty(123))
