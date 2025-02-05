import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Optional

from grep_ast import TreeContext
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchfiles import watch

from aider.dump import dump  # noqa
from aider.watch_prompts import watch_ask_prompt, watch_code_prompt

logger = logging.getLogger(__name__)


def load_gitignores(gitignore_paths: list[Path]) -> Optional[PathSpec]:
    """Load and parse multiple .gitignore files into a single PathSpec"""
    if not gitignore_paths:
        return None

    patterns = [
        ".aider*",
        ".git",
        # Common editor backup/temp files
        "*~",  # Emacs/vim backup
        "*.bak",  # Generic backup
        "*.swp",  # Vim swap
        "*.swo",  # Vim swap
        "\\#*\\#",  # Emacs auto-save
        ".#*",  # Emacs lock files
        "*.tmp",  # Generic temp files
        "*.temp",  # Generic temp files
        "*.orig",  # Merge conflict originals
        "*.pyc",  # Python bytecode
        "__pycache__/",  # Python cache dir
        ".DS_Store",  # macOS metadata
        "Thumbs.db",  # Windows thumbnail cache
        # IDE files
        ".idea/",  # JetBrains IDEs
        ".vscode/",  # VS Code
        "*.sublime-*",  # Sublime Text
        ".project",  # Eclipse
        ".settings/",  # Eclipse
        "*.code-workspace",  # VS Code workspace
        # Environment files
        ".env",  # Environment variables
        ".venv/",  # Python virtual environments
        "node_modules/",  # Node.js dependencies
        "vendor/",  # Various dependencies
        # Logs and caches
        "*.log",  # Log files
        ".cache/",  # Cache directories
        ".pytest_cache/",  # Python test cache
        "coverage/",  # Code coverage reports
    ]  # Always ignore
    for path in gitignore_paths:
        if path.exists():
            with open(path) as f:
                patterns.extend(f.readlines())

    return PathSpec.from_lines(GitWildMatchPattern, patterns) if patterns else None


class AiderWatcher(FileSystemEventHandler):
    def __init__(self, coder, gitignores=None, analytics=None, root=None):
        self.coder = coder
        self.gitignores = gitignores or []
        self.analytics = analytics
        self.root = root or os.getcwd()
        self.observer = None
        self.last_modified = {}
        self.comment_pattern = re.compile(r"#\s*ai:.*$", re.MULTILINE)

    def start(self):
        """Inicia o observador de arquivos."""
        try:
            self.observer = Observer()
            self.observer.schedule(self, self.root, recursive=True)
            self.observer.start()
            logger.info("Observador de arquivos iniciado em: %s", self.root)
        except Exception as e:
            logger.error("Erro ao iniciar observador de arquivos: %s", str(e))

    def stop(self):
        """Para o observador de arquivos."""
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join()
                logger.info("Observador de arquivos parado")
            except Exception as e:
                logger.error("Erro ao parar observador de arquivos: %s", str(e))

    def on_modified(self, event):
        """Manipula eventos de modificação de arquivo."""
        if event.is_directory:
            return

        try:
            path = Path(event.src_path)
            if not self._should_process_file(path):
                return

            # Evitar processamento duplicado
            current_time = time.time()
            if path in self.last_modified:
                if current_time - self.last_modified[path] < 1:  # 1 segundo de debounce
                    return
            self.last_modified[path] = current_time

            logger.debug("Arquivo modificado: %s", path)
            self._process_file(path)

        except Exception as e:
            logger.error("Erro ao processar modificação de arquivo: %s", str(e))

    def _should_process_file(self, path):
        """Verifica se o arquivo deve ser processado."""
        try:
            # Ignorar arquivos ocultos
            if path.name.startswith("."):
                return False

            # Verificar gitignores
            for gitignore in self.gitignores:
                if gitignore.match_file(path):
                    logger.debug("Arquivo ignorado por gitignore: %s", path)
                    return False

            # Verificar se é um arquivo de texto
            if not self._is_text_file(path):
                logger.debug("Arquivo não é texto: %s", path)
                return False

            return True

        except Exception as e:
            logger.error("Erro ao verificar arquivo: %s", str(e))
            return False

    def _is_text_file(self, path):
        """Verifica se o arquivo é um arquivo de texto."""
        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
                return not bool(b"\x00" in chunk)
        except Exception:
            return False

    def _process_file(self, path):
        """Processa o arquivo modificado."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Procurar por comentários AI
            matches = list(self.comment_pattern.finditer(content))
            if not matches:
                return

            logger.info("Encontrados comentários AI em: %s", path)
            for match in matches:
                comment = match.group()
                logger.debug("Processando comentário: %s", comment)
                # Aqui você pode adicionar a lógica para processar o comentário
                # Por exemplo, enviá-lo para o coder

        except Exception as e:
            logger.error("Erro ao processar arquivo %s: %s", path, str(e))


class FileWatcher:
    """Watches source files for changes and AI comments"""

    # Compiled regex pattern for AI comments
    ai_comment_pattern = re.compile(
        r"(?:#|//|--) *(ai\b.*|ai\b.*|.*\bai[?!]?) *$", re.IGNORECASE
    )

    def __init__(
        self, coder, gitignores=None, verbose=False, analytics=None, root=None
    ):
        self.coder = coder
        self.io = coder.io
        self.root = Path(root) if root else Path(coder.root)
        self.verbose = verbose
        self.analytics = analytics
        self.stop_event = None
        self.watcher_thread = None
        self.changed_files = set()
        self.gitignores = gitignores

        self.gitignore_spec = load_gitignores(
            [Path(g) for g in self.gitignores] if self.gitignores else []
        )

        coder.io.file_watcher = self

    def filter_func(self, change_type, path):
        """Filter function for the file watcher"""
        path_obj = Path(path)
        path_abs = path_obj.absolute()

        if not path_abs.is_relative_to(self.root.absolute()):
            return False

        rel_path = path_abs.relative_to(self.root)
        if self.verbose:
            dump(rel_path)

        if self.gitignore_spec and self.gitignore_spec.match_file(str(rel_path)):
            return False

        if self.verbose:
            dump("ok", rel_path)

        # Check if file contains AI markers
        try:
            comments, _, _ = self.get_ai_comments(str(path_abs))
            return bool(comments)
        except Exception:
            return

    def start(self):
        """Start watching for file changes"""
        self.stop_event = threading.Event()
        self.changed_files = set()

        def watch_files():
            try:
                for changes in watch(
                    str(self.root),
                    watch_filter=self.filter_func,
                    stop_event=self.stop_event,
                ):
                    if not changes:
                        continue
                    changed_files = {str(Path(change[1])) for change in changes}
                    self.changed_files.update(changed_files)
                    self.io.interrupt_input()
                    return
            except Exception as e:
                if self.verbose:
                    dump(f"File watcher error: {e}")
                raise e

        self.watcher_thread = threading.Thread(target=watch_files, daemon=True)
        self.watcher_thread.start()

    def stop(self):
        """Stop watching for file changes"""
        if self.stop_event:
            self.stop_event.set()
        if self.watcher_thread:
            self.watcher_thread.join()
            self.watcher_thread = None
            self.stop_event = None

    def process_changes(self):
        """Get any detected file changes"""

        has_action = None
        added = False
        for fname in self.changed_files:
            _, _, action = self.get_ai_comments(fname)
            if action in ("!", "?"):
                has_action = action

            if fname in self.coder.abs_fnames:
                continue
            if self.analytics:
                self.analytics.event("ai-comments file-add")
            self.coder.abs_fnames.add(fname)
            rel_fname = self.coder.get_rel_fname(fname)
            if not added:
                self.io.tool_output()
                added = True
            self.io.tool_output(f"Added {rel_fname} to the chat")

        if not has_action:
            if added:
                self.io.tool_output(
                    "End your comment with AI! to request changes or AI? to ask questions"
                )
            return ""

        if self.analytics:
            self.analytics.event("ai-comments execute")
        self.io.tool_output("Processing your request...")

        if has_action == "!":
            res = watch_code_prompt
        elif has_action == "?":
            res = watch_ask_prompt

        # Refresh all AI comments from tracked files
        for fname in self.coder.abs_fnames:
            line_nums, comments, _action = self.get_ai_comments(fname)
            if not line_nums:
                continue

            code = self.io.read_text(fname)
            if not code:
                continue

            rel_fname = self.coder.get_rel_fname(fname)
            res += f"\n{rel_fname}:\n"

            # Convert comment line numbers to line indices (0-based)
            lois = [ln - 1 for ln, _ in zip(line_nums, comments) if ln > 0]

            try:
                context = TreeContext(
                    rel_fname,
                    code,
                    color=False,
                    line_number=False,
                    child_context=False,
                    last_line=False,
                    margin=0,
                    mark_lois=True,
                    loi_pad=3,
                    show_top_of_file_parent_scope=False,
                )
                context.lines_of_interest = set()
                context.add_lines_of_interest(lois)
                context.add_context()
                res += context.format()
            except ValueError:
                for ln, comment in zip(line_nums, comments):
                    res += f"  Line {ln}: {comment}\n"

        return res

    def get_ai_comments(self, filepath):
        """Extract AI comment line numbers, comments and action status from a file"""
        line_nums = []
        comments = []
        has_action = None  # None, "!" or "?"
        content = self.io.read_text(filepath, silent=True)
        if not content:
            return None, None, None

        for i, line in enumerate(content.splitlines(), 1):
            if match := self.ai_comment_pattern.search(line):
                comment = match.group(0).strip()
                if comment:
                    line_nums.append(i)
                    comments.append(comment)
                    comment = comment.lower()
                    comment = comment.lstrip("/#-")
                    comment = comment.strip()
                    if comment.startswith("ai!") or comment.endswith("ai!"):
                        has_action = "!"
                    elif comment.startswith("ai?") or comment.endswith("ai?"):
                        has_action = "?"
        if not line_nums:
            return None, None, None
        return line_nums, comments, has_action


def main():
    """Example usage of the file watcher"""
    import argparse

    parser = argparse.ArgumentParser(description="Watch source files for changes")
    parser.add_argument("directory", help="Directory to watch")
    parser.add_argument(
        "--gitignore",
        action="append",
        help="Path to .gitignore file (can be specified multiple times)",
    )
    args = parser.parse_args()

    directory = args.directory
    print(f"Watching source files in {directory}...")

    # Example ignore function that ignores files with "test" in the name
    def ignore_test_files(path):
        return "test" in path.name.lower()

    watcher = FileWatcher(directory, gitignores=args.gitignore)
    try:
        watcher.start()
        while True:
            if changes := watcher.get_changes():
                for file in sorted(changes.keys()):
                    print(file)
                watcher.changed_files = None
    except KeyboardInterrupt:
        print("\nStopped watching files")
        watcher.stop()


if __name__ == "__main__":
    main()
