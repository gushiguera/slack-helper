#!/usr/bin/env bash

if [[ "$GITHUB_ACTIONS" == "true" ]]; then
  # If running in GitHub Actions, then we are building a release
  VERSION=$1
else
  # If not running in GitHub Actions, then we are running locally
  VERSION="latest"
fi
echo "Attempting to build the slack-helper docker image with version $NEW_VERSION"

imageDirectory=$(echo $(pwd))

echo "Building Docker image. Please wait a couple minutes."

# Build the docker container
# Check that the GITHUB_TOKEN variable exists
if [ -z "$GITHUB_TOKEN" ]; then
  echo "GITHUB TOKEN not set. Please set the GITHUB_TOKEN environment variable or secret."
  exit 1
fi

echo "Building Docker image locally"
docker build \
  --file Dockerfile $imageDirectory \
  -t ghcr.io/banno/slack-helper:$VERSION \
  --build-arg GITHUB_TOKEN=$GITHUB_TOKEN \
  --no-cache

if [ $? -ne 0 ]; then
  echo "Failed to build docker image. Failing build."
  exit 1
fi
echo "Successfully built Docker image."
