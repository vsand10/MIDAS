from xdk import Client

client = Client(bearer_token="AAAAAAAAAAAAAAAAAAAAALa4AAIAAAAAM1ANZ84OamgVKpokSJUF37T5KLw%3DHbSjPo9C4TMrZtkM1yiDJY9dC32gcy6TvwVjywK7tAdQAbPHDy")

# Search recent Posts
for page in client.posts.search_recent(
    query="(apple OR AAPL) lang:en min_likes:300 min_reposts:300 min_replies:300 is:verified -is:nullcast"
):
    for post in page.data: # type: ignore
        print(post.text)