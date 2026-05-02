use ndarray::s;
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

#[pyfunction]
fn dot_product(a: PyReadonlyArray1<f64>, b: PyReadonlyArray1<f64>) -> PyResult<f64> {
    InputGuard::validate_f64_array(&a, "a")?;
    InputGuard::validate_f64_array(&b, "b")?;
    InputGuard::validate_same_length(&a, &b, "a", "b")?;
    Ok(a.as_array().dot(&b.as_array()))
}

#[pyfunction]
fn moving_sum(arr: PyReadonlyArray1<f64>, window: usize) -> PyResult<Vec<f64>> {
    InputGuard::validate_f64_array(&arr, "arr")?;
    InputGuard::validate_window(window, arr.as_array().len())?;

    let data = arr.as_array();
    let n = data.len();
    let mut result = Vec::with_capacity(n - window + 1);

    let mut running: f64 = data.slice(s![..window]).sum();
    result.push(running);
    for i in window..n {
        running += data[i] - data[i - window];
        result.push(running);
    }
    Ok(result)
}

fn panic_msg(e: Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = e.downcast_ref::<String>() {
        s.clone()
    } else if let Some(s) = e.downcast_ref::<&str>() {
        s.to_string()
    } else {
        "unknown panic".to_string()
    }
}

#[pyfunction]
fn trigger_panic() -> PyResult<()> {
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        panic!("deliberate test panic")
    }));
    match result {
        Ok(_) => Ok(()),
        Err(e) => Err(pyo3::exceptions::PyRuntimeError::new_err(
            format!("Rust panic: {}", panic_msg(e)),
        )),
    }
}

#[pymodule]
fn twquant_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(array_sum, m)?)?;
    m.add_function(wrap_pyfunction!(dot_product, m)?)?;
    m.add_function(wrap_pyfunction!(moving_sum, m)?)?;
    m.add_function(wrap_pyfunction!(trigger_panic, m)?)?;
    Ok(())
}
