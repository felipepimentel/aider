#!/usr/bin/env python

import logging
import subprocess
import sys

from aider.dump import dump  # noqa: F401

logger = logging.getLogger(__name__)


def run_grid_search(models, edit_formats, num_tests=None, threads=None):
    """Run grid search over models and edit formats."""
    for model in models:
        for edit_format in edit_formats:
            cmd = build_command(model, edit_format, num_tests, threads)
            logger.info("Running command: %s", " ".join(cmd))
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(
                    "Command failed with exit code %d: %s", e.returncode, " ".join(cmd)
                )
            except Exception as e:
                logger.error("Error running command: %s", e)


def build_command(model, edit_format, num_tests=None, threads=None):
    """Build command for running benchmark."""
    cmd = ["python", "-m", "benchmark.benchmark"]

    if model:
        cmd.extend(["--model", model])
    if edit_format:
        cmd.extend(["--edit-format", edit_format])
    if num_tests:
        cmd.extend(["--num-tests", str(num_tests)])
    if threads:
        cmd.extend(["--threads", str(threads)])

    return cmd


def main():
    models = [
        "gpt-3.5-turbo-0301",
        "gpt-3.5-turbo-0613",
        # "gpt-3.5-turbo-16k-0613",
        "gpt-3.5-turbo-1106",
        # "gpt-4-0314",
        # "gpt-4-0613",
    ]
    edit_formats = [
        "diff",
        # "diff-func",
        # "whole",
        # "whole-func",
    ]

    # for repeat in range(1, 2, 1):
    for model in models:
        for edit_format in edit_formats:
            # dump(model, edit_format)

            if "-func" in edit_format and "-03" in model:
                continue

            # if (model, edit_format) == ("gpt-3.5-turbo-16k-0613", "whole-func"):
            #    # sublist reliably hangs the API?
            #    continue

            dirname = f"rungrid-nov-{model}-{edit_format}"
            # dirname = f"rungrid-{model}-{edit_format}-repeat-{repeat}"
            run(dirname, model, edit_format)


def run(dirname, model, edit_format):
    cmd = [
        "./benchmark/benchmark.py",
        dirname,
        "--model",
        model,
        "--edit-format",
        edit_format,
        "--threads",
        "10",
        "--cont",
    ]
    print(" ".join(cmd))

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    status = main()
    sys.exit(status)
