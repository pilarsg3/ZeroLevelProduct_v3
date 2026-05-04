"""
Example: Drawing + Interactive Parameter Input

If Claude can't extract certain parameters, user provides them via terminal.
"""

from pathlib import Path
from claude_pipeline import build_from_user_input
if __name__ == "__main__":
    build_from_user_input(
        interactive=True,
        input_dir=Path(__file__).parent,
        model="claude-opus-4-5",
    )




