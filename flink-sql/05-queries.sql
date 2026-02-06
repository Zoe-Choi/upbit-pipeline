-- ============================================================
-- Flink SQL: Analysis Queries
-- Sample queries for analyzing Upbit market data in Paimon
-- ============================================================

USE CATALOG paimon_catalog;
USE upbit;

-- ------------------------------------------------------------
-- Query 1: Latest Ticker per Market
-- ------------------------------------------------------------
SELECT 
    market,
    trade_price,
    change,
    change_rate * 100 AS change_rate_pct,
    acc_trade_volume_24h,
    trade_date,
    trade_time
FROM ticker
WHERE dt = DATE_FORMAT(CURRENT_DATE, 'yyyy-MM-dd')
ORDER BY acc_trade_volume_24h DESC
LIMIT 10;

-- ------------------------------------------------------------
-- Query 2: Recent Trades with Large Volume
-- BTC trades > 0.1 BTC in last hour
-- ------------------------------------------------------------
SELECT
    market,
    trade_price,
    trade_volume,
    trade_value,
    ask_bid,
    trade_time,
    FROM_UNIXTIME(trade_timestamp / 1000) AS trade_datetime
FROM trade
WHERE market = 'KRW-BTC'
  AND dt = DATE_FORMAT(CURRENT_DATE, 'yyyy-MM-dd')
  AND trade_volume > 0.1
ORDER BY trade_timestamp DESC
LIMIT 50;

-- ------------------------------------------------------------
-- Query 3: Buy/Sell Pressure Analysis
-- Count and volume by ask/bid in last hour
-- ------------------------------------------------------------
SELECT
    market,
    ask_bid,
    COUNT(*) AS trade_count,
    SUM(trade_volume) AS total_volume,
    SUM(trade_value) AS total_value,
    AVG(trade_price) AS avg_price
FROM trade
WHERE dt = DATE_FORMAT(CURRENT_DATE, 'yyyy-MM-dd')
GROUP BY market, ask_bid
ORDER BY market, ask_bid;

-- ------------------------------------------------------------
-- Query 4: Spread Analysis
-- Average spread by market
-- ------------------------------------------------------------
SELECT
    market,
    AVG(spread) AS avg_spread,
    AVG(spread_rate) AS avg_spread_rate_pct,
    MIN(spread) AS min_spread,
    MAX(spread) AS max_spread
FROM orderbook
WHERE dt = DATE_FORMAT(CURRENT_DATE, 'yyyy-MM-dd')
GROUP BY market
ORDER BY avg_spread_rate_pct DESC;

-- ------------------------------------------------------------
-- Query 5: 1-Minute OHLCV Candles
-- Recent candles for BTC
-- ------------------------------------------------------------
SELECT
    market,
    window_start,
    window_end,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    trade_count,
    ROUND(vwap, 0) AS vwap
FROM ohlcv_1m
WHERE market = 'KRW-BTC'
  AND dt = DATE_FORMAT(CURRENT_DATE, 'yyyy-MM-dd')
ORDER BY window_start DESC
LIMIT 60;

-- ------------------------------------------------------------
-- Query 6: Price Movement Summary
-- Daily price statistics per market
-- ------------------------------------------------------------
SELECT
    market,
    MIN(trade_price) AS day_low,
    MAX(trade_price) AS day_high,
    FIRST_VALUE(trade_price) AS open,
    LAST_VALUE(trade_price) AS close,
    SUM(trade_volume) AS total_volume,
    COUNT(*) AS trade_count
FROM trade
WHERE dt = DATE_FORMAT(CURRENT_DATE, 'yyyy-MM-dd')
GROUP BY market
ORDER BY total_volume DESC;

-- ------------------------------------------------------------
-- Query 7: Time Travel Query (Historical Analysis)
-- Query data as of a specific snapshot
-- ------------------------------------------------------------
-- SELECT * FROM ticker /*+ OPTIONS('scan.snapshot-id' = '1') */;
-- SELECT * FROM ticker /*+ OPTIONS('scan.timestamp-millis' = '1704067200000') */;

-- ------------------------------------------------------------
-- Query 8: Market Volatility (Price Range / Average)
-- ------------------------------------------------------------
SELECT
    market,
    dt,
    hh,
    COUNT(*) AS candle_count,
    AVG((high_price - low_price) / ((high_price + low_price) / 2) * 100) AS avg_volatility_pct,
    MAX((high_price - low_price) / ((high_price + low_price) / 2) * 100) AS max_volatility_pct
FROM ohlcv_1m
WHERE dt = DATE_FORMAT(CURRENT_DATE, 'yyyy-MM-dd')
GROUP BY market, dt, hh
ORDER BY avg_volatility_pct DESC;
