import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import yaml
from imgcat import imgcat
from matplotlib import rc

logger = logging.getLogger(__name__)


@dataclass
class ModelData:
    name: str
    release_date: date
    pass_rate: float

    @property
    def color(self) -> str:
        model = self.name.lower()
        if "gemini" in model and "pro" in model:
            return "magenta"
        if "qwen" in model:
            return "darkblue"
        if "mistral" in model:
            return "cyan"
        if "haiku" in model:
            return "pink"
        if "deepseek" in model:
            return "brown"
        if "sonnet" in model:
            return "orange"
        if "-4o" in model:
            return "purple"
        if "gpt-4" in model:
            return "red"
        if "gpt-3.5" in model:
            return "green"
        return "lightblue"

    @property
    def legend_label(self) -> str:
        model = self.name.lower()
        if "gemini" in model and "pro" in model:
            return "Gemini 1.5 Pro"
        if "claude-3-sonnet" in model:
            return "Sonnet"
        if "o1-preview" in model:
            return "O1 Preview"
        if "gpt-3.5" in model:
            return "GPT-3.5 Turbo"
        if "gpt-4-" in model and "-4o" not in model:
            return "GPT-4"
        if "qwen" in model:
            return "Qwen"
        if "-4o" in model:
            return "GPT-4o"
        if "haiku" in model:
            return "Haiku"
        if "deepseek" in model:
            return "DeepSeek"
        if "mistral" in model:
            return "Mistral"
        return model


class BenchmarkPlotter:
    LABEL_FONT_SIZE = 16

    def __init__(self):
        self.setup_plot_style()

    def setup_plot_style(self):
        plt.rcParams["hatch.linewidth"] = 0.5
        plt.rcParams["hatch.color"] = "#444444"
        rc("font", **{"family": "sans-serif", "sans-serif": ["Helvetica"], "size": 10})
        plt.rcParams["text.color"] = "#444444"

    def load_data(self, yaml_file: str) -> List[ModelData]:
        with open(yaml_file, "r") as file:
            data = yaml.safe_load(file)

        models = []
        for entry in data:
            if "released" in entry and "pass_rate_2" in entry:
                model = ModelData(
                    name=entry["model"].split("(")[0].strip(),
                    release_date=entry["released"],
                    pass_rate=entry["pass_rate_2"],
                )
                models.append(model)
        return models

    def create_figure(self) -> Tuple[plt.Figure, plt.Axes]:
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.grid(axis="y", zorder=0, lw=0.2)
        for spine in ax.spines.values():
            spine.set_edgecolor("#DDDDDD")
            spine.set_linewidth(0.5)
        return fig, ax

    def plot_model_series(self, ax: plt.Axes, models: List[ModelData]):
        # Group models by color
        color_groups: Dict[str, List[ModelData]] = {}
        for model in models:
            if model.color not in color_groups:
                color_groups[model.color] = []
            color_groups[model.color].append(model)

        # Plot each color group
        for color, group in color_groups.items():
            sorted_group = sorted(group, key=lambda x: x.release_date)
            dates = [m.release_date for m in sorted_group]
            rates = [m.pass_rate for m in sorted_group]

            # Plot line
            ax.plot(dates, rates, c=color, alpha=0.5, linewidth=1)

            # Plot points
            ax.scatter(dates, rates, c=color, alpha=0.5, s=120)

            # Add label for first point
            first_model = sorted_group[0]
            ax.annotate(
                first_model.legend_label,
                (first_model.release_date, first_model.pass_rate),
                xytext=(10, 5),
                textcoords="offset points",
                color=color,
                alpha=0.8,
                fontsize=self.LABEL_FONT_SIZE,
            )

    def set_labels_and_style(self, ax: plt.Axes):
        ax.set_xlabel("Model release date", fontsize=18, color="#555")
        ax.set_ylabel(
            "Aider code editing benchmark,\npercent completed correctly",
            fontsize=18,
            color="#555",
        )
        ax.set_title("LLM code editing skill by model release date", fontsize=20)
        ax.set_ylim(30, 90)
        plt.xticks(fontsize=14, rotation=45, ha="right")
        plt.tight_layout(pad=1.0)

    def save_and_display(self, fig: plt.Figure):
        plt.savefig("aider/website/assets/models-over-time.png")
        plt.savefig("aider/website/assets/models-over-time.svg")
        imgcat(fig)

    def plot(self, yaml_file: str):
        models = self.load_data(yaml_file)
        fig, ax = self.create_figure()
        self.plot_model_series(ax, models)
        self.set_labels_and_style(ax)
        self.save_and_display(fig)


def analyze_model_performance_over_time(models):
    """Analyze model performance over time."""
    for model in sorted(models, key=lambda x: x.release_date):
        logger.info("%s: %s", model.release_date, model.name)


def plot_performance_trends(data, output_dir=None):
    """Plot performance trends over time."""
    if output_dir is None:
        output_dir = Path("plots")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create plots
    plot_pass_rate_trend(data, output_dir)
    plot_duration_trend(data, output_dir)
    plot_cost_trend(data, output_dir)


def plot_pass_rate_trend(data, output_dir):
    """Plot pass rate trend over time."""
    plt.figure(figsize=(10, 6))
    plt.plot(data["date"], data["pass_rate"], marker="o")
    plt.title("Pass Rate Over Time")
    plt.xlabel("Date")
    plt.ylabel("Pass Rate (%)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "pass_rate_trend.png")
    plt.close()


def plot_duration_trend(data, output_dir):
    """Plot duration trend over time."""
    plt.figure(figsize=(10, 6))
    plt.plot(data["date"], data["avg_duration"], marker="o")
    plt.title("Average Duration Over Time")
    plt.xlabel("Date")
    plt.ylabel("Duration (seconds)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "duration_trend.png")
    plt.close()


def plot_cost_trend(data, output_dir):
    """Plot cost trend over time."""
    plt.figure(figsize=(10, 6))
    plt.plot(data["date"], data["avg_cost"], marker="o")
    plt.title("Average Cost Over Time")
    plt.xlabel("Date")
    plt.ylabel("Cost ($)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "cost_trend.png")
    plt.close()


def main():
    plotter = BenchmarkPlotter()
    models = plotter.load_data("aider/website/_data/edit_leaderboard.yml")

    # Print release dates and model names
    analyze_model_performance_over_time(models)

    plotter.plot("aider/website/_data/edit_leaderboard.yml")


if __name__ == "__main__":
    main()
