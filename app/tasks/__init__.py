"""Standalone Taskiq tasks (cron-style scheduled jobs).

Each module here exposes one or more ``@broker.task`` callables
that are intended to be invoked periodically by an external
scheduler. The Backend itself does not run a scheduler loop in
``main.py``; instead the production deploy uses a sidecar (cron,
systemd timer, or ``taskiq scheduler``) that enqueues these
tasks at the configured cadence.

For dev there is a ``Makefile`` target that runs them in a small
asyncio loop locally.
"""
