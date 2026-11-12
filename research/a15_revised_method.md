# A15: revised method (revision D, frozen before any A15 data is collected)

Date: 2026-10-26.
* Supersedes proposed change 2 of `gate_a_plan.md` §5 (revision C) for M2 only.
* §2.2 of `gate_a_plan.md` (revision B) remains the base specification. Everything not mentioned here
  is unchanged.
* No A15 data has been collected (the diagnostic run used 22,000 bytes per source; its results are
  not used).

## 1. Correction of the revision-C statement

Revision C said that training M2 on 250,000 instead of 1,000,000 samples leaves statistical power
"unaffected because power is set by the test size". **That statement is incorrect, and is withdrawn.**

* **What the test size controls.** The standard error of the measured accuracy, about 0.0005 for a
  bit at 10^6 test samples, and hence the smallest accuracy excess that the z-test can resolve. This
  is unchanged.
* **What the training size controls.** How well the model *learns* whatever dependence exists. With
  fewer training samples the fitted coefficients are noisier and weak dependences are fitted less well,
  so the accuracy the model can reach on the test set may be lower. Power against a fixed weak
  structure therefore depends on **both** sizes, and can only decrease when training data is reduced.
* **Consequence.** M2 with 250,000 training samples may be less sensitive than the originally planned
  M2. The loss is **not quantified** and may be zero or substantial, depending on how weak any
  structure is. A negative M2 result is correspondingly weaker evidence than originally planned.
* **Reason for the reduction.** Memory only. 10^6 × 256 features as float64 is about 2 GB, and the
  machine had about 0.8 GB free (7.8 GB total).

## 2. Frozen revised method for M2 (everything else as in §2.2)

* **M2:** logistic regression (L2, C = 1.0, lbfgs, max_iter 200) per output bit b = 0..7, on the 256
  previous bits.
  * Trained on the **first 250,000** training samples (targets 32 … 250,031).
  * Evaluated on the **same full 1,000,000-sample test set** as M1 and M3, predicted in chunks of 100,000.
* M1 and M3 keep the full 1,000,000 training samples.
* **Criteria unchanged:**
  * one-sided z-test against chance;
  * Bonferroni over the 51 ISC tests, z > 3.54;
  * linear-complexity thresholds |L_N − N/2| > 10 and profile maximum > 14;
  * validity rules (a ChaCha20 control trigger makes the method invalid; no positive-control trigger
    makes it insensitive);
  * reporting language.
* **Added descriptive diagnostic (not a criterion; cannot create or remove a finding):** a learning
  curve for M2 at 62,500, 125,000 and 250,000 training samples, for the positive control and for ISC
  lane ℓ1, with test accuracy reported for each.
  * If the positive control's accuracy is still clearly rising at 250,000, the report states that M2
    sensitivity was limited by the training size.
  * This shows whether the reduction plausibly mattered. It does not change any decision rule.

## 3. Stated limitation for the final report

"M2 was trained on 250,000 rather than 1,000,000 samples because of memory limits. This can reduce
its sensitivity to weak dependences; the size of this reduction was not measured, apart from the
descriptive learning curve. M1 and M3 used the full training set."

These rules are frozen as of this file's date. Any later change will be logged with its reason in
`attack_plan.md` §7, and the original rules will be kept.
