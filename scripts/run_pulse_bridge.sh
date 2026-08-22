#!/usr/bin/env bash
# Build and run the engineering-only Pulse SDK bridge probe.
# This script emits simulator telemetry and does not provide clinical advice.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PULSE_ROOT="${PULSE_ROOT:-/home/ubuntu/pulse-build/install}"
BUILD_DIR="${ROOT_DIR}/.build/pulse_bridge"
OUTPUT_DIR="${ROOT_DIR}/artifacts/representative-small-results"

if [[ ! -f "${PULSE_ROOT}/lib/cmake/pulse/PulseConfig.cmake" ]]; then
  echo "Pulse SDK was not found at PULSE_ROOT=${PULSE_ROOT}" >&2
  echo "Build the pinned Pulse revision first, then set PULSE_ROOT to its install directory." >&2
  exit 2
fi
if [[ ! -f "${PULSE_ROOT}/bin/states/StandardMale@0s.json" ]]; then
  echo "StandardMale@0s.json is missing. Run Pulse gendata and genStates first." >&2
  exit 3
fi

cmake -S "${ROOT_DIR}/src/physiology/pulse_bridge" \
  -B "${BUILD_DIR}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="${PULSE_ROOT}"
cmake --build "${BUILD_DIR}" --parallel 1

mkdir -p "${OUTPUT_DIR}"
(
  cd "${PULSE_ROOT}/bin"
  "${BUILD_DIR}/nexora_pulse_bridge" \
    "./states/StandardMale@0s.json" \
    "${OUTPUT_DIR}/pulse_sdk_bridge.json" \
    "${BUILD_DIR}/pulse_state.json"
)
sha256sum "${OUTPUT_DIR}/pulse_sdk_bridge.json"
