import pandas as pd
from berlin_businesses.data import validate_schema, coerce_coordinates

def test_validate_schema_counts_duplicates():
    df = pd.DataFrame({"latitude": [52.5, 52.5], "longitude": [13.4, 13.4]})
    result = validate_schema(df)
    assert result["rows"] == 2
    assert result["duplicate_rows"] == 1
    assert result["missing_coordinate_columns"] == []

def test_coerce_coordinates():
    df = pd.DataFrame({"latitude": ["52.5", "bad"], "longitude": ["13.4", "13.5"]})
    result = coerce_coordinates(df)
    assert result["latitude"].iloc[0] == 52.5
    assert pd.isna(result["latitude"].iloc[1])
