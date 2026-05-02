use pyo3::exceptions;
use pyo3::prelude::*;

#[derive(Debug)]
pub enum TwQuantError {
    EmptyInput { param_name: String },
    DimensionMismatch { expected: usize, got: usize, param_name: String },
    InvalidFloat { position: usize, value: f64, param_name: String },
    WindowTooLarge { window: usize, data_len: usize },
    ComputationError { message: String },
}

impl From<TwQuantError> for PyErr {
    fn from(err: TwQuantError) -> PyErr {
        match err {
            TwQuantError::EmptyInput { param_name } => {
                exceptions::PyValueError::new_err(format!(
                    "輸入陣列 '{}' 不可為空",
                    param_name
                ))
            }
            TwQuantError::DimensionMismatch { expected, got, param_name } => {
                exceptions::PyValueError::new_err(format!(
                    "陣列 '{}' 維度不匹配：預期 {} 個元素，實際 {} 個",
                    param_name, expected, got
                ))
            }
            TwQuantError::InvalidFloat { position, value, param_name } => {
                exceptions::PyValueError::new_err(format!(
                    "陣列 '{}' 在位置 {} 包含無效浮點數：{}",
                    param_name, position, value
                ))
            }
            TwQuantError::WindowTooLarge { window, data_len } => {
                exceptions::PyValueError::new_err(format!(
                    "窗口大小 ({}) 超過數據長度 ({})",
                    window, data_len
                ))
            }
            TwQuantError::ComputationError { message } => {
                exceptions::PyRuntimeError::new_err(format!(
                    "Rust 運算錯誤：{}",
                    message
                ))
            }
        }
    }
}
