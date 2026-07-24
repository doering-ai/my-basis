# syntax=docker/dockerfile:1

##################
### `1` SYSTEM ###
##################
# ---- debian ----
# See https://docs.astral.sh/uv/guides/integration/docker/#available-images
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim AS system
# The distribution contract starts at Python 3.12. Keep the runtime and uv's default
# interpreter explicit so local, floor, and CI jobs cannot drift to the host Python.
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PYTHON_FLOOR=3.12 \
    UV_PYTHON=3.12 \
    _APT="apt-get update && apt-get install -y --no-install-recommends" \
    _APT_CLEAN="apt-get clean && rm -rf /var/lib/apt/lists/*"

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
# `python-downloads=manual` (not `never`) plus `python-preference=system` is what lets this
# single image serve a multi-interpreter test matrix. The baked-in interpreter above stays the
# default, and uv still refuses to *silently* download one -- a typo'd version fails loudly
# rather than pulling a surprise runtime. But `never` also blocks an EXPLICIT
# `uv python install 3.x` ("Change to `manual` to allow explicit installs"), which made it
# impossible to test any version but the baked-in one without swapping the whole image. CI's
# matrix job provisions the extra interpreters deliberately, and they land in UV_CACHE_DIR.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_PYTHON_PREFERENCE=system \
    UV_PYTHON_DOWNLOADS=manual \
    UV_CACHE_DIR=/home/my/.cache/uv

RUN mkdir -p $UV_CACHE_DIR && \
    python -c 'import sys; assert sys.version_info[:2] == (3, 12), sys.version'

#################
### `2` FINAL ###
#################
FROM system AS final

ENTRYPOINT ["task"]
CMD ["test"]
