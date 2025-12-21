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
- `outputs/chat_sessions_analysis.csv` - Processed data for Excel/R/SPSS
- `outputs/analysis_summary.json` - Aggregate metrics
- `outputs/figures/*.png` - Publication-ready visualizations

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
│   ├── METHODOLOGY.md                      # Research methodology documentation
│   └── README.md                           # This file
├── outputs/
│   ├── chat_sessions_raw.json              # Raw exported data
│   ├── chat_sessions_analysis.csv          # Processed CSV
│   ├── analysis_summary.json               # Summary metrics
│   └── figures/                            # Generated visualizations
│       ├── sessions_per_day.png
│       ├── course_comparison.png
│       ├── hourly_distribution.png
│       ├── dow_hour_heatmap.png
│       ├── course_distribution.png
│       └── engagement_comparison.png
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

## Adding Course Event Markers

To add vertical markers for quizzes, exams, or other events on the time series plot, create `analysis/course_events.json`:

```json
{
    "quizzes": [
        {"date": "2024-09-15", "label": "Quiz 1"},
        {"date": "2024-10-01", "label": "Quiz 2"}
    ],
    "exams": [
        {"date": "2024-10-20", "label": "Midterm"},
        {"date": "2024-12-15", "label": "Final"}
    ],
    "other": [
        {"date": "2024-11-01", "label": "Project Due"}
    ]
}
```

Then run:

```powershell
python analysis/run_analysis.py --events analysis/course_events.json
```

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
| `sessions_per_day.png` | Time series of daily session counts |
| `course_comparison.png` | Sessions and messages by inferred course |
| `hourly_distribution.png` | When students use the chatbot |
| `dow_hour_heatmap.png` | Usage patterns by day and hour |
| `course_distribution.png` | Pie chart of course classification |
| `engagement_comparison.png` | Metric comparison between courses |

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
