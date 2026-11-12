"""Strict opt-in systemd entrypoint for the original Chema Owner workspace.

Operator-only alternative to the previous private_broker_worker.py.
Never select this from browser or from an unauthenticated HTTP parameter.
The existing root broker must choose/pin the script and its arguments.
"""
from urano.native_owner_systemd_entry import main

if __name__ == "__main__":
    main()
