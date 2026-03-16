import requests
import json

class PostPromotion:
    def __init__(self, platform_url: str, post_text: str, image_url: str):
        self.platform_url = platform_url
        self.post_text = post_text
        self.image_url = image_url

    def create_post(self):
        payload = {
            'text': self.post_text,
            'image': self.image_url
        }
        response = requests.post(self.platform_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            print('Post created successfully')
            return response.json()
        else:
            print(f'Failed to create post. Status code: {response.status_code}')
            return None

    def comment_on_post(self, post_id: str, comment_text: str):
        comment_payload = {
            'post_id': post_id,
            'comment': comment_text
        }
        comment_response = requests.post(self.platform_url + '/comment', data=json.dumps(comment_payload), headers={'Content-Type': 'application/json'})
        if comment_response.status_code == 200:
            print('Comment posted successfully')
            return comment_response.json()
        else:
            print(f'Failed to post comment. Status code: {comment_response.status_code}')
            return None