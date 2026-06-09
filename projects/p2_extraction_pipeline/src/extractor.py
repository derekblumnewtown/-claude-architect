import anthropic
from agent_platform.config import config
from .schemas import MENU_SCHEMA, INVOICE_SCHEMA, JOB_POSTING_SCHEMA

class Extractor:

    def __init__(self):

        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.schemas = {
            "invoice":INVOICE_SCHEMA,
            "menu": MENU_SCHEMA,
            "job_posting":JOB_POSTING_SCHEMA
        }


    def extract(self, document_text, document_type):
        
        response = self.client.messages.create(
                model=config.default_model,
                max_tokens=1024,
                tools=[{
                    "name": f"extract_{document_type}",
                    "description":f"Extract structured data from a {document_type}",
                    "input_schema": self.schemas[document_type]
                }],
                tool_choice={"type":"tool",
                            "name":f"extract_{document_type}"},
                messages=[{ 
                    "role":"user",
                    "content":f"Extract all data from this document:\n\n{document_text}"
                }]
            )
        print(response)
        print(" ")

        for block in response.content:
            if block.type=="tool_use":
                return block.input



    def extract_with_feedback(self, document_text, document_type, errors):
        
        error_summary = "\n".join([f"- {e['field']}: {e['error']}" for e in errors])

        response = self.client.messages.create(
                model=config.default_model,
                max_tokens=1024,
                tools=[{
                    "name": f"extract_{document_type}",
                    "description":f"Extract structured data from a {document_type}",
                    "input_schema": self.schemas[document_type]
                }],
                tool_choice={"type":"tool",
                            "name":f"extract_{document_type}"},
                messages=[{ 
                    "role":"user",
                    "content": f"Extract all data from this document. Previous extraction had errors:\n{error_summary}\nPlease fix these issues.\n\n{document_text}"
                }]
            )
        print(response)
        print(" ")
        for block in response.content:
            if block.type=="tool_use":
                return block.input