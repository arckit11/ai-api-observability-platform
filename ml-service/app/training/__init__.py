"""Training orchestration for the ML modules.

Each module owns a ``train(...)`` function under ``app.modules.<name>.train``
that this package composes into a single CLI runnable via
``python -m app.training.cli``.
"""
