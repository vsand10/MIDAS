import torch
from fastapi import APIRouter, FastAPI
from scipy.special import softmax
from transformers import AutoModelForSequenceClassification, AutoTokenizer

sentiment_app = FastAPI()

# Load model and tokenizer
MODEL = "cardiffnlp/twitter-roberta-base-sentiment"
tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL)

def analyze_sentiments(texts):
    if not texts:
        return None

    sentiments = []
    for text in texts:
        encoded_input = tokenizer(text, return_tensors='pt')
        with torch.no_grad():
            output = model(**encoded_input)
            scores = output.logits[0].detach().numpy()
            scores = softmax(scores)
            sentiments.append(scores)
    res = [0,0,0]
    for sentiment in sentiments:
        res[0] += sentiment[0]
        res[1] += sentiment[1]
        res[2] += sentiment[2]
    res = [x / len(sentiments) for x in res]
    res = [float(x) for x in res]
    res = [round(x, 3) for x in res]
    return res

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])

@router.get("/")
def read_root():
    return {"message": "Welcome to the Sentiment Analysis API!"}

@router.get("/twitter/{query}")
def twitter_analysis(query: str):
    from app.services import twitter_service

    tweets = twitter_service.get_tweets(query)
    if not tweets:
        return {"sentiments": None, "message": "No tweets found"}

    return {"sentiments": analyze_sentiments(tweets)}
