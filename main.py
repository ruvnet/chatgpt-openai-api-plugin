#              - chatgpt-openai-api-plugin 
#     /\__/\   - main.py 
#    ( o.o  )  - v0.0.1
#      >^<     - by @rUv

import os
import requests
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from typing import List, Optional
import openai
from fastapi import FastAPI, Depends
from fastapi import UploadFile, File
from fastapi import FastAPI, HTTPException, File, UploadFile, Depends
import io
import json
from urllib.parse import unquote  # Import the unquote function
import time
import mimetypes        # Library for determining the MIME type of a file
from fastapi.responses import FileResponse  # File response class for FastAPI

app = FastAPI()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE_URL = "https://api.openai.com/v1"

def get_api_key():
    API_KEY_NAME = os.environ.get('OPENAI_API_KEY')
    if not API_KEY_NAME:
        raise ValueError("API key not found in environment variables")
    return API_KEY_NAME

# Define the list of JSON objects
json_objects = [
    {"prompt": "Translate the following English text to French: 'Hello, how are you?'", "completion": "Bonjour, comment ça va ?"},
    {"prompt": "What is the capital of France?", "completion": "The capital of France is Paris."},
    {"prompt": "Write a short poem about the moon.", "completion": "Gentle moon, in the night sky,\nSilent guardian, shining high.\nCasting shadows, soft and deep,\nGuiding all who wake or sleep."}
]

# Convert the list of JSON objects into a JSONL string
jsonl_content = "\n".join([json.dumps(obj) for obj in json_objects])

class Message(BaseModel):
    role: str
    content: str

class CompletionRequest(BaseModel):
    model: str = "gpt-3.5-turbo-0301"
    temperature: float = 1.0
    max_tokens: int = 1000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    messages: List[Message] = [
        {
            "role": "system",
            "content": "you are a bot to test openai connections"
        },
        {
            "role": "assistant",
            "content": "Hello, user! How can I help you today?"
        },
        {
            "role": "user",
            "content": "Hello, assistant!"
        }
    ]
    n: int = 1
    stream: bool = False

def call_openai_api(endpoint: str, data: dict):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{OPENAI_API_BASE_URL}/{endpoint}"
    response = requests.post(url, headers=headers, json=data)
    return response.json()

@app.post("/proxy_openai_api/completions/",
          description="Generate completions for a given prompt using the GPT-3.5-turbo model.")
async def proxy_openai_api_completions(completion_request: CompletionRequest):
    data = {
        "model": completion_request.model,
        "temperature": completion_request.temperature,
        "max_tokens": completion_request.max_tokens,
        "top_p": completion_request.top_p,
        "frequency_penalty": completion_request.frequency_penalty,
        "presence_penalty": completion_request.presence_penalty,
        "messages": [message.dict() for message in completion_request.messages],
        "n": completion_request.n,
        "stream": completion_request.stream,
    }
    return call_openai_api("chat/completions", data)

@app.get("/proxy_openai_api/files/",
         description="List all files that have been uploaded to the OpenAI API.")
async def proxy_openai_api_list_files():
    response = requests.get(f"{OPENAI_API_BASE_URL}/files", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"})
    return response.json()


@app.post("/proxy_openai_api/files/",
          description="Upload a JSONL file to the OpenAI API for fine-tuning.")
async def proxy_openai_api_upload_file(jsonl_content: str):
    # URL-decode the input string
    decoded_jsonl_content = unquote(jsonl_content)
    
    # Replace spaces between JSON objects with newline characters
    decoded_jsonl_content = decoded_jsonl_content.replace("} {", "}\n{")
    
    # Split the decoded input string by newline characters and parse each line as a JSON object
    json_objects = [json.loads(line) for line in decoded_jsonl_content.split('\n') if line.strip()]
    
    # Serialize each JSON object as a string and join with newline characters
    formatted_jsonl_content = "\n".join([json.dumps(obj) for obj in json_objects])
    
    # Convert the formatted JSONL string into a file-like object
    jsonl_file = io.StringIO(formatted_jsonl_content)
    
    # Generate a unique timestamp
    timestamp = int(time.time())
    
    # Set the filename for the file to be uploaded (with the unique timestamp)
    filename = f"training_{timestamp}.jsonl"
    
    # Set the content type for the file
    content_type = "application/json"
    
    # Create the "files" dictionary for the request
    files = {"file": (filename, jsonl_file, content_type)}
    
    # Set the "purpose" parameter to the valid value "fine-tune"
    data = {"purpose": "fine-tune"}
    
    response = requests.post(
        f"{OPENAI_API_BASE_URL}/files",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        files=files,
        data=data  # Pass the data containing the "purpose" parameter
    )
    return response.json()
  
@app.get("/proxy_openai_api/models/",
         description="List all models available in the OpenAI API.")
async def proxy_openai_api_list_models():
    response = requests.get(f"{OPENAI_API_BASE_URL}/models", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"})
    return response.json()

@app.get("/proxy_openai_api/models/{model_name}/",
         description="Retrieve information about a specific model in the OpenAI API.")
async def proxy_openai_api_get_model(model_name: str):
    response = requests.get(f"{OPENAI_API_BASE_URL}/models/{model_name}", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"})
    return response.json()

class FineTuneRequest(BaseModel):
    training_file_id: str

class FineTuneResponse(BaseModel):
    fine_tune_job_id: str

@app.post("/proxy_openai_api/finetune/",
          response_model=FineTuneResponse,
          description="Create a fine-tuning job using a specified training file.")
async def create_fine_tune(request: FineTuneRequest, api_key: str = Depends(get_api_key)):
    openai.api_key = api_key

    # Create the fine-tuning job
    try:
        fine_tune_job = openai.FineTune.create(
            training_file=request.training_file_id
        )
        return FineTuneResponse(fine_tune_job_id=fine_tune_job["id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
      
class FineTunedCompletionRequest(BaseModel):
    fine_tuned_model_id: str
    prompt: str
    max_tokens: int = 50
    temperature: float = 0.7

@app.post("/proxy_openai_api/completions_finetuned/",
          description="Generate completions using a fine-tuned model. Replace the model name and file name as needed")
async def generate_finetuned_completion(prompt: str, model_id: str = "modelname:ft-samplefileupload-2023-04-22-16-27-56", api_key: str = Depends(get_api_key)):
    openai.api_key = api_key
    try:
        # Use the provided model_id to generate completions with the fine-tuned model
        response = openai.Completion.create(
            engine=model_id,
            prompt=prompt,
            max_tokens=100
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/proxy_openai_api/finetuned_models/",
         description="List all fine-tuned models available in the OpenAI API.")
async def list_finetuned_models(api_key: str = Depends(get_api_key)):
    openai.api_key = api_key
    try:
        # Use the OpenAI API to list fine-tuned models
        response = openai.FineTune.list()
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Define a route for serving files from the ".well-known" path
@app.get('/.well-known/{filename}')
async def download(filename: str):
    file_path = 'plugins/' + filename  # Construct the file path based on the filename
    media_type, _ = mimetypes.guess_type(file_path)  # Determine the MIME type of the file
    return FileResponse(file_path, media_type=media_type or 'text/plain')  # Serve the file


# Run the FastAPI application using the Uvicorn ASGI server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
