/*
 * Legacy C component of the physics simulator.
 *
 * The Aero semantic mapper extracts:
 *   - GLOBAL_TOLERANCE       (uast_global)
 *   - Stencil               (uast_type, via typedef)
 *   - laplacian_1d          (uast_function)
 *   - the extern declaration c_relax (c_extern FFI binding into the Rust core)
 */

#include <stddef.h>

double GLOBAL_TOLERANCE = 1e-12;

typedef struct {
    double left;
    double center;
    double right;
} Stencil;

/* Imported from the Rust core via the C ABI. */
extern void c_relax(double *ptr, size_t len, size_t iterations);

double laplacian_1d(const Stencil *s) {
    return s->left - 2.0 * s->center + s->right;
}

void relax_with_native(double *field, size_t len, size_t iters) {
    c_relax(field, len, iters);
}
