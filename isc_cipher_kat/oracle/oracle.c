/*
 * Independent known-answer oracle for ISC-IMG v1 numerical profile 1 (F64-FDLIBM).
 *
 * Links the unmodified fdlibm 5.3 sources (third_party/fdlibm/netlib_5.3) and evaluates
 *   - sin/cos for given binary64 arguments          (mode "trig")
 *   - ISC trajectories with the operation order of research/algorithm_design.md §6.1 (mode "traj")
 * Build (see build_oracle.sh):  gcc -O0 -ffp-contract=off -fno-builtin -D__LITTLE_ENDIAN
 * Every double is printed as the 16-hex-digit IEEE 754 bit pattern.
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

double sin(double);   /* fdlibm s_sin.c */
double cos(double);   /* fdlibm s_cos.c */

static uint64_t bits(double v) { uint64_t u; memcpy(&u, &v, 8); return u; }
static double from_bits(uint64_t u) { double v; memcpy(&v, &u, 8); return v; }

static const double A = 0.9, C = 0.4, D = 6.0, W = 10.0, ONE = 1.0, TWO = 2.0;

static void step(double *px, double *py)
{
    double x = *px, y = *py;
    double t1 = x * x, t2 = y * y, r = t1 + t2;
    double t3 = ONE + r, t4 = D / t3, t = C - t4;
    double ct = cos(t), st = sin(t);
    double t5 = x * ct, t6 = y * st, t7 = t5 - t6, t8 = A * t7, X = ONE + t8;
    double t9 = x * st, t10 = y * ct, t11 = t9 + t10, Y = A * t11;
    double t12 = W * X, sx = sin(t12), t13 = W * Y, sy = sin(t13);
    double t14 = sx * sx, t15 = TWO * t14;
    double t16 = sy * sy, t17 = TWO * t16;
    *px = t15 - ONE;
    *py = t17 - ONE;
}

int main(int argc, char **argv)
{
    char mode[16];
    if (argc != 2) { fprintf(stderr, "usage: oracle trig|traj < input\n"); return 2; }
    strncpy(mode, argv[1], sizeof mode - 1); mode[sizeof mode - 1] = 0;
    if (strcmp(mode, "trig") == 0) {
        unsigned long long u;
        while (scanf("%llx", &u) == 1) {
            double a = from_bits((uint64_t)u);
            printf("%016llx %016llx %016llx\n", (unsigned long long)u,
                   (unsigned long long)bits(sin(a)), (unsigned long long)bits(cos(a)));
        }
        return 0;
    }
    if (strcmp(mode, "traj") == 0) {
        /* input lines: x0hex y0hex burnin outsteps ; output: one line per state after each step
           (burn-in steps marked B, output steps marked O): tag index xhex yhex */
        unsigned long long ux, uy; long burn, outs;
        while (scanf("%llx %llx %ld %ld", &ux, &uy, &burn, &outs) == 4) {
            double x = from_bits((uint64_t)ux), y = from_bits((uint64_t)uy);
            printf("S %016llx %016llx %ld %ld\n", ux, uy, burn, outs);
            for (long i = 1; i <= burn; i++) {
                step(&x, &y);
                printf("B %ld %016llx %016llx\n", i, (unsigned long long)bits(x), (unsigned long long)bits(y));
            }
            for (long j = 1; j <= outs; j++) {
                step(&x, &y);
                printf("O %ld %016llx %016llx\n", j, (unsigned long long)bits(x), (unsigned long long)bits(y));
            }
        }
        return 0;
    }
    fprintf(stderr, "unknown mode\n");
    return 2;
}
