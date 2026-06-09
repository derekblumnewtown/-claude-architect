"""
projects/p2_extraction_pipeline/src/schemas.py
JSON schemas for the three document types.

These schemas are passed to Claude as tool input_schema
to force structured extraction output.
"""

INVOICE_SCHEMA = {
    "type": "object",
    "required": ["invoice_number", "vendor_name", "total_amount", "invoice_date", "due_date"],
    "properties": {
        "invoice_number": {"type": "string", "description": "Unique invoice identifier"},
        "vendor_name": {"type": "string", "description": "Name of the company issuing the invoice"},
        "total_amount": {"type": "number", "description": "Total amount due in dollars"},
        "invoice_date": {"type": "string", "description": "Invoice date in YYYY-MM-DD format"},
        "due_date": {"type": "string", "description": "Payment due date in YYYY-MM-DD format"},
        "description": {"type": "string", "description": "Invoice-level description of goods or services"},
        "tax_amount": {"type": "number", "description": "Tax amount in dollars"},
        "payment_terms": {"type": "string", "description": "Payment terms e.g. Net 30"},
        "line_items": {
            "type": "array",
            "description": "Individual line items on the invoice",
            "items": {
                "type": "object",
                "required": ["description", "line_total"],
                "properties": {
                    "description": {"type": "string", "description": "Description of the line item"},
                    "quantity": {"type": "number", "description": "Quantity of units"},
                    "unit_price": {"type": "number", "description": "Price per unit in dollars"},
                    "line_total": {"type": "number", "description": "Total for this line item in dollars"}
                }
            }
        }
    }
}

JOB_POSTING_SCHEMA = {
    "type": "object",
    "required": ["company_name", "state", "city", "zip", "role"],
    "properties": {
        "company_name": {"type": "string", "description": "Name of the company"},
        "state": {"type": "string", "description": "State of the company"},
        "city": {"type": "string", "description": "City of the company"},
        "zip": {"type": "string", "description": "Zip code of the company"},
        "role": {"type": "string", "description": "Role that is being sought"},
        "job_type": {"type": "string", "description": "Full-time, part-time or contract"},
        "posted": {"type": "string", "description": "Date role was posted in YYYY-MM-DD format"},
        "salary": {
            "type": "object",
            "properties": {
                "salary_min": {"type": "number", "description": "Minimum salary"},
                "salary_max": {"type": "number", "description": "Maximum salary"}
            }
        },
        "skills": {
            "type": "array",
            "description": "Skills required",
            "items": {
                "type": "object",
                "required": ["skill"],
                "properties": {
                    "skill": {"type": "string", "description": "Name of the skill"},
                    "years": {"type": "number", "description": "Years of experience required"}
                }
            }
        }
    }
}

MENU_SCHEMA = {
    "type": "object",
    "required": ["restaurant_name", "restaurant_address", "menu"],
    "properties": {
        "restaurant_name": {"type": "string", "description": "Name of the restaurant"},
        "restaurant_address": {"type": "string", "description": "Address of the restaurant"},
        "menu": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["item_name", "price"],
                "properties": {
                    "item_name": {"type": "string", "description": "Name of the menu item"},
                    "description": {"type": "string", "description": "Description of the item"},
                    "price": {"type": "number", "description": "Price of the item in dollars"},
                    "dietary_flags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Dietary flags e.g. vegetarian, vegan, gluten-free"
                    }
                }
            }
        }
    }
}