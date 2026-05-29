import asyncio

from feature_tree_feedback_skill.core import revise_feature_tree_stream


FEATURE_TREE_PATH = "examples/feature_tree.json"
FEEDBACK_PATH = "examples/feedback.txt"
OUTPUT_DIR = "outputs"


async def main():
    async for message in revise_feature_tree_stream(
        feature_tree_path=FEATURE_TREE_PATH,
        feedback_path=FEEDBACK_PATH,
        output_dir=OUTPUT_DIR,
    ):
        print(message)


if __name__ == "__main__":
    asyncio.run(main())
