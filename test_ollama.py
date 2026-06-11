import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3.2:1b",
        "prompt": "Say hello in one sentence",
        "stream": False
    },
    timeout=60
)
print(response.json()["response"])