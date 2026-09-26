"""Regular package, not a mere namespace.

The whole-tree bizlathe drill imports ``scripts.verify_sandbox`` for the
armada-battery verifier test while test modules collected earlier have put
their own ``scripts/`` packages on sys.path (workspaces/robin/games at the
time of writing). A regular package wins over a namespace portion found
earlier in sys.path, so this file is what keeps this venture's ``scripts``
the one that resolves.
"""
