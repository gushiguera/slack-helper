import os
import requests
import json
import ssl
import certifi
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from slack_sdk import WebClient

# Determine the configuration mode (default to "dev")
config_mode = os.environ.get("CONFIG_MODE", "dev")

# Load the appropriate .env file
if config_mode == "prod":
    load_dotenv(".env.prod", verbose=True, override=True)
else:
    load_dotenv(".env.dev", verbose=True, override=True)

# Slack configuration
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
SLACK_WORKSPACE_URL = os.environ.get("SLACK_WORKSPACE_URL")

# Emoji triggers
QUESTION_EMOJI_TRIGGER = "bell"  
DONE_EMOJI_TRIGGER = "white_check_mark" if config_mode == "dev" else "light-blue-check"
JOKE_EMOJI_TRIGGER = "socks" 

# Status emojis
IN_PROGRESS_EMOJI = "arrows_counterclockwise" if config_mode == "dev" else "loadingspinner"
JIRA_TICKET_CREATED_EMOJI = "ticket" if config_mode == "dev" else "jira"  

# Google Gemini configuration
GOOGLE_GEMINI_MODEL= "gemini-2.5-flash"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL = ChatGoogleGenerativeAI(
    model=GOOGLE_GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY,
)

# JIRA configuration
DEFAULT_JIRA_PROJECT_KEY = "SLACKHELPER"
JIRA_URL = os.environ.get("JIRA_URL") 
JIRA_USERNAME = os.environ.get("JIRA_USERNAME")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
JIRA_ISSUE_TYPE = "Task"  

# Create an SSL context with the certifi CA bundle
ssl_context = ssl.create_default_context(cafile=certifi.where())
slack_client = WebClient(token=os.environ['SLACK_BOT_TOKEN'], ssl=ssl_context)

app = App(signing_secret=SLACK_SIGNING_SECRET, client=slack_client)

def load_prompts(file_path):
    """Loads prompts from a text file."""
    prompts = {}
    current_key = None
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith("#"):
                # Treat lines starting with '#' as keys
                current_key = line[1:].strip().lower().replace(" ", "_")
                prompts[current_key] = ""
            elif current_key:
                # Append the line to the current key's value
                prompts[current_key] += line + " "
    return prompts

# Load prompts from the text file
PROMPTS = load_prompts("prompts.txt")
SLACK_HELPER_SYSTEM_PROMPT = PROMPTS["slack_helper_system_prompt"]
SLACK_HELPER_SOCK_SYSTEM_PROMPT = PROMPTS["slack_helper_sock_system_prompt"]

def create_jira_title(message_text):
    """Generates a JIRA ticket title using Gemini."""
    prompt = PROMPTS["title_prompt"].format(message_text=message_text)
    messages = [
        SystemMessage(content=SLACK_HELPER_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    response = GEMINI_MODEL.invoke(messages)
    # Remove all newlines and strip leading/trailing whitespace
    return response.content.replace('\n', ' ').strip()

def create_jira_description(message_text, slack_link):
    """Generates a JIRA ticket description using Gemini."""
    prompt = PROMPTS["description_prompt"].format(message_text=message_text, slack_link=slack_link)

    messages = [
        SystemMessage(content=SLACK_HELPER_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    
    response = GEMINI_MODEL.invoke(messages)
    return response.content.strip()

def create_jira_ticket(title, description, project_key):
    """Creates a JIRA ticket in the specified project."""
    url = f"{JIRA_URL}/rest/api/3/issue"
    auth = HTTPBasicAuth(JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {
        "Content-Type": "application/json",
    }
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": title,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": description}
                        ]
                    }
                ]
            },
            "issuetype": {"name": JIRA_ISSUE_TYPE},
        }
    }
    response = requests.post(url, auth=auth, headers=headers, data=json.dumps(payload))
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("Error creating JIRA ticket:", response.content)
        raise e
    return response.json()["key"], f"{JIRA_URL}/browse/{response.json()['key']}"

def add_jira_comment(issue_key, comment):
    """Adds a comment to a JIRA ticket."""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"
    auth = HTTPBasicAuth(JIRA_USERNAME, JIRA_API_TOKEN)  # Use HTTPBasicAuth
    headers = {
        "Content-Type": "application/json",
    }
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": comment}
                    ]
                }
            ]
        }
    }

    response = requests.post(url, auth=auth, headers=headers, data=json.dumps(payload))
    try:
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.HTTPError as e:
        print("Response content:", response.content)  # Debugging: Print the response content
        raise e
    
def add_reaction_to_slack(channel_id, timestamp, emoji):
    """Adds a reaction to a Slack message."""
    try:
        app.client.reactions_add(
            name=emoji,
            channel=channel_id,
            timestamp=timestamp,
        )
    except Exception as e:
        if "already_reacted" in str(e):
            try:
                app.client.reactions_remove(
                    name=emoji,
                    channel=channel_id,
                    timestamp=timestamp,
                )
            except Exception as e:
                if "no_reaction" in str(e):
                    print(f"Reaction '{emoji}' does not exist on message {timestamp} in channel {channel_id}.")
                else:
                    raise
            app.client.reactions_remove(
                name=emoji,
                channel=channel_id,
                timestamp=timestamp,
            )

def remove_reaction_from_slack(channel_id, timestamp, emoji):
    """Removes a reaction from a Slack message."""
    try:
        app.client.reactions_remove(
            name=emoji,
            channel=channel_id,
            timestamp=timestamp,
        )
    except Exception as e:
        print(f"Failed to remove reaction '{emoji}' from message {timestamp} in channel {channel_id}: {e}")

def slack_reply(channel_id, thread_ts, message):
    """Replies to a Slack message."""
    app.client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=message,
    )

def close_jira_ticket(issue_key):
    """Closes a JIRA ticket by transitioning it to the 'Closed' state."""
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions"
    auth = HTTPBasicAuth(JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {
        "Content-Type": "application/json",
    }

    # Get available transitions for the issue
    response = requests.get(url, auth=auth, headers=headers)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("Error fetching transitions:", response.content)
        raise e

    transitions = response.json()["transitions"]
    done_transition = next((t for t in transitions if t["name"].lower() == "done"), None)

    if not done_transition:
        print(f"No 'Close' transition found for issue {issue_key}.")
        return

    # Perform the transition to close the ticket
    payload = {"transition": {"id": done_transition["id"]}}
    response = requests.post(url, auth=auth, headers=headers, data=json.dumps(payload))
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("Error closing ticket:", response.content)
        raise e

    print(f"JIRA ticket {issue_key} has been closed.")

def get_jira_projects():
    """Fetches the list of JIRA projects."""
    url = f"{JIRA_URL}/rest/api/3/project"
    auth = HTTPBasicAuth(JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {
        "Content-Type": "application/json",
    }
    response = requests.get(url, auth=auth, headers=headers)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("Error fetching JIRA projects:", response.content)
        raise e

    projects = response.json()
    return [{"text": {"type": "plain_text", "text": project["name"]}, "value": project["key"]} for project in projects]

@app.event("reaction_added")
def handle_reaction_added(event, say):
    """Handles the reaction_added event."""
    reaction = event["reaction"]
    channel_id = event["item"]["channel"]
    message_ts = event["item"]["ts"]
    
    # Fetch the message text and construct the Slack link
    message_info = app.client.conversations_history(
        channel=channel_id, latest=message_ts, limit=1, inclusive=True
    )
    # Fetch the main message text
    message_text = message_info["messages"][0]["text"]

    # Fetch all messages in the thread if present
    thread_messages = app.client.conversations_replies(
        channel=channel_id, ts=message_ts
    )
    combined_context = message_text  # Start with the main message text
    if "messages" in thread_messages:
        # Combine all messages in the thread
        combined_context = "\n".join(
            [msg["text"] for msg in thread_messages["messages"] if "text" in msg]
        )
    else:
        combined_context = message_text

    # Define reaction handlers
    reaction_handlers = {
        QUESTION_EMOJI_TRIGGER: lambda: handle_bell_reaction(channel_id, message_ts, combined_context),
        DONE_EMOJI_TRIGGER: lambda: handle_check_reaction(event, channel_id, message_ts),
        JOKE_EMOJI_TRIGGER: lambda: handle_socks_reaction(channel_id, message_ts, combined_context),
    }

    # Call the appropriate handler based on the reaction
    handler = reaction_handlers.get(reaction)
    try:
        if handler:
            handler()
    except Exception as e:
        print(f"Error handling reaction {reaction}: {e}")

def create_ticket_workflow(channel_id, message_ts, message_text, project_key):
        """Creates and runs the JIRA ticket creation workflow."""
        slack_link = f"{SLACK_WORKSPACE_URL}/archives/{channel_id}/p{message_ts.replace('.', '')}"

        # Start defining the langgraph workflow
        def generate_title(state):
            title = create_jira_title(state["message_text"])
            print(title)
            state["title"] = title
            return state

        def generate_description(state):
            description = create_jira_description(state["message_text"], slack_link)
            state["description"] = description
            return state

        def create_ticket(state):
            issue_key, issue_link = create_jira_ticket(state["title"], state["description"], project_key)
            state["issue_key"] = issue_key
            state["issue_link"] = issue_link
            return state

        def reply_to_slack(state):
            remove_reaction_from_slack(channel_id, message_ts, "loadingspinner")
            reply_message = f"Slack Helper has created a ticket for you in project *{project_key}*: <{state['issue_link']}|{state['issue_key']}>"
            slack_reply(channel_id, message_ts, reply_message)
            return state

        def add_comment_to_jira(state):
            add_jira_comment(state["issue_key"], "Ticket created by Slack Helper bot.")
            return state

        def add_slack_complete_reaction(state):
            add_reaction_to_slack(channel_id, message_ts, JIRA_TICKET_CREATED_EMOJI)
            return state

        def add_in_progress_reaction(state):
            add_reaction_to_slack(channel_id, message_ts, IN_PROGRESS_EMOJI)
            return state

        def remove_in_progress_reaction(state):
            remove_reaction_from_slack(channel_id, message_ts, IN_PROGRESS_EMOJI)
            return state
        
        workflow = StateGraph(dict)
        workflow.add_node("add_in_progress_reaction", add_in_progress_reaction)
        workflow.add_node("generate_title", generate_title)
        workflow.add_node("generate_description", generate_description)
        workflow.add_node("create_ticket", create_ticket)
        workflow.add_node("reply_to_slack", reply_to_slack)
        workflow.add_node("add_reaction_to_jira", add_comment_to_jira)
        workflow.add_node("add_slack_complete_reaction", add_slack_complete_reaction)
        workflow.add_node("remove_in_progress_reaction", remove_in_progress_reaction)

        workflow.add_edge("add_in_progress_reaction", "generate_title")
        workflow.add_edge("generate_title", "generate_description")
        workflow.add_edge("generate_description", "create_ticket")
        workflow.add_edge("create_ticket", "reply_to_slack")
        workflow.add_edge("reply_to_slack", "add_reaction_to_jira")
        workflow.add_edge("add_reaction_to_jira", "add_slack_complete_reaction")
        workflow.add_edge("add_slack_complete_reaction", "remove_in_progress_reaction")
        
        workflow.set_entry_point("add_in_progress_reaction")

        try:
            app_workflow = workflow.compile()
            app_workflow.invoke({"message_text": message_text})
        except Exception as e:
            if "Error creating JIRA ticket" in str(e):
                print(f"Error creating ticket: {e}")
                error_message = f"Slack Helper couldn't create the ticket: {str(e)}"
                slack_reply(channel_id, message_ts, error_message)
                remove_reaction_from_slack(channel_id, message_ts, IN_PROGRESS_EMOJI)

def handle_bell_reaction(channel_id, message_ts, message_text):
    """Handles the bell reaction (project selection)."""
    channel_info = app.client.conversations_info(channel=channel_id)
    channel_name = channel_info["channel"]["name"]


    if "slack-helper" in channel_name.lower():
        # Directly create the JIRA ticket with the default project
        create_ticket_workflow(channel_id, message_ts, message_text, DEFAULT_JIRA_PROJECT_KEY)
    else:
        # Post a message with a button to select the project
        app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text="Slack Helper is happy! Slack Helper is here to help! Please pick a project for your magical ticket:",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Slack Helper is happy! Slack Helper is here to help! Please pick a project for your magical ticket:"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Choose Project",
                            "emoji": True
                        },
                        "action_id": "select_project",
                        "value": f"{channel_id}|{message_ts}|{message_text}"
                    }
                }
            ]
        )
        remove_reaction_from_slack(channel_id, message_ts, IN_PROGRESS_EMOJI)

def handle_check_reaction(event, channel_id, message_ts):
    """Handles the check reaction (close JIRA ticket)."""
    # Close the JIRA ticket if it finds one in the thread
    issue_key = extract_issue_key_from_message(event)
    if issue_key:
        add_reaction_to_slack(channel_id, message_ts, IN_PROGRESS_EMOJI)
        close_jira_ticket(issue_key)
        reply_message = f"Slack Helper is so happy! Slack Helper has closed the ticket {issue_key} for you!"
        slack_reply(channel_id, message_ts, reply_message)
        remove_reaction_from_slack(channel_id, message_ts, IN_PROGRESS_EMOJI)

def handle_socks_reaction(channel_id, message_ts, message_text):
    """Handles the socks reaction (fetch joke)."""
    # Fetch the sock prompt
    add_reaction_to_slack(channel_id, message_ts, IN_PROGRESS_EMOJI)
    prompt = PROMPTS["sock_prompt"].format(message_text=message_text)
    messages = [
        SystemMessage(content=SLACK_HELPER_SOCK_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]
    response = GEMINI_MODEL.invoke(messages)
    joke = response.content.strip()

    # Reply to the thread with the joke
    slack_reply(channel_id, message_ts, joke)
    remove_reaction_from_slack(channel_id, message_ts, IN_PROGRESS_EMOJI)

@app.view("jira_project_selection")
def handle_project_selection(ack, body, client):
    """Handles the submission of the JIRA project selection modal."""
    ack()  # Acknowledge the modal submission
    
    # Extract metadata parts
    metadata_parts = body["view"]["private_metadata"].split("|")
    channel_id = metadata_parts[0]
    message_ts = metadata_parts[1]
    message_text = metadata_parts[2]

    # Extract the selected project key
    selected_project = body["view"]["state"]["values"]["project_selection"]["project_select_action"]["selected_option"]["value"]
    create_ticket_workflow(channel_id, message_ts, message_text, selected_project)

@app.action("select_project")
def handle_select_project(ack, body, client):
    """Handles the project selection button click."""
    ack()
    
    # Extract the metadata from the button value
    value_parts = body["actions"][0]["value"].split("|")
    channel_id = value_parts[0]
    message_ts = value_parts[1]
    message_text = value_parts[2]
    
    # Now we have a trigger_id from the button click, so we can open a modal
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "jira_project_selection",
            "private_metadata": f"{channel_id}|{message_ts}|{message_text}",
            "title": {"type": "plain_text", "text": "Select JIRA Project"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "project_selection",
                    "element": {
                        "type": "external_select",
                        "action_id": "project_select_action",
                        "placeholder": {"type": "plain_text", "text": "Search for a project"},
                        "min_query_length": 1
                    },
                    "label": {"type": "plain_text", "text": "JIRA Project"},
                }
            ],
            "submit": {"type": "plain_text", "text": "Submit"},
        }
    )

@app.options("project_select_action")
def handle_project_options(ack, body):
    # Get the search query
    query = body.get("value", "").lower()
    
    # Fetch and filter projects based on the query
    url = f"{JIRA_URL}/rest/api/3/project/search?query={query}"
    auth = HTTPBasicAuth(JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {"Content-Type": "application/json"}
    
    response = requests.get(url, auth=auth, headers=headers)
    projects = response.json().get("values", [])
    
    # Convert to Slack options format (max 100)
    options = [
        {
            "text": {"type": "plain_text", "text": project["name"]},
            "value": project["key"]
        }
        for project in projects[:100]
    ]
    
    # Acknowledge with the options
    ack(options=options)

def extract_issue_key_from_message(event):
    """Looks up the thread that was reacted on and finds the JIRA ticket key from the ticket message."""
    import re

    # Fetch the thread messages
    thread_messages = app.client.conversations_replies(
        channel=event["item"]["channel"], ts=event["item"]["ts"]
    )

    # Iterate through the messages in the thread to find the ticket message
    for message in thread_messages["messages"]:
        match = re.search(r"https?://[^\s]+/browse/([A-Z]+-\d+)", message.get("text", ""))
        print(match)
        if match:
            return match.group(1)

    # Return None if no ticket key is found
    return None

if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()