#!/usr/bin/env python3
"""
Chat Sessions Analysis Pipeline
================================
Computes engagement metrics and generates publication-ready visualizations
from Firestore chat session data.

Usage:
    python analysis/run_analysis.py [--input PATH] [--events PATH]

Requirements:
    pip install pandas matplotlib seaborn
"""

import json
import sys
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import seaborn as sns
except ImportError as e:
    print(f"ERROR: Missing required package: {e}")
    print("Install dependencies with: pip install pandas matplotlib seaborn")
    sys.exit(1)

from classify_courses import CourseClassifier, CourseClassification


# ============================================================================
# USER ID NORMALIZATION
# ============================================================================

def normalize_user_id(uid: Any) -> Optional[str]:
    """
    Normalize user identifiers:
      - '12345678' -> 'C12345678'
      - 'C12345678' -> 'C12345678'
      - anything else -> None (treated as anonymous/unstable)
    """
    if pd.isna(uid):
        return None

    uid = str(uid).strip().upper()

    # 8 digits only → prepend C
    if re.fullmatch(r"\d{8}", uid):
        return f"C{uid}"

    # C + 8 digits → valid
    if re.fullmatch(r"C\d{8}", uid):
        return uid

    # Anything else is not a stable identifier
    return None


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class AnalysisConfig:
    """Configuration for the analysis pipeline."""
    input_path: Path
    output_dir: Path
    figures_dir: Path
    events_path: Optional[Path] = None

    # Classification parameters
    classification_threshold: int = 5
    classification_min_score: int = 3

    # Visualization settings
    figure_dpi: int = 300
    figure_format: str = "png"
    style: str = "seaborn-v0_8-whitegrid"


def load_course_events(events_path: Optional[Path]) -> Dict[str, List[Dict[str, str]]]:
    """
    Load course events from JSON file for visualization markers.

    Expected format:
    {
        "quizzes": [{"date": "2024-09-15", "label": "Quiz 1"}],
        "exams": [{"date": "2024-10-20", "label": "Midterm"}],
        "other": [{"date": "2024-11-01", "label": "Project Due"}]
    }
    """
    if events_path and events_path.exists():
        with open(events_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure keys exist
        return {
            "quizzes": data.get("quizzes", []),
            "exams": data.get("exams", []),
            "other": data.get("other", []),
        }
    return {"quizzes": [], "exams": [], "other": []}


# ============================================================================
# DATA LOADING & PREPROCESSING
# ============================================================================

def load_sessions(input_path: Path) -> List[Dict[str, Any]]:
    """Load session data from JSON file."""
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def preprocess_sessions(sessions: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convert raw session data to a pandas DataFrame with proper types."""
    records: List[Dict[str, Any]] = []

    for session in sessions:
        start_time = None
        end_time = None

        if session.get("start_time"):
            try:
                start_time = pd.to_datetime(session["start_time"])
            except Exception:
                pass

        if session.get("end_time"):
            try:
                end_time = pd.to_datetime(session["end_time"])
            except Exception:
                pass

        duration_sec = session.get("session_duration_sec")
        if duration_sec is None and start_time is not None and end_time is not None:
            duration_sec = (end_time - start_time).total_seconds()

        record = {
            "session_id": session.get("session_id", session.get("_document_id")),
            "user_id": session.get("user_id", "unknown"),
            "user_name": session.get("user_name"),
            "start_time": start_time,
            "end_time": end_time,
            "date": start_time.date() if start_time is not None else None,
            "hour": start_time.hour if start_time is not None else None,
            "day_of_week": start_time.dayofweek if start_time is not None else None,
            "day_name": start_time.strftime("%A") if start_time is not None else None,
            "user_message_count": session.get("user_message_count", 0),
            "total_message_count": session.get("total_message_count", 0),
            "session_duration_sec": duration_sec,
            "session_duration_min": duration_sec / 60 if duration_sec else None,
            "avg_user_msg_len_chars": session.get("avg_user_msg_len_chars"),
            "avg_user_msg_len_words": session.get("avg_user_msg_len_words"),
            "student_to_bot_ratio": session.get("student_to_bot_ratio"),
            "topics": session.get("topics", []),
            "topic_counts": session.get("topic_counts", {}),
            # Classification placeholders (will be filled in later)
            "inferred_course": session.get("inferred_course"),
            "calculus_score": session.get("course_classification", {}).get("calculus_score"),
            "linear_algebra_score": session.get("course_classification", {}).get("linear_algebra_score"),
            "classification_confidence": session.get("course_classification", {}).get("confidence"),
            "_message_count_from_log": len(session.get("messages", [])),
        }
        records.append(record)

    df = pd.DataFrame(records)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date

    # Normalize IDs and flag identified users
    df["normalized_user_id"] = df["user_id"].apply(normalize_user_id)
    df["is_identified"] = df["normalized_user_id"].notna()

    return df


def classify_sessions_in_df(
    df: pd.DataFrame,
    sessions: List[Dict[str, Any]],
    classifier: CourseClassifier
):
    """Apply course classification to sessions and update DataFrame."""
    classifications = classifier.classify_sessions(sessions)
    class_lookup = {c.session_id: c for c in classifications}

    df["inferred_course"] = df["session_id"].apply(
        lambda x: class_lookup.get(x).inferred_course if class_lookup.get(x) else None
    )
    df["calculus_score"] = df["session_id"].apply(
        lambda x: class_lookup.get(x).calculus_score if class_lookup.get(x) else 0
    )
    df["linear_algebra_score"] = df["session_id"].apply(
        lambda x: class_lookup.get(x).linear_algebra_score if class_lookup.get(x) else 0
    )
    df["classification_confidence"] = df["session_id"].apply(
        lambda x: class_lookup.get(x).confidence if class_lookup.get(x) else None
    )

    return df, classifications


# ============================================================================
# ENGAGEMENT METRICS
# ============================================================================

def compute_overall_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute overall engagement metrics."""
    valid_dates = df[df["date"].notna()]

    metrics: Dict[str, Any] = {
        "total_sessions": len(df),
        # unique users should be based on normalized IDs (anonymous/invalid = None, not counted)
        "unique_users": df["normalized_user_id"].nunique(dropna=True),
        "total_user_messages": df["user_message_count"].sum(),
        "total_messages": df["total_message_count"].sum(),
        "avg_messages_per_session": df["total_message_count"].mean(),
        "avg_user_messages_per_session": df["user_message_count"].mean(),
        "avg_session_duration_min": df["session_duration_min"].mean(),
        "median_session_duration_min": df["session_duration_min"].median(),
        "avg_user_msg_length_chars": df["avg_user_msg_len_chars"].mean(),
        "avg_user_msg_length_words": df["avg_user_msg_len_words"].mean(),
        # extra transparency
        "identified_sessions": int(df["is_identified"].sum()),
        "anonymous_or_unstable_sessions": int((~df["is_identified"]).sum()),
    }

    if len(valid_dates) > 0:
        dates = valid_dates["date"]
        metrics["date_range_start"] = str(min(dates))
        metrics["date_range_end"] = str(max(dates))
        metrics["total_days"] = (max(dates) - min(dates)).days + 1

    return metrics


def compute_daily_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute metrics aggregated by day."""
    valid = df[df["date"].notna()].copy()

    daily = valid.groupby("date").agg({
        "session_id": "count",
        # unique users by day should be based on normalized IDs; NaN won't be counted
        "normalized_user_id": "nunique",
        "user_message_count": "sum",
        "total_message_count": "sum",
        "session_duration_min": ["mean", "median"],
    }).reset_index()

    daily.columns = [
        "date", "sessions", "unique_users", "user_messages",
        "total_messages", "avg_duration_min", "median_duration_min"
    ]
    daily["avg_messages_per_session"] = daily["total_messages"] / daily["sessions"]
    return daily


def compute_hourly_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compute session distribution by hour of day."""
    valid = df[df["hour"].notna()].copy()

    hourly = valid.groupby("hour").agg({
        "session_id": "count",
        "normalized_user_id": "nunique",
        "user_message_count": "sum",
    }).reset_index()

    hourly.columns = ["hour", "sessions", "unique_users", "user_messages"]

    all_hours = pd.DataFrame({"hour": range(24)})
    hourly = all_hours.merge(hourly, on="hour", how="left").fillna(0)
    return hourly


def compute_dow_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compute session distribution by day of week."""
    valid = df[df["day_of_week"].notna()].copy()

    dow = valid.groupby(["day_of_week", "day_name"]).agg({
        "session_id": "count",
        "normalized_user_id": "nunique",
        "user_message_count": "sum",
    }).reset_index()

    dow.columns = ["day_of_week", "day_name", "sessions", "unique_users", "user_messages"]
    return dow.sort_values("day_of_week")


def compute_heatmap_data(df: pd.DataFrame) -> pd.DataFrame:
    """Compute hour × day-of-week heatmap data."""
    valid = df[(df["hour"].notna()) & (df["day_of_week"].notna())].copy()

    heatmap = valid.groupby(["day_of_week", "hour"]).agg({
        "session_id": "count"
    }).reset_index()

    heatmap.columns = ["day_of_week", "hour", "sessions"]

    heatmap_pivot = heatmap.pivot(
        index="day_of_week",
        columns="hour",
        values="sessions"
    ).fillna(0)

    return heatmap_pivot


def compute_metrics_by_course(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Compute metrics broken down by inferred course."""
    results: Dict[str, Dict[str, Any]] = {}

    for course in ["multivariable_calculus", "linear_algebra", "mixed_or_uncertain"]:
        course_df = df[df["inferred_course"] == course]

        if len(course_df) > 0:
            results[course] = {
                "session_count": len(course_df),
                "unique_users": course_df["normalized_user_id"].nunique(dropna=True),
                "total_user_messages": course_df["user_message_count"].sum(),
                "avg_messages_per_session": course_df["total_message_count"].mean(),
                "avg_session_duration_min": course_df["session_duration_min"].mean(),
                "median_session_duration_min": course_df["session_duration_min"].median(),
                "avg_user_msg_length_words": course_df["avg_user_msg_len_words"].mean(),
                "identified_sessions": int(course_df["is_identified"].sum()),
                "anonymous_or_unstable_sessions": int((~course_df["is_identified"]).sum()),
            }
        else:
            results[course] = {"session_count": 0}

    return results


def compute_daily_by_course(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Compute daily metrics broken down by course."""
    results: Dict[str, pd.DataFrame] = {}

    for course in ["multivariable_calculus", "linear_algebra"]:
        course_df = df[(df["inferred_course"] == course) & (df["date"].notna())]

        if len(course_df) > 0:
            daily = course_df.groupby("date").agg({
                "session_id": "count",
                "normalized_user_id": "nunique",
                "user_message_count": "sum",
            }).reset_index()

            daily.columns = ["date", "sessions", "unique_users", "user_messages"]
            results[course] = daily
        else:
            results[course] = pd.DataFrame(columns=["date", "sessions", "unique_users", "user_messages"])

    return results


def compute_user_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Compute user-level engagement summary (one row per identified normalized user)."""
    identified = df[df["normalized_user_id"].notna()].copy()

    return (
        identified.groupby("normalized_user_id")
        .agg(
            total_sessions=("session_id", "count"),
            total_messages=("total_message_count", "sum"),
            total_user_messages=("user_message_count", "sum"),
            avg_session_duration_min=("session_duration_min", "mean"),
            active_days=("date", lambda s: s.dropna().nunique()),
            courses_used=("inferred_course", lambda s: s.dropna().nunique()),
        )
        .reset_index()
        .rename(columns={"normalized_user_id": "user_id"})
    )


# ============================================================================
# VISUALIZATION
# ============================================================================

def setup_plotting_style(style: str = "seaborn-v0_8-whitegrid"):
    """Configure matplotlib style for publication-quality figures."""
    try:
        plt.style.use(style)
    except Exception:
        plt.style.use("seaborn-whitegrid")

    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.titlesize": 14,
        "figure.dpi": 100,
    })


def _add_event_markers(ax, date_min, date_max, events: Dict[str, List[Dict[str, str]]]):
    """Shared helper to draw event markers."""
    colors = {"quizzes": "#f59e0b", "exams": "#dc2626", "other": "#10b981"}
    for event_type, event_list in events.items():
        for event in event_list:
            try:
                event_date = pd.to_datetime(event["date"])
                if date_min <= event_date <= date_max:
                    ax.axvline(
                        x=event_date,
                        color=colors.get(event_type, "#666"),
                        linestyle="--",
                        alpha=0.7,
                        linewidth=1.5,
                    )
                    if event.get("label"):
                        ax.text(
                            event_date,
                            ax.get_ylim()[1] * 0.95,
                            event.get("label", ""),
                            rotation=45,
                            ha="right",
                            fontsize=8,
                        )
            except Exception:
                pass


def plot_sessions_per_day(daily: pd.DataFrame, events: Dict[str, List[Dict[str, str]]], output_path: Path, dpi: int = 300):
    """Generate time series of sessions per day."""
    fig, ax = plt.subplots(figsize=(12, 5))

    dates = pd.to_datetime(daily["date"])
    ax.plot(dates, daily["sessions"], marker="o", markersize=3, linewidth=1, color="#2563eb")
    ax.fill_between(dates, daily["sessions"], alpha=0.3, color="#2563eb")

    _add_event_markers(ax, dates.min(), dates.max(), events)

    ax.set_xlabel("Date")
    ax.set_ylabel("Number of Sessions")
    ax.set_title("Daily Chat Sessions Over Time")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_sessions_per_day_by_course(
    daily_by_course: Dict[str, pd.DataFrame],
    events: Dict[str, List[Dict[str, str]]],
    output_path: Path,
    dpi: int = 300,
):
    """Second figure: sessions/day by course (keeps combined plot too)."""
    fig, ax = plt.subplots(figsize=(12, 5))

    label_map = {
        "multivariable_calculus": "Multivariable Calculus",
        "linear_algebra": "Linear Algebra",
    }
    color_map = {
        "multivariable_calculus": "#2563eb",
        "linear_algebra": "#dc2626",
    }

    all_dates = []
    for course, daily in daily_by_course.items():
        if daily is None or len(daily) == 0:
            continue
        dates = pd.to_datetime(daily["date"])
        all_dates.append(dates)
        ax.plot(
            dates,
            daily["sessions"],
            marker="o",
            markersize=3,
            linewidth=1,
            label=label_map.get(course, course.replace("_", " ").title()),
            color=color_map.get(course, None),
        )

    if all_dates:
        date_min = min(d.min() for d in all_dates)
        date_max = max(d.max() for d in all_dates)
        _add_event_markers(ax, date_min, date_max, events)

    ax.set_xlabel("Date")
    ax.set_ylabel("Number of Sessions")
    ax.set_title("Daily Chat Sessions Over Time by Inferred Course")
    ax.legend()

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_unique_users_per_day(daily: pd.DataFrame, events: Dict[str, List[Dict[str, str]]], output_path: Path, dpi: int = 300):
    """Time series of unique identified users per day (based on normalized_user_id)."""
    fig, ax = plt.subplots(figsize=(12, 5))

    dates = pd.to_datetime(daily["date"])
    ax.plot(dates, daily["unique_users"], marker="o", markersize=3, linewidth=1, color="#111827")
    ax.fill_between(dates, daily["unique_users"], alpha=0.2, color="#111827")

    _add_event_markers(ax, dates.min(), dates.max(), events)

    ax.set_xlabel("Date")
    ax.set_ylabel("Unique Users")
    ax.set_title("Daily Unique Users Over Time")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_unique_users_per_day_by_course(
    daily_by_course: Dict[str, pd.DataFrame],
    events: Dict[str, List[Dict[str, str]]],
    output_path: Path,
    dpi: int = 300,
):
    """Unique users/day by course (based on normalized_user_id)."""
    fig, ax = plt.subplots(figsize=(12, 5))

    label_map = {
        "multivariable_calculus": "Multivariable Calculus",
        "linear_algebra": "Linear Algebra",
    }
    color_map = {
        "multivariable_calculus": "#2563eb",
        "linear_algebra": "#dc2626",
    }

    all_dates = []
    for course, daily in daily_by_course.items():
        if daily is None or len(daily) == 0:
            continue
        dates = pd.to_datetime(daily["date"])
        all_dates.append(dates)
        ax.plot(
            dates,
            daily["unique_users"],
            marker="o",
            markersize=3,
            linewidth=1,
            label=label_map.get(course, course.replace("_", " ").title()),
            color=color_map.get(course, None),
        )

    if all_dates:
        date_min = min(d.min() for d in all_dates)
        date_max = max(d.max() for d in all_dates)
        _add_event_markers(ax, date_min, date_max, events)

    ax.set_xlabel("Date")
    ax.set_ylabel("Unique Users")
    ax.set_title("Daily Unique Users Over Time by Inferred Course")
    ax.legend()

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_course_comparison(daily_by_course: Dict[str, pd.DataFrame], output_path: Path, dpi: int = 300):
    """Generate comparison of sessions between inferred courses."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    colors = {
        "multivariable_calculus": "#2563eb",
        "linear_algebra": "#dc2626",
    }
    labels = {
        "multivariable_calculus": "Multivariable Calculus",
        "linear_algebra": "Linear Algebra",
    }

    ax1 = axes[0]
    for course, daily in daily_by_course.items():
        if len(daily) > 0:
            dates = pd.to_datetime(daily["date"])
            ax1.plot(dates, daily["sessions"], marker="o", markersize=3,
                     linewidth=1, color=colors[course], label=labels[course])

    ax1.set_ylabel("Sessions per Day")
    ax1.set_title("Daily Sessions by Inferred Course")
    ax1.legend()
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    ax2 = axes[1]
    for course, daily in daily_by_course.items():
        if len(daily) > 0:
            dates = pd.to_datetime(daily["date"])
            ax2.plot(dates, daily["user_messages"], marker="o", markersize=3,
                     linewidth=1, color=colors[course], label=labels[course])

    ax2.set_xlabel("Date")
    ax2.set_ylabel("User Messages per Day")
    ax2.set_title("Daily User Messages by Inferred Course")
    ax2.legend()
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))

    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_hourly_distribution(hourly: pd.DataFrame, output_path: Path, dpi: int = 300):
    """Generate histogram of sessions by hour of day."""
    fig, ax = plt.subplots(figsize=(10, 5))

    bars = ax.bar(hourly["hour"], hourly["sessions"], color="#2563eb", alpha=0.8)
    peak_hour = int(hourly.loc[hourly["sessions"].idxmax(), "hour"])
    bars[peak_hour].set_color("#dc2626")

    ax.set_xlabel("Hour of Day (24-hour format)")
    ax.set_ylabel("Number of Sessions")
    ax.set_title("Session Distribution by Time of Day")
    ax.set_xticks(range(0, 24))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=45, ha="right")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_dow_heatmap(heatmap_data: pd.DataFrame, output_path: Path, dpi: int = 300):
    """Generate day-of-week × hour heatmap."""
    fig, ax = plt.subplots(figsize=(14, 6))

    heatmap_data = heatmap_data.reindex(columns=range(24), fill_value=0)
    heatmap_data = heatmap_data.reindex(range(7), fill_value=0)

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    sns.heatmap(
        heatmap_data,
        ax=ax,
        cmap="Blues",
        annot=True,
        fmt=".0f",
        cbar_kws={"label": "Number of Sessions"},
        xticklabels=[f"{h:02d}" for h in range(24)],
        yticklabels=day_names,
    )

    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Day of Week")
    ax.set_title("Session Distribution: Day of Week × Hour of Day")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_course_distribution_pie(df: pd.DataFrame, output_path: Path, dpi: int = 300):
    """Generate pie chart of course distribution."""
    course_counts = df["inferred_course"].value_counts()

    fig, ax = plt.subplots(figsize=(8, 8))

    colors = {
        "multivariable_calculus": "#2563eb",
        "linear_algebra": "#dc2626",
        "mixed_or_uncertain": "#6b7280",
    }
    labels = {
        "multivariable_calculus": "Multivariable Calculus",
        "linear_algebra": "Linear Algebra",
        "mixed_or_uncertain": "Mixed/Uncertain",
    }

    pie_colors = [colors.get(c, "#888") for c in course_counts.index]
    pie_labels = [labels.get(c, c) for c in course_counts.index]

    ax.pie(
        course_counts.values,
        labels=pie_labels,
        colors=pie_colors,
        autopct=lambda pct: f"{pct:.1f}%\n({int(pct/100*sum(course_counts.values))})",
        startangle=90,
        explode=[0.02] * len(course_counts),
    )

    ax.set_title("Session Distribution by Inferred Course")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_engagement_metrics_comparison(metrics_by_course: Dict[str, Dict[str, Any]], output_path: Path, dpi: int = 300):
    """Generate bar chart comparing engagement metrics by course."""
    courses = ["multivariable_calculus", "linear_algebra"]
    labels = ["Multivariable Calculus", "Linear Algebra"]
    colors = ["#2563eb", "#dc2626"]

    metrics_to_plot = [
        ("avg_messages_per_session", "Avg Messages/Session"),
        ("avg_session_duration_min", "Avg Duration (min)"),
        ("avg_user_msg_length_words", "Avg Message Length (words)"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    for idx, (metric_key, metric_label) in enumerate(metrics_to_plot):
        ax = axes[idx]
        values = [metrics_by_course.get(c, {}).get(metric_key, 0) or 0 for c in courses]

        bars = ax.bar(labels, values, color=colors)
        ax.set_ylabel(metric_label)
        ax.set_title(metric_label)

        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{val:.1f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    plt.suptitle("Engagement Metrics by Inferred Course", fontsize=12, y=1.02)
    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_analysis_csv(df: pd.DataFrame, classifications: List[CourseClassification], output_path: Path):
    """Generate analysis CSV suitable for Excel/R/SPSS."""
    class_lookup = {c.session_id: c for c in classifications}

    export_records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        classification = class_lookup.get(row["session_id"])

        record = {
            "session_id": row["session_id"],
            "user_id_raw": row["user_id"],
            "user_id": row.get("normalized_user_id"),
            "is_identified": row.get("is_identified"),
            "user_name": row["user_name"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "date": row["date"],
            "hour": row["hour"],
            "day_of_week": row["day_of_week"],
            "day_name": row["day_name"],
            "user_message_count": row["user_message_count"],
            "total_message_count": row["total_message_count"],
            "session_duration_sec": row["session_duration_sec"],
            "session_duration_min": row["session_duration_min"],
            "avg_user_msg_len_chars": row["avg_user_msg_len_chars"],
            "avg_user_msg_len_words": row["avg_user_msg_len_words"],
            "student_to_bot_ratio": row["student_to_bot_ratio"],
            "inferred_course": row["inferred_course"],
            "calculus_score": row["calculus_score"],
            "linear_algebra_score": row["linear_algebra_score"],
            "classification_confidence": row["classification_confidence"],
            "topics": "; ".join(row["topics"]) if row["topics"] else "",
            "topic_count": len(row["topics"]) if row["topics"] else 0,
        }

        if classification:
            calc_hits = classification.calculus_hits
            la_hits = classification.linear_algebra_hits
            record["calculus_keyword_count"] = len(calc_hits)
            record["linear_algebra_keyword_count"] = len(la_hits)
            record["top_calculus_keywords"] = "; ".join(
                f"{k}({v})" for k, v in sorted(calc_hits.items(), key=lambda x: -x[1])[:5]
            )
            record["top_linear_algebra_keywords"] = "; ".join(
                f"{k}({v})" for k, v in sorted(la_hits.items(), key=lambda x: -x[1])[:5]
            )

        export_records.append(record)

    export_df = pd.DataFrame(export_records)
    export_df.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")


def generate_summary_json(overall_metrics: Dict[str, Any], metrics_by_course: Dict[str, Dict[str, Any]], output_path: Path):
    """Generate summary metrics as JSON."""
    summary = {
        "generated_at": datetime.now().isoformat(),
        "overall": overall_metrics,
        "by_course": metrics_by_course,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Saved: {output_path}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_analysis(config: AnalysisConfig):
    """Execute the complete analysis pipeline."""
    print("=" * 60)
    print("Chat Sessions Analysis Pipeline")
    print("=" * 60)

    setup_plotting_style(config.style)
    config.figures_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    course_events = load_course_events(config.events_path)

    print("\n[1/6] Loading session data...")
    sessions = load_sessions(config.input_path)
    print(f"    Loaded {len(sessions)} sessions")

    print("\n[2/6] Preprocessing data...")
    df = preprocess_sessions(sessions)
    print(f"    DataFrame shape: {df.shape}")

    print("\n[3/6] Classifying sessions by course...")
    classifier = CourseClassifier(
        threshold=config.classification_threshold,
        min_score=config.classification_min_score,
    )
    df, classifications = classify_sessions_in_df(df, sessions, classifier)

    course_counts = df["inferred_course"].value_counts()
    for course, count in course_counts.items():
        print(f"    {course}: {count} sessions ({100 * count / len(df):.1f}%)")

    print("\n[4/6] Computing engagement metrics...")
    overall_metrics = compute_overall_metrics(df)
    daily_metrics = compute_daily_metrics(df)
    hourly_dist = compute_hourly_distribution(df)
    heatmap_data = compute_heatmap_data(df)
    metrics_by_course = compute_metrics_by_course(df)
    daily_by_course = compute_daily_by_course(df)
    user_summary = compute_user_summary(df)

    print(f"    Total sessions: {overall_metrics['total_sessions']}")
    print(f"    Unique users (normalized IDs): {overall_metrics['unique_users']}")
    print(f"    Identified sessions: {overall_metrics['identified_sessions']}")
    print(f"    Anonymous/unstable sessions: {overall_metrics['anonymous_or_unstable_sessions']}")
    print(f"    Average session duration: {overall_metrics['avg_session_duration_min']:.1f} min")

    print("\n[5/6] Generating visualizations...")

    plot_sessions_per_day(
        daily_metrics,
        course_events,
        config.figures_dir / "sessions_per_day.png",
        dpi=config.figure_dpi,
    )

    plot_sessions_per_day_by_course(
        daily_by_course=daily_by_course,
        events=course_events,
        output_path=config.figures_dir / "sessions_per_day_by_course.png",
        dpi=config.figure_dpi,
    )

    plot_unique_users_per_day(
        daily_metrics,
        course_events,
        config.figures_dir / "unique_users_per_day.png",
        dpi=config.figure_dpi,
    )

    plot_unique_users_per_day_by_course(
        daily_by_course,
        course_events,
        config.figures_dir / "unique_users_per_day_by_course.png",
        dpi=config.figure_dpi,
    )

    plot_course_comparison(
        daily_by_course,
        config.figures_dir / "course_comparison.png",
        dpi=config.figure_dpi,
    )

    plot_hourly_distribution(
        hourly_dist,
        config.figures_dir / "hourly_distribution.png",
        dpi=config.figure_dpi,
    )

    plot_dow_heatmap(
        heatmap_data,
        config.figures_dir / "dow_hour_heatmap.png",
        dpi=config.figure_dpi,
    )

    plot_course_distribution_pie(
        df,
        config.figures_dir / "course_distribution.png",
        dpi=config.figure_dpi,
    )

    plot_engagement_metrics_comparison(
        metrics_by_course,
        config.figures_dir / "engagement_comparison.png",
        dpi=config.figure_dpi,
    )

    print("\n[6/6] Generating output files...")

    generate_analysis_csv(
        df,
        classifications,
        config.output_dir / "chat_sessions_analysis.csv",
    )

    generate_summary_json(
        overall_metrics,
        metrics_by_course,
        config.output_dir / "analysis_summary.json",
    )

    user_summary_path = config.output_dir / "user_level_summary.csv"
    user_summary.to_csv(user_summary_path, index=False)
    print(f"Saved: {user_summary_path}")

    print("\n" + "=" * 60)
    print("Analysis Complete!")
    print("=" * 60)
    print(f"\nOutputs saved to: {config.output_dir}")
    print(f"Figures saved to: {config.figures_dir}")

    return df, classifications, overall_metrics


def main():
    parser = argparse.ArgumentParser(description="Analyze chat session data from Firestore export")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        help="Path to input JSON file (default: outputs/chat_sessions_raw.json)"
    )
    parser.add_argument(
        "--events", "-e",
        type=Path,
        help="Path to course events JSON for visualization markers"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=5,
        help="Classification threshold (default: 5)"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Figure DPI for saved images (default: 300)"
    )

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    input_path = args.input or project_root / "outputs" / "chat_sessions_raw.json"
    output_dir = project_root / "outputs"
    figures_dir = output_dir / "figures"

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("\nRun the export script first:")
        print("    python scripts/export_firestore_chat_sessions.py")
        sys.exit(1)

    config = AnalysisConfig(
        input_path=input_path,
        output_dir=output_dir,
        figures_dir=figures_dir,
        events_path=args.events,
        classification_threshold=args.threshold,
        figure_dpi=args.dpi,
    )

    run_analysis(config)


if __name__ == "__main__":
    main()
