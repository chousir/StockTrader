/// 簡化版 Kalman 濾波降噪移動平均
/// 接收 close prices，回傳平滑後的 price array
pub fn kalman_smooth(prices: &[f64], process_noise: f64, measurement_noise: f64) -> Vec<f64> {
    let n = prices.len();
    let mut smoothed = vec![0.0f64; n];

    // 初始化
    let mut x = prices[0]; // 狀態估計值
    let mut p = 1.0f64; // 估計誤差共變異數

    let q = process_noise;
    let r = measurement_noise;

    for (i, &z) in prices.iter().enumerate() {
        // 預測步驟
        let p_pred = p + q;

        // 更新步驟（Kalman gain）
        let k = p_pred / (p_pred + r);
        x = x + k * (z - x);
        p = (1.0 - k) * p_pred;

        smoothed[i] = x;
    }

    smoothed
}
