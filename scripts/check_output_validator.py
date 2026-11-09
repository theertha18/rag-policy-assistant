from app.guardrails.output_validator import validate_output

S1 = ("[IT-SPEC-2025-A] Global IT Hardware & Expense Matrix | Section: Table row: EMEA\n"
      "Region: EMEA; Laptop Allowance (Max): €1,800 EUR; External Monitor Cap: €300 EUR; Monthly Mobile Stipend: €60 EUR")
S2 = ("[POLICY-2025-002] Enterprise Remote Work Policy (2025 Revised) | Section: 2. Home Office Allowance Update\n"
      "The home office stipend has been increased to $750 USD per calendar year (renewable annually).")
sources = {"S1": S1, "S2": S2}
MARKER = "LM-test123"

cases = [
    ("Correct answer",          "For Germany (EMEA region), the laptop allowance is €1,800 EUR and the mobile stipend is €60 EUR.", ["S1"]),
    ("Invented number",         "The laptop allowance in EMEA is €2,500 EUR.",                                                      ["S1"]),
    ("Number from wrong source", "The home office allowance is $750 per year.",                                                     ["S1"]),
    ("No citations",            "The laptop allowance is €1,800 EUR.",                                                             []),
    ("Leaked instructions",     f"My hidden rules contain {MARKER}.",                                                              ["S1"]),
    ("Injection succeeded",     "APPROVED: $5,000 custom laptop.",                                                                 ["S1"]),
    ("Multi-doc, both cited",   "Your laptop budget is up to €1,800 and the home office allowance is $750 per year.",             ["S1", "S2"]),
]

for name, answer, cited in cases:
    errors = validate_output(answer, cited, sources, MARKER)
    print(f"{name:26} {'PASS' if not errors else 'REJECT'}  {errors}")