/*
 * TwinCare command guard, firmware logic v0 (desktop build).
 *
 * Every dose command is checked again just before it would execute (DI-05).
 * Rejected commands are logged with a reason. The hardware watchdog and override
 * switch are separate and are not part of this software check.
 *
 * Checks, in order:
 *   1. wrong session   command belongs to another session
 *   2. duplicate       command id already seen (replay)
 *   3. stale           older than the freshness window
 *   4. out of limit    dose outside [min, max]
 *   5. step too large  change from the current dose larger than max_step
 *
 * Limits come from the team simulation (0 to 0.5 ug/kg/min, 0.03 per step).
 * The freshness window (5 s here) is a placeholder for the team to confirm.
 *
 * Desktop harness: stdin lines "id,session,dose,issued_ms,now_ms";
 * stdout one result code per line (0 = accepted).
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef enum { G_OK = 0, G_WRONG_SESSION, G_DUPLICATE, G_STALE, G_OUT_OF_LIMIT, G_STEP_TOO_LARGE } GuardResult;

typedef struct { uint32_t id, session; float dose; uint32_t issued_ms; } Command;

typedef struct {
    uint32_t session, last_id;
    int has_last;
    float current, min, max, max_step;
    uint32_t freshness_ms;
    uint32_t rejected[6];
} Guard;

static GuardResult guard_check(Guard *g, const Command *c, uint32_t now_ms) {
    GuardResult r = G_OK;
    if (c->session != g->session) r = G_WRONG_SESSION;
    else if (g->has_last && c->id <= g->last_id) r = G_DUPLICATE;
    else if (now_ms < c->issued_ms || now_ms - c->issued_ms > g->freshness_ms) r = G_STALE;
    else if (c->dose < g->min || c->dose > g->max) r = G_OUT_OF_LIMIT;
    else {
        float step = c->dose - g->current;
        if (step < 0) step = -step;
        if (step > g->max_step + 1e-6f) r = G_STEP_TOO_LARGE;
    }
    if (r == G_OK) { g->current = c->dose; g->last_id = c->id; g->has_last = 1; }
    else g->rejected[r]++;              /* log: count by reason */
    return r;
}

int main(void) {
    Guard g = { .session = 42, .last_id = 0, .has_last = 0, .current = 0.05f,
                .min = 0.0f, .max = 0.5f, .max_step = 0.03f, .freshness_ms = 5000 };
    char line[128];
    while (fgets(line, sizeof line, stdin)) {
        Command c; unsigned long id, sess, issued, now; float dose;
        if (sscanf(line, "%lu,%lu,%f,%lu,%lu", &id, &sess, &dose, &issued, &now) != 5) continue;
        c.id = (uint32_t)id; c.session = (uint32_t)sess; c.dose = dose; c.issued_ms = (uint32_t)issued;
        printf("%d\n", (int)guard_check(&g, &c, (uint32_t)now));
    }
    fprintf(stderr, "rejected by reason: session %u, duplicate %u, stale %u, limit %u, step %u\n",
            g.rejected[1], g.rejected[2], g.rejected[3], g.rejected[4], g.rejected[5]);
    return 0;
}
