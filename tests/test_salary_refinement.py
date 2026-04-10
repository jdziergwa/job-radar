from src.salary import parse_salary_string
import re

def test_salary_parsing():
    test_cases = [
        # Standard annual
        ("$100k - $150k", (100000, 150000, "USD")),
        ("120000 - 140000 EUR", (120000, 140000, "EUR")),
        
        # Hourly
        ("$50 - $100 per hour", (104000, 208000, "USD")),
        ("60-80/hr", (124800, 166400, None)),
        ("£40/hour", (83200, 83200, "GBP")),
        
        # Noisy / Non-salary
        ("Senior Data Science/Full Stack/Backend/Android/iOS/QA positions", (None, None, None)),
        ("Stack Backend", (None, None, None)),
        
        # Currency only (discard current behavior if no numbers)
        ("$ Competitive", (None, None, None)),
        
        # Hybrid k-ranges
        ("$70 - 90k", (70000, 90000, "USD")),
    ]
    
    print("\nRunning Salary Parsing Tests:")
    print("-" * 30)
    
    all_passed = True
    for s, expected in test_cases:
        actual = parse_salary_string(s)
        if actual == expected:
            print(f"✅ PASS: '{s}' -> {actual}")
        else:
            print(f"❌ FAIL: '{s}'")
            print(f"   Expected: {expected}")
            print(f"   Actual:   {actual}")
            all_passed = False
            
    return all_passed

if __name__ == "__main__":
    if test_salary_parsing():
        print("\nAll tests passed! 🎉")
    else:
        print("\nSome tests failed. 🚨")
        exit(1)
