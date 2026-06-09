from .extractor import Extractor
from .validator import Validator
from agent_platform.config import config
import json
import os

class Router:

    def __init__(self):
        self.extractor = Extractor()
        self.validator = Validator()

    def save(self, file_path, data_to_write):
        print(f"In save {file_path}")      

        os.makedirs(os.path.dirname(file_path), exist_ok=True)  
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data_to_write, f, indent=2)

    def route(self, document_name, document_type):

        with open(document_name, "r", encoding="utf-8") as f:
            document_text = f.read() 
        for i in range(3):
            
            if i==0:
                extracted_data = self.extractor.extract(document_text, document_type)
            else:
                extracted_data = self.extractor.extract_with_feedback(document_text, document_type,response["errors"])
            
            response = self.validator.validate(extracted_data, document_type)
            
            if response["status"] == "semantic_error":
                document_name= "projects/p2_extraction_pipeline/output/review_queue/" +  os.path.basename(document_name) 
                document_name = document_name.replace(".txt", ".json")
                self.save(document_name, response["data"])
                return("send to human")
            elif response["status"] == "valid":    
                document_name= "projects/p2_extraction_pipeline/output/extracted/" +  os.path.basename(document_name) 
                document_name = document_name.replace(".txt", ".json")
                self.save(document_name, response["data"])
                return("valid")
            elif response["status"] == "format_error":
                print("handle format") 
        
        document_name= "projects/p2_extraction_pipeline/output/review_queue/" +  os.path.basename(document_name) 
        document_name = document_name.replace(".txt", ".json")
        self.save(document_name, response["data"])        
        return("hit max")
