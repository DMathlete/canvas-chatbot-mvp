#!/usr/bin/env python3
"""
Course Inference Module
========================
Classifies chat sessions as either multivariable_calculus, linear_algebra,
or mixed_or_uncertain based on keyword scoring of session content.

Methodology:
- Uses full session message text (user + assistant messages)
- Employs keyword-based scoring with explicit term lists
- Returns explainable classification with scores and matched keywords

This approach prioritizes interpretability over accuracy, making it suitable
for academic research where methodology transparency is essential.
"""

import re
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class CourseClassification:
    """Classification result for a single session."""
    session_id: str
    inferred_course: str  # "multivariable_calculus", "linear_algebra", "mixed_or_uncertain"
    calculus_score: int
    linear_algebra_score: int
    calculus_hits: Dict[str, int] = field(default_factory=dict)
    linear_algebra_hits: Dict[str, int] = field(default_factory=dict)
    confidence: str = ""  # "high", "medium", "low"
    classification_reason: str = ""


# ============================================================================
# KEYWORD LISTS
# ============================================================================
# These lists are designed to be mutually exclusive where possible.
# Terms that appear in both courses are excluded or placed in shared context.

MULTIVARIABLE_CALCULUS_KEYWORDS = {
    # Partial Derivatives & Gradients
    "partial derivative": 5,
    "partial derivatives": 5,
    "gradient": 4,
    "directional derivative": 5,
    "directional derivatives": 5,
    "nabla": 4,
    "del operator": 4,

    # Multi-variable functions
    "multivariable": 5,
    "multi-variable": 5,
    "multivariate": 4,
    "function of several variables": 5,
    "functions of several variables": 5,
    "f(x,y)": 4,
    "f(x,y,z)": 5,
    "z = f(x,y)": 4,

    # Limits & Continuity in Multiple Variables
    "limit in two variables": 5,
    "limit in three variables": 5,
    "path dependent": 4,
    "path-dependent": 4,

    # Tangent Planes & Linearization
    "tangent plane": 5,
    "tangent planes": 5,
    "linearization": 4,
    "linear approximation": 3,
    "total differential": 5,

    # Chain Rule (Multi)
    "multivariable chain rule": 5,
    "chain rule partial": 4,
    "total derivative": 4,

    # Optimization
    "lagrange multiplier": 5,
    "lagrange multipliers": 5,
    "constrained optimization": 5,
    "critical point": 3,
    "critical points": 3,
    "saddle point": 4,
    "saddle points": 4,
    "local maximum": 3,
    "local minimum": 3,
    "local extrema": 4,
    "second derivative test": 3,
    "hessian": 4,
    "hessian matrix": 5,

    # Multiple Integrals
    "double integral": 5,
    "double integrals": 5,
    "triple integral": 5,
    "triple integrals": 5,
    "iterated integral": 5,
    "iterated integrals": 5,
    "region of integration": 4,
    "change of order": 4,
    "fubini": 4,

    # Coordinate Systems
    "polar coordinates": 4,
    "cylindrical coordinates": 5,
    "spherical coordinates": 5,
    "polar integral": 5,
    "cylindrical integral": 5,
    "spherical integral": 5,
    "r dr dtheta": 5,
    "rho": 3,
    "phi": 2,  # Lower weight as it's used in many contexts

    # Change of Variables
    "jacobian": 4,  # Also used in linear algebra but more common in calc
    "jacobian determinant": 5,
    "change of variables": 4,
    "u-substitution": 3,

    # Vector Calculus
    "vector field": 4,
    "vector fields": 4,
    "line integral": 5,
    "line integrals": 5,
    "path integral": 4,
    "work integral": 5,
    "circulation": 4,
    "surface integral": 5,
    "surface integrals": 5,
    "flux integral": 5,
    "flux": 3,
    "outward flux": 5,

    # Conservative Fields
    "conservative field": 5,
    "conservative vector field": 5,
    "potential function": 4,
    "exact differential": 4,
    "path independent": 4,
    "path-independent": 4,

    # Vector Calculus Operations
    "curl": 5,
    "divergence": 5,
    "div": 2,  # Lower weight, common word

    # Major Theorems
    "green's theorem": 5,
    "greens theorem": 5,
    "stokes theorem": 5,
    "stokes' theorem": 5,
    "divergence theorem": 5,
    "gauss's theorem": 5,

    # Parametric Curves & Surfaces
    "parametric curve": 4,
    "parametric curves": 4,
    "parametric surface": 5,
    "parametric surfaces": 5,
    "arc length": 4,
    "parameterization": 4,
    "parameterize": 4,

    # Applications
    "center of mass": 3,
    "moment of inertia": 4,
    "mass density": 4,
    "surface area": 3,
    "volume element": 4,
}

LINEAR_ALGEBRA_KEYWORDS = {
    # Matrices - Basic
    "matrix": 3,
    "matrices": 4,
    "row": 2,
    "column": 2,
    "square matrix": 4,
    "identity matrix": 4,
    "zero matrix": 3,
    "transpose": 4,
    "symmetric matrix": 5,
    "symmetric matrices": 5,
    "diagonal matrix": 4,
    "diagonal matrices": 4,

    # Vectors - Basic
    "vector": 2,  # Lower weight as used in both courses
    "vectors": 2,
    "scalar": 3,
    "scalar multiplication": 4,
    "linear combination": 5,
    "linear combinations": 5,

    # Matrix Operations
    "matrix multiplication": 5,
    "matrix product": 4,
    "dot product": 3,  # Also in calc but weighted toward LA
    "inner product": 4,
    "outer product": 4,
    "cross product": 3,

    # Systems of Equations
    "system of equations": 4,
    "systems of equations": 4,
    "system of linear equations": 5,
    "augmented matrix": 5,
    "coefficient matrix": 5,

    # Row Reduction
    "gaussian elimination": 5,
    "gauss-jordan": 5,
    "gauss jordan": 5,
    "row reduction": 5,
    "row reduce": 5,
    "row echelon": 5,
    "echelon form": 5,
    "ref": 3,
    "rref": 5,
    "reduced row echelon": 5,
    "pivot": 4,
    "pivots": 4,
    "pivot column": 5,
    "pivot position": 5,
    "free variable": 5,
    "free variables": 5,
    "leading entry": 4,
    "leading one": 4,

    # Solutions
    "consistent": 3,
    "inconsistent": 4,
    "unique solution": 4,
    "infinitely many solutions": 5,
    "no solution": 3,
    "trivial solution": 5,
    "nontrivial solution": 5,
    "homogeneous": 4,
    "homogeneous system": 5,
    "particular solution": 4,
    "general solution": 3,

    # Inverses & Determinants
    "inverse": 3,
    "inverse matrix": 5,
    "invertible": 5,
    "non-invertible": 5,
    "singular": 4,
    "singular matrix": 5,
    "nonsingular": 5,
    "determinant": 5,
    "det": 3,
    "cofactor": 5,
    "cofactor expansion": 5,
    "minor": 3,
    "cramer's rule": 5,
    "cramers rule": 5,
    "cramer": 4,

    # Vector Spaces
    "vector space": 5,
    "vector spaces": 5,
    "subspace": 5,
    "subspaces": 5,
    "span": 4,
    "spanning set": 5,
    "linear independence": 5,
    "linearly independent": 5,
    "linearly dependent": 5,
    "linear dependence": 5,
    "basis": 4,
    "bases": 4,
    "standard basis": 5,
    "dimension": 3,
    "dim": 2,
    "finite dimensional": 5,

    # Fundamental Subspaces
    "column space": 5,
    "row space": 5,
    "null space": 5,
    "nullspace": 5,
    "kernel": 4,
    "range": 2,
    "image": 2,
    "rank": 4,
    "nullity": 5,
    "rank-nullity": 5,
    "rank nullity theorem": 5,

    # Orthogonality
    "orthogonal": 4,
    "orthonormal": 5,
    "orthogonal complement": 5,
    "perpendicular": 3,
    "gram-schmidt": 5,
    "gram schmidt": 5,
    "orthogonal projection": 5,
    "projection": 3,
    "proj": 3,
    "least squares": 5,
    "normal equations": 5,
    "qr factorization": 5,
    "qr decomposition": 5,

    # Eigenvalues & Eigenvectors
    "eigenvalue": 5,
    "eigenvalues": 5,
    "eigenvector": 5,
    "eigenvectors": 5,
    "eigenspace": 5,
    "characteristic polynomial": 5,
    "characteristic equation": 5,
    "diagonalizable": 5,
    "diagonalization": 5,
    "diagonalize": 5,
    "defective": 4,
    "algebraic multiplicity": 5,
    "geometric multiplicity": 5,

    # Linear Transformations
    "linear transformation": 5,
    "linear transformations": 5,
    "linear map": 5,
    "linear mapping": 5,
    "linear operator": 5,
    "transformation matrix": 5,
    "standard matrix": 5,
    "one-to-one": 3,
    "onto": 3,
    "isomorphism": 5,

    # Decompositions
    "lu factorization": 5,
    "lu decomposition": 5,
    "svd": 5,
    "singular value": 5,
    "singular values": 5,
    "spectral decomposition": 5,
    "positive definite": 5,
    "positive semidefinite": 5,
}


class CourseClassifier:
    """
    Classifies chat sessions by course using keyword scoring.

    Configuration:
        threshold: Minimum score difference for confident classification
        min_score: Minimum score required for any classification
    """

    def __init__(self, threshold: int = 5, min_score: int = 3):
        """
        Initialize the classifier.

        Args:
            threshold: Minimum score difference between courses for confident classification.
                       If |calc_score - la_score| < threshold, classify as mixed_or_uncertain.
            min_score: Minimum total score required. If max(scores) < min_score,
                       classify as mixed_or_uncertain.
        """
        self.threshold = threshold
        self.min_score = min_score
        self.calc_keywords = MULTIVARIABLE_CALCULUS_KEYWORDS
        self.la_keywords = LINEAR_ALGEBRA_KEYWORDS

    def _extract_text(self, session: Dict[str, Any]) -> str:
        """Extract all text content from a session for analysis.

        Note: Excludes system messages to prevent the system prompt
        (which mentions both courses) from biasing classification.
        """
        text_parts = []

        # Extract from messages array if present
        # Exclude system messages to avoid bias from system prompt
        messages = session.get("messages", [])
        for msg in messages:
            role = msg.get("role", "")
            if role == "system":
                continue  # Skip system prompt
            content = msg.get("content", "")
            if content and isinstance(content, str):
                text_parts.append(content)

        # Also check for any direct text fields
        for field in ["topics", "topic_counts"]:
            if field in session:
                val = session[field]
                if isinstance(val, list):
                    text_parts.extend(str(v) for v in val)
                elif isinstance(val, dict):
                    text_parts.extend(str(k) for k in val.keys())

        return " ".join(text_parts).lower()

    def _score_keywords(
        self, text: str, keywords: Dict[str, int]
    ) -> Tuple[int, Dict[str, int]]:
        """
        Score text against a keyword dictionary.

        Returns:
            Tuple of (total_score, {keyword: count})
        """
        total_score = 0
        hits = {}

        for keyword, weight in keywords.items():
            # Use word boundary matching for most terms
            # Escape special regex characters
            escaped = re.escape(keyword)
            # Match as whole word/phrase
            pattern = r'\b' + escaped + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            count = len(matches)

            if count > 0:
                hits[keyword] = count
                # Score is weight * count, but cap individual keyword contribution
                # to prevent a single repeated term from dominating
                capped_count = min(count, 5)
                total_score += weight * capped_count

        return total_score, hits

    def classify(self, session: Dict[str, Any]) -> CourseClassification:
        """
        Classify a single session.

        Args:
            session: Session dictionary with messages and metadata

        Returns:
            CourseClassification with scores and classification
        """
        session_id = session.get("session_id", session.get("_document_id", "unknown"))
        text = self._extract_text(session)

        # Score against both keyword sets
        calc_score, calc_hits = self._score_keywords(text, self.calc_keywords)
        la_score, la_hits = self._score_keywords(text, self.la_keywords)

        # Determine classification
        max_score = max(calc_score, la_score)
        score_diff = abs(calc_score - la_score)

        if max_score < self.min_score:
            inferred = "mixed_or_uncertain"
            confidence = "low"
            reason = f"Insufficient keyword matches (max score: {max_score} < {self.min_score})"
        elif score_diff < self.threshold:
            inferred = "mixed_or_uncertain"
            confidence = "low"
            reason = f"Scores too close (calc: {calc_score}, LA: {la_score}, diff: {score_diff} < {self.threshold})"
        elif calc_score > la_score:
            inferred = "multivariable_calculus"
            if score_diff >= self.threshold * 2:
                confidence = "high"
            else:
                confidence = "medium"
            reason = f"Calculus score ({calc_score}) > LA score ({la_score}) by {score_diff}"
        else:
            inferred = "linear_algebra"
            if score_diff >= self.threshold * 2:
                confidence = "high"
            else:
                confidence = "medium"
            reason = f"LA score ({la_score}) > Calculus score ({calc_score}) by {score_diff}"

        return CourseClassification(
            session_id=session_id,
            inferred_course=inferred,
            calculus_score=calc_score,
            linear_algebra_score=la_score,
            calculus_hits=calc_hits,
            linear_algebra_hits=la_hits,
            confidence=confidence,
            classification_reason=reason,
        )

    def classify_sessions(
        self, sessions: List[Dict[str, Any]]
    ) -> List[CourseClassification]:
        """Classify multiple sessions."""
        return [self.classify(session) for session in sessions]


def classify_sessions_from_json(
    input_path: str,
    threshold: int = 5,
    min_score: int = 3,
) -> List[CourseClassification]:
    """
    Convenience function to classify sessions from a JSON file.

    Args:
        input_path: Path to JSON file with session data
        threshold: Classification threshold (score difference required)
        min_score: Minimum score for any classification

    Returns:
        List of CourseClassification results
    """
    import json
    from pathlib import Path

    with open(input_path, 'r', encoding='utf-8') as f:
        sessions = json.load(f)

    classifier = CourseClassifier(threshold=threshold, min_score=min_score)
    return classifier.classify_sessions(sessions)


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    # Default paths
    project_root = Path(__file__).parent.parent
    default_input = project_root / "outputs" / "chat_sessions_raw.json"
    default_output = project_root / "outputs" / "chat_sessions_classified.json"

    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_input
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else default_output

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Run the export script first: python scripts/export_firestore_chat_sessions.py")
        sys.exit(1)

    print(f"Classifying sessions from: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        sessions = json.load(f)

    classifier = CourseClassifier(threshold=5, min_score=3)
    classifications = classifier.classify_sessions(sessions)

    # Merge classifications back into session data
    for session, classification in zip(sessions, classifications):
        session["inferred_course"] = classification.inferred_course
        session["course_classification"] = {
            "calculus_score": classification.calculus_score,
            "linear_algebra_score": classification.linear_algebra_score,
            "calculus_hits": classification.calculus_hits,
            "linear_algebra_hits": classification.linear_algebra_hits,
            "confidence": classification.confidence,
            "reason": classification.classification_reason,
        }

    # Save enriched data
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

    print(f"Saved classified sessions to: {output_path}")

    # Print summary
    calc_count = sum(1 for c in classifications if c.inferred_course == "multivariable_calculus")
    la_count = sum(1 for c in classifications if c.inferred_course == "linear_algebra")
    mixed_count = sum(1 for c in classifications if c.inferred_course == "mixed_or_uncertain")

    print("\n=== Classification Summary ===")
    print(f"Total sessions: {len(classifications)}")
    print(f"Multivariable Calculus: {calc_count} ({100*calc_count/len(classifications):.1f}%)")
    print(f"Linear Algebra: {la_count} ({100*la_count/len(classifications):.1f}%)")
    print(f"Mixed/Uncertain: {mixed_count} ({100*mixed_count/len(classifications):.1f}%)")

    # Confidence breakdown
    high = sum(1 for c in classifications if c.confidence == "high")
    medium = sum(1 for c in classifications if c.confidence == "medium")
    low = sum(1 for c in classifications if c.confidence == "low")
    print(f"\nConfidence: High={high}, Medium={medium}, Low={low}")
