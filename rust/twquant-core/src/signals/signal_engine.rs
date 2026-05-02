use crate::indicators::custom_denoise::kalman_smooth;

/// 基於 Kalman 平滑結果產生買賣訊號
/// 平滑曲線斜率由負轉正 → 買入；由正轉負 → 賣出
pub fn kalman_signals(
    prices: &[f64],
    process_noise: f64,
    measurement_noise: f64,
) -> (Vec<bool>, Vec<bool>) {
    let n = prices.len();
    let smoothed = kalman_smooth(prices, process_noise, measurement_noise);

    let mut entries = vec![false; n];
    let mut exits = vec![false; n];

    for i in 1..n {
        let slope_prev = smoothed[i - 1] - if i >= 2 { smoothed[i - 2] } else { smoothed[i - 1] };
        let slope_curr = smoothed[i] - smoothed[i - 1];

        if slope_prev <= 0.0 && slope_curr > 0.0 {
            entries[i] = true;
        } else if slope_prev >= 0.0 && slope_curr < 0.0 {
            exits[i] = true;
        }
    }

    (entries, exits)
}
