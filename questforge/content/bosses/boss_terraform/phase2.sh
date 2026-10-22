#!/usr/bin/env bash
# Phase 2 du boss : mêmes exigences que le TP tf2 (analyse du dossier de travail, sans réseau).
exec python3 -I "$(dirname "${BASH_SOURCE[0]}")/../../modules/terraform/lessons/_hcl_check.py" tf2
