import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.validator import Validator

validator = Validator()

# Test 1 - valid
result1 = validator.validate({
    'company_name': 'Acme', 'state': 'OR', 'city': 'Portland',
    'zip': '97214', 'role': 'Engineer'
}, "job_posting")
print(result1["status"])  # should print: valid

# Test 2 - format_error
result2 = validator.validate({
    'company_name': 'Acme', 'state': 'OR', 'city': 'Portland',
    'zip': 'ABCDE', 'role': 'Engineer'
}, "job_posting")
print(result2["status"])  # should print: format_error

# Test 3 - semantic_error
result3 = validator.validate({
    'restaurant_name': 'Cafe', 'restaurant_address': '123 Main',
    'menu': [{'item_name': 'Pasta', 'price': 0}]
}, "menu")
print(result3["status"])  # should print: semantic_error

exit()

##########
import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.validator import Validator

validator = Validator()
result = {
    'company_name': 'Hexcel Aerospace',
    'state': 'OR',
    'city': 'Portland',
    'zip': 'ABCDE',
    'role': 'Senior Engineer'
}

validator_return=validator.validate(result, "job_posting")
print(f"Error {validator_return["errors"]}")
exit(0)
###
import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.extractor import Extractor

#Instantiate the extractor
extractor = Extractor()

#Open a file
#with open("projects/p2_extraction_pipeline/data/invoices/invoice_01.txt", "r", encoding="utf-8") as f:
#with open("projects/p2_extraction_pipeline/data/menus/menu_01.txt", "r", encoding="utf-8") as f:
with open("projects/p2_extraction_pipeline/data/job_postings/job_posting_01.txt", "r", encoding="utf-8") as f:
    document_text = f.read()

#Extract the data
#result = extractor.extract(document_text, "invoice")
#result = extractor.extract(document_text, "menu")
result = extractor.extract(document_text, "job_posting")


#Print the results
print(result)
exit()

##########
import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.validator import Validator

validator = Validator()
result = {'invoice_number': 'MDS-2024-03847', 'vendor_name': 'Meridian Design Studios', 'invoice_date': '2024-03-15', 'due_date': '2024-04-15', 'description': 'Brand identity refresh project for Spring 2024 product line. Includes logo refinement, color palette development, and packaging design mockups for client approval. Three rounds of revisions included. Additional revisions billed at $150/hour.', 'total_amount': 0, 'tax_amount': 0, 'payment_terms': 'Net 30', 'line_items': [{'description': 'Brand identity refresh project for Spring 2024 product line - logo refinement, color palette development, and packaging design mockups with three rounds of revisions', 'line_total': 5875.0}]}

validator_return=validator.validate(result, "invoice")
print(f"Error {validator_return["errors"]}")
exit(0)


####
import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.extractor import Extractor

extractor = Extractor()
with open("projects/p2_extraction_pipeline/data/menus/menu_01.txt", "r", encoding="utf-8") as f:
    document_text = f.read()

result = extractor.extract(document_text, "menu")
print(result)
exit()

###########
import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.validator import Validator


#Instantiate the extractor
validator = Validator()
result = {
    'company_name': 12345,   # should be string, passing number
    'state': 'OR',
    'city': 'Portland',
    'zip': '97214',
    'role': 'Senior Materials Scientist',
}
error=validator.validate(result,"job_posting")
print(error)
exit(0)

################

import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.validator import Validator


#Instantiate the extractor
validator = Validator()
result = {
    'company_name': 12345,   # should be string, passing number
    'state': 'OR',
    'city': 'Portland',
    'zip': '97214',
    'role': 'Senior Materials Scientist',
}
error=validator.validate(result,"job_posting")
print(error)
exit(0)


import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.validator import Validator


#Instantiate the extractor
validator = Validator()
result = {
    'company_name': 'Hexcel Aerospace Materials',
    'state': 'OR',
    'city': 'Portland',
    'zip': '<UNKNOWN>',
    'role': 'Senior Materials Scientist',
    'job_type': 'Full-time',
    'salary': {'salary_min': 145000, 'salary_max': 185000},
    'skills': '[\n  {"skill": "Materials Science", "years": 7}]'
}
error=validator.validate(result,"job_posting")
print(error)

result = {
    'state': 'OR',
    'city': 'Portland',
    'zip': '<UNKNOWN>',
    'role': 'Senior Materials Scientist',
    'job_type': 'Full-time',
    'salary': {'salary_min': 145000, 'salary_max': 185000},
    'skills': '[\n  {"skill": "Materials Science", "years": 7}]'
}
error=validator.validate(result,"job_posting")
print(error)


result = {
    'company_name': 'Success Company',
    'state': 'OR',
    'city': 'Portland',
    'zip': '18940',
    'role': 'Senior Materials Scientist',
    'job_type': 'Full-time',
    'salary': {'salary_min': 145000, 'salary_max': 185000},
    'skills': '[\n  {"skill": "Materials Science", "years": 7}]'
}
error=validator.validate(result,"job_posting")
print(error)


exit(0)

###########################################
import sys
sys.path.insert(0, '.')
from projects.p2_extraction_pipeline.src.extractor import Extractor

#Instantiate the extractor
extractor = Extractor()

#Open a file
#with open("projects/p2_extraction_pipeline/data/invoices/invoice_01.txt", "r", encoding="utf-8") as f:
#with open("projects/p2_extraction_pipeline/data/menus/menu_01.txt", "r", encoding="utf-8") as f:
with open("projects/p2_extraction_pipeline/data/job_postings/job_posting_01.txt", "r", encoding="utf-8") as f:
    document_text = f.read()

#Extract the data
#result = extractor.extract(document_text, "invoice")
#result = extractor.extract(document_text, "menu")
#result = extractor.extract(document_text, "job_posting")


# hardcoded extraction result to test validator without API calls
result = {
    'company_name': 'Hexcel Aerospace Materials',
    'state': 'OR',
    'city': 'Portland',
    'zip': '<UNKNOWN>',
    'role': 'Senior Materials Scientist',
    'job_type': 'Full-time',
    'salary': {'salary_min': 145000, 'salary_max': 185000},
    'skills': '[\n  {"skill": "Materials Science", "years": 7}]'
}

#Print the results
print(result)
exit()

######################################################################

with open("projects/p2_extraction_pipeline/data/invoices/invoice_01.txt", "r", encoding="utf-8") as f:
    document_text = f.read()

import anthropic
from agent_platform.config import config

client = anthropic.Anthropic(api_key=config.anthropic_api_key)

""""
response = client.messages.create(
    model=config.default_model,
    max_tokens=1024,
    messages=[{ 
        "role":"user",
        "content":f"Extract the vendor name and the total amount from this invoice:\n\n{document_text}"
        }]
)
"""

response = client.messages.create(
    model=config.default_model,
    max_tokens=1024,
    tools=[{
        "name":"extract_invoice",
        "description":"Extract structured data from an invoice",
        "input_schema":{
            "type":"object",
            "required":["vendor_name","total_amount"],
            "properties": {
                "vendor_name":{"type":"string"},
                "total_amount":{"type":"number"}
            }
        }
    }],
    tool_choice={"type":"tool","name":"extract_invoice"},
    messages=[{ 
        "role":"user",
        "content":f"Extract the vendor name and the total amount from this invoice:\n\n{document_text}"
    }]
)


print(response.content[0].input)
