/**
 * symplectic_miner_loop.c — C version of the RustChain mining loop
 * Uses symplectic decomposition from bytropix math vault to schedule
 * optimal attestation intervals.
 *
 * Math: g = q·2π + r — decomposes time gradient into integer cycles + remainder drift.
 * This C version runs the decomposition loop without Python overhead.
 *
 * Compile: gcc -O3 -lm -o symplectic_miner_loop symplectic_miner_loop.c
 * Usage:  ./symplectic_miner_loop [--interval 600] [--cycles 20]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <unistd.h>
#include <signal.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define BOUNDARY (2.0 * M_PI)
#define DEFAULT_INTERVAL 600   /* 10 min base interval */
#define DEFAULT_CYCLES 20      /* cycles before re-optimizing */
#define MIN_INTERVAL 10.0      /* minimum 10s between attestations */

/* ─── Symplectic Decomposition (from bytropix/THEORY/math_viz/06_symplectic_optimizer.py) ─── */

typedef struct {
    long long q;    /* integer cycles */
    double r;       /* remainder drift in [-π, π] */
} symplectic_pair;

static symplectic_pair decompose(double g, double boundary) {
    /* g = q * boundary + r, where q = integer, r in [-boundary/2, boundary/2] */
    symplectic_pair result;
    result.q = (long long)floor((g + boundary / 2.0) / boundary);
    result.r = fmod(g + boundary / 2.0, boundary) - boundary / 2.0;
    return result;
}

static double recompose(symplectic_pair p, double boundary) {
    return (double)p.q * boundary + p.r;
}

/* ─── Optimal Schedule Generation ─── */

typedef struct {
    double *intervals;   /* array of N intervals */
    int count;           /* number of intervals */
    double total_time;   /* total time spanned */
} symplectic_schedule;

static symplectic_schedule generate_schedule(double base_interval, int count) {
    /* Generate symplectically-optimal attestation intervals.
     * Decomposes total time into q (discrete cycles) + r (continuum drift).
     * Distributes remainder drift across cycles so cumulative drift never exceeds boundary.
     */
    symplectic_schedule sched;
    sched.count = count;
    sched.intervals = (double *)calloc(count, sizeof(double));
    
    double total = base_interval * count;
    symplectic_pair total_dec = decompose(total, BOUNDARY);
    sched.total_time = recompose(total_dec, BOUNDARY);
    
    double accumulated_r = 0.0;
    for (int i = 0; i < count; i++) {
        double target_r = total_dec.r * (i + 1) / count;
        double drift = target_r - accumulated_r;
        double interval = base_interval + drift;
        if (interval < MIN_INTERVAL) interval = MIN_INTERVAL;
        sched.intervals[i] = interval;
        accumulated_r = target_r;
    }
    
    return sched;
}

static void free_schedule(symplectic_schedule *sched) {
    free(sched->intervals);
    sched->intervals = NULL;
    sched->count = 0;
}

/* ─── PID Controller for Interval Drift Correction ─── */

typedef struct {
    double Kp, Ki, Kd;    /* PID gains */
    double integral;       /* accumulated integral */
    double prev_error;     /* previous error for derivative */
    struct timespec last_time;
    int initialized;
} pid_controller;

static pid_controller pid_new(double Kp, double Ki, double Kd) {
    pid_controller pid = {Kp, Ki, Kd, 0.0, 0.0, {0, 0}, 0};
    return pid;
}

static double pid_update(pid_controller *pid, double setpoint, double measurement) {
    double error = setpoint - measurement;
    
    /* Proportional */
    double P = pid->Kp * error;
    
    /* Integral (with anti-windup clamp) */
    pid->integral += error;
    if (pid->integral > 100.0) pid->integral = 100.0;
    if (pid->integral < -100.0) pid->integral = -100.0;
    double I = pid->Ki * pid->integral;
    
    /* Derivative */
    double D = 0.0;
    if (pid->initialized) {
        D = pid->Kd * (error - pid->prev_error);
    }
    pid->prev_error = error;
    pid->initialized = 1;
    
    return P + I + D;
}

/* ─── Mining Loop ─── */

static volatile int running = 1;

static void handle_signal(int sig) {
    (void)sig;
    running = 0;
}

static double get_time_seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

int main(int argc, char **argv) {
    double base_interval = DEFAULT_INTERVAL;
    int cycles = DEFAULT_CYCLES;
    
    /* Parse args */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--interval") == 0 && i + 1 < argc) {
            base_interval = atof(argv[++i]);
        } else if (strcmp(argv[i], "--cycles") == 0 && i + 1 < argc) {
            cycles = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--help") == 0) {
            printf("Usage: %s [--interval SECONDS] [--cycles N]\n", argv[0]);
            printf("  --interval  Base attestation interval (default: %d)\n", DEFAULT_INTERVAL);
            printf("  --cycles    Cycles before re-optimizing schedule (default: %d)\n", DEFAULT_CYCLES);
            return 0;
        }
    }
    
    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);
    
    printf("╔═══════════════════════════════════════════╗\n");
    printf("║  Symplectic Miner Loop (C)               ║\n");
    printf("║  Math: g = q·2π + r                      ║\n");
    printf("║  bytropix symplectic decomposition        ║\n");
    printf("╚═══════════════════════════════════════════╝\n");
    printf("Base interval: %.0fs (%d min)\n", base_interval, (int)(base_interval / 60));
    printf("Cycles per schedule: %d\n\n", cycles);
    
    pid_controller pid = pid_new(0.1, 0.01, 0.05);
    int cycle_num = 0;
    
    while (running) {
        double t_start = get_time_seconds();
        cycle_num++;
        
        /* Generate symplectic schedule */
        symplectic_schedule sched = generate_schedule(base_interval, cycles);
        
        printf("[Cycle %d] Schedule generated: %d intervals, total_time=%.1fs\n",
               cycle_num, sched.count, sched.total_time);
        
        /* Execute the schedule */
        for (int i = 0; i < sched.count && running; i++) {
            double scheduled_interval = sched.intervals[i];
            
            /* PID correction for clock drift */
            double expected = t_start + scheduled_interval;
            double actual = get_time_seconds();
            double drift = expected - actual;
            double correction = pid_update(&pid, 0.0, drift);
            
            double adjusted_interval = scheduled_interval + correction;
            if (adjusted_interval < MIN_INTERVAL) adjusted_interval = MIN_INTERVAL;
            
            printf("  [%d/%d] Wait %.1fs (base=%.1f drift=%.4f correction=%.4f)\n",
                   i + 1, sched.count, adjusted_interval, 
                   scheduled_interval, drift, correction);
            
            /* Sleep for the adjusted interval */
            struct timespec ts;
            ts.tv_sec = (time_t)adjusted_interval;
            ts.tv_nsec = (long)((adjusted_interval - ts.tv_sec) * 1e9);
            nanosleep(&ts, NULL);
            
            /* Check if interrupted */
            if (!running) break;
            
            /* At this point, call the Python miner for attestation:
             *   system("python3 ~/rustchain/miners/linux/rustchain_linux_miner.py --wallet ... --attest-only");
             * For now, just log the checkpoint
             */
            printf("  [%d/%d] ⏰ Attestation checkpoint at t=%.1fs\n", 
                   i + 1, sched.count, get_time_seconds() - t_start);
        }
        
        free_schedule(&sched);
        
        if (!running) break;
        
        /* Re-optimize: decompose the actual elapsed time vs expected */
        double t_elapsed = get_time_seconds() - t_start;
        symplectic_pair actual_dec = decompose(t_elapsed, BOUNDARY);
        printf("[Cycle %d] Complete: elapsed=%.1fs q=%lld r=%.4f\n\n",
               cycle_num, t_elapsed, actual_dec.q, actual_dec.r);
    }
    
    printf("\nMiner loop stopped after %d cycles\n", cycle_num);
    return 0;
}
