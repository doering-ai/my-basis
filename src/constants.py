############
### HEAD ###
############
# Standard imports
from pathlib import Path
import regex as re
import os

# External imports

# Internal imports

############
### DATA ###
############
# -------------
# I. Filesystem
# -------------
DEBUG = False

# ROOT = Path(__file__).resolve().parents[1]
assert (rootvar := os.getenv('MY_AI')), 'Environment variable MY_AI is not set.'
ROOT = Path(rootvar).expanduser().resolve().absolute()
assert ROOT.exists(), f"Root directory {ROOT} does not exist."
"""The root directory of the project"""

# ------------------
# II. Regex Patterns
# ------------------

DATA_REGEX = re.compile(r'Data$')
"""Finds and removes "Data" from classnames"""

# ------------
# III. Strings
# ------------
DELIM = ' // '
