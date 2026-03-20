# BoTTube Video Discoverability - #2159 (20 RTC)

class VideoDiscoverability:
    def __init__(self):
        self.videos = []
    
    def search(self, query):
        return {'query': query, 'results': []}
    
    def get_trending(self, category):
        return {'category': category, 'videos': []}
    
    def get_recommendations(self, user_id):
        return {'user': user_id, 'recommendations': []}

if __name__ == '__main__':
    vd = VideoDiscoverability()
    print(vd.search('test'))
