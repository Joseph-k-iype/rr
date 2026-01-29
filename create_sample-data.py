import pandas as pd
import random

# Sample data generator for comprehensive testing
def generate_sample_data():
    """
    Generates comprehensive test data covering all compliance scenarios
    """
    
    # Define sample values
    eu_countries = ['United Kingdom', 'Germany', 'France', 'Spain', 'Italy', 'Netherlands', 'Belgium', 'Ireland', 'Poland', 'Sweden']
    adequacy_countries = ['Canada', 'Japan', 'Switzerland', 'Israel', 'New Zealand', 'Argentina', 'Uruguay']
    crown_dependencies = ['Jersey', 'Guernsey', 'Isle of Man']
    rest_of_world = ['United States of America', 'India', 'China', 'Brazil', 'Australia', 'Singapore', 'Hong Kong', 'South Africa', 'United Arab Emirates', 'Saudi Arabia']
    
    purposes_l1 = [
        'Prevention of Financial Crime',
        'Risk Management (excluding any Financial Crime related Risk Mgmt.)',
        'Provision of Banking and Financial Services',
        'Compliance with Laws and Regulations',
        'Back Office Operations Support',
        'Front Office Operations Support',
        'Product and Service Improvement',
        'Marketing to Target Subjects'
    ]
    
    purposes_l2 = [
        'AML Screening',
        'Transaction Monitoring',
        'Customer Due Diligence',
        'Credit Risk Assessment',
        'Fraud Prevention',
        'Account Management',
        'Payment Processing',
        'Customer Service',
        'Product Analytics',
        'Market Research',
        'Direct Marketing',
        'Customer Profiling'
    ]
    
    purposes_l3 = [
        'KYC Verification',
        'Sanctions Screening',
        'PEP Screening',
        'Transaction Pattern Analysis',
        'Behavioral Analytics',
        'Credit Scoring',
        'Collateral Valuation',
        'Payment Authorization',
        'Settlement Processing',
        'Query Resolution',
        'Complaint Handling',
        'Usage Analysis',
        'Feature Development',
        'Campaign Management',
        'Segmentation Analysis'
    ]

    # NEW: Process hierarchy for Processes_L1_L2_L3 column
    process_hierarchies = [
        'Back Office-HR-Payroll',
        'Back Office-HR-Benefits',
        'Back Office-Finance-AP',
        'Back Office-Finance-AR',
        'Back Office-IT-Support',
        'Back Office-IT-Development',
        'Front Office-Sales-Lead Gen',
        'Front Office-Sales-Closing',
        'Front Office-Marketing-Digital',
        'Front Office-Marketing-Content',
        'Front Office-Service-Support',
        'Front Office-Service-Retention',
        'Operations-Processing-Batch',
        'Operations-Processing-Real Time',
        'Operations-Clearing-Settlement',
        'Operations-Reconciliation-Daily',
        'Risk-Credit-Assessment',
        'Risk-Credit-Monitoring',
        'Risk-Market-Trading',
        'Risk-Market-Hedging',
        'Compliance-AML-Screening',
        'Compliance-AML-Reporting',
        'Compliance-Regulatory-Filing',
        'Compliance-Audit-Internal',
    ]
    
    personal_data_categories = [
        'Identity Data',
        'Contact Information',
        'Financial Data',
        'Employment Information',
        'Biometric Data',
        'Location Data',
        'Behavioral Data',
        'Transaction History'
    ]
    
    personal_data_items = [
        'Full Name',
        'Date of Birth',
        'National ID Number',
        'Passport Number',
        'Email Address',
        'Phone Number',
        'Home Address',
        'Bank Account Number',
        'Credit Card Number',
        'Salary Information',
        'Employment Status',
        'Employer Name',
        'Fingerprint',
        'Facial Recognition Data',
        'IP Address',
        'GPS Coordinates',
        'Purchase History',
        'Browsing History',
        'Transaction Amounts',
        'Payment Methods'
    ]
    
    categories = [
        'Customer Data',
        'Employee Data',
        'Vendor Data',
        'Partner Data',
        'Regulatory Data',
        'Operational Data',
        'Marketing Data',
        'Analytics Data'
    ]
    
    module_statuses = ['CM', None]
    
    data = []
    case_id_counter = 1
    
    # Scenario 1: EU/EEA Internal Transfers (RULE_1)
    print("Generating EU/EEA internal transfers...")
    for i in range(50):
        origin = random.choice(eu_countries)
        receiving = '|'.join(random.sample([c for c in eu_countries if c != origin], k=random.randint(1, 3)))
        
        has_pii = random.choice([True, False])
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': origin,
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'Processes_L1_L2_L3': random.choice(process_hierarchies),  # NEW
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(2, 4))) if has_pii else '',
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(3, 8))) if has_pii else '',
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(1, 3))),
            'pia_module': 'CM' if random.random() > 0.3 else None,
            'tia_module': None,
            'hrpr_module': None
        })
        case_id_counter += 1
    
    # Scenario 2: EU/EEA to Adequacy Countries (RULE_2)
    print("Generating EU/EEA to Adequacy transfers...")
    for i in range(40):
        origin = random.choice(eu_countries)
        receiving = '|'.join(random.sample(adequacy_countries, k=random.randint(1, 2)))
        
        has_pii = random.choice([True, False])
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': origin,
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(2, 4))) if has_pii else '',
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(3, 8))) if has_pii else '',
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(1, 3))),
            'pia_module': 'CM' if random.random() > 0.2 else None,
            'tia_module': None,
            'hrpr_module': None
        })
        case_id_counter += 1
    
    # Scenario 3: UK to EU/EEA/Adequacy (RULE_4)
    print("Generating UK transfers...")
    for i in range(30):
        receiving_pool = eu_countries + adequacy_countries
        receiving_pool.remove('United Kingdom') if 'United Kingdom' in receiving_pool else None
        receiving = '|'.join(random.sample(receiving_pool, k=random.randint(1, 3)))
        
        has_pii = random.choice([True, False])
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': 'United Kingdom',
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(2, 4))) if has_pii else '',
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(3, 8))) if has_pii else '',
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(1, 3))),
            'pia_module': 'CM' if random.random() > 0.25 else None,
            'tia_module': None,
            'hrpr_module': None
        })
        case_id_counter += 1
    
    # Scenario 4: Crown Dependencies (RULE_3)
    print("Generating Crown Dependencies transfers...")
    for i in range(20):
        origin = random.choice(crown_dependencies)
        receiving_pool = adequacy_countries + eu_countries
        receiving = '|'.join(random.sample(receiving_pool, k=random.randint(1, 2)))
        
        has_pii = random.choice([True, False])
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': origin,
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(2, 4))) if has_pii else '',
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(3, 8))) if has_pii else '',
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(1, 3))),
            'pia_module': 'CM' if random.random() > 0.2 else None,
            'tia_module': None,
            'hrpr_module': None
        })
        case_id_counter += 1
    
    # Scenario 5: Switzerland (RULE_5)
    print("Generating Switzerland transfers...")
    for i in range(25):
        receiving_pool = adequacy_countries + eu_countries + ['Gibraltar', 'Monaco']
        receiving = '|'.join(random.sample(receiving_pool, k=random.randint(1, 2)))
        
        has_pii = random.choice([True, False])
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': 'Switzerland',
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(2, 4))) if has_pii else '',
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(3, 8))) if has_pii else '',
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(1, 3))),
            'pia_module': 'CM' if random.random() > 0.2 else None,
            'tia_module': None,
            'hrpr_module': None
        })
        case_id_counter += 1
    
    # Scenario 6: EU/EEA to Rest of World (RULE_6)
    print("Generating EU/EEA to Rest of World transfers...")
    for i in range(60):
        origin = random.choice(eu_countries + ['United Kingdom'])
        receiving = '|'.join(random.sample(rest_of_world, k=random.randint(1, 3)))
        
        has_pii = True  # Usually these need both PIA and TIA
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': origin,
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(2, 5))),
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(5, 12))),
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(2, 4))),
            'pia_module': 'CM' if random.random() > 0.3 else None,
            'tia_module': 'CM' if random.random() > 0.4 else None,
            'hrpr_module': None
        })
        case_id_counter += 1
    
    # Scenario 7: BCR Countries (RULE_7)
    print("Generating BCR country transfers...")
    bcr_countries = ['United Kingdom', 'United States of America', 'India', 'China', 'Hong Kong', 'Singapore', 'Australia']
    for i in range(50):
        origin = random.choice(bcr_countries)
        all_countries = eu_countries + adequacy_countries + rest_of_world
        receiving = '|'.join(random.sample([c for c in all_countries if c != origin], k=random.randint(1, 3)))
        
        has_pii = True  # BCR usually involves PII
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': origin,
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(3, 6))),
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(6, 15))),
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(2, 5))),
            'pia_module': 'CM' if random.random() > 0.2 else None,
            'tia_module': None,
            'hrpr_module': 'CM' if random.random() > 0.3 else None
        })
        case_id_counter += 1
    
    # Scenario 8: Cases with PII requirement (RULE_8)
    print("Generating PII-focused cases...")
    for i in range(30):
        origin = random.choice(eu_countries + rest_of_world)
        all_countries = eu_countries + adequacy_countries + rest_of_world
        receiving = '|'.join(random.sample([c for c in all_countries if c != origin], k=random.randint(1, 2)))
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': origin,
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(4, 7))),
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(8, 18))),
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(2, 4))),
            'pia_module': 'CM' if random.random() > 0.15 else None,
            'tia_module': 'CM' if random.random() > 0.5 else None,
            'hrpr_module': 'CM' if random.random() > 0.6 else None
        })
        case_id_counter += 1
    
    # Scenario 9: Cases WITHOUT PII
    print("Generating non-PII cases...")
    for i in range(25):
        origin = random.choice(eu_countries + rest_of_world)
        all_countries = eu_countries + adequacy_countries + rest_of_world
        receiving = '|'.join(random.sample([c for c in all_countries if c != origin], k=random.randint(1, 2)))
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}',
            'OriginatingCountryName': origin,
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}",
            'PersonalDataCategoryNames': '',
            'PersonalDataNames': '',
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(1, 2))),
            'pia_module': 'CM' if random.random() > 0.5 else None,
            'tia_module': None,
            'hrpr_module': None
        })
        case_id_counter += 1
    
    # Scenario 10: Edge cases with varying purpose levels
    print("Generating edge cases...")
    for i in range(20):
        origin = random.choice(eu_countries + rest_of_world)
        all_countries = eu_countries + adequacy_countries + rest_of_world
        receiving = '|'.join(random.sample([c for c in all_countries if c != origin], k=random.randint(1, 3)))
        
        # Vary purpose hierarchy depth
        if i % 3 == 0:
            purposes = random.choice(purposes_l1)  # Only L1
        elif i % 3 == 1:
            purposes = f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}"  # L1 and L2
        else:
            purposes = f"{random.choice(purposes_l1)}|{random.choice(purposes_l2)}|{random.choice(purposes_l3)}"  # Full hierarchy
        
        has_pii = random.choice([True, False])
        
        data.append({
            'CaseId': f'CASE{case_id_counter:05d}',
            'EimId': f'EIM{case_id_counter:04d}' if random.random() > 0.2 else '',
            'BusinessApp_Id': f'APP{random.randint(100, 999)}' if random.random() > 0.1 else '',
            'OriginatingCountryName': origin,
            'ReceivingJurisdictions': receiving,
            'LegalProcessingPurposeNames': purposes,
            'Processes_L1_L2_L3': random.choice(process_hierarchies),
            'PersonalDataCategoryNames': '|'.join(random.sample(personal_data_categories, k=random.randint(1, 4))) if has_pii else '',
            'PersonalDataNames': '|'.join(random.sample(personal_data_items, k=random.randint(2, 10))) if has_pii else '',
            'CategoryNames': '|'.join(random.sample(categories, k=random.randint(1, 3))),
            'pia_module': random.choice(['CM', None, 'IP', 'NS']),
            'tia_module': random.choice(['CM', None, 'IP']),
            'hrpr_module': random.choice(['CM', None, 'IP'])
        })
        case_id_counter += 1
    
    return pd.DataFrame(data)


if __name__ == '__main__':
    print("="*70)
    print("GENERATING COMPREHENSIVE TEST DATA")
    print("="*70)
    
    df = generate_sample_data()
    
    print(f"\nGenerated {len(df)} cases")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nSample data preview:")
    print(df.head(3).to_string())
    
    # Save to Excel
    output_file = 'sample_data_comprehensive.xlsx'
    df.to_excel(output_file, index=False, engine='openpyxl')
    
    print(f"\n✅ Saved to: {output_file}")
    
    # Print statistics
    print("\n" + "="*70)
    print("DATA STATISTICS")
    print("="*70)
    print(f"Total Cases: {len(df)}")
    print(f"\nOrigin Countries: {df['OriginatingCountryName'].nunique()}")
    print(f"Unique Origin Countries: {sorted(df['OriginatingCountryName'].unique())[:10]}")
    print(f"\nCases with PII: {df[df['PersonalDataNames'] != ''].shape[0]}")
    print(f"Cases without PII: {df[df['PersonalDataNames'] == ''].shape[0]}")
    print(f"\nPIA Completed (CM): {df[df['pia_module'] == 'CM'].shape[0]}")
    print(f"TIA Completed (CM): {df[df['tia_module'] == 'CM'].shape[0]}")
    print(f"HRPR Completed (CM): {df[df['hrpr_module'] == 'CM'].shape[0]}")
    
    print("\n" + "="*70)
    print("TEST SCENARIOS INCLUDED")
    print("="*70)
    print("✓ EU/EEA Internal Transfers (RULE_1)")
    print("✓ EU/EEA to Adequacy Countries (RULE_2)")
    print("✓ Crown Dependencies Transfers (RULE_3)")
    print("✓ UK Transfers (RULE_4)")
    print("✓ Switzerland Transfers (RULE_5)")
    print("✓ EU/EEA to Rest of World (RULE_6)")
    print("✓ BCR Country Transfers (RULE_7)")
    print("✓ PII-focused Cases (RULE_8)")
    print("✓ Non-PII Cases")
    print("✓ Edge Cases with Varying Purpose Levels")
    print("✓ Mixed Compliance Statuses")
    
    print("\n" + "="*70)
    print("USAGE")
    print("="*70)
    print("1. Run this script to generate the Excel file:")
    print("   python generate_sample_data.py")
    print("\n2. Update load.py CONFIG with the filename:")
    print("   'excel_file': 'sample_data_comprehensive.xlsx'")
    print("\n3. Load into FalkorDB:")
    print("   python load.py")
    print("\n4. Start the dashboard:")
    print("   python app.py")
    print("="*70)