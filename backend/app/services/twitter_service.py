from xdk import Client
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("X_API_KEY")
if key is not None:
    client = Client(bearer_token=key)
else:
    raise ValueError("X_API_KEY environment variable not set")

def get_tweets(query: str):
    tweets = []
    for page in client.posts.search_recent(
        query=f"{query} lang:en min_likes:300 min_reposts:300 min_replies:300 is:verified -is:nullcast"
    ):
        if page.data is None:
            continue
        for post in page.data:
            tweets.append(post.text)
    return tweets