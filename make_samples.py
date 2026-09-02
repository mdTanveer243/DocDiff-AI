"""
Generates two sample PDF pairs for testing the comparison tool, saved into samples/.
Run once: python make_samples.py
Requires: pip install fpdf2
"""
from fpdf import FPDF
import os

os.makedirs("samples", exist_ok=True)


def make_pdf(path, paragraphs):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for para in paragraphs:
        pdf.multi_cell(0, 8, para)
        pdf.ln(2)
    pdf.output(path)


# --- Pair 1: a vendor services contract, revised ---
pair1_a = [
    "This Agreement is made between Acme Corp and the Vendor for the supply of goods.",
    "The vendor shall deliver the goods within 30 days of order confirmation.",
    "Payment is due on receipt of invoice.",
    "Either party may terminate this agreement with 60 days written notice.",
    "This agreement shall be governed by the laws of the State of Delaware.",
    "All disputes shall be resolved through binding arbitration in New York.",
]

pair1_b = [
    "This Agreement is made between Acme Corp and the Vendor for the supply of goods.",
    "The vendor shall deliver the goods within 45 business days of order confirmation.",
    "Payment is due within 15 days of receipt of invoice.",
    "Either party may terminate this agreement with 30 days written notice.",
    "This agreement shall be governed by the laws of the State of Delaware.",
    "All disputes shall be resolved through binding arbitration in Chicago.",
    "The vendor must maintain liability insurance of at least $1,000,000 throughout the term.",
]

# --- Pair 2: an insurance policy schedule, revised ---
pair2_a = [
    "This policy provides coverage for accidental damage up to $5,000 per incident.",
    "The policyholder must report any claim within 14 days of the incident occurring.",
    "Coverage does not extend to damage caused by intentional acts.",
    "The annual premium for this policy is $450, payable in monthly installments.",
    "This policy automatically renews unless cancelled in writing 30 days before expiry.",
]

pair2_b = [
    "This policy provides coverage for accidental damage up to $7,500 per incident.",
    "The policyholder must report any claim within 30 days of the incident occurring.",
    "Coverage does not extend to damage caused by intentional acts or gross negligence.",
    "The annual premium for this policy is $450, payable in monthly installments.",
    "This policy automatically renews unless cancelled in writing 45 days before expiry.",
    "Claims exceeding $2,000 require supporting documentation and photographic evidence.",
]

make_pdf("samples/pair1_docA.pdf", pair1_a)
make_pdf("samples/pair1_docB.pdf", pair1_b)
make_pdf("samples/pair2_docA.pdf", pair2_a)
make_pdf("samples/pair2_docB.pdf", pair2_b)

print("Sample PDFs created in samples/")