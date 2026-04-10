from setuptools import setup, find_packages

setup(
    name="binance-ta-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "loguru",
        "ccxt",
        "numpy",
    ],
    entry_points={
        'console_scripts': [
            'binance-ta-bot=binance_ta_bot.main:main',
        ],
    },
)