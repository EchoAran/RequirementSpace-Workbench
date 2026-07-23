import json
from pathlib import Path
from backend.main import app

SNAPSHOT_PATH = Path(__file__).parent / "openapi_snapshot.json"

def test_openapi_matches_snapshot():
    # Force FastAPI to generate/resolve OpenAPI schema
    current_openapi = app.openapi()
    
    # Deep copy/filter to avoid modifying the live app's openapi schema in-place
    clean_openapi = json.loads(json.dumps(current_openapi))
    
    # Filter out test-only routes registered dynamically during test suite runs
    if "paths" in clean_openapi:
        clean_openapi["paths"] = {
            path: details
            for path, details in clean_openapi["paths"].items()
            if not path.startswith("/api/test-")
        }
    
    # Serialize with sorted keys for deterministic comparison
    current_str = json.dumps(clean_openapi, sort_keys=True, indent=2)
    
    if not SNAPSHOT_PATH.exists():
        # Initialize snapshot on first run
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            f.write(current_str)
        return
        
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot_str = f.read().rstrip("\n")
        
    if current_str != snapshot_str:
        # Save the new version as .new.json to help developers inspect/diff
        new_path = SNAPSHOT_PATH.with_suffix(".new.json")
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(current_str)
        
        assert current_str == snapshot_str, (
            f"OpenAPI schema does not match snapshot! "
            f"Differences saved to {new_path}. "
            f"If this schema change is intentional, overwrite openapi_snapshot.json with the new version."
        )
