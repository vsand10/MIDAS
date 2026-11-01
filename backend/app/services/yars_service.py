from yars.utils import display_results
from yars.yars import YARS

miner = YARS()

search_results = miner.search_reddit("OpenAI", limit=3)
display_results(search_results, "SEARCH")