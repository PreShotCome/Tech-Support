"""Theo's local ML package.

Small PyTorch model that scores tickers on the probability of beating
SPY over the next 5 trading days. Inputs are 6 features computed via
yfinance + a placeholder congress signal. See theo_net.py for the
architecture, features.py for the input pipeline, train.py for
training, predict.py for inference.
"""
