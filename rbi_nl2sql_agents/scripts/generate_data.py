import os
import random
import datetime
import pandas as pd

# Set random seed for reproducibility
random.seed(42)

# Define banks, officers, and complaint categories
BANKS = [f"Bank_{i:02d}" for i in range(1, 11)]

OFFICERS = [
    {"id": "OFF_101", "name": "Mr. Suresh Kumar"},
    {"id": "OFF_102", "name": "Ms. Ananya Rao"},
    {"id": "OFF_103", "name": "Mr. David D'Souza"},
    {"id": "OFF_104", "name": "Ms. Fatima Sheikh"},
    {"id": "OFF_105", "name": "Mr. Rajesh Malhotra"}
]

CATEGORIES = [
    "Unauthorized Electronic Transaction",
    "Mis-selling of Financial Products",
    "Loan Recovery Harassment",
    "Credit Card Overcharging",
    "Pension & Account Maintenance Issues"
]

# Complaint & Speaking Order templates
TEMPLATES = {
    "Unauthorized Electronic Transaction": [
        {
            "complaint": "I noticed unauthorized online transactions amounting to Rs. {amount} from my savings account on {date}. I immediately blocked my card and registered a complaint with the bank, but they refused to refund the amount, claiming customer negligence in safeguarding details. I did not share any OTP or password.",
            "allowed": "The Ombudsman observed that the customer reported the unauthorized transactions within 24 hours of occurrence. As per RBI guidelines on limited liability of customers, the bank is directed to reverse the charges of Rs. {amount} and restore the balance. No additional compensation is awarded.",
            "rejected": "Forensic logs submitted by the bank confirm the transactions were completed using the customer's registered mobile device and the second-factor authentication OTP was sent and entered successfully. The complaint is dismissed due to customer negligence."
        },
        {
            "complaint": "On {date}, Rs. {amount} was debited from my account through UPI. I did not initiate this payment. The UPI ID of the recipient is unknown to me. The bank is refusing to credit back the amount, saying the transaction was authenticated by my PIN.",
            "allowed": "The bank did not implement proper fraud risk velocity checks on UPI transfers. The bank is directed to restore the debited amount of Rs. {amount} to the complainant's account.",
            "rejected": "The transaction was verified to be a person-to-person transfer initiated from the complainant's device with correct UPI PIN. No security breach detected on bank's systems. Complaint dismissed."
        },
        {
            "complaint": "My debit card was cloned and cash amounting to Rs. {amount} was withdrawn at an ATM on {date} while the card was in my physical possession. I immediately reported it, but the bank claims the card PIN was used and therefore they are not liable.",
            "allowed": "The Ombudsman noted that the ATM video footage showed a third party using a cloned card, and the customer reported within 2 days. The bank is directed to credit back Rs. {amount} to the customer's account.",
            "rejected": "The bank provided evidence that the transactions were validated with chip-and-PIN technology. The customer failed to establish that the compromise occurred due to bank's negligence. Complaint dismissed."
        }
    ],
    "Mis-selling of Financial Products": [
        {
            "complaint": "I went to {bank_name} to renew my Fixed Deposit of Rs. {amount} for {years} years. The executive tricked me into signing a policy document, claiming it was a tax-saving FD. Later, I realized it is a ULIP with an annual premium obligation of Rs. {amount}. I want my premium refunded.",
            "allowed": "Evidence shows the customer is a senior citizen and the product sold is highly unsuitable. The bank is directed to cancel the policy and refund the premium of Rs. {amount} in full without any surrender charges.",
            "rejected": "The bank submitted the signed key feature document indicating the customer consented to the insurance plan. No evidence of misrepresentation. Complaint dismissed."
        },
        {
            "complaint": "The bank relationship manager forced me to buy a credit life insurance policy of Rs. {amount} as a condition for approving my home loan on {date}. They said the loan would not be sanctioned without it. This is tied-selling and against RBI rules.",
            "allowed": "Tied-selling of insurance is prohibited under RBI guidelines. The bank is directed to refund the premium of Rs. {amount} and decouple the insurance from the loan.",
            "rejected": "The customer signed a separate consent form opting for the insurance coverage. No proof of coercion is found. Complaint dismissed."
        },
        {
            "complaint": "I was sold a high-risk mutual fund with a lump sum investment of Rs. {amount} by the bank relationship manager, who promised guaranteed returns of 15% per annum. The portfolio value has dropped, and I have lost my principal. This is mis-selling.",
            "allowed": "The bank staff made misleading statements regarding returns. The bank is ordered to refund the principal amount of Rs. {amount} less current portfolio value, and pay Rs. 5,000 for service deficiency.",
            "rejected": "Mutual fund investments are subject to market risks. The customer signed the risk disclosure documents. No service deficiency established. Complaint dismissed."
        }
    ],
    "Loan Recovery Harassment": [
        {
            "complaint": "My loan EMI was delayed by two weeks due to a medical emergency. The bank's recovery agents are calling me at 11 PM, sending abusive messages on WhatsApp, and harassing my family members, violating RBI recovery agent guidelines.",
            "allowed": "The bank's recovery agents violated RBI guidelines on calling hours and harassment. The bank is directed to pay Rs. {compensation} to the complainant as compensation and issue a warning to the collection agency.",
            "rejected": "The bank provided call logs proving calls were made during standard hours (8 AM to 7 PM). No evidence of abusive language. Complaint dismissed."
        },
        {
            "complaint": "Even after I settled my personal loan account in full and obtained a No Dues Certificate from {bank_name}, recovery agents visited my office on {date} demanding further payments of Rs. {amount} as pending interest.",
            "allowed": "The bank failed to update its system post-settlement. The bank is directed to immediately cease recovery efforts, issue a formal apology letter, and pay Rs. 15,000 for reputational damage.",
            "rejected": "The settlement payment was defaulted on, resulting in the cancellation of the settlement agreement. The bank's recovery actions are legally valid. Complaint dismissed."
        },
        {
            "complaint": "The recovery team of the bank seized my vehicle on {date} without giving the mandatory 14 days pre-possession notice. They also demanded Rs. {amount} as recovery charges to release the vehicle.",
            "allowed": "The repossession was done without following due process and without adequate notice. The bank is directed to return the vehicle, waive the recovery charges of Rs. {amount}, and pay Rs. 20,000 as compensation.",
            "rejected": "The bank proved that multiple notices were sent to the customer's registered address. The repossession was carried out legally under the loan agreement terms. Complaint dismissed."
        }
    ],
    "Credit Card Overcharging": [
        {
            "complaint": "I was charged Rs. {amount} as an annual fee on my credit card on {date}, despite being promised a lifetime free card. The customer care executive is refusing to reverse it, saying the offer has expired.",
            "allowed": "The welcome kit and application form confirm the credit card was marketed as 'Lifetime Free'. The bank is directed to reverse the annual fee of Rs. {amount} along with any interest charged.",
            "rejected": "The card terms state that the annual fee is waived only if annual spend exceeds Rs. 1,00,000. The complainant's spend was lower. Complaint dismissed."
        },
        {
            "complaint": "The bank charged me a late fee of Rs. {amount} and high interest charges on {date}, even though I paid the total amount due on the due date. The payment was processed late by the bank's own gateway.",
            "allowed": "The complainant initiated payment before the cutoff time on the due date. The gateway delay is the bank's responsibility. The bank is directed to refund all late fees and interest of Rs. {amount}.",
            "rejected": "The payment was initiated after the banking hours cutoff on the due date, leading to next-day clearance. Late fee is as per terms. Complaint dismissed."
        },
        {
            "complaint": "My credit card bill dated {date} shows a charge of Rs. {amount} for a transaction I never made. I reported the dispute, but the bank has charged me interest and late payment fees on this disputed amount.",
            "allowed": "As per RBI rules, disputed credit card transactions must not be charged interest while investigation is pending. The bank is directed to reverse Rs. {amount} and all interest and fees.",
            "rejected": "The bank provided transaction logs confirming the transaction was authenticated by the customer using OTP and 3D Secure. The dispute is invalid. Complaint dismissed."
        }
    ],
    "Pension & Account Maintenance Issues": [
        {
            "complaint": "My pension payment for the month of {month} 2026 has been delayed by the bank. I am a retired government employee and depend on this pension. The bank staff is giving excuses.",
            "allowed": "As per RBI circulars on pension disbursement, delayed pensions attract an interest of 8% per annum. The bank is directed to pay the pension along with Rs. {compensation} as interest for the delay.",
            "rejected": "The delay was due to late receipt of the pension scroll from the government treasury department, not the bank. Complaint dismissed."
        },
        {
            "complaint": "My savings account was frozen by {bank_name} on {date} without any prior notice. I cannot withdraw money for my basic needs. The bank manager says they are checking KYC, but I submitted all documents last month.",
            "allowed": "The customer had submitted valid KYC documents prior to the freeze. The bank froze the account without 30 days notice. The bank is directed to unfreeze the account and pay Rs. 5,000 for service deficiency.",
            "rejected": "The account was frozen following a cyber-police directive regarding a suspicious deposit. The bank acted in compliance with law enforcement directives. Complaint dismissed."
        },
        {
            "complaint": "The bank charged me Rs. {amount} as penalty for non-maintenance of minimum balance on {date}, but they never sent me an alert or warning SMS that my balance had dropped below the threshold.",
            "allowed": "As per RBI regulations, banks must notify customers before levying charges for minimum balance non-maintenance. The bank is ordered to refund the penalty of Rs. {amount}.",
            "rejected": "The bank provided log records showing that three SMS warnings were sent to the customer's registered number over a period of 30 days prior to charging the penalty. Complaint dismissed."
        }
    ]
}

# Generate CMS dataset (200 rows)
cms_data = []

# To make the data highly realistic, some banks are skewed towards certain complaints:
# Bank_03: Mis-selling of Financial Products (highly likely)
# Bank_01: Unauthorized Electronic Transaction (highly likely)
# Bank_05: Loan Recovery Harassment (highly likely)
# Bank_09: Pension & Account Maintenance Issues (highly likely)
# Bank_02: Credit Card Overcharging (highly likely)
# Other banks are uniform.

for i in range(1, 201):
    case_id = f"CMS_2026_{i:03d}"
    
    # Determine bank based on weighted distribution
    # Let's decide category first or bank first. Let's decide bank first.
    # Uniform weight for banks, but we can assign specific categories to specific banks
    bank_name = random.choice(BANKS)
    
    # Select category based on bank bias
    if bank_name == "Bank_03" and random.random() < 0.6:
        category = "Mis-selling of Financial Products"
    elif bank_name == "Bank_01" and random.random() < 0.6:
        category = "Unauthorized Electronic Transaction"
    elif bank_name == "Bank_05" and random.random() < 0.6:
        category = "Loan Recovery Harassment"
    elif bank_name == "Bank_09" and random.random() < 0.6:
        category = "Pension & Account Maintenance Issues"
    elif bank_name == "Bank_02" and random.random() < 0.6:
        category = "Credit Card Overcharging"
    else:
        category = random.choice(CATEGORIES)
        
    # Pick a template from the category
    templates = TEMPLATES[category]
    template = random.choice(templates)
    
    # Random variables
    amount_val = random.randint(1000, 250000)
    # Format amount
    amount_str = f"{amount_val:,}"
    
    day = random.randint(1, 28)
    month_num = random.randint(1, 5)
    month_name = ["January", "February", "March", "April", "May"][month_num - 1]
    date_val = datetime.date(2026, month_num, day)
    date_str = date_val.strftime("%d-%b-%b" if random.random() < 0.2 else "%d-%m-%Y") # slightly vary format but mostly standard
    date_str = date_val.strftime("%d-%B-%Y")
    
    years = random.randint(3, 10)
    compensation_val = random.randint(2000, 25000)
    compensation_str = f"{compensation_val:,}"
    
    # Render complaint text
    complaint_text = template["complaint"].format(
        bank_name=bank_name,
        amount=amount_str,
        date=date_str,
        years=years,
        month=month_name
    )
    
    # Determine outcome
    outcome = "Allowed" if random.random() < 0.55 else "Dismissed"
    
    if outcome == "Allowed":
        speaking_order_text = template["allowed"].format(
            bank_name=bank_name,
            amount=amount_str,
            date=date_str,
            years=years,
            compensation=compensation_str,
            month=month_name
        )
    else:
        speaking_order_text = template["rejected"].format(
            bank_name=bank_name,
            amount=amount_str,
            date=date_str,
            years=years,
            month=month_name
        )
        
    # Assign Officer
    officer = random.choice(OFFICERS)
    
    cms_data.append({
        "case_id": case_id,
        "complaint_category": category,
        "complaint": complaint_text,
        "officer_name": officer["name"],
        "officer_id": officer["id"],
        "speaking_order": speaking_order_text,
        "bank_name": bank_name,
        "resolution_status": outcome
    })

# Convert to DataFrame
cms_df = pd.DataFrame(cms_data)

# Generate DAKSH dataset (30 rows)
# Reports about banks where some banks have been judged to have indulged in certain wrong practices.
# We will create exactly 30 supervisory reports.
# Let's align DAKSH reports with the systemic issues we skewed in CMS!
# Bank_03 -> Mis-selling
# Bank_01 -> Cyber security failures (Unauthorized transactions)
# Bank_05 -> Recovery agent guidelines violation
# Bank_09 -> Operational / Pension system failures
# Bank_02 -> Credit card billing discrepancies

daksh_findings_pool = [
    {
        "category": "Mis-selling Systemic Issues",
        "findings": "A thematic review of third-party product sales at {bank} revealed that branch managers were offering insurance policies as bundled products with loans and fixed deposits, violating RBI's tied-selling guidelines. Suitability tests and risk profiling of senior citizens were found to be completely neglected, leading to a high rate of CMS complaints.",
        "action": "Monetary penalty of Rs. 1.2 Crores imposed on the bank. Cease-and-desist order on selling insurance through branch channels until remediation plan is completed.",
        "severity": "High"
    },
    {
        "category": "Cybersecurity Deficiencies",
        "findings": "An IT audit at {bank} revealed significant vulnerabilities in retail banking software. The multi-factor authentication (MFA) system failed to log transaction IP anomalies, and SMS alerts were delayed by an average of 45 minutes, violating circulars on fraud mitigation and enabling unauthorized fund transfers.",
        "action": "Supervisory Letter and Corrective Action Plan (CAP) mandated. Bank ordered to upgrade its authentication systems within 90 days and submit bi-weekly progress reports.",
        "severity": "High"
    },
    {
        "category": "Debt Recovery Violations",
        "findings": "During the inspection of {bank}, it was observed that the bank failed to conduct due diligence on its outsourced collection agency. The recovery agents engaged by the bank systematically violated the Fair Practices Code, calling borrowers at odd hours, threatening family members, and performing unauthorized repossessions.",
        "action": "Monetary penalty of Rs. 55 Lakhs imposed. The bank is ordered to suspend operations with the recovery agency and audit all pending loan recovery files.",
        "severity": "High"
    },
    {
        "category": "Fair Practices Code Violation",
        "findings": "Supervisory examination of {bank}'s credit card operations revealed systematic overcharging of fees. The bank failed to honor 'lifetime free' credit card promotions and charged annual fees, subsequently levying compound interest on these wrongful charges. Delay in resolving disputed transactions violated the regulatory turnaround time (TAT).",
        "action": "Advisory letter issued. Bank directed to auto-refund all wrongfully charged annual fees and interest to affected cardholders within 30 days.",
        "severity": "Medium"
    },
    {
        "category": "Inadequate Internal Controls",
        "findings": "Operational inspection of {bank}'s government business division revealed significant delays in pension credits. The bank did not integrate its core banking software with the Central Pension Accounting System properly, causing a backlog. Penal interest for delayed pension payments was not paid automatically to beneficiaries.",
        "action": "Supervisory warning letter issued. The bank is directed to run an automated batch process to calculate and credit delayed pension interest at 8% per annum for all accounts since Jan 2025.",
        "severity": "Medium"
    },
    {
        "category": "Compliance Deficiencies",
        "findings": "During routine supervision of {bank}, it was noted that the bank delayed submitting the mandatory fraud monitoring reports (FMR) to RBI within the stipulated timeline of 3 weeks from detection. In addition, the customer grievance redressal policy was not updated on the bank website.",
        "action": "Advisory letter and warning issued. The bank must update the policy and streamline its FMR filing system.",
        "severity": "Low"
    },
    {
        "category": "KYC/AML Non-compliance",
        "findings": "A review of customer accounts at {bank} showed deficiencies in updating KYC documents for high-risk accounts. Accounts were frozen without the mandated 30-day notice, causing severe operational disruptions to customers and leading to a volume of ombudsman complaints.",
        "action": "Corrective Action Plan (CAP) issued. Bank directed to establish a dedicated compliance desk for KYC rectifications and avoid arbitrary account freezes.",
        "severity": "Medium"
    }
]

daksh_data = []
# Create 30 rows of DAKSH reports
# Ensure we map the banks to findings consistent with CMS
# For example, Bank_03 gets Mis-selling, Bank_01 gets Cybersecurity, Bank_05 gets Debt Recovery, etc.
# We'll make sure to distribute the 30 reports across the 10 banks, focusing on banks with issues.

# Let's define the findings distribution for each bank to ensure integrity
bank_findings_map = {
    "Bank_01": ["Cybersecurity Deficiencies", "KYC/AML Non-compliance"],
    "Bank_02": ["Fair Practices Code Violation", "Compliance Deficiencies"],
    "Bank_03": ["Mis-selling Systemic Issues", "Fair Practices Code Violation"],
    "Bank_04": ["Compliance Deficiencies"],
    "Bank_05": ["Debt Recovery Violations", "KYC/AML Non-compliance"],
    "Bank_06": ["Compliance Deficiencies"],
    "Bank_07": ["Mis-selling Systemic Issues", "Fair Practices Code Violation"],
    "Bank_08": ["Compliance Deficiencies"],
    "Bank_09": ["Inadequate Internal Controls", "Compliance Deficiencies"],
    "Bank_10": ["Compliance Deficiencies"]
}

for i in range(1, 31):
    report_id = f"DKSH_2026_{i:02d}"
    
    # Choose a bank. Let's make it slightly more biased to Bank_01, Bank_03, Bank_05, Bank_07, Bank_09
    bank = random.choice(BANKS)
    
    # Find allowed categories for this bank
    allowed_categories = bank_findings_map.get(bank, ["Compliance Deficiencies"])
    selected_cat = random.choice(allowed_categories)
    
    # Find the corresponding template finding
    pool_item = next(item for item in daksh_findings_pool if item["category"] == selected_cat)
    
    # Generate random date
    day = random.randint(1, 28)
    month_num = random.randint(1, 5)
    audit_date = datetime.date(2026, month_num, day)
    audit_date_str = audit_date.strftime("%d-%B-%Y")
    
    findings_text = pool_item["findings"].format(bank=bank)
    
    daksh_data.append({
        "report_id": report_id,
        "bank_name": bank,
        "audit_date": audit_date_str,
        "wrong_practice_category": pool_item["category"],
        "supervisory_finding": findings_text,
        "severity_level": pool_item["severity"],
        "action_taken": pool_item["action"]
    })

# Convert to DataFrame
daksh_df = pd.DataFrame(daksh_data)

# Create folders if not exists
os.makedirs("project_data/cms", exist_ok=True)
os.makedirs("project_data/daksh", exist_ok=True)

# Write to Excel and CSV files
cms_file_path = "project_data/cms/cms_cases.xlsx"
cms_csv_path = "project_data/cms/cms_cases.csv"
daksh_file_path = "project_data/daksh/daksh_reports.xlsx"
daksh_csv_path = "project_data/daksh/daksh_reports.csv"

cms_df.to_excel(cms_file_path, index=False)
cms_df.to_csv(cms_csv_path, index=False)
daksh_df.to_excel(daksh_file_path, index=False)
daksh_df.to_csv(daksh_csv_path, index=False)

print(f"Data Generation Successful!")
print(f"CMS Data shape: {cms_df.shape}")
print(f"DAKSH Data shape: {daksh_df.shape}")
print(f"CMS Cases saved to: {cms_file_path} and {cms_csv_path}")
print(f"DAKSH Reports saved to: {daksh_file_path} and {daksh_csv_path}")

# Verification prints
print("\nCMS Sample Row:")
print(cms_df.iloc[0].to_dict())

print("\nDAKSH Sample Row:")
print(daksh_df.iloc[0].to_dict())
