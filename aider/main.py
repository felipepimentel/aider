import configparser
import json
import os
import re
import sys
import threading
import traceback
from pathlib import Path

try:
    import git
except ImportError:
    git = None

import logging

import importlib_resources
from dotenv import load_dotenv

from aider import __version__, models, urls, utils
from aider.args import parse_args
from aider.coders import Coder
from aider.io import InputOutput
from aider.litellm_init import init_litellm
from aider.llm import litellm  # noqa: F401; properly init litellm on launch
from aider.logging import setup_logging
from aider.models import Model
from aider.repo import ANY_GIT_ERROR, GitRepo

from .dump import dump  # noqa: F401

logger = logging.getLogger(__name__)


def check_config_files_for_yes(config_files):
    found = False
    for config_file in config_files:
        if Path(config_file).exists():
            try:
                with open(config_file, "r") as f:
                    for line in f:
                        if line.strip().startswith("yes:"):
                            print("Configuration error detected.")
                            print(
                                f"The file {config_file} contains a line starting with 'yes:'"
                            )
                            print(
                                "Please replace 'yes:' with 'yes-always:' in this file."
                            )
                            found = True
            except Exception:
                pass
    return found


def get_git_root():
    """Get the root directory of the git repository.

    Returns:
        Path to git root directory or None if not in a repo
    """
    try:
        try:
            repo = git.Repo(search_parent_directories=True)
            return repo.git.rev_parse("--show-toplevel")
        except git.InvalidGitRepositoryError:
            return None
    except ImportError:
        return None


def guessed_wrong_repo(io, git_root, fnames, git_dname):
    """After we parse the args, we can determine the real repo. Did we guess wrong?"""

    try:
        check_repo = Path(GitRepo(io, fnames, git_dname).root).resolve()
    except (OSError,) + ANY_GIT_ERROR:
        return

    # we had no guess, rely on the "true" repo result
    if not git_root:
        return str(check_repo)

    git_root = Path(git_root).resolve()
    if check_repo == git_root:
        return

    return str(check_repo)


def make_new_repo(git_root, io):
    try:
        repo = git.Repo.init(git_root)
        check_gitignore(git_root, io, False)
    except ANY_GIT_ERROR as err:  # issue #1233
        io.tool_error(f"Unable to create git repo in {git_root}")
        io.tool_output(str(err))
        return

    io.tool_output(f"Git repository created in {git_root}")
    return repo


def setup_git(git_root, io):
    if git is None:
        return

    try:
        cwd = Path.cwd()
    except OSError:
        cwd = None

    repo = None

    if git_root:
        try:
            repo = git.Repo(git_root)
        except ANY_GIT_ERROR:
            pass
    elif cwd == Path.home():
        io.tool_warning(
            "You should probably run aider in your project's directory, not your home dir."
        )
        return
    elif cwd:
        git_root = str(cwd.resolve())
        repo = make_new_repo(git_root, io)

    if not repo:
        return

    user_name = None
    user_email = None
    with repo.config_reader() as config:
        try:
            user_name = config.get_value("user", "name", None)
        except (configparser.NoSectionError, configparser.NoOptionError):
            pass
        try:
            user_email = config.get_value("user", "email", None)
        except (configparser.NoSectionError, configparser.NoOptionError):
            pass

    if user_name and user_email:
        return repo.working_tree_dir

    with repo.config_writer() as git_config:
        if not user_name:
            git_config.set_value("user", "name", "Your Name")
            io.tool_warning('Update git name with: git config user.name "Your Name"')
        if not user_email:
            git_config.set_value("user", "email", "you@example.com")
            io.tool_warning(
                'Update git email with: git config user.email "you@example.com"'
            )

    return repo.working_tree_dir


def check_gitignore(git_root, io, ask=True):
    if not git_root:
        return

    try:
        repo = git.Repo(git_root)
        if repo.ignored(".aider") and repo.ignored(".env"):
            return
    except ANY_GIT_ERROR:
        pass

    patterns = [".aider*", ".env"]
    patterns_to_add = []

    gitignore_file = Path(git_root) / ".gitignore"
    if gitignore_file.exists():
        try:
            content = io.read_text(gitignore_file)
            if content is None:
                return
            existing_lines = content.splitlines()
            for pat in patterns:
                if pat not in existing_lines:
                    if "*" in pat or (Path(git_root) / pat).exists():
                        patterns_to_add.append(pat)
        except OSError as e:
            io.tool_error(f"Error when trying to read {gitignore_file}: {e}")
            return
    else:
        content = ""
        patterns_to_add = patterns

    if not patterns_to_add:
        return

    if content and not content.endswith("\n"):
        content += "\n"
    content += "\n".join(patterns_to_add) + "\n"

    try:
        io.write_text(gitignore_file, content)
        io.tool_output(f"Added {', '.join(patterns_to_add)} to .gitignore")
    except OSError as e:
        io.tool_error(f"Error when trying to write to {gitignore_file}: {e}")
        io.tool_output(
            "Try running with appropriate permissions or manually add these patterns to .gitignore:"
        )
        for pattern in patterns_to_add:
            io.tool_output(f"  {pattern}")


def check_streamlit_install(io):
    return utils.check_pip_install_extra(
        io,
        "streamlit",
        "You need to install the aider browser feature",
        ["aider-chat[browser]"],
    )


def write_streamlit_credentials():
    from streamlit.file_util import get_streamlit_file_path

    # See https://github.com/Aider-AI/aider/issues/772

    credential_path = Path(get_streamlit_file_path()) / "credentials.toml"
    if not os.path.exists(credential_path):
        empty_creds = '[general]\nemail = ""\n'

        os.makedirs(os.path.dirname(credential_path), exist_ok=True)
        with open(credential_path, "w") as f:
            f.write(empty_creds)
    else:
        print("Streamlit credentials already exist.")


def launch_gui(args):
    from streamlit.web import cli

    from aider import gui

    print()
    print("CONTROL-C to exit...")

    # Necessary so streamlit does not prompt the user for an email address.
    write_streamlit_credentials()

    target = gui.__file__

    st_args = ["run", target]

    st_args += [
        "--browser.gatherUsageStats=false",
        "--runner.magicEnabled=false",
        "--server.runOnSave=false",
    ]

    # https://github.com/Aider-AI/aider/issues/2193
    is_dev = "-dev" in str(__version__)

    if is_dev:
        print("Watching for file changes.")
    else:
        st_args += [
            "--global.developmentMode=false",
            "--server.fileWatcherType=none",
            "--client.toolbarMode=viewer",  # minimal?
        ]

    st_args += ["--"] + args

    cli.main(st_args)

    # from click.testing import CliRunner
    # runner = CliRunner()
    # from streamlit.web import bootstrap
    # bootstrap.load_config_options(flag_options={})
    # cli.main_run(target, args)
    # sys.argv = ['streamlit', 'run', '--'] + args


def parse_lint_cmds(lint_cmds, io):
    err = False
    res = dict()
    for lint_cmd in lint_cmds:
        if re.match(r"^[a-z]+:.*", lint_cmd):
            pieces = lint_cmd.split(":")
            lang = pieces[0]
            cmd = lint_cmd[len(lang) + 1 :]
            lang = lang.strip()
        else:
            lang = None
            cmd = lint_cmd

        cmd = cmd.strip()

        if cmd:
            res[lang] = cmd
        else:
            io.tool_error(f'Unable to parse --lint-cmd "{lint_cmd}"')
            io.tool_output('The arg should be "language: cmd --args ..."')
            io.tool_output('For example: --lint-cmd "python: flake8 --select=E9"')
            err = True
    if err:
        return
    return res


def generate_search_path_list(default_file, git_root, command_line_file=None):
    """Generate a list of paths to search for configuration files.

    Args:
        default_file: Default filename to search for
        git_root: Git repository root directory
        command_line_file: Optional file specified on command line

    Returns:
        List of paths to search in priority order
    """
    search_paths = []

    # Add command line file if specified
    if command_line_file:
        search_paths.append(command_line_file)

    # Add current directory
    search_paths.append(os.path.join(os.getcwd(), default_file))

    # Add git root if available
    if git_root:
        search_paths.append(os.path.join(git_root, default_file))

    # Add user's home directory
    search_paths.append(os.path.join(str(Path.home()), default_file))

    # Add aider config directory in home
    search_paths.append(os.path.join(str(Path.home()), ".aider", default_file))

    # Remove duplicates while preserving order
    seen = set()
    unique_paths = []
    for path in search_paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)

    return unique_paths


def register_models(git_root, model_settings_fname, io, verbose=False):
    model_settings_files = generate_search_path_list(
        ".aider.model.settings.yml", git_root, model_settings_fname
    )

    try:
        files_loaded = models.register_models(model_settings_files)
        if len(files_loaded) > 0:
            logger.info("Configurações de modelo carregadas de:")
            for file_loaded in files_loaded:
                logger.info("  - %s", file_loaded)
        else:
            logger.info("Nenhum arquivo de configuração de modelo carregado")
    except Exception as e:
        logger.error("Erro ao carregar configurações do modelo aider: %s", e)
        return 1

    logger.debug("Procurou arquivos de configuração de modelo em:")
    for file in model_settings_files:
        logger.debug("  - %s", file)

    return None


def load_dotenv_files(git_root, dotenv_fname, encoding="utf-8"):
    """Load environment variables from .env files.

    Args:
        git_root: Git repository root directory
        dotenv_fname: Name of the .env file
        encoding: File encoding to use

    Returns:
        List of successfully loaded .env files
    """
    logger.debug("Loading environment variables from .env files")
    loaded_files = []

    # Generate list of potential .env file paths
    search_paths = generate_search_path_list(dotenv_fname, git_root)
    logger.debug("Searching for .env files in: %s", search_paths)

    # Load each .env file if it exists
    for env_path in search_paths:
        if os.path.exists(env_path):
            try:
                load_dotenv(env_path, override=True, encoding=encoding)
                loaded_files.append(env_path)
                logger.info(
                    "Successfully loaded environment variables from %s", env_path
                )
            except UnicodeDecodeError as e:
                logger.error("Encoding error loading %s: %s", env_path, e)
                logger.info("Try using a different encoding (current: %s)", encoding)
            except PermissionError as e:
                logger.error("Permission denied reading %s: %s", env_path, e)
            except Exception as e:
                logger.error("Unexpected error loading %s: %s", env_path, e)
                logger.debug("Full traceback:", exc_info=True)

    if not loaded_files:
        logger.warning("No .env files were found or successfully loaded")
    else:
        logger.debug("Loaded %d .env files", len(loaded_files))

    return loaded_files


def register_litellm_models(git_root, model_metadata_fname, io, verbose=False):
    model_metadata_files = []

    # Add the resource file path
    resource_metadata = importlib_resources.files("aider.resources").joinpath(
        "model-metadata.json"
    )
    model_metadata_files.append(str(resource_metadata))

    model_metadata_files += generate_search_path_list(
        ".aider.model.metadata.json", git_root, model_metadata_fname
    )

    try:
        model_metadata_files_loaded = models.register_litellm_models(
            model_metadata_files
        )
        if len(model_metadata_files_loaded) > 0 and verbose:
            io.tool_output("Loaded model metadata from:")
            for model_metadata_file in model_metadata_files_loaded:
                io.tool_output(f"  - {model_metadata_file}")  # noqa: E221
    except Exception as e:
        io.tool_error(f"Error loading model metadata models: {e}")
        return 1


def sanity_check_repo(repo, io):
    if not repo:
        return True

    if not repo.repo.working_tree_dir:
        io.tool_error("The git repo does not seem to have a working tree?")
        return False

    bad_ver = False
    try:
        repo.get_tracked_files()
        if not repo.git_repo_error:
            return True
        error_msg = str(repo.git_repo_error)
    except UnicodeDecodeError as exc:
        error_msg = (
            "Failed to read the Git repository. This issue is likely caused by a path encoded "
            f'in a format different from the expected encoding "{sys.getfilesystemencoding()}".\n'
            f"Internal error: {str(exc)}"
        )
    except ANY_GIT_ERROR as exc:
        error_msg = str(exc)
        bad_ver = "version in (1, 2)" in error_msg
    except AssertionError as exc:
        error_msg = str(exc)
        bad_ver = True

    if bad_ver:
        io.tool_error("Aider only works with git repos with version number 1 or 2.")
        io.tool_output(
            "You may be able to convert your repo: git update-index --index-version=2"
        )
        io.tool_output("Or run aider --no-git to proceed without using git.")
        io.offer_url(urls.git_index_version, "Open documentation url for more info?")
        return False

    io.tool_error("Unable to read git repository, it may be corrupt?")
    io.tool_output(error_msg)
    return False


def main():
    """Main entry point for aider."""
    args = parse_args()
    setup_logging(args)

    # Load environment variables first
    git_root = get_git_root()
    load_dotenv_files(git_root, ".env")

    # Initialize LiteLLM after environment variables are loaded
    init_litellm()

    # Initialize InputOutput after environment is set up
    io = InputOutput(args)

    try:
        # Initialize provider if using StackSpot
        provider = None
        if args.model.startswith("stackspot") and not os.environ.get("AIDER_TEST_MODE"):
            from aider.providers.stackspot import StackSpotProvider

            try:
                provider = StackSpotProvider(
                    api_key=os.getenv("STACKSPOTAI_CLIENT_KEY"),
                    client_id=os.getenv("STACKSPOTAI_CLIENT_ID"),
                    realm=os.getenv("STACKSPOTAI_REALM", "stackspot"),
                )
            except ValueError as e:
                io.tool_error(str(e))
                return 1

        # Load model settings and metadata files
        model_settings_files = generate_search_path_list(
            ".aider.model.settings.yml", git_root, args.model_settings_file
        )
        model_metadata_files = generate_search_path_list(
            ".aider.model.metadata.json", git_root, args.model_metadata_file
        )

        # Register models with settings and metadata
        try:
            files_loaded = models.register_models(model_settings_files)
            if len(files_loaded) > 0:
                logger.info("Model settings loaded from:")
                for file_loaded in files_loaded:
                    logger.info("  - %s", file_loaded)
            else:
                logger.info("No model settings files loaded")
        except Exception as e:
            logger.error("Error loading aider model settings: %s", e)
            return 1

        # Initialize model settings
        model_settings = Model(
            args.model,
            api_key=args.api_key,
            use_temperature=True,
            use_repo_map=True,
            extra_params={
                "max_tokens": 8192,
                "model_type": "code",
                "streaming": True,
                "temperature": 0.7,
                "api_base": "https://genai-code-buddy-api.stackspot.com",
                "api_path": "/v1/chat/completions",
            },
        )

        # Initialize coder
        try:
            coder = Coder.create(
                main_model=model_settings,
                io=io,
                verbose=args.verbose,
                fnames=[],
                chat_language="python",
                edit_format="diff",
                map_tokens=1024,
                map_mul_no_files=2,
                map_refresh="auto",
                use_git=True,
                auto_commits=True,
                auto_lint=True,
                auto_test=False,
                restore_chat_history=True,
            )

            # Attach provider to model if available
            if provider:
                coder.main_model.provider = provider

            # Run the coder
            return coder.run()
        except Exception as e:
            io.tool_error(f"Error initializing coder: {str(e)}")
            return 1

    except KeyboardInterrupt:
        io.tool_error("\nExiting due to keyboard interrupt...")
        return 1
    except Exception as e:
        io.tool_error(f"\nUnhandled error: {str(e)}")
        logger.error("Exception details:", exc_info=True)
        return 1


def is_first_run_of_new_version(io, verbose=False):
    """Check if this is the first run of a new version/executable combination"""
    installs_file = Path.home() / ".aider" / "installs.json"
    key = (__version__, sys.executable)

    # Never show notes for .dev versions
    if ".dev" in __version__:
        return False

    if verbose:
        io.tool_output(
            f"Checking imports for version {__version__} and executable {sys.executable}"
        )
        io.tool_output(f"Installs file: {installs_file}")

    try:
        if installs_file.exists():
            with open(installs_file, "r") as f:
                installs = json.load(f)
            if verbose:
                io.tool_output("Installs file exists and loaded")
        else:
            installs = {}
            if verbose:
                io.tool_output("Installs file does not exist, creating new dictionary")

        is_first_run = str(key) not in installs

        if is_first_run:
            installs[str(key)] = True
            installs_file.parent.mkdir(parents=True, exist_ok=True)
            with open(installs_file, "w") as f:
                json.dump(installs, f, indent=4)

        return is_first_run

    except Exception as e:
        io.tool_warning(f"Error checking version: {e}")
        if verbose:
            io.tool_output(f"Full exception details: {traceback.format_exc()}")
        return True  # Safer to assume it's a first run if we hit an error


def check_and_load_imports(io, is_first_run, verbose=False):
    try:
        if is_first_run:
            logger.info(
                "Primeira execução para esta versão e executável, carregando imports sincronamente"
            )
            try:
                load_slow_imports(swallow=False)
            except Exception as err:
                logger.error("Erro ao carregar imports necessários: %s", str(err))
                io.tool_output(
                    "Erro ao carregar imports necessários. O aider foi instalado corretamente?"
                )
                io.offer_url(
                    urls.install_properly, "Abrir documentação para mais informações?"
                )
                sys.exit(1)

            logger.info("Imports carregados e arquivo de instalação atualizado")
        else:
            logger.info(
                "Não é primeira execução, carregando imports em thread em background"
            )
            thread = threading.Thread(target=load_slow_imports)
            thread.daemon = True
            thread.start()

    except Exception as e:
        logger.error("Erro ao carregar imports: %s", e)
        if verbose:
            logger.debug("Detalhes completos da exceção: %s", traceback.format_exc())


def load_slow_imports(swallow=True):
    # These imports are deferred in various ways to
    # improve startup time.
    # This func is called either synchronously or in a thread
    # depending on whether it's been run before for this version and executable.

    try:
        import httpx  # noqa: F401
        import litellm  # noqa: F401
        import networkx  # noqa: F401
        import numpy  # noqa: F401
    except Exception as e:
        if not swallow:
            raise e


if __name__ == "__main__":
    status = main()
    sys.exit(status)
