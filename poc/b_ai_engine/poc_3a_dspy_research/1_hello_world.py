"""
DSPy Hello World Example
PoC-3a: DSPy 프레임워크 리서치

DSPy의 핵심 개념 검증:
- LM 설정 (OpenAI gpt-5-nano)
- Signature 정의
- Module 사용 (Predict, ChainOfThought)
"""

import os
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

# 스크립트 디렉토리 기준으로 .env 로드
env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found. Please set it in .env.local file.")

    # 1. LM 설정
    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME)
    dspy.configure(lm=lm)

    # 2. Signature 정의 (입출력 선언)
    class Greeting(dspy.Signature):
        """Generate a friendly greeting message."""

        name: str = dspy.InputField(desc="Name of the person to greet")
        greeting: str = dspy.OutputField(desc="A friendly greeting message")

    # 3. 기본 Predict 사용
    print("=== Basic Predict ===")
    predictor = dspy.Predict(Greeting)
    result = predictor(name="World")
    print(f"Greeting: {result.greeting}")

    # 4. ChainOfThought 사용 (추론 과정 포함)
    print("\n=== ChainOfThought ===")
    cot_predictor = dspy.ChainOfThought(Greeting)
    result = cot_predictor(name="OpsNow")
    print(f"Reasoning: {result.reasoning}")
    print(f"Greeting: {result.greeting}")


if __name__ == "__main__":
    main()
