FROM mcr.microsoft.com/devcontainers/python:3-3.13-trixie

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Create a script file sourced by both interactive and non-interactive bash shells
ENV BASH_ENV "${HOME}/.bash_env"
RUN touch "${BASH_ENV}"
RUN echo '. "${BASH_ENV}"' >> ~/.bashrc

# Download and install nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.6/install.sh | PROFILE="${BASH_ENV}" bash
RUN echo node > .nvmrc
RUN nvm install

# Install the pi.dev CLI binary only.
# Do NOT bind-mount the binary itself from the host (~/.local/bin/pi) --
# host/container OS or arch mismatches (e.g. macOS host, linux/amd64 container)
# will break it. Config, auth, skills, and extensions come from a mounted
# ~/.pi instead (see devcontainer.json), so this install just needs to land
# a working binary for the *container's* platform.
USER vscode
RUN curl -fsSL https://pi.dev/install.sh | sh
ENV PATH="/home/vscode/.local/bin:${PATH}"

# Install uv
USER vscode
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install GitHub CLI                                                                                         
USER vscode                                                                                                  
RUN (type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
	&& sudo mkdir -p -m 755 /etc/apt/keyrings \
	&& out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
	&& cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
	&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
	&& sudo mkdir -p -m 755 /etc/apt/sources.list.d \
	&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
	&& sudo apt update \
	&& sudo apt install gh -y \
    && sudo rm -rf /var/lib/apt/lists/* 

USER root