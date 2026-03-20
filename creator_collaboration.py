# BoTTube Creator Collaboration - #2161 (25 RTC)

class CreatorCollaboration:
    def __init__(self):
        self.collabs = []
    
    def create_collab(self, creator1, creator2, video_id):
        self.collabs.append({'c1': creator1, 'c2': creator2, 'video': video_id})
        return {'status': 'created', 'creators': [creator1, creator2]}
    
    def list_collabs(self):
        return self.collabs

if __name__ == '__main__':
    cc = CreatorCollaboration()
    cc.create_collab('creator1', 'creator2', 'video1')
    print(cc.list_collabs())
