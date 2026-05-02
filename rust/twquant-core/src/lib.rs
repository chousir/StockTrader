use numpy::PyReadonlyArray1;
use pyo3::prelude::*;

#[pyfunction]
fn array_sum(arr: PyReadonlyArray1<f64>) -> f64 {
    arr.as_array().sum()
}

#[pymodule]
fn twquant_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(array_sum, m)?)?;
    Ok(())
}
