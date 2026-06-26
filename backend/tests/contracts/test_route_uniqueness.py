from collections import Counter
from fastapi.routing import APIRoute
from backend.main import app

def test_no_duplicate_routes():
    """Verify that there are no duplicate route registrations (same method + path)."""
    route_pairs = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            # FastAPI routes list supported HTTP methods (e.g., {'GET', 'POST'})
            for method in route.methods:
                route_pairs.append((method.upper(), route.path))
                
    counter = Counter(route_pairs)
    duplicates = {pair: count for pair, count in counter.items() if count > 1}
    
    assert not duplicates, f"Duplicate HTTP routes detected: {duplicates}. Please ensure routes are registered exactly once."
