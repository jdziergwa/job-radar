from src.providers.utils import slugify, strip_html
from src.salary import parse_salary_string

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
    assert parse_salary_string("$5,000/month") == (60000, 60000, "USD")
    assert parse_salary_string("€2,000 per week") == (104000, 104000, "EUR")
    assert parse_salary_string("£400/day") == (104000, 104000, "GBP")
    assert parse_salary_string("Not specified") == (None, None, None)
    assert parse_salary_string("Competitive") == (None, None, None)
    assert parse_salary_string("100k") == (100000, 100000, None) # No currency indicator
    print("✅ parse_salary tests passed")


def test_strip_html_removes_tags_and_normalizes_whitespace():
    text = strip_html("<div><h2>Role</h2><p>Build APIs</p><ul><li>Python</li><li>Docker</li></ul></div>")

    assert text == "Role\n\nBuild APIs\n\n• Python\n• Docker"


def test_strip_html_ignores_script_style_and_decodes_entities():
    text = strip_html(
        "<style>.x{display:none;}</style><p>Tom &amp; Jerry</p>"
        "<script>alert('x')</script><p>Remote&nbsp;EMEA</p>"
    )

    assert text == "Tom & Jerry\n\nRemote EMEA"


def test_strip_html_fallback_cleans_malformed_markup():
    malformed = "<div><p>What You'll Do<li>Build tests<li>Own CI</broken <span>Remote &amp; Hybrid"
    text = strip_html(malformed)

    assert "<div>" not in text
    assert "<span>" not in text
    assert "What You'll Do" in text
    assert "• Build tests" in text
    assert "• Own CI" in text
    assert "Remote & Hybrid" in text

if __name__ == "__main__":
    test_slugify()
    test_parse_salary()
