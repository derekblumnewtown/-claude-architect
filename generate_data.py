"""
generate_data.py
Generates synthetic test documents for the extraction pipeline.
Run once to populate the data folders.
"""

import anthropic
import os
from agent_platform.config import config

client = anthropic.Anthropic(api_key=config.anthropic_api_key)

def generate_documents(doc_type: str, count: int, output_dir: str):
    print(f"Generating {count} {doc_type} documents...")
    os.makedirs(output_dir, exist_ok=True)
    
    prompts = {
        "invoice": """Generate a realistic invoice as plain text. 
            Do not include Invoices.
            Vary the format each time — some formal, some informal, some with line items, 
            some without. Occasionally omit optional fields like tax or payment terms.
            Make some have missing or ambiguous data to test edge cases.""",
        
        "job_posting": """Generate a single realistic job posting as plain text for ONE job at ONE company.
            Do not include multiple job listings.
            Vary the format — some structured with clear sections, some as flowing paragraphs.
            Vary the industry and role each time.
            Some should have salary ranges, some should not.
            Some should list specific skill years, some just list skills.
            Include edge cases like missing zip codes or ambiguous job types.""",
        
        "menu": """Generate a realistic restaurant menu as plain text.
            Do not include multiple menus.
            Vary the restaurant type — Italian, Mexican, American diner, fine dining, etc.
            Some menus should have dietary flags, some should not.
            Some items should have descriptions, some just a name and price.
            Include edge cases like prix fixe menus or items with no price listed."""
    }
    
    for i in range(1, count + 1):
        response = client.messages.create(
            model=config.dev_model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"{prompts[doc_type]}\n\nGenerate document #{i} of {count}. Make it different from typical examples."
            }]
        )
        
        content = response.content[0].text
        filepath = os.path.join(output_dir, f"{doc_type}_{i:02d}.txt")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"  ✓ {filepath}")

if __name__ == "__main__":
    generate_documents("invoice", 15, "projects/p2_extraction_pipeline/data/invoices")
    generate_documents("job_posting", 15, "projects/p2_extraction_pipeline/data/job_postings")
    generate_documents("menu", 15, "projects/p2_extraction_pipeline/data/menus")
    print("\nDone — 45 documents generated.")