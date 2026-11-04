import torch
from fastapi import FastAPI
from scipy.special import softmax
from transformers import AutoModelForSequenceClassification, AutoTokenizer

sentiment_app = FastAPI()

# Load model and tokenizer
MODEL = "cardiffnlp/twitter-roberta-base-sentiment"
tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL)

def analyze_sentiments(texts):
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

@sentiment_app.get("/")
def read_root():
    return {"message": "Welcome to the Sentiment Analysis API!"}

@sentiment_app.get("/sentiment/twitter/{query}")
def twitter_analysis(query: str):
    import twitter_service
    tweets = twitter_service.get_tweets(query)
    sentiments = analyze_sentiments(tweets)
    return {"sentiments": sentiments}

def main():
    sentiments = twitter_analysis("OpenAI")
    print("Sentiment scores (negative, neutral, positive):", sentiments)

if __name__ == "__main__":
    main()  