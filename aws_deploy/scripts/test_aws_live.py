"""Kiểm tra Bedrock thật khi người dùng chủ động chạy script."""

import os
import time

import boto3


def main():
    """Gọi Nova một lần và in thời gian phản hồi."""
    region = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1")
    model = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")
    client = boto3.client("bedrock-runtime", region_name=region)
    started = time.perf_counter()
    result = client.converse(
        modelId=model,
        messages=[{"role": "user", "content": [{"text": "Trả lời: OK"}]}],
        inferenceConfig={"maxTokens": 32, "temperature": 0},
    )
    print("Region:", region, "model:", model)
    print("Elapsed seconds:", round(time.perf_counter() - started, 2))
    print("Response:", result["output"]["message"]["content"][0]["text"])


if __name__ == "__main__":
    main()
