# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on (if applicable)
# EXPOSE 3000

# Define environment variables (optional, can also be set in Kubernetes)
ENV PYTHONUNBUFFERED=1

# Default to running in production mode, but allow overriding at runtime
# Note prod mode means it's using prod config but actually runs in our dev environment since it's just an internal bot
ENV CONFIG_MODE=prod

# Run the script when the container launches
CMD ["python", "ticket-creation.py"]