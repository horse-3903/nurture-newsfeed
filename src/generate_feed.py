import argparse
import sys

from nurture_feed.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RSS feed and optionally send email notifications.")
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Update feed.xml/cache.json but do not send email notifications.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run_pipeline(enable_email=not args.skip_email))
