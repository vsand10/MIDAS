from yars.yars import YARS
from yars.utils import display_results

miner = YARS()

search_results = miner.search_reddit("OpenAI", limit=3)
display_results(search_results, "SEARCH")