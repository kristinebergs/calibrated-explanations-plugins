import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("calibrated_explanations")
pytest.importorskip("lime")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import calibrated_explanations.plugins.registry as registry
from calibrated_explanations import CalibratedExplainer
from ce_explanation_factual_lime import plugin as lime_plugin_mod
from ce_explanation_factual_lime.lime_helper import LimeHelper
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split


def _reset_registry_state() -> None:
    reset_catalog = getattr(registry, "reset_plugin_catalog", None)
    if callable(reset_catalog):
        reset_catalog(kind="all")
    clear_env_cache = getattr(registry, "clear_env_trust_cache", None)
    if callable(clear_env_cache):
        clear_env_cache()
    clear_warnings = getattr(registry, "clear_trust_warnings", None)
    if callable(clear_warnings):
        clear_warnings()


def test_plugin_should_emit_lime_backed_factual_explanations(monkeypatch):
    def _preload_without_single_row_nan(self, x_cal=None):
        """Use full calibration matrix in tests to avoid single-row LIME NaN failures."""
        if self._enabled and self._explainer_instance is not None:
            return self._explainer_instance, self._reference_explanation

        from calibrated_explanations.utils import safe_import

        lime_cls = safe_import("lime.lime_tabular", "LimeTabularExplainer")
        if not lime_cls:
            self._enabled = False
            return None, None

        features = self.explainer.feature_names
        x_cal_source = self.explainer.x_cal if x_cal is None else x_cal
        if self.explainer.mode == "classification":
            self._explainer_instance = lime_cls(
                x_cal_source,
                feature_names=features,
                class_names=["0", "1"],
                mode=self.explainer.mode,
            )
            self._reference_explanation = self._explainer_instance.explain_instance(
                self.explainer.x_cal[0, :],
                self.explainer.learner.predict_proba,
                num_features=self.explainer.num_features,
            )
        elif "regression" in self.explainer.mode:
            self._explainer_instance = lime_cls(
                x_cal_source,
                feature_names=features,
                mode="regression",
            )
            self._reference_explanation = self._explainer_instance.explain_instance(
                self.explainer.x_cal[0, :],
                self.explainer.learner.predict,
                num_features=self.explainer.num_features,
            )
        self._enabled = self._explainer_instance is not None
        return self._explainer_instance, self._reference_explanation

    monkeypatch.setattr(LimeHelper, "preload", _preload_without_single_row_nan)

    monkeypatch.setenv(
        "CE_TRUST_PLUGIN",
        ",".join(
            [
                "official.explanation.factual.lime",
                "ce_explanation_factual_lime.plugin:FactualLimeExplanationPlugin",
            ]
        ),
    )
    _reset_registry_state()
    lime_plugin_mod.register_scaffold_explanation_plugin()

    descriptor = registry.find_explanation_descriptor("official.explanation.factual.lime")
    assert descriptor is not None

    x, y = make_classification(
        n_samples=80,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=0,
    )
    x_train, x_test, y_train, _ = train_test_split(x, y, test_size=0.2, random_state=0, stratify=y)
    learner = LogisticRegression(random_state=0, solver="liblinear")
    learner.fit(x_train, y_train)

    explainer = CalibratedExplainer(
        learner,
        x_train,
        y_train,
        mode="classification",
        seed=0,
        factual_plugin="official.explanation.factual.lime",
    )
    x_payload = x_test[:2]

    collection = explainer.explain_factual(x_payload)
    baseline = explainer.explain_factual(x_payload, _use_plugin=False)

    assert collection.explanations
    assert len(collection.explanations) == 2
    assert "lime" in collection.batch_metadata
    assert collection.batch_metadata["lime"] == {"enabled": True}
    assert (
        explainer.plugin_manager.explanation_plugin_identifiers["factual"]
        == "official.explanation.factual.lime"
    )

    weight_vectors_plugin = []
    weight_vectors_baseline = []
    for explanation, baseline_explanation in zip(
        collection.explanations, baseline.explanations, strict=False
    ):
        # Contract: LIME factual plugin should emit ordinary factual explanations with conditions.
        assert explanation.__class__.__name__ == "FactualExplanation"
        rules = explanation.get_rules()

        assert "rule" in rules
        assert rules["rule"], "Expected rule conditions in factual LIME output."
        assert any(
            ("<" in str(rule_text)) or (">" in str(rule_text)) or ("=" in str(rule_text))
            for rule_text in rules["rule"]
        )

        baseline_rules = baseline_explanation.get_rules()
        weight_vectors_plugin.append(np.asarray(rules["weight"], dtype=float))
        weight_vectors_baseline.append(np.asarray(baseline_rules["weight"], dtype=float))

    # Guardrail: if plugin silently falls back to plain factual output, these vectors are identical.
    assert not all(
        np.allclose(plugin_w, base_w, rtol=1e-6, atol=1e-8)
        for plugin_w, base_w in zip(weight_vectors_plugin, weight_vectors_baseline, strict=False)
    ), "LIME plugin output is numerically identical to plain factual fallback."
