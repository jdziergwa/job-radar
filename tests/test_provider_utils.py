from src.providers.utils import slugify, parse_salary_string

def test_slugify():
    assert slugify("Google") == "google"
    assert slugify("Hello World") == "hello-world"
    assert slugify("A!@#B$%C") == "a-b-c"
    assert slugify("---test---") == "test"
    assert slugify("") == "unknown"
    print("✅ slugify tests passed")

def test_parse_salary():
    assert parse_salary_string("$100k - $120k") == (100000, 120000, "USD")
    assert parse_salary_string("€50,000") == (50000, 50000, "EUR")
    assert parse_salary_string("70000 GBP") == (70000, 70000, "GBP")
    assert parse_salary_string("Not specified") == (None, None, None)
    assert parse_salary_string("Competitive") == (None, None, None)
    assert parse_salary_string("100k") == (100000, 100000, None) # No currency indicator
    print("✅ parse_salary tests passed")

if __name__ == "__main__":
    test_slugify()
    test_parse_salary()
