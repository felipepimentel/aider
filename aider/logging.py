import logging
import logging.config
import os
from pathlib import Path

import yaml


def find_config_file(filename=".aider.conf.yml"):
    """
    Procura o arquivo de configuração em diferentes locais:
    - Diretório atual
    - Raiz do git repo
    - Home do usuário
    """
    # Current directory
    if os.path.exists(filename):
        return filename

    # Git root (if in a git repo)
    try:
        import git

        try:
            repo = git.Repo(search_parent_directories=True)
            git_root = repo.git.rev_parse("--show-toplevel")
            git_config = os.path.join(git_root, filename)
            if os.path.exists(git_config):
                return git_config
        except git.InvalidGitRepositoryError:
            pass
    except ImportError:
        pass

    # User's home directory
    home_config = os.path.join(str(Path.home()), filename)
    if os.path.exists(home_config):
        return home_config

    return None


def setup_logging(config_path=None):
    """
    Configura o sistema de logging baseado no arquivo de configuração.
    Se config_path não for fornecido, procura o arquivo de configuração nos locais padrão.
    """
    # Desabilitar todos os loggers existentes primeiro
    for logger_name in logging.root.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.propagate = True
        logger.setLevel(logging.WARNING)

    if config_path is None:
        config_path = find_config_file()
        if not config_path:
            # Configuração padrão se nenhum arquivo for encontrado
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            return

    # Se config_path for um objeto Namespace ou dict, extrair o caminho do arquivo
    if hasattr(config_path, "config_file"):
        config_path = config_path.config_file
    elif isinstance(config_path, dict):
        config_path = config_path.get("config_file")
    elif not isinstance(config_path, (str, bytes, os.PathLike)):
        # Se não for um caminho válido, usar o padrão
        config_path = find_config_file()
        if not config_path:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            return

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logging.error(f"Erro ao carregar arquivo de configuração: {e}")
        return

    logging_config = config.get("logging", {})

    # Configuração básica do logging
    root_level = logging_config.get("level", "INFO")
    if isinstance(root_level, str):
        root_level = getattr(logging, root_level.upper())

    # Resetar configuração básica
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=root_level,
        format=logging_config.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
    )

    # Configurar handlers específicos
    handlers_config = logging_config.get("handlers", {})

    # Handler de arquivo
    file_config = handlers_config.get("file", {})
    if file_config.get("enabled"):
        file_handler = logging.FileHandler(file_config.get("filename", "aider.log"))
        file_level = file_config.get("level", "INFO")
        if isinstance(file_level, str):
            file_level = getattr(logging, file_level.upper())
        file_handler.setLevel(file_level)
        formatter = logging.Formatter(logging_config.get("format"))
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)

    # Configurar níveis por componente
    for component, settings in logging_config.get("components", {}).items():
        component_level = settings.get("level", "INFO")
        if isinstance(component_level, str):
            component_level = getattr(logging, component_level.upper())
        logger = logging.getLogger(f"aider.{component}")
        logger.setLevel(component_level)
        logger.propagate = True

    # Configurar loggers de terceiros
    for logger_name, settings in logging_config.get("loggers", {}).items():
        logger_level = settings.get("level", "WARNING")
        if isinstance(logger_level, str):
            logger_level = getattr(logging, logger_level.upper())
        logger = logging.getLogger(logger_name)
        logger.setLevel(logger_level)
        logger.propagate = True


def setup_verbose_mode(verbose=False):
    """
    Ajusta o nível de log global para DEBUG quando o modo verbose está ativado
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
