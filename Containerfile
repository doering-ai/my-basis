# syntax=docker/dockerfile:1

##################
### `1` SYSTEM ###
##################
# ---- debian ----
# See https://docs.astral.sh/uv/guides/integration/docker/#available-images
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS system
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    _APT="apt-get update && apt-get install -y --no-install-recommends" \
    _APT_CLEAN="apt-get clean"

# ---- apt ----
RUN set -eux && \
    eval "${_APT} git curl ca-certificates gosu" && \
    eval "${_APT_CLEAN}"

# ---- tools ----
# Taskfile
RUN sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin

# Prek
COPY --from=ghcr.io/j178/prek:v0.3.13 /prek /usr/local/bin/prek

# ---- user ----
# stackoverflow.com/a/48329093/9979003
RUN groupadd -r my && useradd --no-log-init -r -m -g my my
USER my:my
ENV PATH=$PATH:/home/my/.local/bin
WORKDIR /home/my/

# ---- uv ----
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_NO_MANAGED_PYTHON=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_CACHE_DIR=/home/my/.cache/uv

RUN mkdir -p $UV_CACHE_DIR

#################
### `2` FINAL ###
#################
FROM system AS final

ENTRYPOINT ["task"]
CMD ["test"]

# Bootstrap trigger
