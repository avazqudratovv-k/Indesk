"""The sandbox service: runs model-written pandas code in a fresh subprocess per job.

The container (compose.yaml: no network, read-only root, dropped capabilities, memory and process
limits) is the security boundary. Everything in this package is defense in depth on top of it. The
container shares the kernel of the host, so a kernel bug could still cross the boundary.
"""
