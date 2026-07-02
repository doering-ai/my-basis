############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import argparse as ap

### EXTERNAL
import pydantic as pyd

### INTERNAL


############
### BODY ###
############
class Worker(pyd.BaseModel):
    xxx: str = ""

    def __call__(self) -> None:
        print("Worker()")


############
### MAIN ###
############
def _cli(*vargs: str) -> ap.Namespace:
    parser = ap.ArgumentParser(
        description="Startup sublime text and wait for it to be setup."
    )

    parser.add_argument(
        "-x",
        "--xxx",
        help="yyy",
    )

    return parser.parse_args(vargs or None)


def main(*vargs: str) -> None:
    args = _cli(*vargs)

    worker = Worker(**vars(args))
    worker()


if __name__ == "__main__":
    main()
