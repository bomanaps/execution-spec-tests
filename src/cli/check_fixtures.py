"""
Perform sanity checks on the framework's pydantic serialization and
deserialization using generated json fixtures files.
"""

from pathlib import Path
from typing import Generator

import click
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn

from ethereum_test_base_types import to_json
from ethereum_test_fixtures.file import Fixtures
from ethereum_test_specs.base import HashMismatchExceptionError


def count_json_files_exclude_index(start_path: Path) -> int:
    """
    Return the number of json files in the specified directory, excluding
    index.json files.
    """
    json_file_count = sum(1 for file in start_path.rglob("*.json") if file.name != "index.json")
    return json_file_count


def check_json(json_file_path: Path):
    """
    Check all fixtures in the specified json file:
    1. Load the json file into a pydantic model. This checks there are no
        Validation errors when loading fixtures into EEST models.
    2. Serialize the loaded pydantic model to "json" (actually python data
        structures, ready to written as json).
    3. Load the serialized data back into a pydantic model (to get an updated
        hash) from step 2.
    4. Compare hashes:
        a. Compare the newly calculated hashes from step 2. and 3. and
        b. If present, compare info["hash"] with the calculated hash from step 2.
    """
    fixtures: Fixtures = Fixtures.model_validate_json(json_file_path.read_text())
    fixtures_json = to_json(fixtures)
    fixtures_deserialized: Fixtures = Fixtures.model_validate(fixtures_json)
    for fixture_name, fixture in fixtures.items():
        new_hash = fixtures_deserialized[fixture_name].hash
        if (original_hash := fixture.hash) != new_hash:
            raise HashMismatchExceptionError(
                original_hash,
                new_hash,
                message=f"Fixture hash attributes do not match for {fixture_name}",
            )
        if "hash" in fixture.info and fixture.info["hash"] != original_hash:
            info_hash = fixture.info["hash"]
            raise HashMismatchExceptionError(
                original_hash,
                fixture.info["hash"],
                message=f"Fixture info['hash'] does not match calculated hash for {fixture_name}:"
                f"'{info_hash}' != '{original_hash}'",
            )


@click.command()
@click.option(
    "--input",
    "-i",
    "input_str",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True),
    required=True,
    help="The input json file or directory containing json fixture files",
)
@click.option(
    "--quiet",
    "-q",
    "quiet_mode",
    is_flag=True,
    default=False,
    expose_value=True,
    help="Don't show the progress bar while processing fixture files.",
)
@click.option(
    "--stop-on-error",
    "--raise-on-error",
    "-s",
    "stop_on_error",
    is_flag=True,
    default=False,
    expose_value=True,
    help="Stop and raise any exceptions encountered while checking fixtures.",
)
def check_fixtures(input_str: str, quiet_mode: bool, stop_on_error: bool):
    """Perform some checks on the fixtures contained in the specified directory."""
    input_path = Path(input_str)
    success = True
    file_count = 0
    filename_display_width = 25
    if input_path.is_file():
        file_count = 1
    elif not quiet_mode:
        file_count = count_json_files_exclude_index(input_path)

    def get_input_files() -> Generator[Path, None, None]:
        if input_path.is_file():
            yield input_path
        else:
            yield from input_path.rglob("*.json")

    with Progress(
        TextColumn(
            f"[bold cyan]{{task.fields[filename]:<{filename_display_width}}}[/]", justify="left"
        ),
        BarColumn(bar_width=None, complete_style="green3", finished_style="bold green3"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        expand=True,
        disable=quiet_mode,
    ) as progress:  # type: Progress
        task_id = progress.add_task("Checking fixtures", total=file_count, filename="...")
        for json_file_path in get_input_files():
            if json_file_path.name == "index.json":
                continue

            display_filename = json_file_path.name
            if len(display_filename) > filename_display_width:
                display_filename = display_filename[: filename_display_width - 3] + "..."
            else:
                display_filename = display_filename.ljust(filename_display_width)

            try:
                progress.update(task_id, advance=1, filename=f"Checking {display_filename}")
                check_json(json_file_path)
            except Exception as e:
                success = False
                if stop_on_error:
                    raise e
                else:
                    progress.console.print(f"\nError checking {json_file_path}:")
                    progress.console.print(f"  {e}")

        reward_string = "🦄" if success else "🐢"
        progress.update(
            task_id, completed=file_count, filename=f"Completed checking all files {reward_string}"
        )

    return success


if __name__ == "__main__":
    check_fixtures()
