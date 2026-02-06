"""
Main entry point for Upbit data pipeline.
Connects to Upbit WebSocket and streams data to Kafka.
"""
import asyncio
import sys
from typing import List, Optional

from src.config import get_config
from src.consumers import UpbitWebSocketClient
from src.pipeline import KafkaMessageHandler
from src.producers import ensure_topics_exist
from src.utils import get_logger

logger = get_logger(__name__)


async def run_pipeline(
    markets: Optional[List[str]] = None,
    subscribe_ticker: bool = True,
    subscribe_trade: bool = True,
    subscribe_orderbook: bool = False,
) -> None:
    """
    Run the Upbit to Kafka data pipeline.
    
    Args:
        markets: List of market codes (e.g., ["KRW-BTC", "KRW-ETH"])
        subscribe_ticker: Subscribe to ticker updates
        subscribe_trade: Subscribe to trade updates
        subscribe_orderbook: Subscribe to orderbook updates
    """
    config = get_config()
    
    # Use default markets if not specified
    target_markets = markets or config.markets.default_markets
    
    logger.info("=" * 60)
    logger.info("Upbit Data Pipeline")
    logger.info("=" * 60)
    logger.info("Markets: %s", ", ".join(target_markets))
    logger.info("Ticker: %s, Trade: %s, Orderbook: %s",
                subscribe_ticker, subscribe_trade, subscribe_orderbook)
    logger.info("=" * 60)
    
    # Ensure Kafka topics exist
    topics = []
    if subscribe_ticker:
        topics.append(config.kafka.topic_ticker)
    if subscribe_trade:
        topics.append(config.kafka.topic_trade)
    if subscribe_orderbook:
        topics.append(config.kafka.topic_orderbook)
    
    logger.info("Creating Kafka topics if not exist: %s", topics)
    ensure_topics_exist(topics)
    
    # Initialize handler and client
    handler = KafkaMessageHandler()
    client = UpbitWebSocketClient(handler=handler)
    
    # Setup subscriptions
    if subscribe_ticker:
        client.subscribe_ticker(target_markets)
    if subscribe_trade:
        client.subscribe_trade(target_markets)
    if subscribe_orderbook:
        client.subscribe_orderbook(target_markets)
    
    try:
        await client.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        handler.close()
        logger.info("Pipeline shutdown complete")
        logger.info("Final stats: %s", handler.stats)


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
