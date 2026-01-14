# Chat Sessions Analysis Pipeline

A complete data analysis pipeline for extracting, classifying, and analyzing engagement data from the Canvas Chatbot Firestore database.

## Quick Start (Windows + VS Code)

### Prerequisites

1. **Python 3.8+** - Download from [python.org](https://www.python.org/downloads/)
2. **Firebase Service Account Key** - Required for data export

### Step 1: Set Up Python Environment

Open VS Code Terminal (`` Ctrl+` ``) and run:

```powershell
# Create virtual environment
python -m venv venv

# Activate it (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Or for Command Prompt
.\venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Firebase Authentication

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (canvaschatbot)
3. Navigate to **Project Settings > Service Accounts**
4. Click **Generate new private key**
5. Save the downloaded JSON file as `serviceAccountKey.json` in the project root

**Important**: Never commit this file to git! It's already in `.gitignore`.

### Step 3: Export Data from Firestore

```powershell
python scripts/export_firestore_chat_sessions.py
```

This creates `outputs/chat_sessions_raw.json` with all session data.

### Step 4: Run Analysis Pipeline

```powershell
python analysis/run_analysis.py
```

This generates:
- `outputs/chat_sessions_analysis.csv` - Processed session data for Excel/R/SPSS
- `outputs/user_level_summary.csv` - Per-user engagement metrics
- `outputs/user_level_summary_deidentified.csv` - De-identified version (hashed user IDs)
- `outputs/wpr_window_summary.csv` - Pre-WPR engagement analysis
- `outputs/analysis_summary.json` - Aggregate metrics
- `outputs/figures/*.png` - Publication-ready visualizations (11 figures)

## One-Command Execution

After setup, run the entire pipeline with:

```powershell
# Export + Analyze in one command
python scripts/export_firestore_chat_sessions.py && python analysis/run_analysis.py
```

## Directory Structure

```
canvas-chatbot-mvp/
├── scripts/
│   ├── export_firestore_chat_sessions.py  # Firestore export
│   └── classify_courses.py                 # Course classification module
├── analysis/
│   ├── run_analysis.py                     # Main analysis pipeline
│   ├── course_events.json                  # WPR/exam dates (gitignored)
│   ├── course_events.example.json          # Example events file
│   ├── METHODOLOGY.md                      # Research methodology documentation
│   └── README.md                           # This file
├── outputs/                                # All outputs gitignored
│   ├── chat_sessions_raw.json              # Raw exported data
│   ├── chat_sessions_analysis.csv          # Processed session CSV
│   ├── user_level_summary.csv              # Per-user metrics
│   ├── user_level_summary_deidentified.csv # De-identified user metrics
│   ├── wpr_window_summary.csv              # Pre-WPR engagement
│   ├── analysis_summary.json               # Summary metrics
│   └── figures/                            # Generated visualizations
│       ├── sessions_per_day.png            # With WPR markers
│       ├── sessions_per_day_ma205.png      # MA205 only
│       ├── sessions_per_day_ma371.png      # MA371 only
│       ├── course_comparison.png
│       ├── hourly_distribution.png
│       ├── dow_hour_heatmap.png
│       ├── course_distribution.png
│       ├── engagement_comparison.png
│       ├── sessions_per_user_hist.png      # User engagement distribution
│       ├── active_days_per_user_hist.png
│       └── users_active_per_day.png
├── requirements.txt                        # Python dependencies
└── serviceAccountKey.json                  # Firebase credentials (not in git)
```

## Command Reference

### Export Script

```powershell
# Default output
python scripts/export_firestore_chat_sessions.py

# Custom output path
python scripts/export_firestore_chat_sessions.py path/to/output.json
```

### Analysis Script

```powershell
# Default settings
python analysis/run_analysis.py

# With custom options
python analysis/run_analysis.py --input outputs/chat_sessions_raw.json --threshold 5 --dpi 300

# With course event markers
python analysis/run_analysis.py --events analysis/course_events.json
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--input, -i` | `outputs/chat_sessions_raw.json` | Input JSON file |
| `--events, -e` | None | Course events JSON for visualization markers |
| `--threshold, -t` | 5 | Classification score difference threshold |
| `--dpi` | 300 | Figure resolution (dots per inch) |

## Adding Course Event Markers (WPRs, Exams)

The pipeline automatically loads `analysis/course_events.json` if it exists (no CLI flag needed).

### Event File Format

Create `analysis/course_events.json` with the following structure:

```json
{
    "events": [
        {
            "date": "2025-09-09",
            "label": "WPR 1",
            "course": "multivariable_calculus",
            "type": "wpr"
        },
        {
            "date": "2025-09-17",
            "label": "WPR 1",
            "course": "linear_algebra",
            "type": "wpr"
        }
    ],
    "_metadata": {
        "description": "Course assessment events",
        "courses": {
            "multivariable_calculus": "MA205",
            "linear_algebra": "MA371"
        }
    }
}
```

### Event Fields

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `date` | Yes | `YYYY-MM-DD` | Event date |
| `label` | Yes | string | Display label (e.g., "WPR 1") |
| `course` | No | `multivariable_calculus`, `linear_algebra`, `both` | Which course (default: `both`) |
| `type` | No | `wpr`, `exam`, `quiz`, `other` | Event type for color coding |

### Behavior

- Events appear as vertical dashed lines on time series plots
- Course-specific plots (`sessions_per_day_ma205.png`, `sessions_per_day_ma371.png`) only show relevant events
- WPR events trigger pre-window analysis in `wpr_window_summary.csv`

To use a different events file:

```powershell
python analysis/run_analysis.py --events path/to/custom_events.json
```

## De-identification (HASH_SALT)

User IDs are hashed using SHA-256 for the de-identified output file. By default, a constant salt (`local-dev`) is used.

For production/publication, set a custom salt via environment variable:

```powershell
# PowerShell
$env:HASH_SALT = "your-secret-salt-here"
python analysis/run_analysis.py

# Or inline
$env:HASH_SALT = "your-salt"; python analysis/run_analysis.py
```

**Note**: Use the same salt for reproducible hashes across runs.

## Understanding the Outputs

### CSV File (`chat_sessions_analysis.csv`)

Each row represents one session with columns for:
- Session metadata (ID, user, timestamps)
- Engagement metrics (message counts, duration)
- Course classification (inferred course, scores, confidence)
- Top matched keywords for each course

**Compatible with**: Excel, R, SPSS, Stata, Python pandas

### Visualizations

| Figure | Description |
|--------|-------------|
| `sessions_per_day.png` | Time series with WPR event markers |
| `sessions_per_day_ma205.png` | MA205 (Multivariable Calculus) sessions only |
| `sessions_per_day_ma371.png` | MA371 (Linear Algebra) sessions only |
| `course_comparison.png` | Sessions and messages by inferred course |
| `hourly_distribution.png` | When students use the chatbot |
| `dow_hour_heatmap.png` | Usage patterns by day and hour |
| `course_distribution.png` | Pie chart of course classification |
| `engagement_comparison.png` | Metric comparison between courses |
| `sessions_per_user_hist.png` | Distribution of sessions per user |
| `active_days_per_user_hist.png` | Distribution of active days per user |
| `users_active_per_day.png` | Time series of daily unique users |

## Troubleshooting

### "firebase-admin package not installed"

```powershell
pip install firebase-admin
```

### "Service account key not found"

Ensure `serviceAccountKey.json` is in the project root, or set the environment variable:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\your\key.json"
```

### "Input file not found"

Run the export script before analysis:

```powershell
python scripts/export_firestore_chat_sessions.py
```

### matplotlib font warnings

These are harmless. To suppress:

```python
import warnings
warnings.filterwarnings('ignore')
```

## Methodology

For detailed documentation of the analysis methodology suitable for academic papers, see [METHODOLOGY.md](METHODOLOGY.md).
