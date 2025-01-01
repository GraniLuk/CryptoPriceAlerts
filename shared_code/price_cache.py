class PriceCache:
    def __init__(self):
        self._cache = {}

    def get_price(self, symbol: str) -> float | None:
        """Get cached price for symbol"""
        return self._cache.get(symbol)

    def set_price(self, symbol: str, price: float) -> None:
        """Cache price for symbol"""
        self._cache[symbol] = price

    def clear(self) -> None:
        """Clear all cached prices"""
        self._cache.clear()

# Global instance for easy access
price_cache = PriceCache()