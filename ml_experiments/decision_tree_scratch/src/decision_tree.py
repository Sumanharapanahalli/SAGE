"""
decision_tree.py
----------------
Decision Tree Classifier built entirely from scratch.

Splitting criterion : Information Gain (entropy-based, Quinlan ID3/C4.5)
Post-pruning        : Reduced Error Pruning — Quinlan (1987)
                      Bottom-up: replace every internal node with a leaf
                      if validation accuracy does not decrease.

Design notes
------------
- node.prediction is set for EVERY node (not just leaves) during _build().
  This stores the majority-class label of training samples at that node,
  which is the leaf prediction used during REP without re-examining train data.
- Candidate thresholds are midpoints between consecutive unique feature
  values (C4.5-style), giving O(n_samples × n_features) candidates.
- No sklearn or external ML library is used for the core logic.
"""

from __future__ import annotations

import numpy as np
from collections import Counter
from typing import Optional, Any


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class Node:
    """A single node in the decision tree."""

    __slots__ = (
        "feature_index", "threshold",
        "left", "right",
        "is_leaf", "prediction",
        "samples", "impurity",
    )

    def __init__(self) -> None:
        self.feature_index: Optional[int] = None
        self.threshold: Optional[float] = None
        self.left: Optional["Node"] = None
        self.right: Optional["Node"] = None
        self.is_leaf: bool = False
        # Stored for ALL nodes — REP uses this when collapsing a subtree.
        self.prediction: Optional[Any] = None
        self.samples: int = 0
        self.impurity: float = 0.0


# ---------------------------------------------------------------------------
# Entropy & Information Gain
# ---------------------------------------------------------------------------

def _entropy(y: np.ndarray) -> float:
    """Shannon entropy H(y) in bits."""
    if len(y) == 0:
        return 0.0
    counts = np.bincount(y)
    probs = counts[counts > 0] / float(len(y))
    return float(-np.sum(probs * np.log2(probs)))


def _information_gain(y: np.ndarray, left_mask: np.ndarray) -> float:
    """
    IG(y, split) = H(y) - weighted_entropy(children)

    Parameters
    ----------
    y         : integer label array of the current node
    left_mask : boolean mask — True → left child, False → right child
    """
    n = len(y)
    n_left = int(left_mask.sum())
    n_right = n - n_left
    if n_left == 0 or n_right == 0:
        return 0.0
    parent_h = _entropy(y)
    child_h = (n_left / n) * _entropy(y[left_mask]) + \
              (n_right / n) * _entropy(y[~left_mask])
    return parent_h - child_h


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class DecisionTreeClassifier:
    """
    Decision Tree Classifier (from scratch).

    Parameters
    ----------
    max_depth          : cap on tree depth (None = unlimited)
    min_samples_split  : minimum samples to attempt a split
    min_samples_leaf   : minimum samples required in each child after a split
    """

    def __init__(
        self,
        max_depth: Optional[int] = None,
        min_samples_split: int = 2,
        min_samples_leaf: int = 1,
    ) -> None:
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf

        self.root: Optional[Node] = None
        self.n_features_: Optional[int] = None
        self.classes_: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> "DecisionTreeClassifier":
        """Grow the full (unpruned) tree on (X, y)."""
        self.n_features_ = X.shape[1]
        self.classes_ = np.unique(y)
        self.root = self._build(X, y.astype(int), depth=0)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.root is None:
            raise RuntimeError("Tree has not been fitted yet. Call fit() first.")
        return np.array([self._predict_row(x, self.root) for x in X], dtype=int)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        return float(np.mean(self.predict(X) == y.astype(int)))

    # ------------------------------------------------------------------
    # Tree statistics (useful for comparing pre/post pruning)
    # ------------------------------------------------------------------

    def depth(self) -> int:
        return self._node_depth(self.root)

    def n_nodes(self) -> int:
        return self._count_nodes(self.root)

    def n_leaves(self) -> int:
        return self._count_leaves(self.root)

    # ------------------------------------------------------------------
    # Internal: build
    # ------------------------------------------------------------------

    def _build(self, X: np.ndarray, y: np.ndarray, depth: int) -> Node:
        node = Node()
        node.samples = len(y)
        node.impurity = _entropy(y)
        # Majority-class prediction stored for every node (used by REP).
        node.prediction = int(Counter(y.tolist()).most_common(1)[0][0])

        # ---- stopping conditions ----------------------------------------
        only_one_class = len(np.unique(y)) == 1
        too_small = len(y) < self.min_samples_split
        depth_exceeded = (self.max_depth is not None) and (depth >= self.max_depth)

        if only_one_class or too_small or depth_exceeded:
            node.is_leaf = True
            return node

        # ---- search for best (feature, threshold) split -----------------
        best_gain = -np.inf
        best_feat: Optional[int] = None
        best_thr: Optional[float] = None
        best_mask: Optional[np.ndarray] = None

        for feat_idx in range(X.shape[1]):
            col = X[:, feat_idx]
            unique_vals = np.unique(col)
            if len(unique_vals) < 2:
                continue
            # C4.5-style: midpoints between consecutive sorted unique values
            thresholds = (unique_vals[:-1] + unique_vals[1:]) / 2.0

            for thr in thresholds:
                mask = col <= thr
                if mask.sum() < self.min_samples_leaf or (~mask).sum() < self.min_samples_leaf:
                    continue
                gain = _information_gain(y, mask)
                if gain > best_gain:
                    best_gain = gain
                    best_feat = feat_idx
                    best_thr = thr
                    best_mask = mask

        # No valid split found → make leaf
        if best_gain <= 1e-10 or best_feat is None:
            node.is_leaf = True
            return node

        node.feature_index = best_feat
        node.threshold = best_thr
        node.left = self._build(X[best_mask], y[best_mask], depth + 1)
        node.right = self._build(X[~best_mask], y[~best_mask], depth + 1)
        return node

    # ------------------------------------------------------------------
    # Internal: predict
    # ------------------------------------------------------------------

    def _predict_row(self, x: np.ndarray, node: Node) -> int:
        if node.is_leaf:
            return node.prediction  # type: ignore[return-value]
        if x[node.feature_index] <= node.threshold:
            return self._predict_row(x, node.left)
        return self._predict_row(x, node.right)

    # ------------------------------------------------------------------
    # Internal: tree statistics helpers
    # ------------------------------------------------------------------

    def _node_depth(self, node: Optional[Node]) -> int:
        if node is None or node.is_leaf:
            return 0
        return 1 + max(self._node_depth(node.left), self._node_depth(node.right))

    def _count_nodes(self, node: Optional[Node]) -> int:
        if node is None:
            return 0
        return 1 + self._count_nodes(node.left) + self._count_nodes(node.right)

    def _count_leaves(self, node: Optional[Node]) -> int:
        if node is None:
            return 0
        if node.is_leaf:
            return 1
        return self._count_leaves(node.left) + self._count_leaves(node.right)


# ---------------------------------------------------------------------------
# Reduced Error Pruning (REP)
# ---------------------------------------------------------------------------

def reduced_error_pruning(
    tree: DecisionTreeClassifier,
    X_val: np.ndarray,
    y_val: np.ndarray,
) -> DecisionTreeClassifier:
    """
    Reduced Error Pruning — Quinlan (1987).

    Algorithm (post-order / bottom-up):
      For every internal node visited bottom-up:
        1. Temporarily replace the subtree with a leaf whose prediction is
           node.prediction (majority class of training samples that reached
           this node, stored during fit()).
        2. Measure accuracy on the held-out validation set.
        3. If accuracy >= baseline_accuracy → keep pruned (accept).
        4. Otherwise → restore the original subtree (reject).

    The baseline accuracy starts at the full-tree validation accuracy and
    is updated whenever a prune is accepted, so accepted prunes can enable
    further pruning higher up the tree.

    Parameters
    ----------
    tree  : fitted (unpruned) DecisionTreeClassifier
    X_val : validation features  — MUST NOT overlap with train or test
    y_val : validation labels

    Returns
    -------
    The same tree object, pruned in-place, for convenience.
    """
    if tree.root is None:
        raise RuntimeError("Tree has not been fitted yet.")

    y_val = y_val.astype(int)
    baseline_acc = tree.score(X_val, y_val)
    prune_count = [0]  # mutable counter for post-call inspection

    def _prune(node: Node) -> None:
        nonlocal baseline_acc

        if node.is_leaf:
            return

        # Post-order: prune children before considering this node
        _prune(node.left)
        _prune(node.right)

        # --- Snapshot internal node state ---
        saved_left = node.left
        saved_right = node.right
        saved_feat = node.feature_index
        saved_thr = node.threshold

        # --- Convert to leaf temporarily ---
        node.is_leaf = True
        node.left = None
        node.right = None
        node.feature_index = None
        node.threshold = None
        # node.prediction was set during _build() — already correct.

        new_acc = tree.score(X_val, y_val)

        if new_acc >= baseline_acc:
            # Accept prune: update baseline
            baseline_acc = new_acc
            prune_count[0] += 1
        else:
            # Reject: restore original subtree
            node.is_leaf = False
            node.left = saved_left
            node.right = saved_right
            node.feature_index = saved_feat
            node.threshold = saved_thr

    _prune(tree.root)
    tree.n_pruned_nodes_ = prune_count[0]  # type: ignore[attr-defined]
    return tree
