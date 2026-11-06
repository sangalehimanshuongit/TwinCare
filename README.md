# TwinCare

**A test bench for software that warns of falling blood pressure and suggests a dose, before that software ever reaches a patient.**

## The patient

A patient in a cardiac intensive care unit is in shock: their circulation cannot hold blood pressure up without drugs. In 16 advanced North American cardiac units, 22 % of admissions met shock criteria, and 31 to 39 % of those patients died in hospital [1]. In one cardiogenic shock cohort, a mean pressure below 65 mmHg in the first 24 hours went with 57 % mortality, against 28 % without it [2].

## The problem at the bedside

In many units, a critical care nurse keeps blood pressure in range by hand, with a vasopressor (a drug that raises blood pressure) [3]. The response typically takes 3 to 5 minutes to show [4]. So the number on the monitor does not yet show the last dose. Raise the dose too soon and two changes act at once. Wait too long and pressure stays low.

After cardiac surgery, nurses aiming for 65 to 75 mmHg changed the dose 13 times in 2 hours. Pressure stayed in range 66 % of the time, below it 12.5 % and above it 20.6 % [5].

## What we are building

Software can warn early and suggest a dose. It cannot be tried first on real patients. So we are building the bench to test it: a simulated patient whose pressure responds to a dose after a realistic delay, one small device that runs the software, and a screen where a clinician decides. No patient, pump or drug is involved. The dose is an electrical signal.

| Bedside step | The gap today | What TwinCare tests |
|---|---|---|
| Watch the pressure | The monitor shows now, not 10 minutes from now | A forecaster that warns at least 10 minutes before pressure falls below 65 mmHg |
| Change the dose | The screen does not show doses still taking effect | A digital twin (a running model of this patient) that tracks those doses and suggests one small change |
| Give the dose | An order can be out of date by the time it runs | Clinician approval of every dose, a software check, and a hardware cut within 100 ms |
| Hand over | The next clinician needs the full dose story | A handover summary, and a record of every event |
| Try new software | Real patients cannot be the first test | Repeatable runs on simulated patients for our sponsor's research lab |

**Where this could go:** Canada has about 3,170 intensive care beds [6]. We expect hospitals and health authorities to be the buyers, and our venture plan starts with Alberta's adult cardiac units. Today TwinCare is a university capstone, not a medical device.

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

## References

1. D. D. Berg et al., "Epidemiology of shock in contemporary cardiac intensive care units," *Circ. Cardiovasc. Qual. Outcomes*, vol. 12, e005618, 2019. [doi](https://doi.org/10.1161/CIRCOUTCOMES.119.005618)
2. B. Burstein et al., "Association between mean arterial pressure during the first 24 hours and hospital mortality in patients with cardiogenic shock," *Crit. Care*, vol. 24, 513, 2020. [doi](https://doi.org/10.1186/s13054-020-03217-6)
3. E. Waterval et al., "Nurses' decision-making and confidence with titration of vasoactive medication," *Am. J. Crit. Care*, vol. 34, e24, 2025. [doi](https://doi.org/10.4037/ajcc2025332)
4. V. S. Nair et al., "Artificial intelligence-driven norepinephrine control using adaptive cardiac digital twin for critical care patients," *Methods Inf. Med.*, vol. 65, 36, 2026. [doi](https://doi.org/10.1055/a-2927-7553)
5. O. Desebbe et al., "Control of postoperative hypotension using a closed-loop system for norepinephrine infusion in patients after cardiac surgery," *Anesth. Analg.*, vol. 134, 964, 2022. [doi](https://doi.org/10.1213/ANE.0000000000005888)
6. R. A. Fowler et al., "Critical care capacity in Canada," *Crit. Care*, vol. 19, 133, 2015. [doi](https://doi.org/10.1186/s13054-015-0852-6)

---

ENGG 501 Team 11, University of Calgary. Our full design history file stays private, because it holds survey responses and sponsor records.

<sub>**AI use.** Claude, by Anthropic PBC, was used to synthesize the team's notes and ideas into these pages, to help with formatting and to draft the prototype code in `firmware/` and `ml/`. The repository reflects the team's ideas and work, and the team takes full responsibility for it.</sub>
