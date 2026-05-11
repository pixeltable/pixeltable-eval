"""
Generate minimal PDF fixtures for eval stories.

Each PDF contains known facts that the functional verifier can check for.
Uses reportlab to keep fixture generation self-contained.
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "u1"


U1_DOCS = {
    "company_policy.pdf": [
        "Company Vacation Policy",
        "",
        "All full-time employees receive 20 vacation days per calendar year.",
        "Vacation days do not roll over to the following year.",
        "Employees must submit vacation requests at least two weeks in advance.",
        "The maximum consecutive vacation period is 10 business days.",
        "Part-time employees receive vacation days pro-rated based on hours worked.",
        "",
        "Sick leave is separate from vacation and provides 10 days per year.",
        "Unused sick days roll over up to a maximum of 30 accumulated days.",
    ],
    "remote_work.pdf": [
        "Remote Work Guidelines",
        "",
        "Remote work requires explicit written approval from the employee's direct manager.",
        "Employees working remotely must be available during core hours (10am-3pm local time).",
        "A home office stipend of $500 is provided annually for remote workers.",
        "Remote workers must have reliable internet with minimum 50 Mbps download speed.",
        "All remote work arrangements are reviewed quarterly.",
        "",
        "International remote work requires additional approval from HR and Legal.",
        "The company does not support remote work from countries on the restricted list.",
    ],
    "benefits_guide.pdf": [
        "Employee Benefits Summary",
        "",
        "401(k) Retirement Plan:",
        "The company matches employee contributions up to 6% of base salary.",
        "Vesting schedule: 25% per year, fully vested after 4 years.",
        "Employees may contribute up to the IRS annual limit.",
        "",
        "Health Insurance:",
        "Three plan options: Basic, Standard, and Premium.",
        "The company covers 80% of premiums for the Standard plan.",
        "Dental and vision insurance are included in all plan tiers.",
        "",
        "Additional Benefits:",
        "Annual learning and development budget of $2,000 per employee.",
        "Gym membership reimbursement up to $75 per month.",
    ],
}

VERIFICATION_FACTS = {
    "How many vacation days do employees get?": "20",
    "Does remote work require manager approval?": "manager",
    "What is the 401k match percentage?": "6%",
}


def generate_pdf(filepath: Path, lines: list[str]):
    c = canvas.Canvas(str(filepath), pagesize=letter)
    y = 750
    for line in lines:
        if y < 72:
            c.showPage()
            y = 750
        fontsize = 16 if lines.index(line) == 0 else 12
        c.setFont("Helvetica-Bold" if lines.index(line) == 0 else "Helvetica", fontsize)
        c.drawString(72, y, line)
        y -= fontsize + 6
    c.save()


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    for filename, lines in U1_DOCS.items():
        generate_pdf(FIXTURES_DIR / filename, lines)
        print(f"Generated {filename}")

    facts_path = FIXTURES_DIR / "verification_facts.json"
    import json
    facts_path.write_text(json.dumps(VERIFICATION_FACTS, indent=2))
    print(f"Generated verification_facts.json")

    print(f"\nFixtures ready in {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
