import pandas as pd
from berlin_businesses.analysis import count_by, category_shares_by_group, coordinate_summary

def test_count_by():
    df = pd.DataFrame({"district": ["Mitte", "Mitte", "Pankow"]})
    result = count_by(df, "district")
    assert dict(zip(result["district"], result["business_count"])) == {"Mitte": 2, "Pankow": 1}

def test_category_shares_by_group():
    df = pd.DataFrame({"district": ["Mitte", "Mitte", "Pankow"], "category": ["A", "B", "A"]})
    result = category_shares_by_group(df, "district", "category")
    mitte = result[result["district"] == "Mitte"]
    assert abs(mitte["share_within_group"].sum() - 1.0) < 1e-12

def test_coordinate_summary():
    df = pd.DataFrame({
        "latitude": [52.5, 52.5, 52.6],
        "longitude": [13.4, 13.4, 13.5],
    })
    result = coordinate_summary(df)
    assert result["unique_coordinate_pairs"] == 2
    assert result["records_at_shared_coordinates"] == 2
