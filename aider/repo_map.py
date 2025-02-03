def get_repo_map(self, chat_history, mentioned_fnames, max_tokens):
    if not self.repo_map_active:
        return ""

    all_files = set(self.get_all_files())
    if not all_files:
        return ""

    repo_content = self._build_repo_map(
        all_files,
        mentioned_fnames,
        max_tokens,
    )
    return repo_content


def _build_repo_map(self, files, mentioned_fnames, max_tokens):
    if not files:
        return ""

    content = []
    total_tokens = 0

    for fname in sorted(files):
        if total_tokens >= max_tokens:
            break

        file_content = self._get_file_content(fname)
        if not file_content:
            continue

        estimated_tokens = len(file_content.split()) * 1.3
        if total_tokens + estimated_tokens > max_tokens:
            continue

        content.append(f"File: {fname}\n{file_content}\n")
        total_tokens += estimated_tokens

    return "\n".join(content)


def _get_file_content(self, fname):
    try:
        with open(fname, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
