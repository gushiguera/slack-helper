#!/usr/bin/env python3
"""
Test script for Gemini model integration in ticket-creation.py
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables
load_dotenv(".env.dev", verbose=True, override=True)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_GEMINI_MODEL = "gemini-2.5-flash"

print(f"Testing Gemini model: {GOOGLE_GEMINI_MODEL}")
print(f"API Key present: {'Yes' if GOOGLE_API_KEY else 'No'}")
print(f"API Key starts with: {GOOGLE_API_KEY[:10] if GOOGLE_API_KEY else 'N/A'}...")

# Initialize the model
try:
    gemini_model = ChatGoogleGenerativeAI(
        model=GOOGLE_GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )
    print("✓ Model initialized successfully")
except Exception as e:
    print(f"✗ Failed to initialize model: {e}")
    exit(1)

# Test 1: Simple title generation
print("\n--- Test 1: Title Generation ---")
test_message = "We need to fix the login page because users are getting 500 errors when they try to authenticate with SSO"

system_prompt = "You are Slack Helper, a helpful assistant. You create clear, concise JIRA ticket titles."
title_prompt = f"Create a concise JIRA ticket title (max 100 characters) for this request: {test_message}"

messages = [
    SystemMessage(content=system_prompt),
    HumanMessage(content=title_prompt)
]

try:
    response = gemini_model.invoke(messages)
    title = response.content.replace('\n', ' ').strip()
    print(f"Generated Title: {title}")
    print(f"Title length: {len(title)} characters")
    print("✓ Title generation successful")
except Exception as e:
    print(f"✗ Title generation failed: {e}")
    exit(1)

# Test 2: Description generation
print("\n--- Test 2: Description Generation ---")
slack_link = "https://banno.slack.com/archives/C12345/p1234567890"
description_prompt = f"Create a detailed JIRA ticket description for this request:\n\nSlack thread: {slack_link}\n\nContext: {test_message}"

messages = [
    SystemMessage(content=system_prompt),
    HumanMessage(content=description_prompt)
]

try:
    response = gemini_model.invoke(messages)
    description = response.content.strip()
    print(f"Generated Description:\n{description}")
    print(f"\nDescription length: {len(description)} characters")
    print("✓ Description generation successful")
except Exception as e:
    print(f"✗ Description generation failed: {e}")
    exit(1)

print("\n=== All tests passed! ===")
print(f"Model '{GOOGLE_GEMINI_MODEL}' is working correctly.")
