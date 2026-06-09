
# import requests
# import json
# import time
# from datetime import datetime

# # Configuration
# OLLAMA_HOST = "https://ollama.osourceglobal.com:11434"
# MODEL_NAME = "llama3:8b-instruct-q4_K_M"

# # Parameters
# TEMPERATURE = 0.7  # Reasonably high temperature for more creative responses
# NUM_CTX = 1024      # 4K context window
# NUM_PREDICT = 512   # Max tokens to generate in response
# REASONING_DISABLED = True  # Disable reasoning mode

# # Timeout configuration (in seconds)
# CONNECTION_TIMEOUT = 10  # Initial connection timeout
# READ_TIMEOUT = 300  # 5 minutes for reading response
# TOTAL_TIMEOUT = (CONNECTION_TIMEOUT, READ_TIMEOUT)


# def log_debug(stage: str, message: str, level: str = "INFO"):
   
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
#     level_colors = {
#         "INFO": "ℹ️ ",
#         "DEBUG": "🔍",
#         "WARNING": "⚠️ ",
#         "ERROR": "❌"
#     }
#     icon = level_colors.get(level, "📌")
#     print(f"[{timestamp}] {icon} [{stage}] {message}")


# def test_server_connectivity():
    
#     log_debug("CONNECTIVITY", f"Testing connection to {OLLAMA_HOST}...", "DEBUG")
    
#     try:
#         # Try to reach the health endpoint
#         health_url = f"{OLLAMA_HOST}/api/tags"
#         log_debug("CONNECTIVITY", f"Sending request to health check endpoint: {health_url}", "DEBUG")
        
#         start_time = time.time()
#         response = requests.get(health_url, timeout=CONNECTION_TIMEOUT)
#         elapsed = time.time() - start_time
        
#         log_debug("CONNECTIVITY", f"Health check completed in {elapsed:.2f}s", "DEBUG")
        
#         if response.status_code == 200:
#             log_debug("CONNECTIVITY", "✅ Server is reachable and responsive", "INFO")
#             models = response.json().get("models", [])
#             log_debug("CONNECTIVITY", f"Found {len(models)} model(s) on server", "DEBUG")
            
#             model_names = [m.get("name", "unknown") for m in models]
#             log_debug("CONNECTIVITY", f"Available models: {model_names}", "DEBUG")
            
#             return True
#         else:
#             log_debug("CONNECTIVITY", f"Server returned status code {response.status_code}", "ERROR")
#             return False
            
#     except requests.exceptions.Timeout:
#         log_debug("CONNECTIVITY", f"Connection timeout after {CONNECTION_TIMEOUT}s", "ERROR")
#         return False
#     except requests.exceptions.ConnectionError as e:
#         log_debug("CONNECTIVITY", f"Connection refused: {str(e)}", "ERROR")
#         return False
#     except Exception as e:
#         log_debug("CONNECTIVITY", f"Unexpected error: {str(e)}", "ERROR")
#         return False


# def connect_to_ollama(prompt: str) -> str:
   
#     log_debug("REQUEST_INIT", f"Starting request initialization", "INFO")
#     log_debug("REQUEST_INIT", f"Host: {OLLAMA_HOST}", "DEBUG")
#     log_debug("REQUEST_INIT", f"Model: {MODEL_NAME}", "DEBUG")
#     log_debug("REQUEST_INIT", f"Temperature: {TEMPERATURE}", "DEBUG")
#     log_debug("REQUEST_INIT", f"Context Window: {NUM_CTX}", "DEBUG")
#     log_debug("REQUEST_INIT", f"Max Tokens: {NUM_PREDICT}", "DEBUG")
    
#     url = f"{OLLAMA_HOST}/api/generate"
#     log_debug("REQUEST_INIT", f"API Endpoint: {url}", "DEBUG")
    
#     payload = {
#         "model": MODEL_NAME,
#         "prompt": prompt,
#         "temperature": TEMPERATURE,
#         "num_ctx": NUM_CTX,
#         "num_predict": NUM_PREDICT,
#         "stream": False  # Set to True if you want streaming responses
#     }
    
#     log_debug("PAYLOAD", f"Request payload prepared: {json.dumps(payload, indent=2)}", "DEBUG")
    
#     try:
#         log_debug("CONNECTION", f"Attempting to connect to server...", "INFO")
#         request_start = time.time()
        
#         response = requests.post(
#             url, 
#             json=payload, 
#             timeout=TOTAL_TIMEOUT
#         )
        
#         elapsed = time.time() - request_start
#         log_debug("CONNECTION", f"Response received in {elapsed:.2f}s", "INFO")
#         log_debug("RESPONSE", f"HTTP Status Code: {response.status_code}", "DEBUG")
        
#         response.raise_for_status()
#         log_debug("RESPONSE", f"HTTP request successful", "INFO")
        
#         log_debug("PARSING", f"Parsing JSON response...", "DEBUG")
#         result = response.json()
#         log_debug("PARSING", f"JSON parsed successfully", "DEBUG")
        
#         if "response" in result:
#             log_debug("PARSING", f"Response field found in JSON", "DEBUG")
#             response_text = result.get("response", " ")
#             log_debug("SUCCESS", f"Generated {len(response_text)} characters", "INFO")
#             return response_text
#         else:
#             log_debug("PARSING", f"No 'response' field found in JSON", "WARNING")
#             log_debug("PARSING", f"Full response: {json.dumps(result, indent=2)}", "DEBUG")
#             return "No response received"
        
#     except requests.exceptions.Timeout as e:
#         log_debug("ERROR", f"Request timed out (timeout={TOTAL_TIMEOUT})", "ERROR")
#         log_debug("ERROR", f"The model may still be processing - try increasing READ_TIMEOUT", "WARNING")
#         return f"❌ Error: Request timed out after {READ_TIMEOUT}s"
        
#     except requests.exceptions.ConnectionError as e:
#         log_debug("ERROR", f"Connection error: {str(e)}", "ERROR")
#         log_debug("ERROR", f"Could not connect to Ollama server. Ensure:", "WARNING")
#         log_debug("ERROR", f"  1. Server is running at {OLLAMA_HOST}", "WARNING")
#         log_debug("ERROR", f"  2. Network connectivity is available", "WARNING")
#         log_debug("ERROR", f"  3. Firewall allows connection on port 11434", "WARNING")
#         return "❌ Error: Could not connect to Ollama server."
        
#     except requests.exceptions.HTTPError as e:
#         log_debug("ERROR", f"HTTP error occurred: {str(e)}", "ERROR")
#         log_debug("ERROR", f"Status Code: {response.status_code}", "DEBUG")
#         log_debug("ERROR", f"Response Text: {response.text}", "DEBUG")
#         return f"❌ Error: HTTP {response.status_code}"
        
#     except requests.exceptions.RequestException as e:
#         log_debug("ERROR", f"Request error: {str(e)}", "ERROR")
#         return f"❌ Error: {str(e)}"
        
#     except json.JSONDecodeError as e:
#         log_debug("ERROR", f"JSON decode error: {str(e)}", "ERROR")
#         log_debug("ERROR", f"Response text: {response.text[:500]}", "DEBUG")
#         return "❌ Error: Invalid JSON response from server."
        
#     except Exception as e:
#         log_debug("ERROR", f"Unexpected error: {str(e)}", "ERROR")
#         import traceback
#         log_debug("ERROR", f"Traceback: {traceback.format_exc()}", "DEBUG")
#         return f"❌ Unexpected error: {str(e)}"


# def connect_to_ollama_streaming(prompt: str) -> None:
   
#     log_debug("STREAM_INIT", f"Starting streaming request initialization", "INFO")
#     log_debug("STREAM_INIT", f"Host: {OLLAMA_HOST}", "DEBUG")
#     log_debug("STREAM_INIT", f"Model: {MODEL_NAME}", "DEBUG")
    
#     url = f"{OLLAMA_HOST}/api/generate"
    
#     payload = {
#         "model": MODEL_NAME,
#         "prompt": prompt,
#         "temperature": TEMPERATURE,
#         "num_ctx": NUM_CTX,
#         "num_predict": NUM_PREDICT,
#         "stream": True  # Enable streaming
#     }
    
#     log_debug("STREAM_PAYLOAD", f"Request payload prepared", "DEBUG")
    
#     try:
#         log_debug("STREAM_CONNECTION", f"Attempting streaming connection...", "INFO")
#         stream_start = time.time()
        
#         response = requests.post(
#             url, 
#             json=payload, 
#             stream=True, 
#             timeout=TOTAL_TIMEOUT
#         )
        
#         response.raise_for_status()
#         log_debug("STREAM_CONNECTION", f"Connection established", "INFO")
#         log_debug("STREAM_RESPONSE", f"HTTP Status: {response.status_code}", "DEBUG")
        
#         log_debug("STREAM_DATA", f"Beginning to stream response data...", "INFO")
#         print("📝 Response:")
        
#         chunk_count = 0
#         total_chars = 0
        
#         for line in response.iter_lines():
#             if line:
#                 chunk_count += 1
#                 try:
#                     data = json.loads(line)
#                     chunk_response = data.get("response", " ")
#                     total_chars += len(chunk_response)
                    
#                     if chunk_count <= 3 or chunk_count % 10 == 0:  # Log first few chunks and every 10th
#                         log_debug("STREAM_CHUNK", f"Chunk {chunk_count}: {len(chunk_response)} chars", "DEBUG")
                    
#                     print(chunk_response, end="", flush=True)
#                 except json.JSONDecodeError as e:
#                     log_debug("STREAM_CHUNK", f"JSON decode error in chunk: {str(e)}", "WARNING")
        
#         elapsed = time.time() - stream_start
#         log_debug("STREAM_COMPLETE", f"Streaming completed in {elapsed:.2f}s", "INFO")
#         log_debug("STREAM_COMPLETE", f"Total chunks: {chunk_count}, Total characters: {total_chars}", "INFO")
#         print("\n" + "-" * 50)
        
#     except requests.exceptions.Timeout:
#         log_debug("STREAM_ERROR", f"Stream request timed out (timeout={TOTAL_TIMEOUT})", "ERROR")
#         print("\n❌ Error: Request timed out while streaming.")
        
#     except requests.exceptions.ConnectionError as e:
#         log_debug("STREAM_ERROR", f"Stream connection error: {str(e)}", "ERROR")
#         print("❌ Error: Could not connect to Ollama server for streaming.")
        
#     except requests.exceptions.RequestException as e:
#         log_debug("STREAM_ERROR", f"Stream request error: {str(e)}", "ERROR")
#         print(f"❌ Error: {str(e)}")
        
#     except Exception as e:
#         log_debug("STREAM_ERROR", f"Unexpected streaming error: {str(e)}", "ERROR")
#         import traceback
#         log_debug("STREAM_ERROR", f"Traceback: {traceback.format_exc()}", "DEBUG")
#         print(f"❌ Unexpected error: {str(e)}")


# # Example usage
# if __name__ == "__main__":
#     # Test prompt
#     test_prompt = "What is machine learning? Explain in 2-3 sentences."
    
#     print("=" * 70)
#     print("OLLAMA CLIENT - Debugging Enabled")
#     print("=" * 70)
#     print(f"Timestamp format: [YYYY-MM-DD HH:MM:SS.mmm] [ICON] [STAGE] Message\n")
    
#     # Step 1: Test connectivity
#     print("=" * 70)
#     print("STEP 1: Testing Server Connectivity")
#     print("=" * 70)
#     is_reachable = test_server_connectivity()
    
#     if not is_reachable:
#         print("\n⚠️  Server connectivity test failed. Continuing anyway...")
    
#     # Step 2: Non-streaming response
#     print("\n" + "=" * 70)
#     print("STEP 2: Non-Streaming Mode")
#     print("=" * 70)
#     response = connect_to_ollama(test_prompt)
#     print(f"\n✅ Final Response:\n{response}\n")
    
#     # Step 3: Streaming mode (uncomment to test)
#     print("\n" + "=" * 70)
#     print("STEP 3: Streaming Mode (Optional - Uncomment to test)")
#     print("=" * 70)
#     # connect_to_ollama_streaming(test_prompt)

from .dbanalyser.db.drivers.mssql_driver import MSSQLDriver
from .dbanalyser.db.connection import DbRegistryEntry
# Create a minimal DbRegistryEntry-like object matching your config structure:
entry = DbRegistryEntry()
entry.host = "your_sql_host"
entry.port = 1433
entry.database_name = "your_db"
entry.username = "your_user"
entry.password = "your_pass"
entry.use_windows_auth = False
driver = MSSQLDriver(entry)
print("Connection test:", driver.test_connection())
# Try to list tables (this will exercise parameterized queries)
try:
    tables = driver.list_tables()
    print("Tables:", len(tables))
except Exception as e:
    print("Driver error:", e)