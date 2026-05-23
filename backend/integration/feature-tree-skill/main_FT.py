import asyncio

from feature_tree_skill.core import generate_features_stream


NL_PATH = "examples/raw_requirement.txt"
ACTORS_PATH = "examples/actors.txt"
OUTPUT_DIR = "outputs"


async def main():
    async for message in generate_features_stream(
        nl_path=NL_PATH,
        actors_path=ACTORS_PATH,
        output_dir=OUTPUT_DIR,
    ):
        print(message)


if __name__ == "__main__":
    asyncio.run(main())
