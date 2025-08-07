"""
Test file for plumbing services configuration
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.plumbing_services import (
    PLUMBING_SERVICES, 
    SERVICE_KEYWORDS, 
    SERVICE_CATEGORIES,
    infer_job_type_from_text,
    get_function_definition
)

def test_service_count():
    """Test that we have all expected services"""
    assert len(PLUMBING_SERVICES) >= 60, f"Expected at least 60 services, got {len(PLUMBING_SERVICES)}"
    print(f"✓ Found {len(PLUMBING_SERVICES)} plumbing services")

def test_keyword_mapping():
    """Test keyword mapping functionality"""
    # Test specific service recognition
    assert infer_job_type_from_text("kitchen sink is clogged") == "clogged_kitchen_sink"
    assert infer_job_type_from_text("bathroom sink won't drain") == "clogged_bathroom_sink"
    assert infer_job_type_from_text("toilet is running constantly") == "running_toilet"
    assert infer_job_type_from_text("water heater burst") == "water_heater_repair"
    assert infer_job_type_from_text("need new faucet") == "faucet_replacement"
    assert infer_job_type_from_text("sewer camera inspection") == "camera_inspection"
    
    print("✓ Keyword mapping works correctly")

def test_function_definition():
    """Test that function definition is properly structured"""
    func_def = get_function_definition()
    assert func_def["type"] == "function"
    assert func_def["function"]["name"] == "book_job"
    
    # Check that all services are in the enum
    job_enum = func_def["function"]["parameters"]["properties"]["job"]["properties"]["type"]["enum"]
    assert len(job_enum) == len(PLUMBING_SERVICES)
    
    print("✓ Function definition is properly structured")

def test_service_categories():
    """Test service categorization"""
    assert "clogs" in SERVICE_CATEGORIES
    assert "faucets" in SERVICE_CATEGORIES
    assert "toilets" in SERVICE_CATEGORIES
    assert "leaks" in SERVICE_CATEGORIES
    
    # Check that categories contain expected services
    assert "clogged_kitchen_sink" in SERVICE_CATEGORIES["clogs"]
    assert "leaky_faucet" in SERVICE_CATEGORIES["faucets"]
    assert "running_toilet" in SERVICE_CATEGORIES["toilets"]
    
    print("✓ Service categories are properly organized")

if __name__ == "__main__":
    print("Testing Plumbing Services Configuration...")
    test_service_count()
    test_keyword_mapping()
    test_function_definition()
    test_service_categories()
    print("\n🎉 All tests passed!") 