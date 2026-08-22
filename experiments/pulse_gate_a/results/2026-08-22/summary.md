# Pulse Gate A — CSV Evidence Summary

> **Scope:** This is an engineering record of deterministic Pulse telemetry. It is not medical advice, a treatment protocol, a diagnosis, or a validated clinical model.

All rows were generated locally from the pinned Pulse `stable` source build and are preserved with SHA-256 checksums in `SHA256SUMS.txt`.

## Internal Spleen

Internal splenic hemorrhage, controlled stop, then observation.

The CSV contains **1661** sampled rows from 0s to 1660s. Positive total hemorrhage telemetry begins at 31.0s and ends at 1260.0s; the maximum recorded rate is 1.0 mL/s.

| Requested time (s) | Observed time (s) | HR (1/min) | MAP (mmHg) | Blood volume (mL) | Hemoglobin (g) | Hemorrhage rate (mL/s) | Total hemorrhage (mL) | SpO₂ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0.0000 | 72.0000 | 95.3230 | 5488.9390 | 821.0000 | 0.0000 | 0.0000 | 0.9741 |
| 30 | 30.0000 | 72.0250 | 95.3220 | 5490.1320 | 821.0000 | 0.0000 | 0.0000 | 0.9741 |
| 31 | 31.0000 | 72.0240 | 95.5430 | 5489.1700 | 821.0000 | 1.0000 | 0.9800 | 0.9740 |
| 1260 | 1260.0000 | 101.0020 | 93.5640 | 4327.1390 | 638.0000 | 1.0000 | 1229.9800 | 0.9672 |
| 1261 | 1261.0000 | 101.0480 | 93.5480 | 4327.2090 | 638.0000 | 0.0000 | 1229.9800 | 0.9673 |
| 1660 | 1660.0000 | 99.7080 | 93.7290 | 4353.4820 | 638.0000 | 0.0000 | 1229.9800 | 0.9675 |

## Saline

Dual hemorrhage, controlled stop, then Saline compound infusion.

The CSV contains **1141** sampled rows from 0s to 1140s. Positive total hemorrhage telemetry begins at 31.0s and ends at 620.0s; the maximum recorded rate is 2.333 mL/s.

| Requested time (s) | Observed time (s) | HR (1/min) | MAP (mmHg) | Blood volume (mL) | Hemoglobin (g) | Hemorrhage rate (mL/s) | Total hemorrhage (mL) | SpO₂ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0.0000 | 72.0000 | 95.3230 | 5488.9390 | 821.4640 | 0.0000 | 0.0000 | 0.9741 |
| 30 | 30.0000 | 72.0250 | 95.3220 | 5490.1320 | 821.4640 | 0.0000 | 0.0000 | 0.9741 |
| 620 | 620.0000 | 112.3070 | 88.3580 | 4144.9660 | 615.8950 | 2.3330 | 1376.6200 | 0.9646 |
| 621 | 621.0000 | 112.4020 | 88.2360 | 4145.0480 | 615.8950 | 0.0000 | 1376.6200 | 0.9647 |
| 740 | 740.0000 | 112.8910 | 89.0310 | 4155.1460 | 615.8950 | 0.0000 | 1376.6200 | 0.9627 |
| 1040 | 1040.0000 | 93.2240 | 94.2990 | 4676.3260 | 615.8930 | 0.0000 | 1376.6200 | 0.9685 |
| 1140 | 1140.0000 | 93.4470 | 94.1080 | 4682.5540 | 615.8930 | 0.0000 | 1376.6200 | 0.9694 |

## Packed Rbc

Dual hemorrhage, controlled stop, then PackedRBC compound infusion.

The CSV contains **2881** sampled rows from 0s to 2880s. Positive total hemorrhage telemetry begins at 31.0s and ends at 430.0s; the maximum recorded rate is 4.167 mL/s.

| Requested time (s) | Observed time (s) | HR (1/min) | MAP (mmHg) | Blood volume (mL) | Hemoglobin (g) | Hemorrhage rate (mL/s) | Total hemorrhage (mL) | SpO₂ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0.0000 | 72.0000 | 95.3230 | 5488.9390 | 821.4640 | 0.0000 | 0.0000 | 0.9741 |
| 30 | 30.0000 | 72.0250 | 95.3220 | 5490.1320 | 821.4640 | 0.0000 | 0.0000 | 0.9741 |
| 430 | 430.0000 | 119.1780 | 73.1160 | 3848.5130 | 572.4360 | 4.1670 | 1666.5830 | 0.9604 |
| 431 | 431.0000 | 119.2690 | 72.8950 | 3848.6400 | 572.4360 | 0.0000 | 1666.5830 | 0.9604 |
| 550 | 550.0000 | 121.4480 | 75.9430 | 3864.2550 | 572.4350 | 0.0000 | 1666.5830 | 0.9540 |
| 2880 | 2880.0000 | 94.9470 | 85.7850 | 4286.9810 | 615.1100 | 0.0000 | 1666.5830 | 0.9647 |

## Snapshot Continuity

A state snapshot was saved at 150s during an active internal splenic hemorrhage, then reloaded into a second scenario which advanced for another 120s. The evidence comparison checks the overlapping simulator rows rather than inferring continuity from logs.

| Compared overlapping rows | Overlap start (s) | Overlap end (s) | Maximum absolute numeric difference | Exact numeric match |
| ---: | ---: | ---: | ---: | --- |
| 121 | 150.0000 | 270.0000 | 0.0000 | True |
