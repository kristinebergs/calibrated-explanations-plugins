"""LIME pipeline for factual LIME plugin runtime."""

from __future__ import annotations

from time import time
from typing import Any

import numpy as np

from calibrated_explanations.explanations import CalibratedExplanations
from calibrated_explanations.utils import assert_threshold, safe_isinstance
from calibrated_explanations.utils.exceptions import (
    ConfigurationError,
    DataShapeError,
    ValidationError,
)

from .lime_helper import LimeHelper


class LimePipeline:
    """Pipeline for generating LIME-based factual explanations."""

    def __init__(self, explainer: Any) -> None:
        self.explainer = explainer
        self._lime_helper: LimeHelper | None = None

    def _preload_lime(self, x_cal: Any = None) -> tuple[Any, Any]:
        if self._lime_helper is None:
            self._lime_helper = LimeHelper(self.explainer)
        return self._lime_helper.preload(x_cal=x_cal)

    def explain(
        self,
        x_test: Any,
        threshold: float | None = None,
        low_high_percentiles: tuple[float, float] = (5, 95),
        bins: Any = None,
    ) -> CalibratedExplanations:
        def _truthy_flag(value: Any) -> bool:
            return bool(value() if callable(value) else value)

        lime_explainer, _ = self._preload_lime()

        total_time = time()
        instance_time = []

        if safe_isinstance(x_test, "pandas.core.frame.DataFrame"):
            x_test = x_test.values
        if len(x_test.shape) == 1:
            x_test = x_test.reshape(1, -1)

        if x_test.shape[1] != self.explainer.num_features:
            raise DataShapeError(
                "The number of features in the test data must be the same as in the "
                "calibration data."
            )

        if _truthy_flag(getattr(self.explainer, "is_mondrian", False)):
            if bins is None:
                raise ValidationError(
                    "The bins parameter must be specified for Mondrian explanations."
                )
            if len(bins) != len(x_test):
                raise DataShapeError(
                    "The length of the bins parameter must be the same as the "
                    "number of instances in x."
                )

        explanation = CalibratedExplanations(
            self.explainer,
            x_test,
            threshold,
            bins,
            condition_source=getattr(self.explainer, "condition_source", "prediction"),
        )

        if threshold is not None:
            if "regression" not in self.explainer.mode:
                raise ValidationError(
                    "The threshold parameter is only supported for mode='regression'."
                )
            assert_threshold(threshold, x_test)
        elif "regression" in self.explainer.mode:
            explanation.low_high_percentiles = low_high_percentiles

        feature_weights = {"predict": [], "low": [], "high": []}
        feature_predict = {"predict": [], "low": [], "high": []}
        prediction = {"predict": [], "low": [], "high": [], "classes": []}

        instance_weights = [
            {
                "predict": np.zeros(self.explainer.num_features),
                "low": np.zeros(self.explainer.num_features),
                "high": np.zeros(self.explainer.num_features),
            }
            for _ in range(len(x_test))
        ]
        instance_predict = [
            {
                "predict": np.zeros(self.explainer.num_features),
                "low": np.zeros(self.explainer.num_features),
                "high": np.zeros(self.explainer.num_features),
            }
            for _ in range(len(x_test))
        ]

        predict, low, high, predicted_class = self.explainer.prediction_orchestrator.predict_internal(
            x_test,
            threshold=threshold,
            low_high_percentiles=low_high_percentiles,
            bins=bins,
        )
        prediction["predict"] = predict
        prediction["low"] = low
        prediction["high"] = high
        if _truthy_flag(getattr(self.explainer, "is_multiclass", False)):
            prediction["classes"] = predicted_class
        else:
            prediction["classes"] = np.ones(x_test.shape[0])

        if lime_explainer is None:
            raise ConfigurationError(
                "LIME integration requested but the optional dependency is missing."
            )

        def low_proba(x_data: Any) -> Any:
            _, low_vals, _, _ = self.explainer.prediction_orchestrator.predict_internal(
                x_data,
                threshold=threshold,
                low_high_percentiles=low_high_percentiles,
                bins=bins,
            )
            return np.asarray([[1 - value, value] for value in low_vals])

        def high_proba(x_data: Any) -> Any:
            _, _, high_vals, _ = self.explainer.prediction_orchestrator.predict_internal(
                x_data,
                threshold=threshold,
                low_high_percentiles=low_high_percentiles,
                bins=bins,
            )
            return np.asarray([[1 - value, value] for value in high_vals])

        res_struct = {
            "low": {"explanation": [], "abs_rank": [], "values": []},
            "high": {"explanation": [], "abs_rank": [], "values": []},
        }

        for idx, instance in enumerate(x_test):
            instance_timer = time()
            low_explanation = lime_explainer.explain_instance(
                instance, predict_fn=low_proba, num_features=len(instance)
            )
            high_explanation = lime_explainer.explain_instance(
                instance, predict_fn=high_proba, num_features=len(instance)
            )

            res_struct["low"]["explanation"].append(low_explanation)
            res_struct["high"]["explanation"].append(high_explanation)
            res_struct["low"]["abs_rank"], res_struct["high"]["abs_rank"] = (
                np.zeros(len(instance)),
                np.zeros(len(instance)),
            )
            res_struct["low"]["values"], res_struct["high"]["values"] = (
                np.zeros(len(instance)),
                np.zeros(len(instance)),
            )

            for j, feat_info in enumerate(low_explanation.local_exp[1]):
                res_struct["low"]["abs_rank"][feat_info[0]] = low_explanation.local_exp[1][j][0]
                res_struct["low"]["values"][feat_info[0]] = feat_info[1]

            for j, feat_info in enumerate(high_explanation.local_exp[1]):
                res_struct["high"]["abs_rank"][feat_info[0]] = high_explanation.local_exp[1][j][0]
                res_struct["high"]["values"][feat_info[0]] = feat_info[1]

            for feat_idx in range(self.explainer.num_features):
                tmp_low = res_struct["low"]["values"][feat_idx]
                tmp_high = res_struct["high"]["values"][feat_idx]
                instance_weights[idx]["low"][feat_idx] = np.min([tmp_low, tmp_high])
                instance_weights[idx]["high"][feat_idx] = np.max([tmp_low, tmp_high])
                instance_weights[idx]["predict"][feat_idx] = (
                    instance_weights[idx]["high"][feat_idx]
                    / (
                        1
                        - instance_weights[idx]["low"][feat_idx]
                        + instance_weights[idx]["high"][feat_idx]
                    )
                )

                low_predict_proba = getattr(low_explanation, "predict_proba", None)
                if low_predict_proba is None:
                    low_point = prediction["low"][idx]
                else:
                    low_point = low_predict_proba[-1]

                high_predict_proba = getattr(high_explanation, "predict_proba", None)
                if high_predict_proba is None:
                    high_point = prediction["high"][idx]
                else:
                    high_point = high_predict_proba[-1]

                instance_predict[idx]["low"][feat_idx] = (
                    low_point - instance_weights[idx]["low"][feat_idx]
                )
                instance_predict[idx]["high"][feat_idx] = (
                    high_point - instance_weights[idx]["high"][feat_idx]
                )
                instance_predict[idx]["predict"][feat_idx] = (
                    instance_predict[idx]["high"][feat_idx]
                    / (
                        1
                        - instance_predict[idx]["low"][feat_idx]
                        + instance_predict[idx]["high"][feat_idx]
                    )
                )

            feature_weights["predict"].append(instance_weights[idx]["predict"])
            feature_weights["low"].append(instance_weights[idx]["low"])
            feature_weights["high"].append(instance_weights[idx]["high"])

            feature_predict["predict"].append(instance_predict[idx]["predict"])
            feature_predict["low"].append(instance_predict[idx]["low"])
            feature_predict["high"].append(instance_predict[idx]["high"])
            instance_time.append(time() - instance_timer)

        explanation.finalize_fast(
            feature_weights,
            feature_predict,
            prediction,
            instance_time=instance_time,
            total_time=total_time,
        )

        self.explainer.latest_explanation = explanation
        return explanation
