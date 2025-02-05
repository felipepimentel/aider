#!/usr/bin/env python

import argparse
import json
import logging
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from aider.dump import dump  # noqa

HARD_SET_NUM = 3  # Number of models that defines the hard set threshold

logger = logging.getLogger(__name__)


def get_dirs_from_leaderboard():
    # Load the leaderboard data
    with open("aider/website/_data/edit_leaderboard.yml") as f:
        leaderboard = yaml.safe_load(f)
    return [(entry["dirname"], entry["model"]) for entry in leaderboard]


def load_results(dirname, stats_languages=None):
    all_results = []
    if stats_languages:
        languages = [lang.strip().lower() for lang in stats_languages.split(",")]
        glob_patterns = [
            f"{lang}/exercises/practice/*/.aider.results.json" for lang in languages
        ]
    else:
        glob_patterns = ["*/exercises/practice/*/.aider.results.json"]

    for pattern in glob_patterns:
        for fname in Path(dirname).glob(pattern):
            try:
                result = json.loads(fname.read_text())
                all_results.append(result)
            except json.JSONDecodeError:
                logger.error("Bad results file %s", fname)
            except Exception as e:
                logger.error("Error loading %s: %s", fname, e)

    return all_results


def analyze_results(dirname, stats_languages=None):
    all_results = load_results(dirname, stats_languages)
    exercise_stats = defaultdict(lambda: {"solved": 0, "total": 0})
    model_stats = defaultdict(lambda: {"solved": 0, "total": 0})
    parse_error_counts = Counter()

    for result in all_results:
        try:
            dirname = result["dirname"]
            model = result.get("model", "unknown")
            tests_outcomes = result.get("tests_outcomes", [])
            if not tests_outcomes:
                logger.warning(
                    "Missing testcase in %s %s", dirname, json.dumps(result, indent=4)
                )
                continue
        except Exception as e:
            logger.error("Could not load results for %s: %s", dirname, e)
            continue

        exercise_stats[dirname]["total"] += 1
        model_stats[model]["total"] += 1

        if any(outcome == "pass" for outcome in tests_outcomes):
            exercise_stats[dirname]["solved"] += 1
            model_stats[model]["solved"] += 1

        if result.get("syntax_errors", 0) > 0:
            parse_error_counts[dirname] += 1

    logger.info("\nExercise Solution Statistics:")
    logger.info("-" * 40)

    # Sort exercises by solve rate
    sorted_exercises = sorted(
        exercise_stats.items(),
        key=lambda x: (
            x[1]["solved"] / x[1]["total"] if x[1]["total"] > 0 else 0,
            x[0],
        ),
        reverse=True,
    )

    max_name_len = max(len(testcase) for testcase, _ in sorted_exercises)

    solved_at_least_once = 0
    solved_by_none = 0
    solved_by_all = 0
    never_solved = []

    logger.info("\nAll Exercises (sorted by solve rate):")
    for i, (testcase, stats) in enumerate(sorted_exercises, 1):
        num_solved = stats["solved"]
        total_attempts = stats["total"]
        percent = (num_solved / total_attempts * 100) if total_attempts > 0 else 0
        logger.info(
            "%3d. %s : %3d solved (%5.1f%%)",
            i,
            testcase.ljust(max_name_len),
            num_solved,
            percent,
        )

    logger.info("\nSummary:")
    for testcase, stats in sorted_exercises:
        if stats["solved"] > 0:
            solved_at_least_once += 1
        if stats["solved"] == 0:
            solved_by_none += 1
            never_solved.append(testcase)
        if stats["solved"] == stats["total"]:
            solved_by_all += 1

    logger.info("Total exercises solved at least once: %d", solved_at_least_once)
    logger.info("Never solved by any model: %d", solved_by_none)

    logger.info("\nExercises never solved by any model:")
    for testcase in never_solved:
        path = Path(testcase)
        formatted_path = "/".join(path.parts[-3:])  # Get last 3 parts of path
        logger.info("  %s", formatted_path)

    logger.info("\nSolved by all models: %d", solved_by_all)
    logger.info(
        "Percentage of exercises solved by all models: %.1f%%",
        (solved_by_all / len(exercise_stats) * 100),
    )

    # Distribution analysis
    solution_counts = Counter(stats["solved"] for stats in exercise_stats.values())
    logger.info("\nDistribution of solutions:")
    logger.info("Models  Exercises  Cumulative  RevCumulative")
    logger.info("-" * 50)

    total_exercises = len(exercise_stats)
    cumsum = 0
    revcumsum = total_exercises

    for i in range(max(solution_counts.keys()) + 1):
        count = solution_counts[i]
        cumsum += count
        revcumsum -= count
        logger.info("%6d  %9d  %10d  %12d", i, count, cumsum, revcumsum)

    # Parse error analysis
    if parse_error_counts:
        logger.info(
            "\nExercises with parse errors (total: %d):", len(parse_error_counts)
        )
        for ex in sorted(parse_error_counts, key=parse_error_counts.get, reverse=True):
            logger.info("  %s (%d parse errors)", ex, parse_error_counts[ex])

    # Hard set analysis
    HARD_SET_NUM = 2  # Define what constitutes "hard" (solved by 2 or fewer models)
    hard_set = {
        ex for ex, stats in exercise_stats.items() if stats["solved"] <= HARD_SET_NUM
    }

    logger.info("\nHard Set Analysis (exercises solved by ≤%d models):", HARD_SET_NUM)
    logger.info("-" * 60)

    # Count by language
    language_counts = defaultdict(lambda: {"total": 0, "hard": 0, "unsolved": 0})
    for ex in exercise_stats:
        lang = ex.split("/")[0]
        language_counts[lang]["total"] += 1
        if ex in hard_set:
            language_counts[lang]["hard"] += 1
        if exercise_stats[ex]["solved"] == 0:
            language_counts[lang]["unsolved"] += 1

    logger.info("Total hard set exercises: %d", len(hard_set))

    # Model performance on hard set
    model_hard_set_performance = defaultdict(int)
    for result in all_results:
        try:
            dirname = result["dirname"]
            if dirname in hard_set:
                model = result.get("model", "unknown")
                tests_outcomes = result.get("tests_outcomes", [])
                if any(outcome == "pass" for outcome in tests_outcomes):
                    model_hard_set_performance[model] += 1
        except Exception:
            continue

    logger.info("\nUnsolved and hard set problems by language:")
    logger.info(
        "%-12s %8s %9s %7s %8s",
        "Language",
        "Unsolved",
        "Hard Set",
        "Total",
        "%hardUnsolved",
    )
    logger.info("-" * 47)

    for lang in sorted(language_counts):
        count = language_counts[lang]["unsolved"]
        hard = language_counts[lang]["hard"]
        total = language_counts[lang]["total"]
        pct = (hard / count * 100) if count > 0 else 0
        logger.info("%-12s %8d %9d %7d %7.1f%%", lang, count, hard, total, pct)
    logger.info("")

    return hard_set, exercise_stats, model_hard_set_performance


def analyze_exercise_solutions(dirs=None, topn=None, copy_hard_set=False):
    PARSE_ERROR_M = 4  # Threshold for number of parse errors to DQ an exercise

    if dirs is None:
        # Use leaderboard data if no directories specified
        dir_entries = get_dirs_from_leaderboard()
    else:
        # Use provided directories, with dirname as model name
        dir_entries = [(d, d) for d in dirs]

    # Filter out entries that don't load and sort by pass rate
    valid_entries = []
    parse_errors_by_model = {}  # Track which exercises had parse errors for each model

    dump(dir_entries)

    for dirname, model in dir_entries:
        results_data = load_results(dirname)

        if results_data:
            results, model_parse_errors = results_data
            parse_errors_by_model[model] = set(model_parse_errors)
            # Calculate pass rate for sorting when using custom dirs
            if dirs is not None:
                pass_rate = sum(
                    1
                    for r in results
                    if r.get("tests_outcomes", []) and r["tests_outcomes"][-1]
                ) / len(results)
            else:
                # Use existing pass rate from leaderboard
                pass_rate = next(
                    (
                        entry["pass_rate_2"]
                        for entry in yaml.safe_load(
                            open("aider/website/_data/edit_leaderboard.yml")
                        )
                        if entry["dirname"] == dirname
                    ),
                    0,
                )
            valid_entries.append(((dirname, model), results, float(pass_rate)))

    # Sort by pass rate and take top N if specified
    valid_entries.sort(key=lambda x: x[2], reverse=True)
    if topn:
        valid_entries = valid_entries[:topn]

    # Get all exercise names from a complete run
    all_exercises = set()
    exercise_solutions = defaultdict(list)

    # Get all unique exercise names from all results
    all_exercises = set()
    for (dirname, model), results, _ in valid_entries:
        if results:
            for result in results:
                try:
                    all_exercises.add(result["testcase"] + "/" + result["language"])
                except KeyError:
                    print(
                        f"Warning: Missing testcase in {dirname}",
                        json.dumps(result, indent=4),
                    )

    for (dirname, model), results, _ in valid_entries:
        if not results:
            print(f"Could not load results for {dirname}")
            continue

        for result in results:
            testcase = result.get("testcase")
            if not testcase:
                continue
            lang = result.get("language")
            if not lang:
                continue

            testcase = f"{testcase}/{lang}"
            # Consider it solved if the last test attempt passed
            tests_outcomes = result.get("tests_outcomes", [])
            if tests_outcomes and tests_outcomes[-1]:
                exercise_solutions[testcase].append(model)

    # Calculate never solved exercises
    never_solved = len(all_exercises - set(exercise_solutions.keys()))

    # Print per-exercise statistics
    print("\nExercise Solution Statistics:")
    print("-" * 40)

    # Add exercises that were never solved
    for exercise in all_exercises:
        if exercise not in exercise_solutions:
            exercise_solutions[exercise] = []

    # Create list of (language, exercise) pairs with solution stats
    exercise_stats = []
    total_models = len(valid_entries)

    for testcase in all_exercises:
        # Language is already in the testcase string
        lang = testcase.split("/")[0]  # First part is the language
        models = exercise_solutions[testcase]
        num_solved = len(models)
        percent = (num_solved / total_models) * 100
        testcase = testcase.replace("exercises/", "")  # Remove the exercises/ prefix
        # Remove duplicate language prefix (e.g. javascript/javascript/ -> javascript/)
        if testcase.startswith(f"{lang}/{lang}/"):
            testcase = testcase[len(lang) + 1 :]
        exercise_stats.append((lang, testcase, num_solved, percent))

    # Sort all exercises by solve rate, then by exercise name
    exercise_stats.sort(
        key=lambda x: (-x[2], x[1])
    )  # -x[2] for descending solve rate, x[1] for ascending exercise name

    # Calculate max lengths for alignment after cleaning up paths
    max_name_len = max(
        len(f"{lang}/{testcase}") for lang, testcase, _, _ in exercise_stats
    )

    # Print all exercises sorted by solve rate
    print("\nAll Exercises (sorted by solve rate):")
    for i, (lang, testcase, num_solved, percent) in enumerate(exercise_stats, 1):
        print(
            f"{i:>3}. {testcase:<{max_name_len}} : {num_solved:>3} solved ({percent:>5.1f}%)"
        )

    print("\nSummary:")
    solved_at_least_once = len([
        ex for ex, models in exercise_solutions.items() if models
    ])
    solved_by_none = never_solved
    solved_by_all = len([
        ex for ex, models in exercise_solutions.items() if len(models) == total_models
    ])

    print(f"Total exercises solved at least once: {solved_at_least_once}")
    print(f"Never solved by any model: {solved_by_none}")
    if solved_by_none > 0:
        print("\nExercises never solved by any model:")
        unsolved = [ex for ex, models in exercise_solutions.items() if not models]
        for ex in sorted(unsolved):
            # Split into language and exercise parts
            lang, exercise = ex.split("/")
            # Reconstruct path in desired format
            formatted_path = f"{lang}/exercises/practice/{exercise}"
            print(f"  {formatted_path}")
    print(f"\nSolved by all models: {solved_by_all}")
    print(
        f"Total exercises: {len(all_exercises)} = {solved_by_none} (none) + {solved_by_all} (all) +"
        f" {len(all_exercises) - solved_by_none - solved_by_all} (some)"
    )

    # Distribution table of how many models solved each exercise
    print("\nDistribution of solutions:")
    print("Models  Exercises  Cumulative  RevCumulative")
    print("-" * 50)
    counts = [0] * (total_models + 1)
    for ex, models in exercise_solutions.items():
        counts[len(models)] += 1

    cumsum = 0
    revcumsum = sum(counts)  # Start with total number of exercises
    for i, count in enumerate(counts):
        cumsum += count
        print(f"{i:>6d}  {count:>9d}  {cumsum:>10d}  {revcumsum:>12d}")
        revcumsum -= count  # Decrement the reverse cumulative sum

    # Count parse errors per exercise
    parse_error_counts = defaultdict(int)
    for model_errors in parse_errors_by_model.values():
        for exercise in model_errors:
            parse_error_counts[exercise] += 1

    # Find exercises to disqualify based on parse error threshold
    disqualified_exercises = {
        exercise
        for exercise, count in parse_error_counts.items()
        if count >= PARSE_ERROR_M
    }

    if disqualified_exercises:
        print(
            f"\nDisqualified {len(disqualified_exercises)} exercises with {PARSE_ERROR_M}+ parse"
            " errors:"
        )
        for ex in sorted(disqualified_exercises):
            print(f"  {ex} ({parse_error_counts[ex]} parse errors)")

    # Collect the hard set (exercises solved by HARD_SET_NUM or fewer models)
    print(f"\nHard Set Analysis (exercises solved by ≤{HARD_SET_NUM} models):")
    print("-" * 60)
    hard_set = {
        ex
        for ex, models in exercise_solutions.items()
        if len(models) <= HARD_SET_NUM and ex not in disqualified_exercises
    }
    print(f"Total hard set exercises: {len(hard_set)}")

    # Count total problems, unsolved problems, and hard set problems by language
    lang_totals = defaultdict(int)
    lang_unsolved = defaultdict(int)
    lang_hard_set = defaultdict(int)

    for exercise in all_exercises:
        lang = exercise.split("/")[1]  # Get language from path
        lang_totals[lang] += 1
        if not exercise_solutions[exercise]:  # No models solved this exercise
            lang_unsolved[lang] += 1
        if exercise in hard_set:  # Exercise is in the hard set
            lang_hard_set[lang] += 1

    print("\nUnsolved and hard set problems by language:")
    print(
        f"{'Language':<12} {'Unsolved':>8} {'Hard Set':>9} {'Total':>7} {'%hardUnsolved':>8}"
    )
    print("-" * 47)
    for lang in sorted(lang_totals.keys()):
        count = lang_unsolved[lang]
        hard = lang_hard_set[lang]
        total = lang_totals[lang]
        pct = (count / hard) * 100 if hard else -1
        print(f"{lang:<12} {count:>8} {hard:>9} {total:>7} {pct:>7.1f}%")
    print()

    # For each model, compute performance on hard set
    model_hard_stats = []
    for (dirname, model), results, _ in valid_entries:
        if not results:
            continue

        solved_hard = 0
        for result in results:
            testcase = result.get("testcase")
            if not testcase:
                continue
            lang = result.get("language")
            if not lang:
                continue

            testcase = f"{testcase}/{lang}"
            if testcase in hard_set:
                tests_outcomes = result.get("tests_outcomes", [])
                if tests_outcomes and tests_outcomes[-1]:
                    solved_hard += 1

        pct = (solved_hard / len(hard_set)) * 100
        model_hard_stats.append((model, solved_hard, pct))

    # Sort by number solved
    model_hard_stats.sort(key=lambda x: x[1], reverse=True)

    print("\nModel performance on hard set:")
    print(f"{'Model':<55} {'Solved':<8} {'Percent':>7}")
    print("-" * 50)
    for model, solved, pct in model_hard_stats:
        print(f"{model:<55} {solved:>6d}   {pct:>6.1f}%")

    if copy_hard_set:
        # Create hard set directory
        src_dir = Path("tmp.benchmarks/exercism")
        dst_dir = Path("tmp.benchmarks/exercism-polyglot")

        if dst_dir.exists():
            print(f"\nError: Destination directory {dst_dir} already exists")
            return

        print(f"\nCopying hard set problems to {dst_dir}...")

        # Create a set of (exercise, language) pairs from hard_set
        hard_set_pairs = {tuple(exercise.split("/")) for exercise in hard_set}

        # Copy each hard set problem's directory
        copied_by_lang = defaultdict(int)
        for lang_dir in src_dir.glob("*/exercises/practice"):
            if not lang_dir.is_dir():
                continue

            lang = lang_dir.parts[-3]  # Get language from path
            for problem_dir in lang_dir.glob("*"):
                if (problem_dir.name, lang) in hard_set_pairs:
                    rel_path = problem_dir.relative_to(src_dir)
                    dst_path = dst_dir / rel_path
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(problem_dir, dst_path)
                    copied_by_lang[lang] += 1

        total_copied = sum(copied_by_lang.values())
        print(f"\nCopied {total_copied} hard set problems:")
        for lang in sorted(copied_by_lang):
            print(f"  {lang}: {copied_by_lang[lang]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--topn", type=int, help="Only consider top N models by pass rate"
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        help="Directories to analyze (optional, defaults to leaderboard entries)",
    )
    parser.add_argument(
        "--copy-hard-set",
        action="store_true",
        help="Copy hard set problems to tmp.benchmarks/exercism-polygot",
    )
    args = parser.parse_args()

    analyze_exercise_solutions(
        args.dirs if args.dirs else None, args.topn, args.copy_hard_set
    )
