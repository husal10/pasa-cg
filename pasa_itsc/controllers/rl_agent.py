"""
pasa_itsc.controllers.rl_agent
==============================
DQN baseline (Stable-Baselines3) trained on healthy detectors. Not used in the
papers; kept for the follow-up work on learning controllers.

    agent = DQNAgent(obs_dim=9, n_phases=2)
    agent.learn(env, total_timesteps=200_000)
    agent.save("models/dqn_clean")
    phase = DQNAgent.load("models/dqn_clean").predict(obs)
"""

from __future__ import annotations

import os
import numpy as np
from pathlib import Path
from typing import TYPE_CHECKING

import gymnasium as gym


# Action-space wrapper: MultiDiscrete -> Discrete (for DQN compatibility)

class _FlattenAction(gym.ActionWrapper):
    """Converts MultiDiscrete([n1, n2, ...]) -> Discrete(n1*n2*...) for DQN.

    DQN only supports scalar (Discrete) action spaces.  The 2x2 grid env
    exposes MultiDiscrete([2, 2, 2, 2]) - one binary phase choice per
    intersection.  This wrapper encodes/decodes as a mixed-radix integer so
    DQN can select a *joint* action (16 possibilities) without any env change.

    Encoding (little-endian mixed-radix):
        flat_action = a[0] + n0*(a[1] + n1*(a[2] + n2*a[3]))
    Decoding is the reverse modular unwrapping.
    """

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        assert isinstance(env.action_space, gym.spaces.MultiDiscrete), (
            "_FlattenAction requires a MultiDiscrete action space"
        )
        self._nvec = env.action_space.nvec.copy()
        self.action_space = gym.spaces.Discrete(int(np.prod(self._nvec)))

    def action(self, act: int) -> np.ndarray:
        """Decode flat integer -> per-intersection phase array."""
        out: list[int] = []
        for n in self._nvec:
            out.append(int(act % n))
            act //= n
        return np.array(out, dtype=np.int64)


if TYPE_CHECKING:
    pass


# Hyperparameters

DQN_HPARAMS = dict(
    learning_rate          = 1e-3,
    gamma                  = 0.99,
    buffer_size            = 100_000,
    batch_size             = 64,
    learning_starts        = 1_000,
    train_freq             = 4,
    target_update_interval = 500,
    exploration_fraction   = 0.2,
    exploration_final_eps  = 0.05,
    policy_kwargs          = dict(net_arch=[64, 64]),
    verbose                = 0,
)

TRAIN_STEPS = 200_000


# DQNAgent

class DQNAgent:
    """Thin wrapper around SB3 DQN.

    Parameters
    ----------
    obs_dim   : int   Observation dimensionality (default 9).
    n_phases  : int   Number of signal phases (default 2).
    seed      : int   RNG seed.
    """

    def __init__(
        self,
        obs_dim:  int = 9,
        n_phases: int = 2,
        seed:     int = 42,
    ):
        self.obs_dim  = obs_dim
        self.n_phases = n_phases
        self.seed     = seed
        self._model   = None   # lazy: set by learn() or load()

    # training

    def learn(
        self,
        env,
        total_timesteps: int = TRAIN_STEPS,
        reset_num_timesteps: bool = True,
        progress_bar: bool = True,
    ) -> "DQNAgent":
        """Train DQN on *env* (must be a Gymnasium-compatible environment).

        Parameters
        ----------
        env : gymnasium.Env
            Training environment (should use clean/fault-free sensing).
        total_timesteps : int
            Number of environment steps for training.
        reset_num_timesteps : bool
            If False, continue from a previously started training run.
        progress_bar : bool
            Show tqdm progress bar.

        Returns
        -------
        self
        """
        try:
            from stable_baselines3 import DQN
        except ImportError as e:
            raise ImportError(
                "stable-baselines3 is required for RL training. "
                "Install with: pip install stable-baselines3"
            ) from e

        if self._model is None:
            # DQN requires Discrete action space; wrap MultiDiscrete envs.
            if isinstance(env.action_space, gym.spaces.MultiDiscrete):
                env = _FlattenAction(env)
            self._model = DQN(
                "MlpPolicy",
                env,
                seed=self.seed,
                **DQN_HPARAMS,
            )

        self._model.learn(
            total_timesteps=total_timesteps,
            reset_num_timesteps=reset_num_timesteps,
            progress_bar=progress_bar,
        )
        return self

    # inference

    def predict(
        self,
        obs: np.ndarray,
        deterministic: bool = True,
        n_intersections: int | None = None,
    ) -> np.ndarray:
        """Select joint action for *obs*.

        When the model was trained with the _FlattenAction wrapper its output
        is a flat integer encoding all per-intersection phases.  This method
        decodes it back to a ``(n_intersections,)`` integer array so callers
        get one phase index per intersection.

        Parameters
        ----------
        obs : np.ndarray
            Normalised observation vector (shape = n_intersections * obs_dim).
        deterministic : bool
            Use greedy policy (True) or eps-greedy (False).
        n_intersections : int | None
            Number of intersections (used for decoding).  Inferred from
            ``obs`` shape when *None* (assumes obs_dim = 9).

        Returns
        -------
        np.ndarray, shape (n_intersections,)
            Per-intersection phase indices (0 or 1 for a 2-phase controller).
        """
        if self._model is None:
            raise RuntimeError("Model not trained or loaded. Call learn() or load() first.")
        flat_action, _ = self._model.predict(obs, deterministic=deterministic)
        flat_action = int(flat_action)

        # Decode mixed-radix flat integer -> per-intersection phases.
        # Assumes binary (n_phases=2) per intersection.
        if n_intersections is None:
            n_intersections = max(1, len(obs) // self.obs_dim)
        phases: list[int] = []
        for _ in range(n_intersections):
            phases.append(flat_action % self.n_phases)
            flat_action //= self.n_phases
        return np.array(phases, dtype=np.int64)

    # save / load

    def save(self, path: str | Path) -> None:
        """Save trained model to *path* (SB3 format, .zip appended)."""
        if self._model is None:
            raise RuntimeError("No model to save.")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._model.save(str(path))
        print(f"[DQNAgent] Model saved -> {path}.zip")

    @classmethod
    def load(
        cls,
        path: str | Path,
        obs_dim:  int = 9,
        n_phases: int = 2,
        seed:     int = 42,
    ) -> "DQNAgent":
        """Load a previously saved DQN model.

        Parameters
        ----------
        path : str | Path
            Path to model file (with or without .zip extension).

        Returns
        -------
        DQNAgent
        """
        try:
            from stable_baselines3 import DQN
        except ImportError as e:
            raise ImportError(
                "stable-baselines3 is required. "
                "Install with: pip install stable-baselines3"
            ) from e

        agent = cls(obs_dim=obs_dim, n_phases=n_phases, seed=seed)
        agent._model = DQN.load(str(path))
        print(f"[DQNAgent] Model loaded <- {path}")
        return agent

    # helpers

    def build_observation(
        self,
        pasa_aggregates: np.ndarray,
        phase: int,
        q_max: float = 20.0,
    ) -> np.ndarray:
        """Build the 9-dim observation vector used during training.

        [agg_0/Q_max, ..., agg_7/Q_max, phase]

        Parameters
        ----------
        pasa_aggregates : np.ndarray, shape (8,)
            PASA-mean aggregated queues (NOT PASA+; RL sees mean-only aggs).
        phase : int
            Current phase index (0 or 1).
        q_max : float
            Saturation capacity for normalisation.
        """
        norm_agg = np.clip(pasa_aggregates, 0.0, q_max) / q_max
        return np.append(norm_agg, float(phase))

    def __repr__(self) -> str:
        trained = self._model is not None
        return f"DQNAgent(obs_dim={self.obs_dim}, n_phases={self.n_phases}, trained={trained})"
