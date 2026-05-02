use numpy::PyReadonlyArray1;
use pyo3::prelude::*;

pub mod errors;
pub mod indicators;
pub mod signals;
mod validation;

use validation::InputGuard;

#[pyfunction]
fn array_sum(arr: PyReadonlyArray1<f64>) -> PyResult<f64> {
    InputGuard::validate_f64_array(&arr, "arr")?;
    Ok(arr.as_array().sum())
}

#[pymodule]
fn twquant_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(array_sum, m)?)?;
    Ok(())
}
