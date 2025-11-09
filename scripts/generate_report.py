"""Script to generate change reports."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scheduler.tasks import generate_change_report
from src.utils.logger import setup_logger, get_logger

setup_logger()
logger = get_logger()


def main(format: str = 'json'):
    """
    Generate a change report.

    Args:
        format: Output format ('json' or 'csv')
    """
    try:
        logger.info(f"Generating {format} change report...")
        result = generate_change_report(format=format)
        logger.info(f"Report generated: {result}")
        print(f"\nReport saved to: {result}")

    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate change report")
    parser.add_argument(
        "--format",
        choices=['json', 'csv'],
        default='json',
        help="Output format"
    )

    args = parser.parse_args()
    main(args.format)
