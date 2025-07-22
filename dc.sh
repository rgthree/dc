#!/bin/bash

# Starts our dc.py file in the venv
thisfile="$(realpath $(dirname "$0")/dc)"
$(dirname $thisfile)/.venv/bin/python3 $(dirname $thisfile)/dc.py "$@"
