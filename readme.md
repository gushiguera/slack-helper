# Slack Helper

Slack Helper is a Slack-integrated automation tool designed to streamline task management by creating JIRA tickets based on Slack messages. It uses Google Gemini for natural language processing and supports both development and production configurations.

## Features

- **Slack Integration**: React to Slack messages with a specific emoji to trigger ticket creation.
- **JIRA Integration**: Automatically create and manage JIRA tickets, including closing tickets with a reaction.
- **Google Gemini**: Leverages Google Gemini for generating ticket titles and descriptions.
- **Thread Assistant**: `@`-mention the bot in a thread to ask a question. It replies with Gemini and remembers the thread conversation so follow-up questions have continuity.
- **Configurable Environments**: Supports separate configurations for development and production.

---

## Setup

### Prerequisites

1. **Python**: Ensure Python 3.9 or higher is installed.
2. **Slack App**: Create a Slack app with the following scopes:
   - `chat:write`
   - `reactions:write`
   - `channels:history`
   - `app_mentions:read` (for the Thread Assistant)

   Also enable the `app_mention` event subscription so the bot receives `@`-mentions.
3. **JIRA API**: Ensure you have a JIRA account with API access.
4. **Google Gemini API**: Obtain an API key for Google Gemini.

---

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/slack-helper.git
   cd slack-helper
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create environment files:
   - `.env.dev` for development
   - `.env.prod` for production

   Example `.env` file:
   ```plaintext
   SLACK_BOT_TOKEN=your-slack-bot-token
   SLACK_SIGNING_SECRET=your-slack-signing-secret
   SLACK_APP_TOKEN=your-slack-app-token
   SLACK_WORKSPACE_URL=https://your-workspace.slack.com
   GOOGLE_API_KEY=your-google-api-key
   JIRA_URL=https://your-jira-instance.atlassian.net
   JIRA_USERNAME=your-jira-username
   JIRA_API_TOKEN=your-jira-api-token
   ```

---

### Usage

1. **Run the Bot**:
   - For development:
     ```bash
     CONFIG_MODE=dev python ticket-creation.py
     ```
   - For production:
     ```bash
     CONFIG_MODE=prod python ticket-creation.py
     ```

2. **Trigger Ticket Creation**:
   - React to a Slack message with the `:bell:` emoji (or your configured emoji) to create a JIRA ticket.

3. **Close a Ticket**:
   - React to a Slack message with the `:white_check_mark:` emoji to close the associated JIRA ticket.

4. **Ask in a Thread**:
   - `@`-mention the bot in a thread to ask a question. It replies in-thread and remembers
     the conversation for follow-ups.
   - Memory is **in-memory only** and is reset when the bot restarts. Messages posted in a
     thread *between* mentions are not captured until the next time the bot is mentioned.

---

### Prompts

The bot uses prompts stored in `prompts.txt` to generate ticket titles and descriptions. You can customize these prompts to suit your needs.

Example `prompts.txt`:
```plaintext
# Title prompt
Generate a clear and concise JIRA ticket title in the format '[Triage] Subject' based on the following input: {message_text}.

# Description prompt
Generate a detailed JIRA ticket description based on the following input: {message_text}.
```

---

### Docker Support

You can run the bot in a Docker container:

1. Build the Docker image:
   ```bash
   docker build -t slack-helper .
   ```

2. Run the container:
   ```bash
   docker run -e CONFIG_MODE=prod -p 3000:3000 slack-helper
   ```

---

### Kubernetes Deployment

To deploy the bot to Kubernetes, create a deployment and service YAML file. Ensure environment variables are passed as Kubernetes secrets or config maps.

---

### Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

---

### License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

### Acknowledgments

- [Slack API](https://api.slack.com/)
- [JIRA API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- [Google Gemini](https://cloud.google.com/genai)
