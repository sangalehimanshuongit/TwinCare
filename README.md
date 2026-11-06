# TwinCare

A blood-pressure digital twin for cardiac care. It forecasts low pressure and proposes vasopressor doses (drugs that raise blood pressure). A clinician approves every dose.

## How we roll it out

We test on simulated patients only.

<table>
<tr>
<td width="33%" valign="top"><h3>1. Laptop</h3><b>Done</b><br>Our patient code matches the reference model within 0.0002 mmHg.</td>
<td width="33%" valign="top"><h3>2. Dev board</h3><b>27 Nov 2026</b><br>One simulated patient runs end to end for an hour on the ESP32-S3 board.</td>
<td width="33%" valign="top"><h3>3. Our own board</h3><b>Apr 2027</b><br>Three simulated patients run at once on our custom circuit boards.</td>
</tr>
</table>

## What keeps the dose safe

<table>
<tr>
<td width="33%" valign="top"><h3>Clinician approval</h3>Every proposed dose waits for a clinician.</td>
<td width="33%" valign="top"><h3>5,030 of 5,030</h3>Unsafe commands rejected by our software guard in desktop tests. All 4,979 safe ones passed.</td>
<td width="33%" valign="top"><h3>69.1 ms</h3>Worst-case designed time for hardware to cut the dose if the program freezes. The limit is 100 ms. Breadboard test by 13 Nov.</td>
</tr>
</table>

## Explore

<table>
<tr>
<td width="33%" valign="top"><h3><a href="hardware/README.md">Hardware</a></h3>Board choice, safety circuit and design log.</td>
<td width="33%" valign="top"><h3><a href="firmware/README.md">Firmware</a> and <a href="ml/README.md">ML</a></h3>Simulated patient, command guard and small test models.</td>
<td width="33%" valign="top"><h3><a href="reference/lag_aware_sim.py">Reference model</a></h3>The Python model that the patient code is checked against.</td>
</tr>
</table>

---

ENGG 501 Team 11, University of Calgary. Our full design history file stays private, because it holds survey responses and sponsor records.

<sub>**AI use.** Claude, by Anthropic PBC, was used to synthesize the team's notes and ideas into these pages, to help with formatting and to draft the prototype code in `firmware/` and `ml/`. The repository reflects the team's ideas and work, and the team takes full responsibility for it.</sub>
