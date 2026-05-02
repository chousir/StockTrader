use numpy::PyReadonlyArray1;

use crate::errors::TwQuantError;

pub struct InputGuard;

impl InputGuard {
    pub fn validate_f64_array(
        arr: &PyReadonlyArray1<f64>,
        param_name: &str,
    ) -> Result<(), TwQuantError> {
        let slice = arr.as_array();

        if slice.is_empty() {
            return Err(TwQuantError::EmptyInput {
                param_name: param_name.to_string(),
            });
        }

        for (i, &val) in slice.iter().enumerate() {
            if val.is_nan() || val.is_infinite() {
                return Err(TwQuantError::InvalidFloat {
                    position: i,
                    value: val,
                    param_name: param_name.to_string(),
                });
            }
        }

        Ok(())
    }

    pub fn validate_same_length(
        a: &PyReadonlyArray1<f64>,
        b: &PyReadonlyArray1<f64>,
        name_a: &str,
        name_b: &str,
    ) -> Result<(), TwQuantError> {
        let len_a = a.as_array().len();
        let len_b = b.as_array().len();
        if len_a != len_b {
            return Err(TwQuantError::DimensionMismatch {
                expected: len_a,
                got: len_b,
                param_name: format!("{} vs {}", name_a, name_b),
            });
        }
        Ok(())
    }

    pub fn validate_window(window: usize, data_len: usize) -> Result<(), TwQuantError> {
        if window == 0 || window > data_len {
            return Err(TwQuantError::WindowTooLarge { window, data_len });
        }
        Ok(())
    }
}
