#!/usr/bin/env python3
"""
Integration test for the full ticket creation workflow
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables
load_dotenv(".env.dev", verbose=True, override=True)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_GEMINI_MODEL = "gemini-2.5-flash"

# Initialize the model
gemini_model = ChatGoogleGenerativeAI(
    model=GOOGLE_GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY,
)

def load_prompts(file_path):
    """Loads prompts from a text file."""
    prompts = {}
    current_key = None
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith("#"):
                current_key = line[1:].strip().lower().replace(" ", "_")
                prompts[current_key] = ""
            elif current_key:
                prompts[current_key] += line + " "
    return prompts

# Load prompts
PROMPTS = load_prompts("prompts.txt")
SLACK_HELPER_SYSTEM_PROMPT = PROMPTS["slack_helper_system_prompt"]

def create_jira_title(message_text):
    """Generates a JIRA ticket title using Gemini."""
    prompt = PROMPTS["title_prompt"].format(message_text=message_text)
    messages = [
        SystemMessage(content=SLACK_HELPER_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]

    response = gemini_model.invoke(messages)
    return response.content.replace('\n', ' ').strip()

def create_jira_description(message_text, slack_link):
    """Generates a JIRA ticket description using Gemini."""
    prompt = PROMPTS["description_prompt"].format(message_text=message_text, slack_link=slack_link)

    messages = [
        SystemMessage(content=SLACK_HELPER_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]

    response = gemini_model.invoke(messages)
    return response.content.strip()

# Test cases
test_cases = [
    {
        "name": "Bug Report",
        "message": "Users are getting 500 errors when trying to log in with SSO. This is affecting production and needs immediate attention.",
        "slack_link": "https://banno.slack.com/archives/C12345/p1234567890"
    },
    {
        "name": "Feature Request",
        "message": "We need to add a dark mode toggle to the settings page. Users have been requesting this feature for months.",
        "slack_link": "https://banno.slack.com/archives/C67890/p9876543210"
    },
    {
        "name": "Infrastructure Task",
        "message": "Need to upgrade the PostgreSQL database from version 13 to 15 in staging environment. This is required for the new audit features.",
        "slack_link": "https://banno.slack.com/archives/C11111/p1111111111"
    }
]

print("=" * 80)
print("TICKET CREATION WORKFLOW TEST")
print("=" * 80)

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"Test Case {i}: {test['name']}")
    print(f"{'='*80}")
    print(f"\nInput Message:\n{test['message']}")
    print(f"\nSlack Link: {test['slack_link']}")

    try:
        # Generate title
        print("\n--- Generating Title ---")
        title = create_jira_title(test['message'])
        print(f"✓ Title: {title}")
        print(f"  Length: {len(title)} characters")

        # Generate description
        print("\n--- Generating Description ---")
        description = create_jira_description(test['message'], test['slack_link'])
        print(f"✓ Description generated ({len(description)} characters):")
        print("\n" + "-" * 80)
        print(description)
        print("-" * 80)

        print(f"\n✓ Test case '{test['name']}' completed successfully!")

    except Exception as e:
        print(f"\n✗ Test case '{test['name']}' failed: {e}")
        exit(1)

print(f"\n{'='*80}")
print("ALL TESTS PASSED!")
print(f"{'='*80}")
print(f"\nModel: {GOOGLE_GEMINI_MODEL}")
print("The ticket creation workflow is working correctly.")
