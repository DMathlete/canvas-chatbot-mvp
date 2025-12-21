# Methodology: Chat Session Data Analysis

## Overview

This document describes the methodology used to analyze engagement data from an AI-powered tutoring chatbot deployed in multivariable calculus and linear algebra courses. The analysis pipeline extracts session-level data from Firebase Firestore, infers the course context using keyword-based classification, computes engagement metrics, and generates publication-ready visualizations.

---

## 1. Data Source

### 1.1 System Description

The chatbot was deployed as a web-based tutoring assistant accessible to students enrolled in undergraduate mathematics courses. The system used an OpenAI-powered conversational agent with a custom prompt designed to encourage Socratic dialogue and conceptual understanding.

### 1.2 Data Collection Infrastructure

Session data was logged to a Firebase Firestore collection named `chat_sessions`. Each document in the collection represents a single user session and contains the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Unique identifier for the session |
| `user_id` | string | Pseudonymous user identifier (C-number) |
| `user_name` | string/null | Optional username from LMS integration |
| `start_time` | ISO 8601 timestamp | Session start time |
| `end_time` | ISO 8601 timestamp | Time of last interaction |
| `session_duration_sec` | integer | Duration in seconds |
| `user_message_count` | integer | Number of student messages |
| `total_message_count` | integer | Total messages (including system/assistant) |
| `avg_user_msg_len_chars` | integer | Average student message length (characters) |
| `avg_user_msg_len_words` | integer | Average student message length (words) |
| `student_to_bot_ratio` | float | Ratio of student to assistant messages |
| `topics` | array | Automatically detected topic tags |
| `topic_counts` | object | Frequency counts for each detected topic |
| `messages` | array | Full conversation transcript with role and content |

### 1.3 Data Collection Period

Data collection occurred during a single academic semester. The chatbot was available to students throughout the term, and no modifications were made to the logging schema during data collection.

### 1.4 Ethical Considerations

- Users were informed that conversation data would be collected for research purposes
- User identifiers were pseudonymous (institutional ID numbers)
- Full transcripts were stored with appropriate access controls
- Analysis was conducted on aggregated metrics where possible

---

## 2. Course Inference Methodology

### 2.1 Problem Statement

The original chatbot implementation did not log course identifiers. Students from both multivariable calculus and linear algebra courses used the same chatbot instance. To enable course-specific analysis, we developed a post-hoc classification system based on session content.

### 2.2 Classification Approach

We employed a **keyword-based scoring method** that prioritizes interpretability and transparency over predictive accuracy. This approach was chosen because:

1. **Transparency**: Keyword lists can be inspected, validated, and modified by domain experts
2. **Reproducibility**: Deterministic classification enables exact replication
3. **Explainability**: Each classification includes the specific keywords that contributed to the decision
4. **No training data required**: Avoids issues of label availability and model overfitting

### 2.3 Keyword Lists

Two comprehensive keyword lists were developed through expert review of course curricula:

#### Multivariable Calculus Keywords (Selected Examples)

| Category | Keywords |
|----------|----------|
| Partial Derivatives | partial derivative, gradient, directional derivative, nabla |
| Multiple Integrals | double integral, triple integral, iterated integral, Fubini |
| Coordinate Systems | polar coordinates, cylindrical coordinates, spherical coordinates |
| Vector Calculus | line integral, surface integral, flux, curl, divergence |
| Major Theorems | Green's theorem, Stokes' theorem, divergence theorem |
| Optimization | Lagrange multiplier, constrained optimization, Hessian |

#### Linear Algebra Keywords (Selected Examples)

| Category | Keywords |
|----------|----------|
| Matrix Operations | matrix, transpose, determinant, inverse, cofactor |
| Row Reduction | Gaussian elimination, row echelon form, RREF, pivot |
| Vector Spaces | vector space, subspace, span, linear independence, basis |
| Fundamental Subspaces | column space, null space, rank, nullity |
| Eigentheory | eigenvalue, eigenvector, characteristic polynomial, diagonalization |
| Orthogonality | orthogonal, Gram-Schmidt, orthogonal projection, least squares |

### 2.4 Scoring Algorithm

For each session:

1. **Text Extraction**: Concatenate all message content (user and assistant) into a single lowercase text string

2. **Keyword Matching**: For each keyword in both lists, count occurrences using whole-word regex matching

3. **Score Calculation**:
   ```
   score = sum(weight_i * min(count_i, 5))
   ```
   Where:
   - `weight_i` is the predefined importance weight for keyword i (range: 2-5)
   - `count_i` is the number of matches for keyword i
   - Counts are capped at 5 to prevent single repeated terms from dominating

4. **Classification**:
   - If `max(calc_score, la_score) < min_score`: classify as `mixed_or_uncertain`
   - If `|calc_score - la_score| < threshold`: classify as `mixed_or_uncertain`
   - Otherwise: classify as the course with the higher score

### 2.5 Configuration Parameters

| Parameter | Default Value | Description |
|-----------|--------------|-------------|
| `threshold` | 5 | Minimum score difference required for confident classification |
| `min_score` | 3 | Minimum total score required for any classification |

### 2.6 Confidence Levels

Each classification includes a confidence indicator:

- **High**: Score difference >= 2 * threshold
- **Medium**: Score difference >= threshold but < 2 * threshold
- **Low**: Classified as mixed_or_uncertain

### 2.7 Output Fields

Each classified session includes:

- `inferred_course`: One of {multivariable_calculus, linear_algebra, mixed_or_uncertain}
- `calculus_score`: Total weighted score for calculus keywords
- `linear_algebra_score`: Total weighted score for linear algebra keywords
- `calculus_hits`: Dictionary of matched calculus keywords and their counts
- `linear_algebra_hits`: Dictionary of matched linear algebra keywords and their counts
- `classification_confidence`: Confidence level (high/medium/low)
- `classification_reason`: Human-readable explanation of the classification decision

---

## 3. Engagement Metrics

### 3.1 Session-Level Metrics

| Metric | Definition | Unit |
|--------|------------|------|
| Session Duration | `end_time - start_time` | minutes |
| User Messages | Count of messages with role="user" | count |
| Total Messages | Count of all messages (including system prompt) | count |
| Average Message Length | Mean character/word count of user messages | chars/words |
| Student-to-Bot Ratio | `user_message_count / assistant_message_count` | ratio |

### 3.2 Aggregate Metrics

#### Overall Metrics
- Total sessions
- Unique users
- Total user messages
- Average messages per session
- Average/median session duration
- Date range of data collection

#### Daily Metrics
- Sessions per day
- Unique users per day
- User messages per day
- Average session duration per day

#### Temporal Distribution
- Sessions by hour of day (24-hour)
- Sessions by day of week
- Hour × Day-of-Week matrix

### 3.3 Course-Stratified Metrics

All aggregate metrics are computed separately for:
- Multivariable Calculus sessions
- Linear Algebra sessions
- Mixed/Uncertain sessions (typically excluded from comparative analyses)

---

## 4. Visualization Specifications

### 4.1 Time Series: Sessions per Day

- **Type**: Line chart with area fill
- **X-axis**: Date
- **Y-axis**: Number of sessions
- **Features**: Optional vertical markers for course events (quizzes, exams)
- **Purpose**: Identify usage patterns over the semester

### 4.2 Course Comparison

- **Type**: Dual-panel line chart
- **Panels**: (1) Sessions per day, (2) User messages per day
- **Series**: Separate lines for each inferred course
- **Purpose**: Compare engagement patterns between courses

### 4.3 Time-of-Day Distribution

- **Type**: Bar chart (histogram)
- **X-axis**: Hour of day (00:00 - 23:00)
- **Y-axis**: Number of sessions
- **Features**: Peak hour highlighted
- **Purpose**: Identify when students most frequently use the chatbot

### 4.4 Day-of-Week × Hour Heatmap

- **Type**: Annotated heatmap
- **Rows**: Days of week (Monday - Sunday)
- **Columns**: Hours of day (0-23)
- **Values**: Session count
- **Color scale**: Sequential (white to dark blue)
- **Purpose**: Detailed temporal usage patterns

### 4.5 Course Distribution

- **Type**: Pie chart
- **Segments**: Multivariable Calculus, Linear Algebra, Mixed/Uncertain
- **Labels**: Percentage and count
- **Purpose**: Show overall distribution of sessions by inferred course

### 4.6 Engagement Comparison

- **Type**: Grouped bar chart
- **Categories**: Average messages/session, Average duration, Average message length
- **Groups**: Multivariable Calculus, Linear Algebra
- **Purpose**: Compare engagement depth between courses

---

## 5. Treatment of Ambiguous Sessions

### 5.1 Definition

Sessions classified as `mixed_or_uncertain` include:

1. **Low engagement**: Sessions with insufficient text content to generate meaningful keyword matches (score below minimum threshold)
2. **Genuinely mixed**: Sessions discussing topics from both courses
3. **Off-topic**: Sessions about general math concepts, course logistics, or unrelated content

### 5.2 Handling in Analysis

- **Inclusion in overall metrics**: Mixed sessions are included in overall engagement statistics
- **Exclusion from course comparisons**: When comparing courses, mixed sessions are excluded to provide cleaner comparisons
- **Transparent reporting**: The proportion of mixed sessions is always reported to indicate classification coverage

---

## 6. Known Limitations

### 6.1 Course Inference Limitations

1. **Post-hoc classification**: Course labels are inferred rather than directly observed, introducing potential misclassification
2. **Keyword dependence**: Classification quality depends on the comprehensiveness and accuracy of keyword lists
3. **Overlap handling**: Some topics (e.g., "matrix", "vector") appear in both courses; weights attempt to balance this
4. **Evolution of terminology**: Student and assistant language may not perfectly match canonical keyword lists
5. **Context insensitivity**: Keyword matching does not account for negation or contextual usage

### 6.2 Data Limitations

1. **Self-selection bias**: Only students who chose to use the chatbot are represented
2. **Session definition**: A "session" represents a single browser session; students may have multiple sessions
3. **Anonymous users**: Some sessions have `user_id = "anonymous_user"` limiting user-level analysis
4. **Missing course metadata**: Without ground-truth course labels, classification accuracy cannot be validated

### 6.3 Metric Limitations

1. **Session duration**: Measures time from first to last message, not active engagement time
2. **Message counts**: Do not capture message quality or learning outcomes
3. **Time zones**: All timestamps are in the server's time zone (assumed consistent)

---

## 7. Threats to Validity

### 7.1 Internal Validity

- **Classification error**: Misclassified sessions may bias course-level comparisons
- **Survivorship bias**: Analysis only includes completed sessions; abandoned sessions may be underrepresented

### 7.2 External Validity

- **Single institution**: Results may not generalize to other institutions or student populations
- **Specific courses**: Findings are specific to multivariable calculus and linear algebra
- **Deployment context**: The chatbot was supplementary; primary instruction was in-person

### 7.3 Construct Validity

- **Engagement operationalization**: Session count and message volume may not fully capture meaningful engagement
- **Course inference validity**: Keyword-based classification assumes content is primarily course-related

---

## 8. Reproducibility

### 8.1 Software Requirements

- Python 3.8+
- pandas >= 1.3.0
- matplotlib >= 3.4.0
- seaborn >= 0.11.0
- firebase-admin >= 5.0.0

### 8.2 Pipeline Execution

```bash
# Step 1: Export data from Firestore
python scripts/export_firestore_chat_sessions.py

# Step 2: Run analysis pipeline
python analysis/run_analysis.py
```

### 8.3 Configuration

Classification parameters can be adjusted via command-line arguments:

```bash
python analysis/run_analysis.py --threshold 5 --dpi 300
```

### 8.4 Output Files

| File | Description |
|------|-------------|
| `outputs/chat_sessions_raw.json` | Raw exported session data |
| `outputs/chat_sessions_analysis.csv` | Processed data with classifications |
| `outputs/analysis_summary.json` | Aggregate metrics |
| `outputs/figures/*.png` | Publication-ready visualizations |

---

## References

This methodology draws on established practices in learning analytics and educational data mining. The keyword-based classification approach prioritizes interpretability following recommendations for explainable AI in educational contexts.
