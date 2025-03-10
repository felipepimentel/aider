#!/usr/bin/env python

import base64
import json
import locale
import logging
import mimetypes
import os
import platform
import re
import sys
import threading
import time
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List

from aider import __version__, models, urls, utils
from aider.commands import Commands
from aider.exceptions import LiteLLMExceptions
from aider.history import ChatSummary
from aider.io import ConfirmGroup, InputOutput
from aider.linter import Linter
from aider.llm import litellm
from aider.repo import GitRepo
from aider.repomap import RepoMap
from aider.sendchat import RETRY_TIMEOUT
from aider.utils import format_tokens, is_image_file

from ..dump import dump  # noqa: F401
from .chat_chunks import ChatChunks

logger = logging.getLogger(__name__)


class UnknownEditFormat(ValueError):
    def __init__(self, edit_format, valid_formats):
        self.edit_format = edit_format
        self.valid_formats = valid_formats
        super().__init__(
            f"Unknown edit format {edit_format}. Valid formats are: {', '.join(valid_formats)}"
        )


class MissingAPIKeyError(ValueError):
    pass


class FinishReasonLength(Exception):
    pass


def wrap_fence(name):
    return f"<{name}>", f"</{name}>"


all_fences = [
    ("`" * 3, "`" * 3),
    ("`" * 4, "`" * 4),
    wrap_fence("source"),
    wrap_fence("code"),
    wrap_fence("pre"),
    wrap_fence("codeblock"),
    wrap_fence("sourcecode"),
]


class Coder:
    abs_fnames = None
    abs_read_only_fnames = None
    repo = None
    last_aider_commit_hash = None
    aider_edited_files = None
    repo_map = None
    functions = None
    num_exhausted_context_windows = 0
    num_malformed_responses = 0
    last_keyboard_interrupt = None
    num_reflections = 0
    max_reflections = 3
    edit_format = None
    yield_stream = False
    temperature = 0
    auto_lint = True
    auto_test = False
    test_cmd = None
    lint_outcome = None
    test_outcome = None
    multi_response_content = ""
    partial_response_content = ""
    commit_before_message = []
    message_cost = 0.0
    message_tokens_sent = 0
    message_tokens_received = 0
    add_cache_headers = False
    cache_warming_thread = None
    num_cache_warming_pings = 0
    suggest_shell_commands = True
    detect_urls = True
    io = None
    root = None
    analytics = None
    map_mul_no_files = 2
    map_refresh = "auto"

    @classmethod
    def create(
        self,
        main_model=None,
        edit_format=None,
        io=None,
        from_coder=None,
        summarize_from_coder=True,
        **kwargs,
    ):
        import aider.coders as coders

        if not main_model:
            if from_coder:
                main_model = from_coder.main_model
            else:
                main_model = models.Model(models.DEFAULT_MODEL_NAME)

        if edit_format == "code":
            edit_format = None
        if edit_format is None:
            if from_coder:
                edit_format = from_coder.edit_format
            else:
                edit_format = main_model.edit_format

        if not io and from_coder:
            io = from_coder.io

        if from_coder:
            use_kwargs = dict(from_coder.original_kwargs)  # copy orig kwargs

            # If the edit format changes, we can't leave old ASSISTANT
            # messages in the chat history. The old edit format will
            # confused the new LLM. It may try and imitate it, disobeying
            # the system prompt.
            done_messages = from_coder.done_messages
            if (
                edit_format != from_coder.edit_format
                and done_messages
                and summarize_from_coder
            ):
                done_messages = from_coder.summarizer.summarize_all(done_messages)

            # Bring along context from the old Coder
            update = dict(
                fnames=list(from_coder.abs_fnames),
                read_only_fnames=list(
                    from_coder.abs_read_only_fnames
                ),  # Copy read-only files
                done_messages=done_messages,
                cur_messages=from_coder.cur_messages,
                aider_commit_hashes=from_coder.aider_commit_hashes,
                commands=from_coder.commands.clone(),
                total_cost=from_coder.total_cost,
                ignore_mentions=from_coder.ignore_mentions,
                file_watcher=from_coder.file_watcher,
            )
            use_kwargs.update(update)  # override to complete the switch
            use_kwargs.update(kwargs)  # override passed kwargs

            kwargs = use_kwargs

        for coder in coders.__all__:
            if hasattr(coder, "edit_format") and coder.edit_format == edit_format:
                res = coder(main_model, io, **kwargs)
                res.original_kwargs = dict(kwargs)
                return res

        valid_formats = [
            str(c.edit_format)
            for c in coders.__all__
            if hasattr(c, "edit_format") and c.edit_format is not None
        ]
        raise UnknownEditFormat(edit_format, valid_formats)

    def clone(self, **kwargs):
        new_coder = Coder.create(from_coder=self, **kwargs)
        return new_coder

    def get_announcements(self):
        lines = []
        lines.append(f"Aider v{__version__}")

        # Model
        main_model = self.main_model
        output = f"Model: {main_model.name} with {self.edit_format} edit format"
        if self.add_cache_headers or main_model.caches_by_default:
            output += ", prompt cache"
        if main_model.info.get("supports_assistant_prefill"):
            output += ", infinite output"
        lines.append(output)

        if self.edit_format == "architect":
            output = (
                f"Editor model: {main_model.editor_model.name} with"
                f" {main_model.editor_edit_format} edit format"
            )
            lines.append(output)

        # Repo
        if self.repo:
            rel_repo_dir = self.repo.get_rel_repo_dir()
            num_files = len(self.repo.get_tracked_files())

            lines.append(f"Git repo: {rel_repo_dir} with {num_files:,} files")
            if num_files > 1000:
                lines.append(
                    "Warning: For large repos, consider using --subtree-only and .aiderignore"
                )
                lines.append(f"See: {urls.large_repos}")
        else:
            lines.append("Git repo: none")

        # Repo-map
        if self.repo_map:
            map_tokens = self.repo_map.max_map_tokens
            if map_tokens > 0:
                refresh = self.repo_map.refresh
                lines.append(f"Repo-map: using {map_tokens} tokens, {refresh} refresh")
                max_map_tokens = self.main_model.get_repo_map_tokens() * 2
                if map_tokens > max_map_tokens:
                    lines.append(
                        f"Warning: map-tokens > {max_map_tokens} is not recommended. Too much"
                        " irrelevant code can confuse LLMs."
                    )
            else:
                lines.append("Repo-map: disabled because map_tokens == 0")
        else:
            lines.append("Repo-map: disabled")

        # Files
        for fname in self.get_inchat_relative_files():
            lines.append(f"Added {fname} to the chat.")

        for fname in self.abs_read_only_fnames:
            rel_fname = self.get_rel_fname(fname)
            lines.append(f"Added {rel_fname} to the chat (read-only).")

        if self.done_messages:
            lines.append("Restored previous conversation history.")

        if self.io.multiline_mode:
            lines.append(
                "Multiline mode: Enabled. Enter inserts newline, Alt-Enter submits text"
            )

        return lines

    def __init__(self, main_model=None, io=None, **kwargs):
        self.main_model = main_model
        self.io = io
        self.abs_fnames = set()  # Initialize abs_fnames as an empty set
        self.abs_read_only_fnames = (
            set()
        )  # Initialize abs_read_only_fnames as an empty set

        for k, v in kwargs.items():
            setattr(self, k, v)

        from aider.analytics import Analytics

        if self.analytics is None:
            self.analytics = Analytics()
        self.event = self.analytics.event
        self.chat_language = self.chat_language
        self.commit_before_message = []
        self.aider_commit_hashes = set()
        self.rejected_urls = set()
        self.abs_root_path_cache = {}

        self.auto_copy_context = self.auto_copy_context

        self.ignore_mentions = self.ignore_mentions
        if not self.ignore_mentions:
            self.ignore_mentions = set()

        self.file_watcher = self.file_watcher
        if self.file_watcher:
            self.file_watcher.coder = self

        self.suggest_shell_commands = self.suggest_shell_commands
        self.detect_urls = self.detect_urls

        self.num_cache_warming_pings = self.num_cache_warming_pings

        if not self.abs_fnames:
            self.abs_fnames = []

        if self.io is None:
            self.io = InputOutput()

        if self.aider_commit_hashes:
            self.aider_commit_hashes = self.aider_commit_hashes
        else:
            self.aider_commit_hashes = set()

        self.chat_completion_call_hashes = []
        self.chat_completion_response_hashes = []
        self.need_commit_before_edits = set()

        self.total_cost = self.total_cost

        self.verbose = self.verbose
        self.abs_fnames = set()
        self.abs_read_only_fnames = set()

        if self.cur_messages:
            self.cur_messages = self.cur_messages
        else:
            self.cur_messages = []

        if self.done_messages:
            self.done_messages = self.done_messages
        else:
            self.done_messages = []

        self.shell_commands = []

        if not self.auto_commits:
            self.dirty_commits = False

        self.auto_commits = self.auto_commits
        self.dirty_commits = self.dirty_commits

        self.dry_run = self.dry_run
        self.pretty = self.io.pretty

        self.stream = self.stream and self.main_model.streaming

        if self.cache_prompts and self.main_model.cache_control:
            self.add_cache_headers = True

        self.show_diffs = self.show_diffs

        self.commands = self.commands or Commands(self.io, self)
        self.commands.coder = self

        self.repo = self.repo
        if self.use_git and self.repo is None:
            try:
                self.repo = GitRepo(
                    self.io,
                    self.abs_fnames,
                    None,
                    models=self.main_model.commit_message_models(),
                )
            except FileNotFoundError:
                pass

        if self.repo:
            self.root = self.repo.root
        else:
            self.root = utils.find_common_root(self.abs_fnames)

        for fname in self.abs_fnames:
            fname = Path(fname)
            if self.repo and self.repo.git_ignored_file(fname):
                self.io.tool_warning(f"Skipping {fname} that matches gitignore spec.")

            if self.repo and self.repo.ignored_file(fname):
                self.io.tool_warning(f"Skipping {fname} that matches aiderignore spec.")
                continue

            if not fname.exists():
                if utils.touch_file(fname):
                    self.io.tool_output(f"Creating empty file {fname}")
                else:
                    self.io.tool_warning(f"Can not create {fname}, skipping.")
                    continue

            if not fname.is_file():
                self.io.tool_warning(f"Skipping {fname} that is not a normal file.")
                continue

            fname = str(fname.resolve())

            self.abs_fnames.add(fname)
            self.check_added_files()

        if not self.repo:
            self.root = utils.find_common_root(self.abs_fnames)

        if self.abs_read_only_fnames:
            self.abs_read_only_fnames = set()
            for fname in self.abs_read_only_fnames:
                abs_fname = self.abs_root_path(fname)
                if os.path.exists(abs_fname):
                    self.abs_read_only_fnames.add(abs_fname)
                else:
                    self.io.tool_warning(
                        f"Error: Read-only file {fname} does not exist. Skipping."
                    )

        if self.map_tokens is None:
            use_repo_map = self.main_model.use_repo_map
            self.map_tokens = 1024
        else:
            use_repo_map = self.map_tokens > 0

        max_inp_tokens = self.main_model.info.get("max_input_tokens") or 0

        has_map_prompt = (
            hasattr(self, "gpt_prompts") and self.gpt_prompts.repo_content_prefix
        )

        if use_repo_map and self.repo and has_map_prompt:
            self.repo_map = RepoMap(
                self.map_tokens,
                self.root,
                self.main_model,
                self.io,
                self.gpt_prompts.repo_content_prefix,
                self.verbose,
                max_inp_tokens,
                self.map_mul_no_files,
                self.map_refresh,
            )

        self.summarizer = self.summarizer or ChatSummary(
            [self.main_model],
            self.main_model.max_chat_history_tokens,
        )

        self.summarizer_thread = None
        self.summarized_done_messages = []
        self.summarizing_messages = None

        if not self.done_messages and self.restore_chat_history:
            history_md = self.io.read_text(self.io.chat_history_file)
            if history_md:
                self.done_messages = utils.split_chat_history_markdown(history_md)
                self.summarize_start()

        # Linting and testing
        self.linter = Linter(root=self.root, encoding=self.io.encoding)
        self.auto_lint = self.auto_lint
        self.setup_lint_cmds(self.lint_cmds)
        self.lint_cmds = self.lint_cmds
        self.auto_test = self.auto_test
        self.test_cmd = self.test_cmd

        # validate the functions jsonschema
        if self.functions:
            from jsonschema import Draft7Validator

            for function in self.functions:
                Draft7Validator.check_schema(function)

            if self.verbose:
                self.io.tool_output("JSON Schema:")
                self.io.tool_output(json.dumps(self.functions, indent=4))

        self.last_asked_for_commit_time = 0  # Initialize as instance variable

    def setup_lint_cmds(self, lint_cmds):
        if not lint_cmds:
            return
        for lang, cmd in lint_cmds.items():
            self.linter.set_linter(lang, cmd)

    def show_announcements(self):
        bold = True
        for line in self.get_announcements():
            self.io.tool_output(line, bold=bold)
            bold = False

    def add_rel_fname(self, rel_fname):
        self.abs_fnames.add(self.abs_root_path(rel_fname))
        self.check_added_files()

    def drop_rel_fname(self, fname):
        abs_fname = self.abs_root_path(fname)
        if abs_fname in self.abs_fnames:
            self.abs_fnames.remove(abs_fname)
            return True

    def abs_root_path(self, path):
        key = path
        if key in self.abs_root_path_cache:
            return self.abs_root_path_cache[key]

        res = Path(self.root) / path
        res = utils.safe_abs_path(res)
        self.abs_root_path_cache[key] = res
        return res

    fences = all_fences
    fence = fences[0]

    def show_pretty(self):
        if not self.pretty:
            return False

        # only show pretty output if fences are the normal triple-backtick
        if self.fence[0][0] != "`":
            return False

        return True

    def get_abs_fnames_content(self):
        for fname in list(self.abs_fnames):
            content = self.io.read_text(fname)

            if content is None:
                relative_fname = self.get_rel_fname(fname)
                self.io.tool_warning(f"Dropping {relative_fname} from the chat.")
                self.abs_fnames.remove(fname)
            else:
                yield fname, content

    def choose_fence(self):
        all_content = ""
        for _fname, content in self.get_abs_fnames_content():
            all_content += content + "\n"
        for _fname in self.abs_read_only_fnames:
            content = self.io.read_text(_fname)
            if content is not None:
                all_content += content + "\n"

        lines = all_content.splitlines()
        good = False
        for fence_open, fence_close in self.fences:
            if any(
                line.startswith(fence_open) or line.startswith(fence_close)
                for line in lines
            ):
                continue
            good = True
            break

        if good:
            self.fence = (fence_open, fence_close)
        else:
            self.fence = self.fences[0]
            self.io.tool_warning(
                "Unable to find a fencing strategy! Falling back to:"
                f" {self.fence[0]}...{self.fence[1]}"
            )

        return

    def get_files_content(self, fnames=None):
        if not fnames:
            fnames = self.abs_fnames

        prompt = ""
        for fname, content in self.get_abs_fnames_content():
            if not is_image_file(fname):
                relative_fname = self.get_rel_fname(fname)
                prompt += "\n"
                prompt += relative_fname
                prompt += f"\n{self.fence[0]}\n"

                prompt += content

                # lines = content.splitlines(keepends=True)
                # lines = [f"{i+1:03}:{line}" for i, line in enumerate(lines)]
                # prompt += "".join(lines)

                prompt += f"{self.fence[1]}\n"

        return prompt

    def get_read_only_files_content(self):
        prompt = ""
        for fname in self.abs_read_only_fnames:
            content = self.io.read_text(fname)
            if content is not None and not is_image_file(fname):
                relative_fname = self.get_rel_fname(fname)
                prompt += "\n"
                prompt += relative_fname
                prompt += f"\n{self.fence[0]}\n"
                prompt += content
                prompt += f"{self.fence[1]}\n"
        return prompt

    def get_cur_message_text(self):
        """Get the text of the current message being processed."""
        if not self.cur_messages:
            return ""
        return self.cur_messages[-1].get("content", "")

    def get_file_mentions(self, text):
        """Extract file mentions from text."""
        if not text:
            return set()

        mentions = set()
        for rel_fname in self.get_addable_relative_files():
            if rel_fname in text:
                mentions.add(rel_fname)
        return mentions

    def get_ident_mentions(self, text):
        """Extract identifier mentions from text."""
        if not text:
            return set()

        # Simple word extraction - can be improved with better parsing
        words = set(re.findall(r"\b\w+\b", text))
        return words

    def get_ident_filename_matches(self, idents):
        all_fnames = defaultdict(set)
        for fname in self.get_all_relative_files():
            # Skip empty paths or just '.'
            if not fname or fname == ".":
                continue

            try:
                # Handle dotfiles properly
                path = Path(fname)
                base = path.stem.lower()  # Use stem instead of with_suffix("").name
                if len(base) >= 5:
                    all_fnames[base].add(fname)
            except ValueError:
                # Skip paths that can't be processed
                continue

        matches = set()
        for ident in idents:
            if len(ident) < 5:
                continue
            matches.update(all_fnames[ident.lower()])

        return matches

    def get_repo_map(self):
        if not self.repo_map:
            return ""

        cur_msg_text = self.get_cur_message_text()
        mentioned_fnames = self.get_file_mentions(cur_msg_text)
        mentioned_idents = self.get_ident_mentions(cur_msg_text)

        mentioned_fnames.update(self.get_ident_filename_matches(mentioned_idents))

        other_files = set(self.get_all_abs_files()) - set(self.abs_fnames)
        repo_content = self.repo_map.get_repo_map(
            self.abs_fnames,
            other_files,
            mentioned_fnames=mentioned_fnames,
            mentioned_idents=mentioned_idents,
        )

        # fall back to global repo map if files in chat are disjoint from rest of repo
        if not repo_content:
            repo_content = self.repo_map.get_repo_map(
                set(),
                set(self.get_all_abs_files()),
                mentioned_fnames=mentioned_fnames,
                mentioned_idents=mentioned_idents,
            )

        # fall back to completely unhinted repo
        if not repo_content:
            repo_content = self.repo_map.get_repo_map(
                set(),
                set(self.get_all_abs_files()),
            )

        return repo_content

    def get_repo_messages(self):
        repo_messages = []
        repo_content = self.get_repo_map()
        if repo_content:
            repo_messages += [
                dict(role="user", content=repo_content),
                dict(
                    role="assistant",
                    content="Ok, I won't try and edit those files without asking first.",
                ),
            ]
        return repo_messages

    def get_readonly_files_messages(self):
        readonly_messages = []

        # Handle non-image files
        read_only_content = self.get_read_only_files_content()
        if read_only_content:
            readonly_messages += [
                dict(
                    role="user",
                    content=self.gpt_prompts.read_only_files_prefix + read_only_content,
                ),
                dict(
                    role="assistant",
                    content="Ok, I will use these files as references.",
                ),
            ]

        # Handle image files
        images_message = self.get_images_message(self.abs_read_only_fnames)
        if images_message is not None:
            readonly_messages += [
                images_message,
                dict(
                    role="assistant",
                    content="Ok, I will use these images as references.",
                ),
            ]

        return readonly_messages

    def get_chat_files_messages(self):
        chat_files_messages = []
        if self.abs_fnames:
            files_content = self.gpt_prompts.files_content_prefix
            files_content += self.get_files_content()
            files_reply = self.gpt_prompts.files_content_assistant_reply
        elif self.get_repo_map() and self.gpt_prompts.files_no_full_files_with_repo_map:
            files_content = self.gpt_prompts.files_no_full_files_with_repo_map
            files_reply = self.gpt_prompts.files_no_full_files_with_repo_map_reply
        else:
            files_content = self.gpt_prompts.files_no_full_files
            files_reply = "Ok."

        if files_content:
            chat_files_messages += [
                dict(role="user", content=files_content),
                dict(role="assistant", content=files_reply),
            ]

        images_message = self.get_images_message(self.abs_fnames)
        if images_message is not None:
            chat_files_messages += [
                images_message,
                dict(role="assistant", content="Ok."),
            ]

        return chat_files_messages

    def get_images_message(self, fnames):
        supports_images = self.main_model.info.get("supports_vision")
        supports_pdfs = self.main_model.info.get(
            "supports_pdf_input"
        ) or self.main_model.info.get("max_pdf_size_mb")

        # https://github.com/BerriAI/litellm/pull/6928
        supports_pdfs = (
            supports_pdfs or "claude-3-5-sonnet-20241022" in self.main_model.name
        )

        if not (supports_images or supports_pdfs):
            return None

        image_messages = []
        for fname in fnames:
            if not is_image_file(fname):
                continue

            mime_type, _ = mimetypes.guess_type(fname)
            if not mime_type:
                continue

            with open(fname, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            image_url = f"data:{mime_type};base64,{encoded_string}"
            rel_fname = self.get_rel_fname(fname)

            if mime_type.startswith("image/") and supports_images:
                image_messages += [
                    {"type": "text", "text": f"Image file: {rel_fname}"},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    },
                ]
            elif mime_type == "application/pdf" and supports_pdfs:
                image_messages += [
                    {"type": "text", "text": f"PDF file: {rel_fname}"},
                    {"type": "image_url", "image_url": image_url},
                ]

        if not image_messages:
            return None

        return {"role": "user", "content": image_messages}

    def run_stream(self, user_message):
        self.io.user_input(user_message)
        self.init_before_message()
        yield from self.send_message(user_message)

    def init_before_message(self):
        self.aider_edited_files = set()
        self.reflected_message = None
        self.num_reflections = 0
        self.lint_outcome = None
        self.test_outcome = None
        self.shell_commands = []
        self.message_cost = 0

        if self.repo:
            self.commit_before_message.append(self.repo.get_head_commit_sha())

    def run(self, with_message=None, preproc=True):
        try:
            logger.info("Iniciando coder")
            if with_message:
                self.io.user_input(with_message)
                self.run_one(with_message, preproc)
                return self.partial_response_content
            while True:
                try:
                    if not self.io.placeholder:
                        self.copy_context()
                    user_message = self.get_input()
                    self.run_one(user_message, preproc)
                    self.show_undo_hint()
                except KeyboardInterrupt:
                    logger.info("Interrupção do usuário recebida")
                    self.keyboard_interrupt()
        except EOFError:
            return

    def copy_context(self):
        if self.auto_copy_context:
            self.commands.cmd_copy_context()

    def get_input(self):
        inchat_files = self.get_inchat_relative_files()
        read_only_files = [
            self.get_rel_fname(fname) for fname in self.abs_read_only_fnames
        ]
        all_files = sorted(set(inchat_files + read_only_files))
        edit_format = (
            "" if self.edit_format == self.main_model.edit_format else self.edit_format
        )
        return self.io.get_input(
            self.root,
            all_files,
            self.get_addable_relative_files(),
            self.commands,
            self.abs_read_only_fnames,
            edit_format=edit_format,
        )

    def preproc_user_input(self, inp):
        if not inp:
            return

        if self.commands.is_command(inp):
            return self.commands.run(inp)

        self.check_for_file_mentions(inp)
        inp = self.check_for_urls(inp)

        return inp

    def run_one(self, user_message, preproc):
        self.init_before_message()

        if preproc:
            message = self.preproc_user_input(user_message)
        else:
            message = user_message

        while message:
            self.reflected_message = None
            list(self.send_message(message))

            if not self.reflected_message:
                break

            if self.num_reflections >= self.max_reflections:
                self.io.tool_warning(
                    f"Only {self.max_reflections} reflections allowed, stopping."
                )
                return

            self.num_reflections += 1
            message = self.reflected_message

    def check_and_open_urls(self, exc, friendly_msg=None):
        """Check exception for URLs, offer to open in a browser, with user-friendly error msgs."""
        text = str(exc)

        if friendly_msg:
            self.io.tool_warning(text)
            self.io.tool_error(f"{friendly_msg}")
        else:
            self.io.tool_error(text)

        url_pattern = re.compile(r"(https?://[^\s/$.?#].[^\s]*)")
        urls = list(set(url_pattern.findall(text)))  # Use set to remove duplicates
        for url in urls:
            url = url.rstrip(".',\"")
            self.io.offer_url(url)
        return urls

    def check_for_urls(self, inp: str) -> List[str]:
        """Check input for URLs and offer to add them to the chat."""
        if not self.detect_urls:
            return inp

        url_pattern = re.compile(r"(https?://[^\s/$.?#].[^\s]*[^\s,.])")
        urls = list(set(url_pattern.findall(inp)))  # Use set to remove duplicates
        group = ConfirmGroup(urls)
        for url in urls:
            if url not in self.rejected_urls:
                url = url.rstrip(".',\"")
                if self.io.confirm_ask(
                    "Add URL to the chat?", subject=url, group=group, allow_never=True
                ):
                    inp += "\n\n"
                    inp += self.commands.cmd_web(url, return_content=True)
                else:
                    self.rejected_urls.add(url)

        return inp

    def keyboard_interrupt(self):
        now = time.time()

        thresh = 2  # seconds
        if self.last_keyboard_interrupt and now - self.last_keyboard_interrupt < thresh:
            self.io.tool_warning("\n\n^C KeyboardInterrupt")
            self.event("exit", reason="Control-C")
            sys.exit()

        self.io.tool_warning("\n\n^C again to exit")

        self.last_keyboard_interrupt = now

    def summarize_start(self):
        if not self.summarizer.too_big(self.done_messages):
            return

        self.summarize_end()

        if self.verbose:
            self.io.tool_output("Starting to summarize chat history.")

        self.summarizer_thread = threading.Thread(target=self.summarize_worker)
        self.summarizer_thread.start()

    def summarize_worker(self):
        self.summarizing_messages = list(self.done_messages)
        try:
            self.summarized_done_messages = self.summarizer.summarize(
                self.summarizing_messages
            )
        except ValueError as err:
            self.io.tool_warning(err.args[0])

        if self.verbose:
            self.io.tool_output("Finished summarizing chat history.")

    def summarize_end(self):
        if self.summarizer_thread is None:
            return

        self.summarizer_thread.join()
        self.summarizer_thread = None

        if self.summarizing_messages == self.done_messages:
            self.done_messages = self.summarized_done_messages
        self.summarizing_messages = None
        self.summarized_done_messages = []

    def move_back_cur_messages(self, message):
        self.done_messages += self.cur_messages
        self.summarize_start()

        # TODO check for impact on image messages
        if message:
            self.done_messages += [
                dict(role="user", content=message),
                dict(role="assistant", content="Ok."),
            ]
        self.cur_messages = []

    def get_user_language(self):
        if self.chat_language:
            return self.chat_language

        try:
            lang = locale.getlocale()[0]
            if lang:
                return lang  # Return the full language code, including country
        except Exception:
            pass

        for env_var in ["LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES"]:
            lang = os.environ.get(env_var)
            if lang:
                return lang.split(".")[
                    0
                ]  # Return language and country, but remove encoding if present

        return None

    def get_platform_info(self):
        platform_text = f"- Platform: {platform.platform()}\n"
        shell_var = "COMSPEC" if os.name == "nt" else "SHELL"
        shell_val = os.getenv(shell_var)
        platform_text += f"- Shell: {shell_var}={shell_val}\n"

        user_lang = self.get_user_language()
        if user_lang:
            platform_text += f"- Language: {user_lang}\n"

        dt = datetime.now().astimezone().strftime("%Y-%m-%d")
        platform_text += f"- Current date: {dt}\n"

        if self.repo:
            platform_text += "- The user is operating inside a git repository\n"

        if self.lint_cmds:
            if self.auto_lint:
                platform_text += (
                    "- The user's pre-commit runs these lint commands, don't suggest running"
                    " them:\n"
                )
            else:
                platform_text += "- The user prefers these lint commands:\n"
            for lang, cmd in self.lint_cmds.items():
                if lang is None:
                    platform_text += f"  - {cmd}\n"
                else:
                    platform_text += f"  - {lang}: {cmd}\n"

        if self.test_cmd:
            if self.auto_test:
                platform_text += "- The user's pre-commit runs this test command, don't suggest running them: "
            else:
                platform_text += "- The user prefers this test command: "
            platform_text += self.test_cmd + "\n"

        return platform_text

    def fmt_system_prompt(self, prompt):
        lazy_prompt = self.gpt_prompts.lazy_prompt if self.main_model.lazy else ""
        platform_text = self.get_platform_info()

        if self.suggest_shell_commands:
            shell_cmd_prompt = self.gpt_prompts.shell_cmd_prompt.format(
                platform=platform_text
            )
            shell_cmd_reminder = self.gpt_prompts.shell_cmd_reminder.format(
                platform=platform_text
            )
        else:
            shell_cmd_prompt = self.gpt_prompts.no_shell_cmd_prompt.format(
                platform=platform_text
            )
            shell_cmd_reminder = self.gpt_prompts.no_shell_cmd_reminder.format(
                platform=platform_text
            )

        if self.chat_language:
            language = self.chat_language
        else:
            language = "the same language they are using"

        prompt = prompt.format(
            fence=self.fence,
            lazy_prompt=lazy_prompt,
            platform=platform_text,
            shell_cmd_prompt=shell_cmd_prompt,
            shell_cmd_reminder=shell_cmd_reminder,
            language=language,
        )
        return prompt

    def format_chat_chunks(self):
        self.choose_fence()
        main_sys = self.fmt_system_prompt(self.gpt_prompts.main_system)

        example_messages = []
        if self.main_model.examples_as_sys_msg:
            if self.gpt_prompts.example_messages:
                main_sys += "\n# Example conversations:\n\n"
            for msg in self.gpt_prompts.example_messages:
                role = msg["role"]
                content = self.fmt_system_prompt(msg["content"])
                main_sys += f"## {role.upper()}: {content}\n\n"
            main_sys = main_sys.strip()
        else:
            for msg in self.gpt_prompts.example_messages:
                example_messages.append(
                    dict(
                        role=msg["role"], content=self.fmt_system_prompt(msg["content"])
                    )
                )

        if self.gpt_prompts.system_reminder:
            main_sys += "\n" + self.fmt_system_prompt(self.gpt_prompts.system_reminder)

        chunks = ChatChunks()

        if self.main_model.use_system_prompt:
            chunks.system = [
                dict(role="system", content=main_sys),
            ]
        else:
            chunks.system = [
                dict(role="user", content=main_sys),
                dict(role="assistant", content="Ok."),
            ]

        chunks.examples = example_messages

        self.summarize_end()
        chunks.done = self.done_messages

        chunks.repo = self.get_repo_messages()
        chunks.readonly_files = self.get_readonly_files_messages()
        chunks.chat_files = self.get_chat_files_messages()

        if self.gpt_prompts.system_reminder:
            reminder_message = [
                dict(
                    role="system",
                    content=self.fmt_system_prompt(self.gpt_prompts.system_reminder),
                ),
            ]
        else:
            reminder_message = []

        chunks.cur = list(self.cur_messages)
        chunks.reminder = []

        # TODO review impact of token count on image messages
        messages_tokens = self.main_model.token_count(chunks.all_messages())
        reminder_tokens = self.main_model.token_count(reminder_message)
        cur_tokens = self.main_model.token_count(chunks.cur)

        if None not in (messages_tokens, reminder_tokens, cur_tokens):
            total_tokens = messages_tokens + reminder_tokens + cur_tokens
        else:
            # add the reminder anyway
            total_tokens = 0

        if chunks.cur:
            final = chunks.cur[-1]
        else:
            final = None

        max_input_tokens = self.main_model.info.get("max_input_tokens") or 0
        # Add the reminder prompt if we still have room to include it.
        if (
            not max_input_tokens
            or total_tokens < max_input_tokens
            and self.gpt_prompts.system_reminder
        ):
            if self.main_model.reminder == "sys":
                chunks.reminder = reminder_message
            elif (
                self.main_model.reminder == "user" and final and final["role"] == "user"
            ):
                # stuff it into the user message
                new_content = (
                    final["content"]
                    + "\n\n"
                    + self.fmt_system_prompt(self.gpt_prompts.system_reminder)
                )
                chunks.cur[-1] = dict(role=final["role"], content=new_content)

        return chunks

    def format_messages(self):
        chunks = self.format_chat_chunks()
        if self.add_cache_headers:
            chunks.add_cache_control_headers()

        return chunks

    def warm_cache(self, chunks):
        if not self.add_cache_headers:
            return
        if not self.num_cache_warming_pings:
            return

        delay = 5 * 60 - 5
        self.next_cache_warm = time.time() + delay
        self.warming_pings_left = self.num_cache_warming_pings
        self.cache_warming_chunks = chunks

        if self.cache_warming_thread:
            return

        def warm_cache_worker():
            while True:
                time.sleep(1)
                if self.warming_pings_left <= 0:
                    continue
                now = time.time()
                if now < self.next_cache_warm:
                    continue

                self.warming_pings_left -= 1
                self.next_cache_warm = time.time() + delay

                kwargs = dict(self.main_model.extra_params) or dict()
                kwargs["max_tokens"] = 1

                try:
                    completion = litellm.completion(
                        model=self.main_model.name,
                        messages=self.cache_warming_chunks.cacheable_messages(),
                        stream=False,
                        **kwargs,
                    )
                except Exception as err:
                    self.io.tool_warning(f"Cache warming error: {str(err)}")
                    continue

                cache_hit_tokens = getattr(
                    completion.usage, "prompt_cache_hit_tokens", 0
                ) or getattr(completion.usage, "cache_read_input_tokens", 0)

                if self.verbose:
                    self.io.tool_output(
                        f"Warmed {format_tokens(cache_hit_tokens)} cached tokens."
                    )

        self.cache_warming_thread = threading.Timer(0, warm_cache_worker)
        self.cache_warming_thread.daemon = True
        self.cache_warming_thread.start()

        return chunks

    def check_tokens(self, messages):
        """Check if the messages will fit within the model's token limits."""
        input_tokens = self.main_model.token_count(messages)
        max_input_tokens = self.main_model.info.get("max_input_tokens") or 0

        proceed = None

        if max_input_tokens and input_tokens >= max_input_tokens:
            self.io.tool_error(
                f"Your estimated chat context of {input_tokens:,} tokens exceeds the"
                f" {max_input_tokens:,} token limit for {self.main_model.name}!"
            )
            self.io.tool_output("To reduce the chat context:")
            self.io.tool_output("- Use /drop to remove unneeded files from the chat")
            self.io.tool_output("- Use /clear to clear the chat history")
            self.io.tool_output("- Break your code into smaller files")
            proceed = "Y"
            self.io.tool_output(
                "It's probably safe to try and send the request, most providers won't charge if"
                " the context limit is exceeded."
            )

        # Special warning for Ollama models about context window size
        if self.main_model.name.startswith(("ollama/", "ollama_chat/")):
            extra_params = getattr(self.main_model, "extra_params", None) or {}
            num_ctx = extra_params.get("num_ctx", 2048)
            if input_tokens > num_ctx:
                proceed = "N"
                self.io.tool_warning(
                    f"""
Your Ollama model is configured with num_ctx={num_ctx} tokens of context window.
You are attempting to send {input_tokens} tokens.
See https://aider.chat/docs/llms/ollama.html#setting-the-context-window-size
""".strip()
                )  # noqa

        if proceed and not self.io.confirm_ask(
            "Try to proceed anyway?", default=proceed
        ):
            return False
        return True

    def send_message(self, inp):
        self.event("message_send_starting")

        self.cur_messages += [
            dict(role="user", content=inp),
        ]

        chunks = self.format_messages()
        messages = chunks.all_messages()
        if not self.check_tokens(messages):
            return
        self.warm_cache(chunks)

        if self.verbose:
            utils.show_messages(messages, functions=self.functions)

        self.multi_response_content = ""
        if self.show_pretty() and self.stream:
            self.mdstream = self.io.get_assistant_mdstream()
        else:
            self.mdstream = None

        retry_delay = 0.125

        litellm_ex = LiteLLMExceptions()

        self.usage_report = None
        exhausted = False
        interrupted = False
        try:
            while True:
                try:
                    yield from self.send(messages, functions=self.functions)
                    break
                except litellm_ex.exceptions_tuple() as err:
                    ex_info = litellm_ex.get_ex_info(err)

                    if ex_info.name == "ContextWindowExceededError":
                        exhausted = True
                        break

                    should_retry = ex_info.retry
                    if should_retry:
                        retry_delay *= 2
                        if retry_delay > RETRY_TIMEOUT:
                            should_retry = False

                    if not should_retry:
                        self.mdstream = None
                        self.check_and_open_urls(err, ex_info.description)
                        break

                    err_msg = str(err)
                    if ex_info.description:
                        self.io.tool_warning(err_msg)
                        self.io.tool_error(ex_info.description)
                    else:
                        self.io.tool_error(err_msg)

                    self.io.tool_output(f"Retrying in {retry_delay:.1f} seconds...")
                    time.sleep(retry_delay)
                    continue
                except KeyboardInterrupt:
                    interrupted = True
                    break
                except FinishReasonLength:
                    # We hit the output limit!
                    if not self.main_model.info.get("supports_assistant_prefill"):
                        exhausted = True
                        break

                    self.multi_response_content = self.get_multi_response_content()

                    if messages[-1]["role"] == "assistant":
                        messages[-1]["content"] = self.multi_response_content
                    else:
                        messages.append(
                            dict(
                                role="assistant",
                                content=self.multi_response_content,
                                prefix=True,
                            )
                        )
                except Exception as err:
                    self.mdstream = None
                    lines = traceback.format_exception(
                        type(err), err, err.__traceback__
                    )
                    self.io.tool_warning("".join(lines))
                    self.io.tool_error(str(err))
                    self.event("message_send_exception", exception=str(err))
                    return
        finally:
            if self.mdstream:
                self.live_incremental_response(True)
                self.mdstream = None

            self.partial_response_content = self.get_multi_response_content(True)
            self.multi_response_content = ""

        self.io.tool_output()

        self.show_usage_report()

        self.add_assistant_reply_to_cur_messages()

        if exhausted:
            if self.cur_messages and self.cur_messages[-1]["role"] == "user":
                self.cur_messages += [
                    dict(
                        role="assistant",
                        content="FinishReasonLength exception: you sent too many tokens",
                    ),
                ]

            self.show_exhausted_error()
            self.num_exhausted_context_windows += 1
            return

        if self.partial_response_function_call:
            args = self.parse_partial_args()
            if args:
                content = args.get("explanation") or ""
            else:
                content = ""
        elif self.partial_response_content:
            content = self.partial_response_content
        else:
            content = ""

        if not interrupted:
            add_rel_files_message = self.check_for_file_mentions(content)
            if add_rel_files_message:
                if self.reflected_message:
                    self.reflected_message += "\n\n" + add_rel_files_message
                else:
                    self.reflected_message = add_rel_files_message
                return

            try:
                self.reply_completed()
            except KeyboardInterrupt:
                interrupted = True

        if interrupted:
            if self.cur_messages and self.cur_messages[-1]["role"] == "user":
                self.cur_messages[-1]["content"] += "\n^C KeyboardInterrupt"
            else:
                self.cur_messages += [dict(role="user", content="^C KeyboardInterrupt")]
            self.cur_messages += [
                dict(
                    role="assistant",
                    content="I see that you interrupted my previous reply.",
                )
            ]
            return

        edited = self.apply_updates()

        if edited:
            self.aider_edited_files.update(edited)
            saved_message = self.auto_commit(edited)

            if not saved_message and hasattr(
                self.gpt_prompts, "files_content_gpt_edits_no_repo"
            ):
                saved_message = self.gpt_prompts.files_content_gpt_edits_no_repo

            self.move_back_cur_messages(saved_message)

        if self.reflected_message:
            return

        if edited and self.auto_lint:
            lint_errors = self.lint_edited(edited)
            self.auto_commit(edited, context="Ran the linter")
            self.lint_outcome = not lint_errors
            if lint_errors:
                ok = self.io.confirm_ask("Attempt to fix lint errors?")
                if ok:
                    self.reflected_message = lint_errors
                    return

        shared_output = self.run_shell_commands()
        if shared_output:
            self.cur_messages += [
                dict(role="user", content=shared_output),
                dict(role="assistant", content="Ok"),
            ]

        if edited and self.auto_test:
            test_errors = self.commands.cmd_test(self.test_cmd)
            self.test_outcome = not test_errors
            if test_errors:
                ok = self.io.confirm_ask("Attempt to fix test errors?")
                if ok:
                    self.reflected_message = test_errors
                    return

    def reply_completed(self):
        pass

    def show_exhausted_error(self):
        output_tokens = 0
        if self.partial_response_content:
            output_tokens = self.main_model.token_count(self.partial_response_content)
        max_output_tokens = self.main_model.info.get("max_output_tokens") or 0

        input_tokens = self.main_model.token_count(
            self.format_messages().all_messages()
        )
        max_input_tokens = self.main_model.info.get("max_input_tokens") or 0

        total_tokens = input_tokens + output_tokens

        fudge = 0.7

        out_err = ""
        if output_tokens >= max_output_tokens * fudge:
            out_err = " -- possibly exceeded output limit!"

        inp_err = ""
        if input_tokens >= max_input_tokens * fudge:
            inp_err = " -- possibly exhausted context window!"

        tot_err = ""
        if total_tokens >= max_input_tokens * fudge:
            tot_err = " -- possibly exhausted context window!"

        res = ["", ""]
        res.append(f"Model {self.main_model.name} has hit a token limit!")
        res.append("Token counts below are approximate.")
        res.append("")
        res.append(f"Input tokens: ~{input_tokens:,} of {max_input_tokens:,}{inp_err}")
        res.append(
            f"Output tokens: ~{output_tokens:,} of {max_output_tokens:,}{out_err}"
        )
        res.append(f"Total tokens: ~{total_tokens:,} of {max_input_tokens:,}{tot_err}")

        if output_tokens >= max_output_tokens:
            res.append("")
            res.append("To reduce output tokens:")
            res.append("- Ask for smaller changes in each request.")
            res.append("- Break your code into smaller source files.")
            if "diff" not in self.main_model.edit_format:
                res.append("- Use a stronger model that can return diffs.")

        if input_tokens >= max_input_tokens or total_tokens >= max_input_tokens:
            res.append("")
            res.append("To reduce input tokens:")
            res.append("- Use /tokens to see token usage.")
            res.append("- Use /drop to remove unneeded files from the chat session.")
            res.append("- Use /clear to clear the chat history.")
            res.append("- Break your code into smaller source files.")

        res = "".join([line + "\n" for line in res])
        self.io.tool_error(res)
        self.io.offer_url(urls.token_limits)

    def lint_edited(self, fnames):
        res = ""
        for fname in fnames:
            if not fname:
                continue
            errors = self.linter.lint(self.abs_root_path(fname))

            if errors:
                res += "\n"
                res += errors
                res += "\n"

        if res:
            self.io.tool_warning(res)

        return res

    def add_assistant_reply_to_cur_messages(self):
        if self.partial_response_content:
            self.cur_messages += [
                dict(role="assistant", content=self.partial_response_content)
            ]
        if self.partial_response_function_call:
            self.cur_messages += [
                dict(
                    role="assistant",
                    content=None,
                    function_call=self.partial_response_function_call,
                )
            ]

    def check_for_file_mentions(self, content):
        if not content:
            return

        added_fnames = []
        for rel_fname in self.get_addable_relative_files():
            if rel_fname in content:
                self.add_rel_fname(rel_fname)
                added_fnames.append(rel_fname)

        if added_fnames:
            return f"Added mentioned files to chat: {', '.join(added_fnames)}"

    def send(self, messages, model=None, functions=None):
        try:
            completion = litellm.completion(
                model=model or self.main_model.name,
                messages=messages,
                stream=True,
                functions=functions,
                **self.main_model.extra_params,
            )
            if completion.choices[0].message.tool_calls:
                self.partial_response_function_call = (
                    completion.choices[0].message.tool_calls[0].function
                )
        except AttributeError as func_err:
            self.io.tool_error(f"Error accessing function call: {func_err}")
            return None
        except Exception as err:
            self.io.tool_error(f"Error during completion: {err}")
            return None

        return completion

    def get_inchat_relative_files(self):
        """Return a list of relative paths for files in the chat"""
        files = [os.path.relpath(fname, self.root) for fname in self.abs_fnames]
        return sorted(set(files))

    def get_rel_fname(self, fname):
        """Return the relative path for a file"""
        try:
            return os.path.relpath(fname, self.root)
        except ValueError:
            return fname

    def abs_root_path(self, path):
        """Return the absolute path for a file"""
        if os.path.isabs(path):
            return path
        return os.path.join(self.root, path)

    def get_addable_relative_files(self):
        """Return a list of relative paths for files that can be added to the chat"""
        all_files = set(self.get_all_relative_files())
        inchat_files = set(self.get_inchat_relative_files())
        read_only_files = set(
            self.get_rel_fname(fname) for fname in self.abs_read_only_fnames
        )
        return all_files - inchat_files - read_only_files

    def get_all_relative_files(self):
        """Return a list of all relative paths in the repository"""
        if self.repo:
            files = self.repo.get_tracked_files()
        else:
            files = self.get_inchat_relative_files()
        return sorted(set(files))

    def get_mentioned_idents(self):
        """Get identifiers mentioned in the current message."""
        cur_msg_text = self.get_cur_message_text()
        if not cur_msg_text:
            return set()
        return self.get_ident_mentions(cur_msg_text)

    def show_undo_hint(self):
        """Show hint about undo command if needed."""
        if not self.done_messages:
            return

        last_msg = self.done_messages[-1]
        if last_msg.get("role") != "assistant":
            return

        if not self.io.pretty:
            return

        if not self.show_diffs:
            return

        if self.dry_run:
            return

        if not self.repo:
            return

        if not self.repo.last_aider_commit_hash:
            return

        if time.time() - self.last_asked_for_commit_time < 60:
            return

        self.io.tool_output("Use /undo to revert the last edit")
        self.last_asked_for_commit_time = time.time()

    def get_all_abs_files(self):
        """Get all absolute file paths in the repository."""
        if self.repo:
            return self.repo.get_tracked_files()
        return list(self.abs_fnames)
