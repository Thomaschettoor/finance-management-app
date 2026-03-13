import re

text = '"Rs.1,299.00 spent on your HDFC Bank Credit Card ending 4432 at SWIGGY on 12-03-26"'

print(f"Original text: {text}")
print(f"Lowercase: {text.lower()}")
print()

# Test the patterns
patterns = [
    r"(?:rs\.?|inr)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
    r"([0-9,]+(?:\.[0-9]{1,2})?)\s*(?:rs\.?|inr)",
]

for i, pat in enumerate(patterns):
    print(f"\nPattern {i+1}: {pat}")
    m = re.search(pat, text.lower())
    if m:
        print(f"  Match found: '{m.group(0)}'")
        print(f"  Captured group: '{m.group(1)}'")
        amount_str = m.group(1).replace(',', '')
        print(f"  After removing commas: '{amount_str}'")
        print(f"  As float: {float(amount_str)}")
    else:
        print(f"  No match")

# Check what character is at the beginning
print(f"\nFirst char: {repr(text[0])}")
print(f"First 20 chars: {repr(text[:20])}")
