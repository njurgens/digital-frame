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

# Install the pi.dev CLI (an npm package) into the container at a pinned
# version. The toolchain lives in the image, not on a volume: to update pi,
# bump PI_VERSION and rebuild. `pi update --self` still works as a temporary
# hotfix inside one container, but this pin is the source of truth.
# Do NOT bind-mount the host's pi from ~/.local instead: host/container OS or
# arch mismatches (e.g. macOS host, linux/amd64 container) would break it.
ARG PI_VERSION=0.84.2
USER vscode
RUN npm install -g --prefix "$HOME/.local" --ignore-scripts --min-release-age=0 --no-fund --no-audit "@earendil-works/pi-coding-agent@$PI_VERSION"
ENV PATH="/home/vscode/.local/bin:${PATH}"

# Link the shared ~/.agents/skills dir into the mounted ~/.pi volume so skills
# installed by agent-agnostic tools (e.g. `npx skills add`) land on durable
# storage. ~/.agents itself is not mounted, so without this the installs would
# be lost on container rebuild. The link's target doesn't exist in the image
# layer -- the ~/.pi bind mount provides it at runtime.
RUN mkdir -p "$HOME/.agents" \
	&& ln -sfn "$HOME/.pi/agent/skills" "$HOME/.agents/skills"

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