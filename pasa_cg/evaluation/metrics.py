"""
pasa_cg.evaluation.metrics
============================
Per-episode result record (EpisodeResult) and summaries over seeds
(mean, standard deviation and t-based 95% confidence interval).
halving_ratio is an earlier summary statistic, kept for the result-file format.
"""

from __future__ import annotations

import numpy as np
from scipy import stats
from dataclasses import dataclass, field
from typing import Sequence


# Result container

@dataclass
class EpisodeResult:
    """Metrics collected from one episode.

    Network-wide metrics
    --------------------
    mean_queue    : mean halting vehicles / lane, averaged over all lanes and steps
    throughput    : arrived vehicles x 3600 / SIM_DURATION  (veh/h)
    halving_ratio : (ctrl_queue - std_mp_healthy) / (Q_max/2); <1.0 satisfies bound
    jain_fairness : Jain's index J = (sum q_i)^2 / (n*sum q_i^2) over 4 junction means [0,1]

    Per-junction metrics at junction 0 (the fault injection site)
    -------------------------------------------------------------
    j0_s_queue    : time-averaged mean queue on the S-approach lanes (indices 3-4),
                    i.e. the two lanes that receive sensor faults - directly measures
                    underservicing at the targeted link.
    j0_jain       : Jain's index computed over all 12 individual lane queues at
                    junction 0 (n=12), capturing within-junction equity.  Compare with
                    network-wide jain_fairness (n=4 junction means) to isolate
                    the fault site's equity impact.
    j0_throughput : vehicles departed from junction 0's downstream links per hour
                    (proxy: arrived count attributed to junction 0 zone is unavailable
                    from TraCI - this field is reserved for future use and defaults NaN).

    Note on multiplicity correction (W4 - Holm-Bonferroni)
    -------------------------------------------------------
    Primary hypothesis: PASA+-MP vs Std-MP under MX fault at medium demand, junction 0.
    All other (controller x fault_mode) cells are secondary comparisons.
    Apply Holm-Bonferroni correction across the K primary p-values before reporting;
    see ``apply_holm_bonferroni()`` in this module.
    """
    controller:     str
    fault_mode:     str
    seed:           int
    mean_queue:     float     # mean halting vehicles / lane (averaged over steps)
    throughput:     float     # vehicles / hour (arrived vehicles x 3600 / SIM_DURATION)
    halving_ratio:  float = field(default=float("nan"))   # vs Std-MP baseline
    jain_fairness:  float = field(default=float("nan"))   # Jain's index across 4 junction means [0,1]
    # junction-0 metrics (fault injection site)
    j0_s_queue:    float = field(default=float("nan"))   # S-approach mean queue (lanes 3-4)
    j0_jain:       float = field(default=float("nan"))   # per-junction Jain (n=12 lanes)
    j0_throughput: float = field(default=float("nan"))   # reserved; NaN until TraCI support
    j0_queue:      float = field(default=float("nan"))   # mean true queue, all lanes of fault junction
    # trip-based metrics (SUMO tripinfo, unfinished vehicles included)
    travel_time:   float = field(default=float("nan"))   # mean trip duration (s)
    waiting_time:  float = field(default=float("nan"))   # mean time stopped (s)
    time_loss:     float = field(default=float("nan"))   # mean delay vs free-flow (s)
    depart_delay:  float = field(default=float("nan"))   # mean insertion delay (s)
    n_trips:       int   = 0                              # vehicles in tripinfo
    n_unfinished:  int   = 0                              # still in network at episode end
    # experiment bookkeeping
    fault_approach: str  = ""                             # primary faulted approach this episode
    forced_frac:   float = field(default=float("nan"))   # share of junction-decisions forced by max-red / recall
    # fairness
    j0_approach_jain: float = field(default=float("nan"))  # Jain over the 4 approach mean queues, fault junction
    delay_jain:    float = field(default=float("nan"))   # Jain over per-vehicle time loss (1 = equal delay)
    waiting_p95:   float = field(default=float("nan"))   # 95th percentile vehicle waiting time (s)
    delay_by_side: dict  = field(default_factory=dict)   # mean time loss by entry side {N,S,E,W} (s)
    insertion_backlog: float = field(default=float("nan"))  # vehicles still waiting to enter at episode end
    cg_ttd_s:      float = field(default=float("nan"))   # PASA-CG: mean time from fault onset to first flag (detected lanes)
    cg_detected_frac: float = field(default=float("nan"))  # PASA-CG: share of faulty lanes flagged at least once
    # sustainability (stops always; emissions only with --emissions)
    stops_per_trip: float = field(default=float("nan"))  # mean number of stops (tripinfo waitingCount)
    co2_g:          float = field(default=float("nan"))  # mean CO2 per trip (g)
    fuel_g:         float = field(default=float("nan"))  # mean fuel per trip (g)
    nox_g:          float = field(default=float("nan"))  # mean NOx per trip (g)
    pmx_mg:         float = field(default=float("nan"))  # mean PMx per trip (mg)
    co2_total_kg:   float = field(default=float("nan"))  # network CO2 of measured trips (kg)
    fuel_total_kg:  float = field(default=float("nan"))  # network fuel of measured trips (kg)
    n_emission_trips: float = field(default=float("nan"))
    # PASA-CG detection (pasa_cg_mp only; lane-decisions after warm-up)
    cg_tpr:        float = field(default=float("nan"))   # flagged share of faulted lane-decisions
    cg_fpr:        float = field(default=float("nan"))   # flagged share of healthy lane-decisions


@dataclass
class SummaryStats:
    """Aggregated stats (across N_seeds) for one (controller, fault_mode) cell."""
    controller:    str
    fault_mode:    str
    mean:          float
    std:           float
    ci_low:        float
    ci_high:       float
    n_seeds:       int


# Core metric functions

def compute_metrics(
    episode_queues: Sequence[float],
    throughputs:    Sequence[float] | None = None,
    confidence:     float = 0.95,
) -> dict:
    """Compute mean, std, and 95 % CI for a set of episode metrics.

    Parameters
    ----------
    episode_queues : Sequence[float]
        Per-episode mean queue lengths (one per seed run).
    throughputs : Sequence[float] | None
        Per-episode throughputs in veh/h.  If None, not computed.
    confidence : float
        Confidence level (default 0.95 -> 95 % CI).

    Returns
    -------
    dict with keys:
        queue_mean, queue_std, queue_ci_low, queue_ci_high,
        [throughput_mean, throughput_std, throughput_ci_low, throughput_ci_high]
    """
    q = np.asarray(episode_queues, dtype=float)
    n = len(q)
    result: dict = {}

    if n == 1:
        result.update(
            queue_mean=float(q[0]),
            queue_std=float("nan"),
            queue_ci_low=float("nan"),
            queue_ci_high=float("nan"),
        )
    else:
        ci = stats.t.interval(confidence, df=n - 1, loc=np.mean(q), scale=stats.sem(q))
        result.update(
            queue_mean=float(np.mean(q)),
            queue_std=float(np.std(q, ddof=1)),
            queue_ci_low=float(ci[0]),
            queue_ci_high=float(ci[1]),
        )

    if throughputs is not None:
        tp = np.asarray(throughputs, dtype=float)
        if len(tp) > 1:
            ci_tp = stats.t.interval(confidence, df=len(tp)-1,
                                     loc=np.mean(tp), scale=stats.sem(tp))
            result.update(
                throughput_mean=float(np.mean(tp)),
                throughput_std=float(np.std(tp, ddof=1)),
                throughput_ci_low=float(ci_tp[0]),
                throughput_ci_high=float(ci_tp[1]),
            )
        else:
            result.update(
                throughput_mean=float(tp[0]),
                throughput_std=float("nan"),
                throughput_ci_low=float("nan"),
                throughput_ci_high=float("nan"),
            )

    return result


def aggregate_results(
    episode_results: list[EpisodeResult],
    confidence: float = 0.95,
) -> dict[tuple[str, str], SummaryStats]:
    """Aggregate EpisodeResult list into a (controller, fault_mode) -> SummaryStats map.

    Parameters
    ----------
    episode_results : list[EpisodeResult]
        Flat list of per-episode, per-seed results.
    confidence : float
        Confidence level for interval computation.

    Returns
    -------
    dict mapping (controller, fault_mode) tuples to SummaryStats.
    """
    from collections import defaultdict
    buckets: dict[tuple, list[float]] = defaultdict(list)

    for r in episode_results:
        key = (r.controller, r.fault_mode)
        buckets[key].append(r.mean_queue)

    out: dict[tuple[str, str], SummaryStats] = {}
    for (ctrl, fault), values in buckets.items():
        v = np.array(values, dtype=float)
        n = len(v)
        if n > 1:
            ci = stats.t.interval(confidence, df=n-1, loc=np.mean(v), scale=stats.sem(v))
            ci_low, ci_high = float(ci[0]), float(ci[1])
        else:
            ci_low = ci_high = float("nan")

        out[(ctrl, fault)] = SummaryStats(
            controller=ctrl,
            fault_mode=fault,
            mean=float(np.mean(v)),
            std=float(np.std(v, ddof=1)) if n > 1 else float("nan"),
            ci_low=ci_low,
            ci_high=ci_high,
            n_seeds=n,
        )

    return out


def halving_ratio(
    std_mp_queue:     float | np.ndarray,
    controller_queue: float | np.ndarray,
    q_max:            float = 20.0,
) -> float | np.ndarray:
    """Share of the fault-induced degradation that remains, relative to Q_max / 2.


    Returns
    -------
    float
        (controller_queue - std_mp_healthy) / (Q_max / 2)
        Values < 1.0 satisfy the halving bound.
    """
    diff = np.asarray(controller_queue) - np.asarray(std_mp_queue)
    return diff / (q_max / 2.0)


def apply_holm_bonferroni(
    p_values: Sequence[float],
) -> list[bool]:
    """Holm-Bonferroni correction for a family of hypothesis tests.

    Addresses W4 (multiplicity): when K p-values are compared simultaneously
    (one per controller x fault combination) the familywise error rate is
    inflated.  Holm's step-down procedure controls FWER at alpha=0.05 without
    the conservatism of Bonferroni.

    Pre-specified primary family (pre-register before running experiments):
        PASA+-MP vs Std-MP on {NONE, HZ, SL, GN, ID, DR, MX} at medium demand,
        analysed at junction 0 metrics (j0_s_queue and j0_jain).
    Secondary comparisons (all other cells) must survive a separate correction.

    Parameters
    ----------
    p_values : Sequence[float]
        Ordered p-values for K hypotheses.

    Returns
    -------
    list[bool]
        ``rejected[i]`` is True when H_i is rejected at FWER <= 0.05.

    Example
    -------
    >>> rejected = apply_holm_bonferroni([0.001, 0.02, 0.06])
    >>> rejected   # [True, True, False]
    """
    p = np.asarray(p_values, dtype=float)
    k = len(p)
    order = np.argsort(p)
    rejected = np.zeros(k, dtype=bool)
    for rank, idx in enumerate(order):
        threshold = 0.05 / (k - rank)
        if p[idx] <= threshold:
            rejected[idx] = True
        else:
            break   # step-down: once we fail to reject, all remaining are retained
    return rejected.tolist()


def format_results_table(
    summary: dict[tuple[str, str], SummaryStats],
    fault_modes: list[str],
    controllers: list[str],
    metric: str = "Mean Queue (veh/lane)",
) -> str:
    """Return a plain-text ASCII table of results with 95 % CI.

    Suitable for pasting into LaTeX as a starting point.
    """
    col_w = 24
    header = f"{'Controller':<20}" + "".join(f"{fm:>{col_w}}" for fm in fault_modes)
    sep    = "-" * len(header)
    lines  = [metric, sep, header, sep]

    for ctrl in controllers:
        row = f"{ctrl:<20}"
        for fm in fault_modes:
            key = (ctrl, fm)
            if key in summary:
                s = summary[key]
                cell = f"{s.mean:.2f} [{s.ci_low:.2f},{s.ci_high:.2f}]"
            else:
                cell = "-"
            row += f"{cell:>{col_w}}"
        lines.append(row)

    lines.append(sep)
    return "\n".join(lines)
