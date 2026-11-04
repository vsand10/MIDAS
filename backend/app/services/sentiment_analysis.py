import torch
from scipy.special import softmax
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Load model and tokenizer
MODEL = "cardiffnlp/twitter-roberta-base-sentiment"
tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSequenceClassification.from_pretrained(MODEL)

# Input text
text = ["I love using Python for data analysis! It's such a versatile language."]
encoded_inputs = []
for entry in text:
    encoded_inputs.append(tokenizer(entry, return_tensors='pt'))

# Inference

for input in encoded_inputs:
    with torch.no_grad():
        output = model(**input)
        scores = output.logits[0].detach().numpy()
        scores = softmax(scores)

print(scores)