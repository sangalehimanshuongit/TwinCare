/*
 * TwinCare embedded patient simulator, firmware logic v0 (desktop build).
 *
 * The same model the team uses in lag_aware_sim.py, written the way it will run
 * on the dev board: float32 maths, a fixed 1 Hz tick, a ring buffer for the drug
 * delay and no dynamic memory.
 *
 *   MAP = P0 - D(t) + K * e(t)
 *   e follows the dose through a transport delay (td_s) and a first-order lag (tau_s)
 *   D(t) is the scripted hypotension disturbance for the scenario
 *
 * Desktop harness: reads one dose value per line from stdin (ug/kg/min, one per
 * second) and prints "t_s,map_mmHg" to stdout.
 *
 * Build:  cc -O2 -std=c99 -o patient_sim patient_sim.c
 * Run:    ./patient_sim K TD_S TAU_S P0 U0 D_MAX D_START_S D_RAMP_S < doses.txt
 */
#include <stdio.h>
#include <stdlib.h>

#define MAX_DELAY_S 600

typedef struct {
    float k, tau_s, p0, u0;
    int td_s;
    float d_max, d_start_s, d_ramp_s;
    float e;                      /* drug effect state */
    float buf[MAX_DELAY_S + 1];   /* past doses, one per second */
    int head, filled;
    long t_s;
} PatientSim;

static void sim_init(PatientSim *s, float k, int td_s, float tau_s, float p0, float u0,
                     float d_max, float d_start_s, float d_ramp_s) {
    s->k = k; s->td_s = td_s; s->tau_s = tau_s; s->p0 = p0; s->u0 = u0;
    s->d_max = d_max; s->d_start_s = d_start_s; s->d_ramp_s = d_ramp_s;
    s->e = u0; s->head = 0; s->filled = 0; s->t_s = 0;
}

static float disturbance(const PatientSim *s, float t) {
    if (t < s->d_start_s) return 0.0f;
    float f = (t - s->d_start_s) / s->d_ramp_s;
    return s->d_max * (f < 1.0f ? f : 1.0f);
}

/* One 1 Hz tick. Returns MAP for this second, then records the dose commanded now. */
static float sim_tick(PatientSim *s, float dose_now) {
    float delayed = s->u0;
    if (s->filled >= s->td_s && s->td_s > 0) {
        int idx = (s->head - s->td_s + (MAX_DELAY_S + 1)) % (MAX_DELAY_S + 1);
        delayed = s->buf[idx];
    }
    s->e += (delayed - s->e) / s->tau_s;            /* dt = 1 s */
    float map = s->p0 - disturbance(s, (float)s->t_s) + s->k * s->e;
    s->buf[s->head] = dose_now;                       /* push after use */
    s->head = (s->head + 1) % (MAX_DELAY_S + 1);
    if (s->filled < MAX_DELAY_S) s->filled++;
    s->t_s++;
    return map;
}

int main(int argc, char **argv) {
    if (argc != 9) {
        fprintf(stderr, "usage: %s K TD_S TAU_S P0 U0 D_MAX D_START_S D_RAMP_S < doses\n", argv[0]);
        return 2;
    }
    int td = atoi(argv[2]);
    if (td < 1 || td > MAX_DELAY_S) { fprintf(stderr, "TD_S out of range\n"); return 2; }
    PatientSim s;
    sim_init(&s, (float)atof(argv[1]), td, (float)atof(argv[3]), (float)atof(argv[4]),
             (float)atof(argv[5]), (float)atof(argv[6]), (float)atof(argv[7]), (float)atof(argv[8]));
    char line[64];
    while (fgets(line, sizeof line, stdin)) {
        float dose = (float)atof(line);
        long t = s.t_s;
        float map = sim_tick(&s, dose);
        printf("%ld,%.6f\n", t, map);
    }
    return 0;
}
