from agent_platform.config import config
from agent_platform.logging import get_logger, log_event
from .schemas import MENU_SCHEMA, INVOICE_SCHEMA, JOB_POSTING_SCHEMA
import re

class Validator:

    # Build our type_map so we can map the call from the JSON schema to a python type
    type_map = {
        "string": str,
        "number": (int, float),
        "array": list,
        "object": dict,
        "boolean": bool}

    def __init__(self):

        self.schemas = {
            "invoice":INVOICE_SCHEMA,
            "menu": MENU_SCHEMA,
            "job_posting":JOB_POSTING_SCHEMA
        }

    # Private function used for validating zip codes
    def is_valid_zip(self, zip_value):
        return bool(re.match(r'^\d{5}$', zip_value))
    
    # Private function used to validate invoces
    def _validate_invoice(self, extracted_data: dict, errors: list) -> None:
            
            # The total_amount property was not returned in the extracted_data
            if "total_amount" in extracted_data:
                
                # The total amount did not have a value value
                if extracted_data["total_amount"]<=0:
                    errors.append({"field":"total_amount",
                                    "type":"semantic",
                                    "error":f"total_amount must be more than 0 for {extracted_data['invoice_number']}"})

    def _validate_job_posting(self, extracted_data: dict, errors: list) -> None:
            if "zip" in extracted_data:
                
                if not self.is_valid_zip(extracted_data["zip"]):
                    errors.append({"field":"zip", 
                                "type":"format",
                                    "error":f"zip must be 5 digits {extracted_data['company_name']}"})

    def _validate_menu(self, extracted_data: dict, errors: list) -> None:

        for element in extracted_data["menu"]:
            if "price" in element:
                if element["price"]<=0:
                    errors.append({"field":element["item_name"],
                                "type":"semantic", 
                                    "error":f"Price must be more than 0 for {element['item_name']}"})

    def validate(self, extracted_data: dict, document_type: str):
        type_map = {
                "string": str,
                "number": (int, float),
                "array": list,
                "object": dict,
                "boolean": bool}

        errors=[]
        #Loop though the required fields
        for schema_element in self.schemas[document_type]["required"]:


                if schema_element not in extracted_data:
                    errors.append({"field":schema_element, 
                                   "type":"format", 
                                   "error":f"Error {schema_element} was not in the parameter list"})
                                  
                elif extracted_data[schema_element]=="<UNKNOWN>":
                    errors.append({"field":schema_element, 
                                   "type":"format", 
                                   "error":f"Error {schema_element} UNKNOWN value"})
   

                elif not isinstance (extracted_data[schema_element],
                                     type_map[self.schemas[document_type]["properties"][schema_element]["type"]]):
                    errors.append({"field":schema_element,
                                   "type":"format",  
                                   "error":f"invalid type"})
   
        # document-specific checks
        if document_type == "menu":
            self._validate_menu(extracted_data, errors) 

        elif document_type == "invoice":
            self._validate_invoice(extracted_data, errors) 

        elif document_type == "job_posting":
            self._validate_job_posting(extracted_data, errors) 

        if errors:
            has_semantic = any(e.get("type") == "semantic" for e in errors)
            status="semantic_error" if has_semantic else "format_error"
            return {"status":status, "errors":errors, "data":extracted_data}
        else:
            return {"status":"valid", "errors":[], "data":extracted_data}