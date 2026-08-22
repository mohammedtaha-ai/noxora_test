#!/usr/bin/env bash
# Build the PulseAdapter server and run its S0 integration tests.
# This verifies engineering simulation infrastructure only, not clinical advice.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PULSE_ROOT="${PULSE_ROOT:?Set PULSE_ROOT to the pinned Pulse installation directory}"
BUILD_DIR="${ROOT_DIR}/.build/pulse_bridge"
SERVER_PATH="${BUILD_DIR}/nexora_pulse_adapter_server"

if [[ ! -f "${PULSE_ROOT}/lib/cmake/pulse/PulseConfig.cmake" ]]; then
  echo "Pulse SDK CMake package is missing under PULSE_ROOT=${PULSE_ROOT}" >&2
  exit 2
fi
if [[ ! -f "${PULSE_ROOT}/bin/states/StandardMale@0s.json" ]]; then
  echo "StandardMale@0s.json is missing; run the pinned Pulse gendata/genStates flow first." >&2
  exit 3
fi

cmake -S "${ROOT_DIR}/src/physiology/pulse_bridge" \
  -B "${BUILD_DIR}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="${PULSE_ROOT}"
cmake --build "${BUILD_DIR}" --target nexora_pulse_adapter_server --parallel 1

cd "${ROOT_DIR}"
PULSE_ADAPTER_SERVER="${SERVER_PATH}" \
PULSE_ROOT="${PULSE_ROOT}" \
PYTHONPATH=src \
python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_pulse_adapter_integration.py' -v
