#!/usr/bin/env python3
"""
Chat Sessions Analysis Pipeline
================================
Computes engagement metrics and generates publication-ready visualizations
from Firestore chat session data.

This script performs:
1. Data loading and preprocessing
2. Course classification (using keyword scoring)
3. Engagement metric computation (session-level and user-level)
4. Visualization generation (including WPR event markers)
5. CSV export (sessions, user summaries, WPR window analysis)

Usage:
    python analysis/run_analysis.py [--input PATH] [--threshold N] [--dpi N]

Requirements:
    pip install pandas matplotlib seaborn
"""

import json
import sys
import os
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

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
# CONFIGURATION
# ============================================================================

# Default salt for hashing user IDs (can be overridden via HASH_SALT env var)
DEFAULT_HASH_SALT = "local-dev"


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

    # WPR window settings
    wpr_window_days: int = 3  # Days before WPR to include in window
    wpr_include_day_of: bool = False  # Include the WPR day itself in window


@dataclass
class CourseEvent:
    """Represents a course event (WPR, exam, etc.)."""
    date: date
    label: str
    course: str  # "multivariable_calculus", "linear_algebra", or "both"
    event_type: str  # "wpr", "exam", "quiz", etc.


def load_course_events(events_path: Optional[Path]) -> List[CourseEvent]:
    """
    Load course events from JSON file for visualization markers.

    Expected format:
    {
        "events": [
            {"date": "2025-09-09", "label": "WPR 1", "course": "multivariable_calculus", "type": "wpr"},
            ...
        ]
    }

    Returns list of CourseEvent objects.
    """
    if not events_path or not events_path.exists():
        return []

    try:
        with open(events_path, 'r') as f:
            data = json.load(f)

        events = []
        for item in data.get("events", []):
            try:
                event_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
                events.append(CourseEvent(
                    date=event_date,
                    label=item.get("label", ""),
                    course=item.get("course", "both"),
                    event_type=item.get("type", "other"),
                ))
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping invalid event: {item} ({e})")
                continue

        return events
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse events file: {e}")
        return []


def get_hash_salt() -> str:
    """Get hash salt from environment variable or use default."""
    return os.environ.get("HASH_SALT", DEFAULT_HASH_SALT)


def hash_user_id(user_id: str, salt: str) -> str:
    """Create a stable SHA-256 hash of user_id with salt."""
    salted = f"{salt}:{user_id}"
    return hashlib.sha256(salted.encode()).hexdigest()[:16]


# Anonymous/unknown user identifiers to flag in analysis
ANONYMOUS_USER_IDS = {"anonymous_user", "unknown", "", None}


def normalize_cnumber(user_id: str) -> str:
    """
    Normalize C-number format for consistent user identification.

    Handles variations like:
    - C12345678 -> 12345678
    - c12345678 -> 12345678
    - 12345678 -> 12345678
    - C1234567 -> 01234567 (zero-padded to 8 digits)

    Non-C-number IDs (like "anonymous_user") are returned unchanged.
    """
    if not user_id or user_id in ANONYMOUS_USER_IDS:
        return user_id

    # Strip leading C/c if present
    normalized = user_id.strip()
    if normalized.lower().startswith('c'):
        normalized = normalized[1:]

    # If it's all digits, zero-pad to 8 digits
    if normalized.isdigit():
        normalized = normalized.zfill(8)

    return normalized


def is_anonymous_user(user_id: str) -> bool:
    """Check if a user_id represents an anonymous/unknown user."""
    if not user_id:
        return True
    return user_id.lower() in {uid.lower() if uid else "" for uid in ANONYMOUS_USER_IDS if uid}


# ============================================================================
# DATA LOADING & PREPROCESSING
# ============================================================================

def load_sessions(input_path: Path) -> List[Dict[str, Any]]:
    """Load session data from JSON file."""
    with open(input_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def preprocess_sessions(sessions: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert raw session data to a pandas DataFrame with proper types.

    Normalizes user IDs (C-numbers) and flags anonymous users.
    """
    records = []

    for session in sessions:
        # Parse timestamps
        start_time = None
        end_time = None

        if session.get("start_time"):
            try:
                start_time = pd.to_datetime(session["start_time"])
            except:
                pass

        if session.get("end_time"):
            try:
                end_time = pd.to_datetime(session["end_time"])
            except:
                pass

        # Calculate duration if not present
        duration_sec = session.get("session_duration_sec")
        if duration_sec is None and start_time and end_time:
            duration_sec = (end_time - start_time).total_seconds()

        # Normalize user ID for consistent aggregation
        raw_user_id = session.get("user_id", "unknown")
        normalized_user_id = normalize_cnumber(raw_user_id)

        record = {
            "session_id": session.get("session_id", session.get("_document_id")),
            "user_id": normalized_user_id,
            "user_id_raw": raw_user_id,  # Keep original for reference
            "is_anonymous": is_anonymous_user(raw_user_id),
            "user_name": session.get("user_name"),
            "start_time": start_time,
            "end_time": end_time,
            "date": start_time.date() if start_time else None,
            "hour": start_time.hour if start_time else None,
            "day_of_week": start_time.dayofweek if start_time else None,
            "day_name": start_time.strftime("%A") if start_time else None,
            "user_message_count": session.get("user_message_count", 0),
            "total_message_count": session.get("total_message_count", 0),
            "session_duration_sec": duration_sec,
            "session_duration_min": duration_sec / 60 if duration_sec else None,
            "avg_user_msg_len_chars": session.get("avg_user_msg_len_chars"),
            "avg_user_msg_len_words": session.get("avg_user_msg_len_words"),
            "student_to_bot_ratio": session.get("student_to_bot_ratio"),
            "topics": session.get("topics", []),
            "topic_counts": session.get("topic_counts", {}),
            # Course classification (will be filled in later)
            "inferred_course": session.get("inferred_course"),
            "calculus_score": session.get("course_classification", {}).get("calculus_score"),
            "linear_algebra_score": session.get("course_classification", {}).get("linear_algebra_score"),
            "classification_confidence": session.get("course_classification", {}).get("confidence"),
            # Keep raw messages for potential further analysis
            "_message_count_from_log": len(session.get("messages", [])),
        }
        records.append(record)

    df = pd.DataFrame(records)

    # Ensure date column is proper datetime.date type
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date

    return df


def classify_sessions_in_df(
    df: pd.DataFrame,
    sessions: List[Dict[str, Any]],
    classifier: CourseClassifier
) -> pd.DataFrame:
    """
    Apply course classification to sessions and update DataFrame.
    """
    classifications = classifier.classify_sessions(sessions)

    # Create lookup by session_id
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

    metrics = {
        "total_sessions": len(df),
        "unique_users": df["user_id"].nunique(),
        "total_user_messages": df["user_message_count"].sum(),
        "total_messages": df["total_message_count"].sum(),
        "avg_messages_per_session": df["total_message_count"].mean(),
        "avg_user_messages_per_session": df["user_message_count"].mean(),
        "avg_session_duration_min": df["session_duration_min"].mean(),
        "median_session_duration_min": df["session_duration_min"].median(),
        "avg_user_msg_length_chars": df["avg_user_msg_len_chars"].mean(),
        "avg_user_msg_length_words": df["avg_user_msg_len_words"].mean(),
    }

    # Date range
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
        "user_id": "nunique",
        "user_message_count": "sum",
        "total_message_count": "sum",
        "session_duration_min": ["mean", "median"],
    }).reset_index()

    # Flatten column names
    daily.columns = [
        "date", "sessions", "unique_users", "user_messages",
        "total_messages", "avg_duration_min", "median_duration_min"
    ]

    # Add derived metrics
    daily["avg_messages_per_session"] = daily["total_messages"] / daily["sessions"]

    return daily


def compute_hourly_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compute session distribution by hour of day."""
    valid = df[df["hour"].notna()].copy()

    hourly = valid.groupby("hour").agg({
        "session_id": "count",
        "user_id": "nunique",
        "user_message_count": "sum",
    }).reset_index()

    hourly.columns = ["hour", "sessions", "unique_users", "user_messages"]

    # Fill missing hours with zeros
    all_hours = pd.DataFrame({"hour": range(24)})
    hourly = all_hours.merge(hourly, on="hour", how="left").fillna(0)

    return hourly


def compute_dow_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compute session distribution by day of week."""
    valid = df[df["day_of_week"].notna()].copy()

    dow = valid.groupby(["day_of_week", "day_name"]).agg({
        "session_id": "count",
        "user_id": "nunique",
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

    # Pivot for heatmap visualization
    heatmap_pivot = heatmap.pivot(
        index="day_of_week",
        columns="hour",
        values="sessions"
    ).fillna(0)

    return heatmap_pivot


def compute_metrics_by_course(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Compute metrics broken down by inferred course."""
    results = {}

    for course in ["multivariable_calculus", "linear_algebra", "mixed_or_uncertain"]:
        course_df = df[df["inferred_course"] == course]

        if len(course_df) > 0:
            results[course] = {
                "session_count": len(course_df),
                "unique_users": course_df["user_id"].nunique(),
                "total_user_messages": course_df["user_message_count"].sum(),
                "avg_messages_per_session": course_df["total_message_count"].mean(),
                "avg_session_duration_min": course_df["session_duration_min"].mean(),
                "median_session_duration_min": course_df["session_duration_min"].median(),
                "avg_user_msg_length_words": course_df["avg_user_msg_len_words"].mean(),
            }
        else:
            results[course] = {"session_count": 0}

    return results


def compute_daily_by_course(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Compute daily metrics broken down by course."""
    results = {}

    for course in ["multivariable_calculus", "linear_algebra"]:
        course_df = df[(df["inferred_course"] == course) & (df["date"].notna())]

        if len(course_df) > 0:
            daily = course_df.groupby("date").agg({
                "session_id": "count",
                "user_id": "nunique",
                "user_message_count": "sum",
            }).reset_index()

            daily.columns = ["date", "sessions", "unique_users", "user_messages"]
            results[course] = daily
        else:
            results[course] = pd.DataFrame(columns=["date", "sessions", "unique_users", "user_messages"])

    return results


# ============================================================================
# USER-LEVEL METRICS
# ============================================================================

def compute_user_level_metrics(df: pd.DataFrame, exclude_anonymous: bool = True) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Compute per-user engagement metrics.

    Args:
        df: Session DataFrame
        exclude_anonymous: If True, exclude anonymous users from per-user stats

    Returns:
        Tuple of (user_stats DataFrame, anonymous_stats dict)

    DataFrame columns:
    - user_id
    - total_sessions
    - active_days
    - total_user_messages
    - first_session_date
    - last_session_date
    - dominant_course
    - is_anonymous
    """
    valid = df[df["date"].notna()].copy()

    # Compute anonymous user statistics separately
    anonymous_stats = {}
    if "is_anonymous" in valid.columns:
        anon_sessions = valid[valid["is_anonymous"] == True]
        anonymous_stats = {
            "anonymous_session_count": len(anon_sessions),
            "anonymous_session_pct": 100 * len(anon_sessions) / len(valid) if len(valid) > 0 else 0,
            "anonymous_user_messages": anon_sessions["user_message_count"].sum(),
        }

        # Filter out anonymous users for per-user analysis if requested
        if exclude_anonymous:
            valid = valid[valid["is_anonymous"] == False]

    # Group by user
    user_stats = valid.groupby("user_id").agg({
        "session_id": "count",
        "date": ["nunique", "min", "max"],
        "user_message_count": "sum",
    }).reset_index()

    # Flatten column names
    user_stats.columns = [
        "user_id", "total_sessions", "active_days",
        "first_session_date", "last_session_date", "total_user_messages"
    ]

    # Compute dominant course for each user
    def get_dominant_course(user_id):
        user_sessions = valid[valid["user_id"] == user_id]
        # Exclude mixed_or_uncertain from dominant course calculation
        course_sessions = user_sessions[user_sessions["inferred_course"] != "mixed_or_uncertain"]
        if len(course_sessions) == 0:
            return "mixed_or_uncertain"
        course_counts = course_sessions["inferred_course"].value_counts()
        return course_counts.index[0]

    user_stats["dominant_course"] = user_stats["user_id"].apply(get_dominant_course)

    # Flag anonymous users in results
    user_stats["is_anonymous"] = user_stats["user_id"].apply(is_anonymous_user)

    # Convert dates to string format
    user_stats["first_session_date"] = user_stats["first_session_date"].astype(str)
    user_stats["last_session_date"] = user_stats["last_session_date"].astype(str)

    return user_stats, anonymous_stats


def create_deidentified_user_summary(user_stats: pd.DataFrame) -> pd.DataFrame:
    """
    Create a de-identified version of user stats by hashing user_id.
    """
    salt = get_hash_salt()
    deidentified = user_stats.copy()
    deidentified["user_id"] = deidentified["user_id"].apply(lambda x: hash_user_id(x, salt))
    return deidentified


# ============================================================================
# WPR WINDOW ANALYSIS
# ============================================================================

def compute_wpr_window_metrics(
    df: pd.DataFrame,
    events: List[CourseEvent],
    window_days: int = 3,
    include_day_of: bool = False,
) -> pd.DataFrame:
    """
    Compute engagement metrics for the window before each WPR.

    For each WPR:
    - Count unique users with >=1 session in the N days prior
    - Count total sessions in that window
    - If course-specific, only count sessions from that course

    Args:
        df: Session DataFrame
        events: List of CourseEvent objects
        window_days: Number of days before WPR to include
        include_day_of: Whether to include the WPR day itself

    Returns:
        DataFrame with WPR window metrics
    """
    valid = df[df["date"].notna()].copy()

    # Filter to WPR events only
    wpr_events = [e for e in events if e.event_type == "wpr"]

    if not wpr_events:
        return pd.DataFrame(columns=[
            "wpr_date", "label", "course", "window_start", "window_end",
            "unique_users", "total_sessions", "total_user_messages"
        ])

    records = []
    for event in wpr_events:
        # Calculate window
        if include_day_of:
            window_end = event.date
        else:
            window_end = event.date - timedelta(days=1)
        window_start = event.date - timedelta(days=window_days)

        # Filter sessions by date window
        window_sessions = valid[
            (valid["date"] >= window_start) &
            (valid["date"] <= window_end)
        ]

        # Filter by course if course-specific
        if event.course == "multivariable_calculus":
            window_sessions = window_sessions[
                window_sessions["inferred_course"] == "multivariable_calculus"
            ]
        elif event.course == "linear_algebra":
            window_sessions = window_sessions[
                window_sessions["inferred_course"] == "linear_algebra"
            ]
        # If "both", use all sessions (no additional filtering)

        records.append({
            "wpr_date": str(event.date),
            "label": event.label,
            "course": event.course,
            "window_start": str(window_start),
            "window_end": str(window_end),
            "unique_users": window_sessions["user_id"].nunique(),
            "total_sessions": len(window_sessions),
            "total_user_messages": window_sessions["user_message_count"].sum(),
        })

    return pd.DataFrame(records)


# ============================================================================
# VISUALIZATION
# ============================================================================

def setup_plotting_style(style: str = "seaborn-v0_8-whitegrid"):
    """Configure matplotlib style for publication-quality figures."""
    try:
        plt.style.use(style)
    except:
        try:
            plt.style.use("seaborn-whitegrid")
        except:
            pass  # Use default if neither works

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


def plot_sessions_per_day_with_events(
    daily: pd.DataFrame,
    events: List[CourseEvent],
    output_path: Path,
    title: str = "Daily Chat Sessions Over Time",
    course_filter: Optional[str] = None,
    dpi: int = 300,
):
    """
    Generate time series of sessions per day with event markers.

    Args:
        daily: DataFrame with daily metrics
        events: List of CourseEvent objects
        output_path: Path to save figure
        title: Plot title
        course_filter: If set, only show events for this course (or "both")
        dpi: Figure resolution
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    dates = pd.to_datetime(daily["date"])
    ax.plot(dates, daily["sessions"], marker="o", markersize=3, linewidth=1, color="#2563eb")
    ax.fill_between(dates, daily["sessions"], alpha=0.3, color="#2563eb")

    # Filter events by course if specified
    if course_filter:
        filtered_events = [
            e for e in events
            if e.course == course_filter or e.course == "both"
        ]
    else:
        filtered_events = events

    # Add event markers with staggered labels
    event_colors = {
        "wpr": "#dc2626",
        "exam": "#7c3aed",
        "quiz": "#f59e0b",
        "other": "#10b981",
    }

    # Sort events by date for staggering
    filtered_events = sorted(filtered_events, key=lambda e: e.date)

    # Calculate y positions with staggering to avoid overlap
    y_max = ax.get_ylim()[1] if daily["sessions"].max() > 0 else 10
    y_positions = []
    stagger_offsets = [0.95, 0.85, 0.75, 0.65]  # Cycle through these

    for i, event in enumerate(filtered_events):
        try:
            event_date = pd.to_datetime(event.date)
            if dates.min() <= event_date <= dates.max():
                color = event_colors.get(event.event_type, "#666666")

                ax.axvline(
                    x=event_date,
                    color=color,
                    linestyle="--",
                    alpha=0.7,
                    linewidth=1.5
                )

                # Stagger y position
                y_offset = stagger_offsets[i % len(stagger_offsets)]

                # Add label (only for WPRs to reduce clutter)
                if event.event_type == "wpr":
                    # Create label with course indicator
                    if course_filter is None and event.course != "both":
                        course_abbrev = "MA205" if event.course == "multivariable_calculus" else "MA371"
                        label = f"{event.label}\n({course_abbrev})"
                    else:
                        label = event.label

                    ax.text(
                        event_date, y_max * y_offset, label,
                        rotation=0, ha="center", va="top",
                        fontsize=7, color=color,
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor=color)
                    )
        except Exception as e:
            print(f"Warning: Could not plot event {event}: {e}")

    ax.set_xlabel("Date")
    ax.set_ylabel("Number of Sessions")
    ax.set_title(title)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha="right")

    # Add legend for event types
    if filtered_events:
        from matplotlib.lines import Line2D
        legend_elements = []
        event_types_present = set(e.event_type for e in filtered_events)
        for etype in ["wpr", "exam", "quiz", "other"]:
            if etype in event_types_present:
                legend_elements.append(
                    Line2D([0], [0], color=event_colors.get(etype, "#666"),
                          linestyle="--", label=etype.upper())
                )
        if legend_elements:
            ax.legend(handles=legend_elements, loc="upper left", framealpha=0.9)

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_sessions_per_day(
    daily: pd.DataFrame,
    events: List[CourseEvent],
    output_path: Path,
    dpi: int = 300,
):
    """Generate time series of sessions per day (wrapper for backward compatibility)."""
    plot_sessions_per_day_with_events(
        daily, events, output_path,
        title="Daily Chat Sessions Over Time",
        course_filter=None,
        dpi=dpi,
    )


def plot_course_comparison(
    daily_by_course: Dict[str, pd.DataFrame],
    output_path: Path,
    dpi: int = 300,
):
    """Generate comparison of sessions between inferred courses."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    colors = {
        "multivariable_calculus": "#2563eb",
        "linear_algebra": "#dc2626",
    }
    labels = {
        "multivariable_calculus": "Multivariable Calculus (MA205)",
        "linear_algebra": "Linear Algebra (MA371)",
    }

    # Plot 1: Sessions per day
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

    # Plot 2: User messages per day
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


def plot_hourly_distribution(
    hourly: pd.DataFrame,
    output_path: Path,
    dpi: int = 300,
):
    """Generate histogram of sessions by hour of day."""
    fig, ax = plt.subplots(figsize=(10, 5))

    bars = ax.bar(hourly["hour"], hourly["sessions"], color="#2563eb", alpha=0.8)

    # Highlight peak hours
    if hourly["sessions"].max() > 0:
        peak_hour = hourly.loc[hourly["sessions"].idxmax(), "hour"]
        bars[int(peak_hour)].set_color("#dc2626")

    ax.set_xlabel("Hour of Day (24-hour format)")
    ax.set_ylabel("Number of Sessions")
    ax.set_title("Session Distribution by Time of Day")
    ax.set_xticks(range(0, 24))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=45, ha="right")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_dow_heatmap(
    heatmap_data: pd.DataFrame,
    output_path: Path,
    dpi: int = 300,
):
    """Generate day-of-week × hour heatmap."""
    fig, ax = plt.subplots(figsize=(14, 6))

    # Reindex to ensure all hours are present
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
    ax.set_title("Session Distribution: Day of Week x Hour of Day")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_course_distribution_pie(
    df: pd.DataFrame,
    output_path: Path,
    dpi: int = 300,
):
    """Generate pie chart of course distribution."""
    course_counts = df["inferred_course"].value_counts()

    fig, ax = plt.subplots(figsize=(8, 8))

    colors = {
        "multivariable_calculus": "#2563eb",
        "linear_algebra": "#dc2626",
        "mixed_or_uncertain": "#6b7280",
    }
    labels = {
        "multivariable_calculus": "Multivariable Calculus (MA205)",
        "linear_algebra": "Linear Algebra (MA371)",
        "mixed_or_uncertain": "Mixed/Uncertain",
    }

    pie_colors = [colors.get(c, "#888") for c in course_counts.index]
    pie_labels = [labels.get(c, c) for c in course_counts.index]

    wedges, texts, autotexts = ax.pie(
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


def plot_engagement_metrics_comparison(
    metrics_by_course: Dict[str, Dict[str, Any]],
    output_path: Path,
    dpi: int = 300,
):
    """Generate bar chart comparing engagement metrics by course."""
    courses = ["multivariable_calculus", "linear_algebra"]
    labels = ["Multivariable Calculus\n(MA205)", "Linear Algebra\n(MA371)"]
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

        # Add value labels
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                   f"{val:.1f}", ha="center", va="bottom", fontsize=9)

    plt.suptitle("Engagement Metrics by Inferred Course", fontsize=12, y=1.02)
    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_sessions_per_user_histogram(
    user_stats: pd.DataFrame,
    output_path: Path,
    dpi: int = 300,
):
    """Generate histogram of sessions per user."""
    fig, ax = plt.subplots(figsize=(10, 5))

    data = user_stats["total_sessions"]
    bins = min(30, data.max() - data.min() + 1) if data.max() > data.min() else 10

    ax.hist(data, bins=bins, color="#2563eb", alpha=0.8, edgecolor="white")

    ax.axvline(data.mean(), color="#dc2626", linestyle="--", linewidth=2, label=f"Mean: {data.mean():.1f}")
    ax.axvline(data.median(), color="#f59e0b", linestyle="--", linewidth=2, label=f"Median: {data.median():.1f}")

    ax.set_xlabel("Total Sessions per User")
    ax.set_ylabel("Number of Users")
    ax.set_title("Distribution of Sessions per User")
    ax.legend()

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_active_days_per_user_histogram(
    user_stats: pd.DataFrame,
    output_path: Path,
    dpi: int = 300,
):
    """Generate histogram of active days per user."""
    fig, ax = plt.subplots(figsize=(10, 5))

    data = user_stats["active_days"]
    bins = min(30, data.max() - data.min() + 1) if data.max() > data.min() else 10

    ax.hist(data, bins=bins, color="#10b981", alpha=0.8, edgecolor="white")

    ax.axvline(data.mean(), color="#dc2626", linestyle="--", linewidth=2, label=f"Mean: {data.mean():.1f}")
    ax.axvline(data.median(), color="#f59e0b", linestyle="--", linewidth=2, label=f"Median: {data.median():.1f}")

    ax.set_xlabel("Active Days per User")
    ax.set_ylabel("Number of Users")
    ax.set_title("Distribution of Active Days per User")
    ax.legend()

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_users_active_per_day(
    daily: pd.DataFrame,
    output_path: Path,
    dpi: int = 300,
):
    """Generate time series of unique users per day."""
    fig, ax = plt.subplots(figsize=(12, 5))

    dates = pd.to_datetime(daily["date"])
    ax.plot(dates, daily["unique_users"], marker="o", markersize=3, linewidth=1, color="#10b981")
    ax.fill_between(dates, daily["unique_users"], alpha=0.3, color="#10b981")

    ax.set_xlabel("Date")
    ax.set_ylabel("Number of Unique Users")
    ax.set_title("Daily Active Users Over Time")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_analysis_csv(
    df: pd.DataFrame,
    classifications: List[CourseClassification],
    output_path: Path,
):
    """Generate analysis CSV suitable for Excel/R/SPSS."""
    # Create classification lookup
    class_lookup = {c.session_id: c for c in classifications}

    # Build export dataframe
    export_records = []
    for _, row in df.iterrows():
        classification = class_lookup.get(row["session_id"])

        record = {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
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

        # Add keyword hits as separate columns
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


def generate_summary_json(
    overall_metrics: Dict[str, Any],
    metrics_by_course: Dict[str, Dict[str, Any]],
    output_path: Path,
    anonymous_stats: Optional[Dict[str, Any]] = None,
):
    """Generate summary metrics as JSON."""
    summary = {
        "generated_at": datetime.now().isoformat(),
        "overall": overall_metrics,
        "by_course": metrics_by_course,
    }

    if anonymous_stats:
        summary["anonymous_users"] = anonymous_stats

    with open(output_path, 'w', encoding='utf-8') as f:
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

    # Setup
    setup_plotting_style(config.style)
    config.figures_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # Auto-load course events if file exists
    default_events_path = Path(__file__).parent / "course_events.json"
    events_path = config.events_path or (default_events_path if default_events_path.exists() else None)

    if events_path and events_path.exists():
        print(f"\nLoading course events from: {events_path}")
        course_events = load_course_events(events_path)
        print(f"    Loaded {len(course_events)} events")
    else:
        course_events = []
        print("\nNo course events file found (optional)")

    # Step 1: Load data
    print("\n[1/8] Loading session data...")
    sessions = load_sessions(config.input_path)
    print(f"    Loaded {len(sessions)} sessions")

    # Step 2: Preprocess
    print("\n[2/8] Preprocessing data...")
    df = preprocess_sessions(sessions)
    print(f"    DataFrame shape: {df.shape}")

    # Step 3: Classify courses
    print("\n[3/8] Classifying sessions by course...")
    classifier = CourseClassifier(
        threshold=config.classification_threshold,
        min_score=config.classification_min_score,
    )
    df, classifications = classify_sessions_in_df(df, sessions, classifier)

    course_counts = df["inferred_course"].value_counts()
    for course, count in course_counts.items():
        print(f"    {course}: {count} sessions ({100*count/len(df):.1f}%)")

    # Step 4: Compute session-level metrics
    print("\n[4/8] Computing session-level metrics...")
    overall_metrics = compute_overall_metrics(df)
    daily_metrics = compute_daily_metrics(df)
    hourly_dist = compute_hourly_distribution(df)
    dow_dist = compute_dow_distribution(df)
    heatmap_data = compute_heatmap_data(df)
    metrics_by_course = compute_metrics_by_course(df)
    daily_by_course = compute_daily_by_course(df)

    print(f"    Total sessions: {overall_metrics['total_sessions']}")
    print(f"    Unique users: {overall_metrics['unique_users']}")
    print(f"    Average session duration: {overall_metrics['avg_session_duration_min']:.1f} min")

    # Step 5: Compute user-level metrics
    print("\n[5/8] Computing user-level metrics...")
    user_stats, anonymous_stats = compute_user_level_metrics(df, exclude_anonymous=True)
    user_stats_deidentified = create_deidentified_user_summary(user_stats)
    print(f"    Users analyzed: {len(user_stats)}")
    print(f"    Avg sessions per user: {user_stats['total_sessions'].mean():.1f}")
    print(f"    Avg active days per user: {user_stats['active_days'].mean():.1f}")

    # Warn about anonymous users if significant
    if anonymous_stats.get("anonymous_session_pct", 0) > 5:
        print(f"    WARNING: {anonymous_stats['anonymous_session_pct']:.1f}% of sessions are anonymous")
        print(f"             ({anonymous_stats['anonymous_session_count']} sessions excluded from per-user analysis)")

    # Step 6: Compute WPR window metrics
    print("\n[6/8] Computing WPR window metrics...")
    wpr_window_metrics = compute_wpr_window_metrics(
        df, course_events,
        window_days=config.wpr_window_days,
        include_day_of=config.wpr_include_day_of,
    )
    if len(wpr_window_metrics) > 0:
        print(f"    Analyzed {len(wpr_window_metrics)} WPR windows")
    else:
        print("    No WPR events found")

    # Step 7: Generate visualizations
    print("\n[7/8] Generating visualizations...")

    # Main sessions per day plot with all events
    plot_sessions_per_day(
        daily_metrics, course_events,
        config.figures_dir / "sessions_per_day.png",
        dpi=config.figure_dpi,
    )

    # Course-specific sessions per day plots
    if "multivariable_calculus" in daily_by_course and len(daily_by_course["multivariable_calculus"]) > 0:
        plot_sessions_per_day_with_events(
            daily_by_course["multivariable_calculus"],
            course_events,
            config.figures_dir / "sessions_per_day_ma205.png",
            title="Daily Sessions - Multivariable Calculus (MA205)",
            course_filter="multivariable_calculus",
            dpi=config.figure_dpi,
        )

    if "linear_algebra" in daily_by_course and len(daily_by_course["linear_algebra"]) > 0:
        plot_sessions_per_day_with_events(
            daily_by_course["linear_algebra"],
            course_events,
            config.figures_dir / "sessions_per_day_ma371.png",
            title="Daily Sessions - Linear Algebra (MA371)",
            course_filter="linear_algebra",
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

    # New user-level plots
    plot_sessions_per_user_histogram(
        user_stats,
        config.figures_dir / "sessions_per_user_hist.png",
        dpi=config.figure_dpi,
    )

    plot_active_days_per_user_histogram(
        user_stats,
        config.figures_dir / "active_days_per_user_hist.png",
        dpi=config.figure_dpi,
    )

    plot_users_active_per_day(
        daily_metrics,
        config.figures_dir / "users_active_per_day.png",
        dpi=config.figure_dpi,
    )

    # Step 8: Generate output files
    print("\n[8/8] Generating output files...")

    generate_analysis_csv(
        df, classifications,
        config.output_dir / "chat_sessions_analysis.csv",
    )

    generate_summary_json(
        overall_metrics, metrics_by_course,
        config.output_dir / "analysis_summary.json",
        anonymous_stats=anonymous_stats,
    )

    # User-level summaries
    user_stats.to_csv(config.output_dir / "user_level_summary.csv", index=False)
    print(f"Saved: {config.output_dir / 'user_level_summary.csv'}")

    user_stats_deidentified.to_csv(config.output_dir / "user_level_summary_deidentified.csv", index=False)
    print(f"Saved: {config.output_dir / 'user_level_summary_deidentified.csv'}")

    # WPR window summary
    if len(wpr_window_metrics) > 0:
        wpr_window_metrics.to_csv(config.output_dir / "wpr_window_summary.csv", index=False)
        print(f"Saved: {config.output_dir / 'wpr_window_summary.csv'}")

    print("\n" + "=" * 60)
    print("Analysis Complete!")
    print("=" * 60)
    print(f"\nOutputs saved to: {config.output_dir}")
    print(f"Figures saved to: {config.figures_dir}")

    return df, classifications, overall_metrics, user_stats


def main():
    parser = argparse.ArgumentParser(
        description="Analyze chat session data from Firestore export"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        help="Path to input JSON file (default: outputs/chat_sessions_raw.json)"
    )
    parser.add_argument(
        "--events", "-e",
        type=Path,
        help="Path to course events JSON (default: auto-loads analysis/course_events.json if exists)"
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

    # Determine paths
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
