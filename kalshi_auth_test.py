import os
import time
import base64
import requests

from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


load_dotenv()

API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")

BASE_URL = "https://external-api.kalshi.com"
PATH = "/trade-api/v2/portfolio/balance"


def load_private_key():
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(),
            password=None
        )


def sign_request(private_key, timestamp, method, path):
    message = f"{timestamp}{method}{path}".encode("utf-8")

    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )

    return base64.b64encode(signature).decode("utf-8")


private_key = load_private_key()

timestamp = str(int(time.time() * 1000))

signature = sign_request(
    private_key,
    timestamp,
    "GET",
    PATH
)

headers = {
    "KALSHI-ACCESS-KEY": API_KEY_ID,
    "KALSHI-ACCESS-SIGNATURE": signature,
    "KALSHI-ACCESS-TIMESTAMP": timestamp,
}

print("Testing authenticated Kalshi REST API...")
print()

response = requests.get(
    BASE_URL + PATH,
    headers=headers,
    timeout=10
)

print("HTTP Status:", response.status_code)
print()
print(response.text)