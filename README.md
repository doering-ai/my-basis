![logo](<>)

![License](https://img.shields.io/gitlab/license/doering-ai/libs/basis)

![Code Coverage](https://img.shields.io/gitlab/pipeline-coverage/doering-ai%2Flibs%2Fbasis?job_name=eval&branch=main)

![Pipeline Status](https://img.shields.io/gitlab/pipeline-status/doering-ai%2Flibs%2Fbasis?branch=main)

<!-- [![GitLab stars](https://img.shields.io/github/stars/AFK-surf/open-agent?style=social)](https://github.com/AFK-surf/open-agent/stargazers) -->

<!-- [![License: MPL](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) -->

<!-- [![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit) -->

# myBasis

The myBasis Python package contains a variety of utilities generally centered around the topics of text processing, functional programming, and runtime type coercion.
This broad scope is somewhat unusual, as any given application will likely only need a small subset of the contents; for this reason, it is intended for use in applications where dependency purity isn't very important, such as personal projects, local development scripts, offline data-processing projects, and prototypes.
As a metric, the package imports 32 dependencies totalling around ~250 MB in uncompressed `.venv/lib/` files.
