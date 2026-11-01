
import requests

url = "http://localhost:11434/api/chat"

payload = {
    "model": "llama3.2:1b",
    "messages": [
        {
            "role": "user",
            "content": "What is the capital of France?"
        }
    ],
    "stream": False
}

response = requests.post(url, json=payload, timeout=120)

response.raise_for_status()

data = response.json()

print(data["message"]["content"])
