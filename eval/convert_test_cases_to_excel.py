import json

import pandas as pd

from eval.gold_standard_test_cases import TEST_CASES  # your current test cases

# Path to save Excel
excel_path = "eval/gold_standard_test_cases.xlsx"

# Prepare rows for Excel
rows = []
for i, test in enumerate(TEST_CASES):
    row = {
        "framework": test.get("framework", ""),
        "user": test.get("user", ""),
        "question": test.get("question", ""),
        "expected_facts": json.dumps(test.get("expected_facts", [])),
        "acceptable_variations": json.dumps(test.get("acceptable_variations", [])),
        "should_not_mention": json.dumps(test.get("should_not_mention", [])),
        "requires_specific_value": test.get("requires_specific_value", False),
        "safety_critical": test.get("safety_critical", False),
        "clinical_reasoning_required": test.get("clinical_reasoning_required", False),
        "ground_truth": test.get("ground_truth", ""),
        "should_refuse": test.get("should_refuse", False),
        "is_off_topic": test.get("is_off_topic", False),
        "privacy_test": test.get("privacy_test", False),
        "multi_guideline": test.get("multi_guideline", False),
        "conversation": json.dumps(test.get("conversation", [])),
        "run_status": "NOT_RUN",  # default for checkpointing
    }
    rows.append(row)

# Create DataFrame
df = pd.DataFrame(rows)

# Save to Excel
df.to_excel(excel_path, index=False)

print(f"✅ Excel file created at {excel_path}")
