import os
import logging
import requests
from typing import NamedTuple, Optional

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_URL") or os.environ.get("OLLAMA_BASE_URL") or "https://ollama.osourceglobal.com:11434"
LLM_MODEL       = os.environ.get("OLLAMA_MODEL") or os.environ.get("LLM_MODEL") or "llama3:8b-instruct-q4_K_M"

# Parameters matching test.py
TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE") or os.environ.get("TEMPERATURE", "0.7"))
NUM_CTX     = int(os.environ.get("OLLAMA_NUM_CTX") or os.environ.get("NUM_CTX", "1024"))
NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT") or os.environ.get("NUM_PREDICT", "512"))

# Timeout configuration
CONNECTION_TIMEOUT = 10
READ_TIMEOUT = 300
DEFAULT_TIMEOUT = (CONNECTION_TIMEOUT, READ_TIMEOUT)

class LLMResult(NamedTuple):
    text: Optional[str]
    error: Optional[str]
    latency_ms: int

def call_llm(prompt: str, timeout: any = DEFAULT_TIMEOUT, model: Optional[str] = None) -> LLMResult:
    """Call Ollama LLM with defensive logging and structured results."""
    endpoint = f"{OLLAMA_BASE_URL}/api/generate"
    chosen_model = model or LLM_MODEL
    payload = {
        "model": chosen_model,
        "prompt": prompt,
        "temperature": TEMPERATURE,
        "num_ctx": NUM_CTX,
        "num_predict": NUM_PREDICT,
        "stream": False
    }
    
    logger.info(f"Calling Ollama at {endpoint} with model {chosen_model} (prompt length: {len(prompt)} chars)")
    
    try:
        response = requests.post(endpoint, json=payload, timeout=timeout)
        latency_ms = int(response.elapsed.total_seconds() * 1000)
        
        if response.status_code == 200:
            try:
                res_json = response.json()
                if isinstance(res_json, dict):
                    result = res_json.get("response", "")
                    logger.info(f"Ollama call successful, latency: {latency_ms}ms")
                    return LLMResult(text=result, error=None, latency_ms=latency_ms)
                else:
                    error_msg = f"Invalid JSON response structure (not a dictionary): got {type(res_json).__name__}"
                    logger.error(error_msg)
                    return LLMResult(text=None, error=error_msg, latency_ms=latency_ms)
            except Exception as e:
                error_msg = f"Failed to parse JSON response: {str(e)}"
                logger.error(error_msg)
                return LLMResult(text=None, error=error_msg, latency_ms=latency_ms)
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ollama call failed: {error_msg}")
            return LLMResult(text=None, error=error_msg, latency_ms=latency_ms)
            
    except requests.exceptions.Timeout:
        error_msg = f"Request timed out after {timeout} seconds"
        logger.error(f"Ollama call timeout: {error_msg}")
        duration_ms = 0
        if isinstance(timeout, tuple):
            duration_ms = sum(timeout) * 1000
        elif isinstance(timeout, (int, float)):
            duration_ms = int(timeout * 1000)
        return LLMResult(text=None, error=error_msg, latency_ms=duration_ms)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Connection error: {str(e)}"
        logger.error(f"Ollama connection error: {error_msg}")
        return LLMResult(text=None, error=error_msg, latency_ms=0)
