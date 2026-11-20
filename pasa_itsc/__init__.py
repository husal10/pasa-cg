"""
pasa_itsc - simulation code for max-pressure signal control under detector faults
===================================================================================
SUMO experiments behind two papers:
  * the ITSC 2027 paper on which detector faults harm max-pressure, opposing-arm
    aggregation and the cost of the guards;
  * the T-ITS paper on PASA-CG, a consistency-gated filter for detector readings.

Sub-packages
------------
network      2x2 grid builder (build_network) and Cologne1 setup (cologne_network)
sensors      fault injection (fault_modes), opposing-arm aggregation (pasa),
             PASA-CG (pasa_cg), input cleaners for learning controllers (obs_filters)
controllers  max-pressure (max_pressure); DQN baseline (rl_agent, not used in the papers)
env          SUMO environment that runs one episode for one controller
evaluation   sweep runner (experiment), per-episode metrics (metrics), checks (verify)

Command line: python -m pasa_itsc.main --help
"""

__version__ = "0.1.0"
__author__  = "Hussaini Aliyu Idris, Giacomo Cabri"
