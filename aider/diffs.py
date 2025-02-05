import logging
import sys

logger = logging.getLogger(__name__)

from .dump import dump  # noqa: F401


def main():
    """Main function."""
    if len(sys.argv) != 3:
        logger.error("Usage: python diffs.py file1 file2")
        sys.exit(1)

    file1, file2 = sys.argv[1:3]
    res = diff_files(file1, file2)
    logger.info(res)


def create_progress_bar(percentage):
    block = "█"
    empty = "░"
    total_blocks = 30
    filled_blocks = int(total_blocks * percentage // 100)
    empty_blocks = total_blocks - filled_blocks
    bar = block * filled_blocks + empty * empty_blocks
    return bar


def assert_newlines(lines):
    if not lines:
        return
    for line in lines[:-1]:
        assert line and line[-1] == "\n", line


def diff_partial_update(lines_orig, lines_updated, final=False, fname=None):
    """
    Given only the first part of an updated file, show the diff while
    ignoring the block of "deleted" lines that are past the end of the
    partially complete update.
    """

    # dump(lines_orig)
    # dump(lines_updated)

    assert_newlines(lines_orig)

    num_orig_lines = len(lines_orig)

    if final:
        last_non_deleted = num_orig_lines
    else:
        last_non_deleted = find_last_non_deleted(lines_orig, lines_updated)

    # dump(last_non_deleted)
    if last_non_deleted is None:
        return ""

    if num_orig_lines:
        pct = last_non_deleted * 100 / num_orig_lines
    else:
        pct = 50
    bar = create_progress_bar(pct)
    bar = f" {last_non_deleted:3d} / {num_orig_lines:3d} lines [{bar}] {pct:3.0f}%\n"

    lines_orig = lines_orig[:last_non_deleted]

    if not final:
        lines_updated = lines_updated[:-1] + [bar]

    diff = difflib.unified_diff(lines_orig, lines_updated, n=5)

    diff = list(diff)[2:]

    diff = "".join(diff)
    if not diff.endswith("\n"):
        diff += "\n"

    for i in range(3, 10):
        backticks = "`" * i
        if backticks not in diff:
            break

    show = f"{backticks}diff\n"
    if fname:
        show += f"--- {fname} original\n"
        show += f"+++ {fname} updated\n"

    show += diff

    show += f"{backticks}\n\n"

    # print(diff)

    return show


def find_last_non_deleted(lines_orig, lines_updated):
    diff = list(difflib.ndiff(lines_orig, lines_updated))

    num_orig = 0
    last_non_deleted_orig = None

    for line in diff:
        # print(f"{num_orig:2d} {num_updated:2d} {line}", end="")
        code = line[0]
        if code == " ":
            num_orig += 1
            last_non_deleted_orig = num_orig
        elif code == "-":
            # line only in orig
            num_orig += 1
        elif code == "+":
            # line only in updated
            pass

    return last_non_deleted_orig


def diff_files(file1, file2):
    """Compare two files and return diff."""
    try:
        with open(file1, "r") as f1, open(file2, "r") as f2:
            content1 = f1.read()
            content2 = f2.read()
    except Exception as e:
        logger.error("Error reading files: %s", e)
        return None

    return create_diff(content1, content2)


def create_diff(content1, content2):
    """Create diff between two content strings."""
    lines1 = content1.splitlines()
    lines2 = content2.splitlines()

    diff = []
    i = j = 0
    while i < len(lines1) and j < len(lines2):
        if lines1[i] == lines2[j]:
            diff.append(f" {lines1[i]}")
            i += 1
            j += 1
        else:
            diff.append(f"-{lines1[i]}")
            diff.append(f"+{lines2[j]}")
            i += 1
            j += 1

    while i < len(lines1):
        diff.append(f"-{lines1[i]}")
        i += 1

    while j < len(lines2):
        diff.append(f"+{lines2[j]}")
        j += 1

    return "\n".join(diff)


if __name__ == "__main__":
    main()
