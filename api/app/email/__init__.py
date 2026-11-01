"""Sending email (password reset, sign-up verification). The API only enqueues a job (queue.py);
the worker is the one service with a route to the internet and the only one that holds the key."""
