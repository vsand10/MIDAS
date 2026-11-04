import os

from dotenv import load_dotenv
from xdk import Client

load_dotenv()
key = os.getenv("X_API_KEY")
if key is not None:
    client = Client(bearer_token=key)
else:
    raise ValueError("X_API_KEY environment variable not set")

def get_tweets(query: str):
    tweets = []
    for page in client.posts.search_recent(
        query=f"({query}) lang:en min_likes:1000 min_reposts:200 min_replies:100 is:verified -is:nullcast"
    ):
        if page.data is None:
            continue
        for post in page.data:
            tweets.append(post.text)
    return tweets