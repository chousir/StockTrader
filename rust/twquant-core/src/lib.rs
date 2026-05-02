use ndarray::s;
use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use pyo3::prelude::*;

pub mod errors;
pub mod indicators;
pub mod signals;
mod validation;

use indicators::custom_denoise::kalman_smooth;
use signals::signal_engine::kalman_signals;
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

/// 降噪移動平均：Kalman 濾波平滑 close price array
#[pyfunction]
fn denoise_prices(
    py: Python<'_>,
    prices: PyReadonlyArray1<f64>,
    process_noise: Option<f64>,
    measurement_noise: Option<f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    InputGuard::validate_f64_array(&prices, "prices")?;
    let slice = prices.as_slice()?;
    let q = process_noise.unwrap_or(0.01);
    let r = measurement_noise.unwrap_or(1.0);
    let result = py.allow_threads(|| kalman_smooth(slice, q, r));
    Ok(result.into_pyarray_bound(py).into())
}

/// Kalman 訊號引擎：回傳 (entries, exits) bool 陣列
#[pyfunction]
fn compute_kalman_signals(
    py: Python<'_>,
    prices: PyReadonlyArray1<f64>,
    process_noise: Option<f64>,
    measurement_noise: Option<f64>,
) -> PyResult<(Py<PyArray1<bool>>, Py<PyArray1<bool>>)> {
    InputGuard::validate_f64_array(&prices, "prices")?;
    let slice = prices.as_slice()?;
    let q = process_noise.unwrap_or(0.01);
    let r = measurement_noise.unwrap_or(1.0);
    let (entries, exits) = py.allow_threads(|| kalman_signals(slice, q, r));
    Ok((
        entries.into_pyarray_bound(py).into(),
        exits.into_pyarray_bound(py).into(),
    ))
}

#[pymodule]
fn twquant_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(array_sum, m)?)?;
    m.add_function(wrap_pyfunction!(dot_product, m)?)?;
    m.add_function(wrap_pyfunction!(moving_sum, m)?)?;
    m.add_function(wrap_pyfunction!(trigger_panic, m)?)?;
    m.add_function(wrap_pyfunction!(denoise_prices, m)?)?;
    m.add_function(wrap_pyfunction!(compute_kalman_signals, m)?)?;
    Ok(())
}
