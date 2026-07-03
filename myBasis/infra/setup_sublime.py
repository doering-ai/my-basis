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
    """Placeholder worker that starts Sublime Text and waits for it to be set up."""

    xxx: str = ''

    def __call__(self) -> None:
        """Run the worker."""
        print('Worker()')


############
### MAIN ###
############
def _cli(*vargs: str) -> ap.Namespace:
    parser = ap.ArgumentParser(description='Startup sublime text and wait for it to be setup.')

    parser.add_argument(
        '-x',
        '--xxx',
        help='yyy',
    )

    return parser.parse_args(vargs or None)


def main(*vargs: str) -> None:
    """Entry point: parse CLI arguments and run the `Worker`."""
    args = _cli(*vargs)

    worker = Worker(**vars(args))
    worker()


if __name__ == '__main__':
    main()
