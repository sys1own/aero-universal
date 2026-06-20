//! Core numerics for the physics simulator.
//!
//! Exposes a PyO3 entry point (`rust_relax_field`) detected by the Aero semantic
//! mapper as a `pyo3_function`, and a C-ABI export (`c_relax`) detected as a
//! `rust_extern_c` binding.

use pyo3::prelude::*;

/// Jacobi relaxation sweep over a 1-D field. Exposed to Python via PyO3.
#[pyfunction]
fn rust_relax_field(grid: Vec<f64>, iterations: usize) -> Vec<f64> {
    let mut current = grid.clone();
    for _ in 0..iterations {
        let mut next = current.clone();
        for i in 1..current.len().saturating_sub(1) {
            next[i] = 0.5 * (current[i - 1] + current[i + 1]);
        }
        current = next;
    }
    current
}

/// C-ABI relaxation entry point for the legacy C/Fortran call sites.
#[no_mangle]
pub extern "C" fn c_relax(ptr: *mut f64, len: usize, iterations: usize) {
    if ptr.is_null() {
        return;
    }
    let data = unsafe { std::slice::from_raw_parts_mut(ptr, len) };
    for _ in 0..iterations {
        for i in 1..len.saturating_sub(1) {
            data[i] = 0.5 * (data[i - 1] + data[i + 1]);
        }
    }
}

#[pymodule]
fn physics_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rust_relax_field, m)?)?;
    Ok(())
}
