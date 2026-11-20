from setuptools import setup, find_packages

setup(
    name="pasa_itsc",
    version="1.0",
    description="SUMO experiments: max-pressure signal control under detector faults",
    packages=find_packages(include=["pasa_itsc", "pasa_itsc.*"]),
    package_data={"pasa_itsc": ["cologne1/*"]},
    python_requires=">=3.10",
    install_requires=["numpy>=1.24", "scipy>=1.10", "pandas>=2.0", "matplotlib>=3.7", "gymnasium>=0.29"],
    extras_require={"rl": ["stable-baselines3>=2.0"]},
    entry_points={"console_scripts": ["pasa_itsc = pasa_itsc.main:main"]},
)
