"""
Decision Tree Classifier — built from scratch using information gain (entropy).
Includes Reduced Error Pruning (REP) post-pruning.

Design choices:
- Midpoint thresholds: splits evaluated at midpoints between consecutive unique values
- Majority class stored at every node: enables correct REP leaf replacement
- Bottom-up REP: children pruned before parents; repeated until stable
- No external dependencies beyond numpy
"""

from __future__ import annotations

import copy
import numpy as np
from collections import Counter
from typing import Optional


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class Node:
    """A single node in the decision tree (internal or leaf)."""

    __slots__ = (
        "feature_index", "threshold",
        "left", "right",
        "value",           # class label — only set for leaf nodes
        "majority_class",  # majority class of training samples at this node (all nodes)
        "samples",         # number of training samples reaching this node
        "impurity",        # entropy at this node
    )

    def __init__(self) -> None:
        self.feature_index: Optional[int] = None
        self.threshold: Optional[float] = None
        self.left: Optional[Node] = None
        self.right: Optional[Node] = None
        self.value: Optional[int] = None
        self.majority_class: Optional[int] = None
        self.samples: int = 0
        self.impurity: float = 0.0

    @property
    def is_leaf(self) -> bool:
        return self.value is not None

    def __repr__(self) -> str:
        if self.is_leaf:
            return f"Leaf(class={self.value}, n={self.samples})"
        return (
            f"Node(feat={self.feature_index}, thresh={self.threshold:.4f}, "
            f"n={self.samples}, H={self.impurity:.4f})"
        )


# ---------------------------------------------------------------------------
# Impurity / Information Gain
# ---------------------------------------------------------------------------

def entropy(y: np.ndarray) -> float:
    """Shannon entropy of label array y (in bits)."""
    n = len(y)
    if n == 0:
        return 0.0
    counts = np.bincount(y)
    probs = counts[counts > 0] / n
    return float(-np.sum(probs * np.log2(probs)))


def information_gain(
    y: np.ndarray,
    y_left: np.ndarray,
    y_right: np.ndarray,
) -> float:
    """IG = H(parent) - weighted_average_H(children)."""
    n = len(y)
    if n == 0:
        return 0.0
    return (
        entropy(y)
        - (len(y_left) / n) * entropy(y_left)
        - (len(y_right) / n) * entropy(y_right)
    )


# ---------------------------------------------------------------------------
# Decision Tree
# ---------------------------------------------------------------------------

class DecisionTreeClassifier:
    """
    Full decision tree grown to zero training error (or until stopping criteria).

    Parameters
    ----------
    max_depth       : Maximum tree depth (None = unlimited).
    min_samples_split : Minimum samples required to split an internal node.
    min_samples_leaf  : Minimum samples required in each child after a split.
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
        self.n_features_: int = 0
        self.n_classes_: int = 0

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> "DecisionTreeClassifier":
        """Grow the full tree on training data (X, y)."""
        self.n_features_ = X.shape[1]
        self.n_classes_ = len(np.unique(y))
        self.root = self._build_tree(X, y, depth=0)
        return self

    def _build_tree(self, X: np.ndarray, y: np.ndarray, depth: int) -> Node:
        node = Node()
        node.samples = len(y)
        node.impurity = entropy(y)
        node.majority_class = int(Counter(y.tolist()).most_common(1)[0][0])

        # --- Stopping criteria ---
        pure = len(np.unique(y)) == 1
        too_small = len(y) < self.min_samples_split
        max_depth_reached = self.max_depth is not None and depth >= self.max_depth

        if pure or too_small or max_depth_reached:
            node.value = node.majority_class
            return node

        # --- Find best split ---
        best_feat, best_thresh, best_gain = self._best_split(X, y)

        if best_gain <= 0.0:
            node.value = node.majority_class
            return node

        left_mask = X[:, best_feat] <= best_thresh
        right_mask = ~left_mask

        # Enforce min_samples_leaf
        if left_mask.sum() < self.min_samples_leaf or right_mask.sum() < self.min_samples_leaf:
            node.value = node.majority_class
            return node

        node.feature_index = best_feat
        node.threshold = best_thresh
        node.left = self._build_tree(X[left_mask], y[left_mask], depth + 1)
        node.right = self._build_tree(X[right_mask], y[right_mask], depth + 1)
        return node

    def _best_split(
        self, X: np.ndarray, y: np.ndarray
    ) -> tuple[int, float, float]:
        """Exhaustive search over all features and midpoint thresholds."""
        best_gain = -np.inf
        best_feat = 0
        best_thresh = 0.0

        for feat in range(X.shape[1]):
            unique_vals = np.unique(X[:, feat])
            if len(unique_vals) < 2:
                continue
            # Candidate thresholds: midpoints between consecutive unique values
            thresholds = (unique_vals[:-1] + unique_vals[1:]) / 2.0

            for thresh in thresholds:
                left_mask = X[:, feat] <= thresh
                right_mask = ~left_mask
                if left_mask.sum() == 0 or right_mask.sum() == 0:
                    continue

                gain = information_gain(y, y[left_mask], y[right_mask])
                if gain > best_gain:
                    best_gain = gain
                    best_feat = feat
                    best_thresh = thresh

        return best_feat, best_thresh, best_gain

    # ------------------------------------------------------------------
    # Predict
    # ------------------------------------------------------------------

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.root is None:
            raise RuntimeError("Call fit() before predict().")
        return np.array([self._traverse(x, self.root) for x in X], dtype=int)

    def _traverse(self, x: np.ndarray, node: Node) -> int:
        if node.is_leaf:
            return node.value  # type: ignore[return-value]
        if x[node.feature_index] <= node.threshold:
            return self._traverse(x, node.left)
        return self._traverse(x, node.right)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        return float(np.mean(self.predict(X) == y))

    # ------------------------------------------------------------------
    # Tree statistics
    # ------------------------------------------------------------------

    def get_depth(self) -> int:
        return self._depth(self.root)

    def _depth(self, node: Optional[Node]) -> int:
        if node is None or node.is_leaf:
            return 0
        return 1 + max(self._depth(node.left), self._depth(node.right))

    def count_nodes(self) -> int:
        return self._count(self.root)

    def _count(self, node: Optional[Node]) -> int:
        if node is None:
            return 0
        return 1 + self._count(node.left) + self._count(node.right)

    def count_leaves(self) -> int:
        return self._count_leaves(self.root)

    def _count_leaves(self, node: Optional[Node]) -> int:
        if node is None:
            return 0
        if node.is_leaf:
            return 1
        return self._count_leaves(node.left) + self._count_leaves(node.right)


# ---------------------------------------------------------------------------
# Reduced Error Pruning (REP)
# ---------------------------------------------------------------------------

class ReducedErrorPruner:
    """
    Post-pruning via Reduced Error Pruning (Quinlan, 1987).

    Algorithm
    ---------
    Repeatedly make a bottom-up pass over the tree. At each internal node
    whose two children are leaves, tentatively replace it with a leaf (using
    the node's pre-stored majority class). If validation accuracy does not
    decrease, commit the replacement. Repeat until no pruning occurs in a full
    pass.

    The tree is pruned **in-place**; wrap with copy.deepcopy if you need to
    preserve the unpruned version.
    """

    def __init__(self, tree: DecisionTreeClassifier) -> None:
        if tree.root is None:
            raise ValueError("Tree has not been fitted.")
        self.tree = tree

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prune(self, X_val: np.ndarray, y_val: np.ndarray) -> DecisionTreeClassifier:
        """
        Prune self.tree using (X_val, y_val). Returns the (modified) tree.
        """
        improved = True
        while improved:
            improved = self._prune_pass(self.tree.root, X_val, y_val)
        return self.tree

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune_pass(
        self, node: Optional[Node], X_val: np.ndarray, y_val: np.ndarray
    ) -> bool:
        """
        One bottom-up pass. Returns True if at least one node was pruned.
        """
        if node is None or node.is_leaf:
            return False

        pruned = False

        # Recurse into children first (bottom-up order)
        if node.left is not None and not node.left.is_leaf:
            pruned |= self._prune_pass(node.left, X_val, y_val)
        if node.right is not None and not node.right.is_leaf:
            pruned |= self._prune_pass(node.right, X_val, y_val)

        # Attempt to replace this node with a leaf if both children are leaves
        if (
            node.left is not None
            and node.right is not None
            and node.left.is_leaf
            and node.right.is_leaf
        ):
            if self._try_prune(node, X_val, y_val):
                pruned = True

        return pruned

    def _try_prune(
        self, node: Node, X_val: np.ndarray, y_val: np.ndarray
    ) -> bool:
        """
        Tentatively convert node to a leaf. Keep if val accuracy >= baseline.
        """
        baseline_acc = self.tree.score(X_val, y_val)

        # Save internal-node state
        saved = (node.left, node.right, node.feature_index, node.threshold)

        # Convert to leaf
        node.value = node.majority_class
        node.left = None
        node.right = None
        node.feature_index = None
        node.threshold = None

        if self.tree.score(X_val, y_val) >= baseline_acc:
            return True  # keep pruned version

        # Restore
        node.value = None
        node.left, node.right, node.feature_index, node.threshold = saved
        return False
